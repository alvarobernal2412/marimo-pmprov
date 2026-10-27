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

panel = ProvenancePanel(source=MockProvenanceSource(), mode="analyst")

# mo.sidebar(...) must be the last bare expression in its own cell to render —
# it cannot be assigned to a variable and displayed from a different cell.
mo.sidebar(panel.sidebar())
```

The persona is chosen when the panel is created and can't be changed from
the UI: `ProvenancePanel(mode="analyst")` (annotates; `"student"` still works
as a deprecated alias) or `mode="reviewer"`.

The sidebar is one **Annotations** tab. A **Tree** tab is available too, but
only if you opt in when creating the panel with `ProvenancePanel(show_tree=True)`;
it can't be switched on from the UI. With only one tab, no tab bar is shown.

- **Annotations** — a chronological list (oldest first, each with a small
  timestamp). *Analyst*: a composer at the top (pick a notebook output as the
  target, or clear it to annotate the whole analysis, which attaches to the
  latest state), plus edit and delete icons on each annotation (written
  through to the source when it supports `update_annotation` /
  `remove_annotation`, as `PmprovAdapter` does). *Reviewer*: read-only, with a
  **Replay** button on every annotation.
- **Tree** (opt-in) — a Miller-columns view of the full provenance history,
  with filter chips for tags and linked artifacts and an inline inspector.

#### Reviewer replay

Reviewers get a debugger-style stepper (First / Back / Next / Latest, or the
left/right arrow keys when it is focused) at the top of the Annotations and
Tree tabs. Back/Next walk the provenance tree, Next remembers the branch you
stepped back from (redo), and a branch picker appears where the analysis
forks. **Latest** follows the most recent recorded state as the analysis
grows. From Python: `panel.cursor_state_id`, `panel.latest_state_id`,
`panel.go_to(state_id)`, `panel.go_latest()`, and `panel.widget.replay`
(`{"stateId", "params", "isLatest"}`) for notebook cells that want to react.

#### Replay renders the whole notebook

With a `PmprovAdapter` source, stepping (or clicking **Replay** on an
annotation) can re-render the notebook as it stood at that state, from
pmprov's recorded snapshots. Wire it up in three steps:

```python
# 1. bind the replay cursor to a marimo state (a reviewer starts at the latest recorded state)
get_cursor = panel.reactive_cursor(mo.state)

# 2. one cell turns the cursor into a snapshot of every variable at that state
snap = panel.snapshot(get_cursor())

# 3. display cells read from it; `live` is used when there is no snapshot (analysts)
df = snap.get("by_activity", by_activity)      # None = nothing to show at this step
mo.stop(df is None, mo.md(snap.missing("by_activity")))   # "not computed yet" or "not stored by pmprov"
mo.callout(mo.md(snap.banner()))               # "Snapshot of the analysis after ... (step n)"
```

Values load lazily, one variable at a time, from pmprov's recorded state
(`restore_state(names=...)`, cached per artifact version). Treat them as
read-only. It works with any pmprov. **pmprov >= 0.9.0 is recommended**: 0.8+
records exactly which variable was bound to which artifact at every state, and
0.9 also tracks plain aliases (`df = other`) and objects changed through another
variable (`ax.bar(...)` changing `fig`). With an older pmprov, or for histories
recorded before 0.8, each variable is rebuilt from the step that last assigned
it: exact for what pmprov tracked, but slower and blind to those two cases.

Keep computing and displaying in separate cells: a display cell that also
computed would re-run, and re-record a step, every time the reviewer steps.
See `examples/annotate_notebook.py`.

To have pmprov track a notebook while you use it, start marimo through the
launcher; plain `marimo run` / `marimo edit` do not apply pmprov's patch (marimo
loads a notebook by parsing it, so the notebook's own top-level patch never runs):

```bash
python -m provenance_widget.marimo_launcher run notebook.py
python -m provenance_widget.marimo_launcher edit notebook.py --omit my_helper
```

It leaves the widget's own calls and common marimo UI calls out of the
provenance tree; `--omit NAME` adds more. Viewing is read-only: nothing is checked out and no new
steps are recorded.

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
