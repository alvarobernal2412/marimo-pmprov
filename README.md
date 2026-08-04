# marimo-pmprov

A marimo `anywidget` plugin that gives process-mining analysts a git-style
"Source Control" sidebar for analytic provenance and annotation: a curated
commit rail, a Miller-columns provenance tree, a diff inspector, and a
read-only Reviewer mode with tag-based state restore.

This package ships fully decoupled from the `pmprov` library — it runs out
of the box against a `MockProvenanceSource` whose data is shaped exactly
like pmprov's real model (see `provenance_widget/interfaces.py`), so no
`pmprov` install is required to try it or to develop against it.

## Install

```bash
pip install marimo-pmprov
```

This installs the widget with its `MockProvenanceSource` demo backend. See
`examples/demo_notebook.py` for a runnable notebook.

## Using it in a marimo notebook

```python
import marimo as mo
from provenance_widget.mock_source import MockProvenanceSource
from provenance_widget.widget import ProvenancePanel
from provenance_widget.display import show_table

panel = ProvenancePanel(source=MockProvenanceSource(), mode="student")

# mo.sidebar(...) must be the last bare expression in its own cell to render —
# it cannot be assigned to a variable and displayed from a different cell.
mo.sidebar(panel.sidebar())
```

```python
# tag any displayed table so the sidebar's "Pick from notebook" picker can target it
annotated_table = show_table(mo.ui.table(my_dataframe), artifact_id="art-1", artifact_name="my_dataframe")
annotated_table
```

## Connecting a real pmprov-backed history

The widget only depends on the `ProvenanceSource` protocol
(`provenance_widget.interfaces.ProvenanceSource`) — it never imports
`pmprov` directly. To back the sidebar with a real `pmprov.AnalysisHistory`
instead of mock data:

1. Implement a `PmprovAdapter` class with a `get_tree(self) -> ProvenanceTree`
   method that translates `AnalysisHistory.list_states()` /
   `ProvenanceTracker` data into the `ProvenanceTree` dataclasses in
   `provenance_widget/interfaces.py` (field names already mirror pmprov's
   model, per pmprov's `MODEL.md`). `Annotation`/`Tag` are new concepts not
   present in pmprov — the adapter is where you decide how they're sourced
   or persisted against a real history.
2. Install this package with the `pmprov` extra, which pins a specific
   pmprov version as a runtime dependency:

   ```bash
   pip install "marimo-pmprov[pmprov]"
   ```

   (Update the pinned `pmprov @ git+https://github.com/<org>/pmprov.git@vX.Y.Z`
   reference in `pyproject.toml` to the version you intend to depend on
   before installing.)
3. Pass your adapter instead of `MockProvenanceSource` to `ProvenancePanel`.

## Development

```bash
pip install -e ".[dev]"
pytest

cd frontend
npm install
npm run build   # or: npm run watch
```
