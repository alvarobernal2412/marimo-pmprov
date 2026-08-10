import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    from provenance_widget.interfaces import (
        Delta,
        Operation,
        ProvenanceNode,
        ProvenanceTree,
        StepCategory,
    )
    from provenance_widget.widget import ProvenancePanel

    return Delta, Operation, ProvenanceNode, ProvenanceTree, StepCategory, mo, ProvenancePanel


@app.cell
def _(Delta, Operation, ProvenanceNode, ProvenanceTree, StepCategory):
    # The smallest valid tree: a single root node with no children and no
    # annotations. root_id must reference a real node — an empty `nodes`
    # dict isn't a valid tree — so this is the minimal "nothing has happened
    # yet" state, same shape PmprovAdapter falls back to before a real
    # session's first step lands (see pmprov_adapter.py's _root_node()).
    root = ProvenanceNode(
        state_id="root",
        parent_state_id=None,
        branch_id="main",
        operation=Operation(
            operation_id="root",
            name="Session start",
            operation_type="IMPORT",
            command_name="init",
            category=StepCategory.DATA_LOADING,
        ),
        params={},
        delta=Delta([], [], row_count_before=0, row_count_after=0),
        annotations=[],
    )

    class EmptyProvenanceSource:
        def get_tree(self) -> ProvenanceTree:
            return ProvenanceTree(nodes={"root": root}, root_id="root", branches={"main": "root"})

        def state_for_artifact(self, artifact_id: str) -> str | None:
            return None

    return (EmptyProvenanceSource,)


@app.cell
def _(EmptyProvenanceSource, ProvenancePanel):
    panel = ProvenancePanel(source=EmptyProvenanceSource(), mode="student")
    return (panel,)


@app.cell
def _(mo, panel):
    # mo.sidebar(...) must be the last bare expression in this cell to render —
    # it cannot be assigned to a variable and displayed from a different cell.
    mo.sidebar(panel.sidebar())
    return


if __name__ == "__main__":
    app.run()
