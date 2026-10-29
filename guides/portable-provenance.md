# Moving a stored history to another machine

A history recorded with pmprov can be copied or downloaded and opened somewhere else: for example, record an analysis on a
hosted notebook platform such as [molab](https://molab.marimo.io), download the folder, and review or continue it on a laptop.
This guide explains the one thing that gets in the way, and how to deal with it.

## The problem: absolute paths

pmprov keeps a history in a folder with two parts:

```
provenance/
├── provenance.db     # the steps, the states, the notes (DuckDB)
└── artifacts/        # one file per stored value: Parquet for tables, pickle for everything else
```

`provenance.db` records the **absolute path** of every file in `artifacts/` (the `content_ref` column of the
`artifact_states` table). A folder that is downloaded from another machine therefore still points at the folders of the
machine it was recorded on, for example `/home/molab/notebooks/bpm/provenance/artifacts/…`, which do not exist on the new
one.

What that does when you open the copy:

| | Without a fix | With the fix below |
|---|---|---|
| Step tree | opens | opens |
| Notes and tags | open | open |
| Maps, tables and other values at a step | **not restored** (a snapshot reports `not_stored`) | restored |

This was checked on a stored history of 20 steps and 7 notes, copied and rewritten so that all 278 stored paths pointed at a
Linux folder that does not exist on the machine. Without the fix, the notes and the step tree opened but no map or table
could be restored. With it, everything came back: the 11-row schema table and the map figure (pmprov 0.10.0,
marimo-pmprov 0.2.4).

## The fix: point the stored paths at the artifacts folder next to the database

The files themselves are intact; only the paths in the database are stale. Before the history is opened, rewrite each
`content_ref` to the `artifacts/` folder that sits next to `provenance.db`, keeping only the file name. Splitting on both
`\` and `/` makes it work whichever operating system recorded the history.

```python
import re
from pathlib import Path

import duckdb


def relocate_artifacts(db_path, artifact_dir):
    """Point the stored artifacts at `artifact_dir`. Returns how many paths were changed."""
    if not Path(db_path).exists():
        return 0
    try:
        con = duckdb.connect(str(db_path))
        try:
            changed = 0
            rows = con.execute("SELECT artifact_state_id, content_ref FROM artifact_states").fetchall()
            for artifact_state_id, ref in rows:
                new = str(Path(artifact_dir) / re.split(r"[\\/]", ref)[-1])
                if new != ref:
                    con.execute(
                        "UPDATE artifact_states SET content_ref = ? WHERE artifact_state_id = ?",
                        [new, artifact_state_id],
                    )
                    changed += 1
            return changed
        finally:
            con.close()
    except Exception:
        return 0  # no history stored yet
```

Run it **before** pmprov opens the database (`init_marimo(...)`, or `DuckDBSQLiteBackend(...)` when you only read), because
the database cannot be rewritten while another connection holds it. It is safe to run on every start: once the paths are
right it changes nothing.

## Continuing on the other machine

1. Download the whole `provenance/` folder and keep `provenance.db` and `artifacts/` **together**.
2. Put it next to the notebooks, replacing the local one (or point the notebooks at it with their store-location setting,
   for example the `PMPROV_DIR` environment variable of the example notebooks).
3. Open the notebook. In the reviewer mode the history is only read; in the analyst mode it is continued under the same
   history name, so new steps and notes are added to what was downloaded.

## Things to know

- The `artifacts/` folder holds every stored value, so it can be large (a full analysis of the BPI Challenge 2017 log is
  about 0.2 GB). Check the storage limit of the platform before recording there.
- Use the same pmprov and DuckDB major versions on both machines; the database file is DuckDB's own format.
- A working example of both modes with the fix built in, `analyst.py` and `reviewer.py`, is the `molab/bpm` folder of the
  BPI 2017 exercise.
