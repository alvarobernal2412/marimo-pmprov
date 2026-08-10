import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full")


@app.cell
def _():
    import sys
    from pathlib import Path

    _here = Path.cwd()
    PROJECT_ROOT = _here
    for _candidate in [_here, *_here.parents]:
        if (_candidate / "pyproject.toml").exists():
            PROJECT_ROOT = _candidate
            break

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    EXAMPLES_DIR = PROJECT_ROOT / "examples"
    if str(EXAMPLES_DIR) not in sys.path:
        sys.path.insert(0, str(EXAMPLES_DIR))

    INPUT_FILE_NAME = "rtfm_full.csv"
    CASE_ID_COL = "case:concept:name"
    TIMESTAMP_COL = "time:timestamp"
    ACTIVITY_COL = "concept:name"

    data_path = PROJECT_ROOT / "examples" / "data" / INPUT_FILE_NAME

    print("Project root:", PROJECT_ROOT)
    print("Data file   :", data_path, "found" if data_path.exists() else "NOT FOUND")
    return CASE_ID_COL, PROJECT_ROOT, TIMESTAMP_COL, data_path


@app.cell
def _(PROJECT_ROOT):
    # Setup + init, all in one cell, exporting everything downstream tracked
    # cells need (pd, rt, ...) — pmprov's README calls this out as a
    # structural requirement: Marimo's reactive DAG only orders cells by the
    # names they depend on, so a tracked cell that doesn't depend on
    # something exported *from this cell* has no guarantee it runs (or gets
    # its AST-rewritten bytecode compiled) after init_marimo() has patched
    # the compiler and swapped in a real RuntimeTracker.
    import marimo as mo
    import pandas as pd

    from tracker import init_marimo, omit_functions, operation_type, enable_logging
    from utils.event_enricher import (
        create_case_log,
        event_add_relative_case_time,
        case_add_activity_start_times,
    )

    from provenance_widget.display import show_table
    from provenance_widget.pmprov_adapter import PmprovAdapter
    from provenance_widget.widget import ProvenancePanel

    enable_logging(level="DEBUG")

    (PROJECT_ROOT / "examples" / "marimo" / "artifacts").mkdir(parents=True, exist_ok=True)

    rt = init_marimo(
        history_name="RTFM event log exploration (Marimo)",
        branch_name="main",
        db_path=str(PROJECT_ROOT / "examples" / "marimo" / "provenance.db"),
        artifact_dir=str(PROJECT_ROOT / "examples" / "marimo" / "artifacts"),
    )

    operation_type("data_loading", pd.read_csv)
    operation_type("case_aggregation", create_case_log)
    operation_type("attribute_derivation", event_add_relative_case_time)
    operation_type("attribute_derivation", case_add_activity_start_times)
    operation_type("case_filter", pd.DataFrame.apply)

    omit_functions("nunique", "mean", "sum", "min", "max")

    print("Session ID   :", rt.session_id)
    print("History name :", rt._history.name)
    return (
        PmprovAdapter,
        ProvenancePanel,
        case_add_activity_start_times,
        create_case_log,
        event_add_relative_case_time,
        mo,
        pd,
        rt,
        show_table,
    )


@app.cell
def _(PmprovAdapter, ProvenancePanel, rt):
    # Backed by the real pmprov history above (via PmprovAdapter), not an
    # EmptyProvenanceSource — the sidebar reflects rt's actual tracked steps.
    # ProvenancePanel polls and refreshes itself in the background for
    # sources like this one, so tracked cells below don't call settle() or
    # refresh() themselves.
    adapter = PmprovAdapter(rt)
    panel = ProvenancePanel(source=adapter, mode="student")
    return adapter, panel


@app.cell
def _(mo, panel):
    # mo.sidebar(...) must be the last bare expression in this cell to render —
    # it cannot be assigned to a variable and displayed from a different cell.
    mo.sidebar(panel.sidebar())
    return


@app.cell
def _(CASE_ID_COL, TIMESTAMP_COL, adapter, data_path, mo, pd, show_table):
    # Step 1 – load the event log
    event_log = pd.read_csv(
        str(data_path),
        dtype={"org:resource": str, "matricola": str},
        parse_dates=[TIMESTAMP_COL],
    )
    print(f"Loaded {len(event_log):,} events across {event_log[CASE_ID_COL].nunique():,} cases")

    # The one provenance_widget-specific line needed here: which state this
    # table represents, so the picker can link cells in it back to this step.
    state_id = adapter.latest_state_id(func_name="pd.read_csv") or "event_log"

    table = mo.ui.table(event_log.head(3))
    annotated_table = show_table(table, artifact_id=state_id, artifact_name="event_log.csv")
    annotated_table
    return (event_log,)


if __name__ == "__main__":
    app.run()
