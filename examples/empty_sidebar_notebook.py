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
# this must happen at true module level, not inside a cell. Marimo compiles
# every @app.cell body to bytecode when its decorator runs, i.e. while this
# module is first being imported/parsed — well before any cell's own code
# executes. init_marimo() (called from a cell further down) also calls this
# internally, but by then every cell's bytecode — including Step 1's — was
# already compiled unpatched, so nothing would ever get tracked. See
# tracker/kernel_hooks.py's own module docstring, which documents this
# exact requirement.
#
# Only sys.path/sys.modules changes made here carry into cell bodies below —
# marimo runs each @app.cell in its own scope, so a plain module-level
# variable (like _project_root above) is *not* visible inside them the way
# an ordinary Python closure would be. Cells that need the project root
# recompute it themselves and pass it along the normal marimo way.
import builtins as _builtins
from tracker.kernel_hooks import _NoOpRuntime, patch_marimo_ast_compile
from tracker import omit_functions

_builtins._provtrack_runtime = _NoOpRuntime()
patch_marimo_ast_compile()

# Same compile-time-only constraint as the patch above applies to the omit
# list: ProvTrackTransformer decides whether to wrap a call the moment that
# call's cell is first compiled, which — for every cell in this file —
# happens before any cell body runs. omit_functions() called from inside a
# cell (as pmprov's own docs show) can only affect cells compiled *after*
# that point, which in Marimo is none of them. It has to be here instead.
# Without this, the widget's own plumbing calls (constructing the panel,
# building the table, annotating it) would show up in the tree as steps
# alongside the real pandas analysis — noise, not provenance.
omit_functions(
    "nunique", "mean", "sum", "min", "max",
    "PmprovAdapter", "ProvenancePanel", "mo.ui.table", "show_table",
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

    from tracker import init_marimo, operation_type, enable_logging
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
