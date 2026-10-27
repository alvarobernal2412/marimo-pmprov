import marimo

import sys
from pathlib import Path


def _find_project_root() -> Path:
    here = Path.cwd()
    for candidate in [here, *here.parents]:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return here


_project_root = _find_project_root()
for _p in (_project_root, _project_root / "examples"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Activate pmprov's AST rewriting *before* app = marimo.App(...) below —
# this must happen at true module level, not inside a cell (see
# empty_sidebar_notebook.py for the full explanation). Same for the omit
# list: it only affects cells compiled after it is set, which is every cell.
import builtins as _builtins
from tracker.kernel_hooks import _NoOpRuntime, patch_marimo_ast_compile
from tracker import omit_functions

_builtins._provtrack_runtime = _NoOpRuntime()
patch_marimo_ast_compile()

# Widget plumbing, marimo UI calls and the snapshot helpers are not analysis
# steps — keep them out of the provenance tree so it only shows the real
# operations.
omit_functions(
    "nunique", "mean", "sum", "min", "max",
    "PmprovAdapter", "ProvenancePanel", "mo.ui.table", "show_table",
    "mo.ui.multiselect", "mo.ui.slider", "mo.vstack", "mo.md", "mo.stop",
    "mo.callout", "panel.snapshot", "panel.reactive_cursor", "snap.get",
)

__generated_with = "0.23.16"
app = marimo.App(width="full")


@app.cell
def _():
    from pathlib import Path

    here = Path.cwd()
    PROJECT_ROOT = here
    for candidate in [here, *here.parents]:
        if (candidate / "pyproject.toml").exists():
            PROJECT_ROOT = candidate
            break

    data_path = PROJECT_ROOT / "examples" / "data" / "rtfm_full.csv"
    print("Project root:", PROJECT_ROOT)
    print("Data file   :", data_path, "found" if data_path.exists() else "NOT FOUND")

    CASE_ID_COL = "case:concept:name"
    TIMESTAMP_COL = "time:timestamp"
    return CASE_ID_COL, PROJECT_ROOT, TIMESTAMP_COL, data_path


@app.cell
def _(PROJECT_ROOT):
    import marimo as mo
    import pandas as pd

    from tracker import init_marimo, operation_type, step_category, enable_logging
    from utils.event_enricher import create_case_log
    from utils.event_filters import filter_events_by_activity, filter_events_since

    from provenance_widget.display import show_table
    from provenance_widget.pmprov_adapter import PmprovAdapter
    from provenance_widget.widget import ProvenancePanel

    enable_logging(level="DEBUG")

    # Its own database, so annotations made here don't mix with the other
    # example notebooks' histories.
    store = PROJECT_ROOT / "examples" / "marimo" / "annotate"
    (store / "artifacts").mkdir(parents=True, exist_ok=True)

    rt = init_marimo(
        history_name="RTFM event log: filter and annotate (Marimo)",
        branch_name="main",
        db_path=str(store / "provenance.db"),
        artifact_dir=str(store / "artifacts"),
    )

    operation_type("event_filter", filter_events_by_activity)
    operation_type("event_filter", filter_events_since)
    operation_type("case_aggregation", create_case_log)
    # Category names must match the sidebar's categories to get their colors.
    step_category("CLEANING", "event_filter")
    step_category("AGGREGATION", "case_aggregation")

    print("Session ID   :", rt.session_id)
    print("History name :", rt._history.name)
    return (
        PmprovAdapter,
        ProvenancePanel,
        create_case_log,
        filter_events_by_activity,
        filter_events_since,
        mo,
        pd,
        rt,
        show_table,
    )


@app.cell
def _(PmprovAdapter, ProvenancePanel, mo, rt):
    # Reviewer persona: read-only, step through the recorded analysis with the
    # replay stepper and use Replay on each annotation. Switch to
    # mode="analyst" and re-run this cell to annotate and edit instead.
    adapter = PmprovAdapter(rt)
    panel = ProvenancePanel(source=adapter, mode="reviewer")
    # Every step in the sidebar (or Replay on an annotation) updates this
    # cursor; cells that call get_cursor() re-run when it moves.
    get_cursor = panel.reactive_cursor(mo.state)
    return adapter, get_cursor, panel


@app.cell
def _(mo, panel):
    # mo.sidebar(...) must be the last bare expression in this cell to render —
    # it cannot be assigned to a variable and displayed from a different cell.
    mo.sidebar(panel.sidebar())
    return


@app.cell
def _(get_cursor, panel):
    # The whole analysis at the step the reviewer is on: every variable as it
    # was bound then. None cursor = following the live analysis, and the
    # snapshot then just hands back the live values.
    snap = panel.snapshot(get_cursor())
    return (snap,)


@app.cell
def _(mo, snap):
    mo.callout(mo.md(snap.banner()), kind="warn") if not snap.is_live else None
    return


@app.cell
def _(CASE_ID_COL, TIMESTAMP_COL, adapter, data_path, pd):
    # Step 1 – load the event log (live, tracked by pmprov)
    event_log = pd.read_csv(
        str(data_path),
        dtype={"org:resource": str, "matricola": str},
        parse_dates=[TIMESTAMP_COL],
    )
    print(f"Loaded {len(event_log):,} events across {event_log[CASE_ID_COL].nunique():,} cases")

    state_id = adapter.latest_state_id(func_name="pd.read_csv") or "event_log"
    return event_log, state_id


@app.cell
def _(event_log, mo, show_table, snap, state_id):
    _df = snap.get("event_log", event_log)
    mo.stop(_df is None, mo.md("## 1. Event log\n\n" + snap.missing("event_log")))
    _shown = show_table(mo.ui.table(_df.head(3)), artifact_id=state_id, artifact_name="event_log.csv")
    mo.vstack([mo.md(f"## 1. Event log: {len(_df):,} events"), _shown])
    return


@app.cell
def _(event_log, mo):
    # The filters. Each change re-runs the steps below, and every run is
    # recorded as a new state you can annotate (and, as a reviewer, replay).
    activity_select = mo.ui.multiselect(
        options=sorted(event_log["concept:name"].unique()),
        value=["Create Fine", "Send Fine", "Payment"],
        label="Keep activities",
    )
    year_slider = mo.ui.slider(start=2000, stop=2013, value=2005, label="Events since year")
    mo.vstack([mo.md("## Filters"), activity_select, year_slider])
    return activity_select, year_slider


@app.cell
def _(activity_select, adapter, event_log, filter_events_by_activity, mo):
    # Step 2 – filter by activity (live, tracked by pmprov)
    mo.stop(not activity_select.value, mo.md("Select at least one activity."))
    by_activity = filter_events_by_activity(event_log, activity_select.value)

    state_id_activity = adapter.latest_state_id() or "events_by_activity"
    return by_activity, state_id_activity


@app.cell
def _(by_activity, mo, show_table, snap, state_id_activity):
    _df = snap.get("by_activity", by_activity)
    mo.stop(_df is None, mo.md("## 2. By activity\n\n" + snap.missing("by_activity")))
    _shown = show_table(mo.ui.table(_df.head(5)), artifact_id=state_id_activity, artifact_name="events_by_activity")
    mo.vstack([mo.md(f"## 2. By activity: {len(_df):,} events"), _shown])
    return


@app.cell
def _(adapter, by_activity, filter_events_since, year_slider):
    # Step 3 – keep only recent events (live, tracked by pmprov)
    since_year = filter_events_since(by_activity, year_slider.value)

    state_id_year = adapter.latest_state_id() or "events_since_year"
    return since_year, state_id_year


@app.cell
def _(mo, show_table, since_year, snap, state_id_year, year_slider):
    _df = snap.get("since_year", since_year)
    mo.stop(_df is None, mo.md("## 3. Since year\n\n" + snap.missing("since_year")))
    _heading = f"## 3. Events in {year_slider.value} or later: {len(_df):,} events" if snap.is_live else f"## 3. Events since year: {len(_df):,} events"
    _shown = show_table(mo.ui.table(_df.head(5)), artifact_id=state_id_year, artifact_name="events_since_year")
    mo.vstack([mo.md(_heading), _shown])
    return


@app.cell
def _(adapter, create_case_log, since_year):
    # Step 4 – one row per case (live, tracked by pmprov)
    case_log = create_case_log(since_year)

    state_id_cases = adapter.latest_state_id() or "case_log"
    return case_log, state_id_cases


@app.cell
def _(case_log, mo, show_table, snap, state_id_cases):
    _df = snap.get("case_log", case_log)
    mo.stop(_df is None, mo.md("## 4. Case log\n\n" + snap.missing("case_log")))
    _shown = show_table(mo.ui.table(_df.head(5)), artifact_id=state_id_cases, artifact_name="case_log")
    mo.vstack([mo.md(f"## 4. Case log: {len(_df):,} cases"), _shown])
    return


if __name__ == "__main__":
    app.run()
