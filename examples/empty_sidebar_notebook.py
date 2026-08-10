import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    from provenance_widget.interfaces import ProvenanceTree
    from provenance_widget.widget import ProvenancePanel

    return ProvenanceTree, mo, ProvenancePanel


@app.cell
def _(ProvenanceTree):
    # A genuinely empty tree — no nodes at all. Provenance is captured from
    # real user executions (see PmprovAdapter, which writes the actual first
    # state as soon as a session starts); a source with nothing recorded yet
    # should report nothing, not a fabricated "session start" step.
    class EmptyProvenanceSource:
        def get_tree(self) -> ProvenanceTree:
            return ProvenanceTree(nodes={}, root_id="", branches={})

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
