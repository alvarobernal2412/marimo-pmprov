# marimo-pmprov

A marimo `anywidget` plugin that gives process-mining analysts a git-style
"Source Control" sidebar for analytic provenance and annotation: a curated
commit rail, a Miller-columns provenance tree with tag/artifact filters and
an inline inspector, and a read-only Reviewer mode with tag-based state
restore.

This package ships fully decoupled from the `pmprov` library — it runs out
of the box against a `MockProvenanceSource` whose data is shaped exactly
like pmprov's real model (see `provenance_widget/interfaces.py`), so no
`pmprov` install is required to try it or to develop against it.

## Install

```bash
pip install "marimo-pmprov @ git+https://github.com/alvarobernal2412/marimo-pmprov.git"
```

Or, for local development:

```bash
git clone https://github.com/alvarobernal2412/marimo-pmprov.git
cd marimo-pmprov
pip install -e ".[dev]"
```

This installs the widget with its `MockProvenanceSource` demo backend. See
`examples/demo_notebook.py` for a full runnable notebook (run it with
`marimo edit examples/demo_notebook.py`).

## Quickstart

```python
import marimo as mo
from provenance_widget.mock_source import MockProvenanceSource
from provenance_widget.widget import ProvenancePanel

panel = ProvenancePanel(source=MockProvenanceSource(), mode="student")

# mo.sidebar(...) must be the last bare expression in its own cell to render —
# it cannot be assigned to a variable and displayed from a different cell.
mo.sidebar(panel.sidebar())
```

The sidebar has three tabs:

- **curated** — a chronological feed of committed annotations (oldest first,
  newest appended at the bottom), plus a composer for writing new ones.
- **tree** — a Miller-columns view of the full provenance history, with
  filter chips for tags and linked artifacts (matching steps stay expanded,
  the rest collapse to a single line) and an inspector pinned to the bottom
  that opens automatically when you click a node.
- **config** — switches between `student` (can annotate) and `reviewer`
  (read-only, can request a restore to any tagged state) personas.

### Tagging notebook outputs so they can be picked

Any table or chart you want the sidebar's "Pick from notebook" picker (and
the hover "+" gutter affordance) to be able to target needs to be wrapped
with `show_table` / `show_chart`:

```python
from provenance_widget.display import show_table, show_chart

# tables — picking refines down to a specific cell or column automatically
annotated_table = show_table(
    mo.ui.table(my_dataframe), artifact_id="art-event-log", artifact_name="event_log.csv"
)
annotated_table
```

```python
# charts — matplotlib figures work via mo.as_html; any renderer that
# produces an mo.Html works the same way (Altair, Plotly, etc.)
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
my_dataframe.groupby("activity")["duration"].mean().plot.bar(ax=ax)

bar_chart = show_chart(mo.as_html(fig), artifact_id="art-duration-bar", artifact_name="Chart_DurationByActivity")
bar_chart
```

`show_chart` works with any `mo.Html`-producing visualization, for example:

| Visualization | How to produce the `mo.Html` |
| --- | --- |
| Bar chart | `mo.as_html(fig)` from a matplotlib `ax.bar(...)` / `.plot.bar()` figure |
| Line chart | `mo.as_html(fig)` from a matplotlib `.plot.line()` figure |
| Scatter plot | `mo.as_html(fig)` from a matplotlib `ax.scatter(...)` figure |
| Histogram | `mo.as_html(fig)` from a matplotlib `ax.hist(...)` figure |
| Heatmap | `mo.as_html(fig)` from a matplotlib `ax.imshow(...)` figure |

See `examples/demo_notebook.py` for all five wired up against the same
dataset.

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
2. Install `pmprov` alongside this package. PyPI doesn't allow published
   packages to declare a direct VCS dependency, so there's no `pmprov`
   extra — install it separately:

   ```bash
   pip install marimo-pmprov "pmprov @ git+https://github.com/alvarobernal2412/pmprov.git@main"
   ```
3. Pass your adapter instead of `MockProvenanceSource` to `ProvenancePanel`.

## Development

```bash
pip install -e ".[dev]"
pytest

cd frontend
npm install
npm run build   # or: npm run watch
```
