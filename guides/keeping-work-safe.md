# Keeping a student's work safe on a server

A hosted notebook (molab, for example) can lose its files when its kernel restarts, it is forked or it sits idle. `Sync` keeps
the provenance on a [provenance-sync](https://github.com/alvarobernal2412/provenance-sync) server under a personal key, so the
work comes back by itself.

```python
from provenance_widget.sync import Sync

sync = Sync("https://<the server>", key, PROVENANCE_DIR, settle=lambda: rt.storage._executor.submit(lambda: None).result())
sync.restore()   # before anything opens provenance.db: brings the stored work back into an empty or older folder
rt = init_marimo(...)
sync.start()     # saves in the background a few seconds after the last change
sync.status.message   # "Your work is saved on the course server." or what to do about a problem
```

- It sends the same small zip as `portable.zip_provenance` (values over 2 MB are left out), not individual rows.
- It never raises into the notebook. `status.state` is `saved`, `offline`, `unauthorized` or `too-large`.
- Two tabs saving at once end with the latest save, and the status says that a copy from another place was replaced.
- A folder that belongs to another key is put aside, never uploaded under this one. Work that was never synced is put aside
  too, instead of being overwritten by what the server holds (`<folder>.unsynced-<time>` next to it).
- The key is held in memory. It is not written into the provenance folder, so it does not travel in the zip, and it should not be
  written in the notebook either (a fork copies the notebook).
- The state of the last save is kept next to the folder, in `<folder>.sync.json`.

# Spotting steps that were run again

`PmprovAdapter.repeated_runs(min_length=4)` returns sequences of `min_length` or more consecutive steps that came back later with
the same functions and arguments, as when a part of a notebook is executed again after a restart. `describe_run(run)` gives a
sentence ("Steps 6 to 9 repeat steps 1 to 4."). A single step used twice at different points of an analysis is normal and is not
flagged. Nothing is filtered or removed: the history is untouched.
