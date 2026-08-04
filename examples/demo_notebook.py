import marimo

__generated_with = "0.9.0"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import pandas as pd

    from provenance_widget.display import show_table
    from provenance_widget.mock_source import MockProvenanceSource
    from provenance_widget.widget import ProvenancePanel

    return MockProvenanceSource, ProvenancePanel, mo, pd, show_table


@app.cell
def _(mo):
    mode_toggle = mo.ui.radio(options=["student", "reviewer"], value="student", label="Persona")
    return (mode_toggle,)


@app.cell
def _(MockProvenanceSource, ProvenancePanel, mode_toggle):
    panel = ProvenancePanel(source=MockProvenanceSource(), mode=mode_toggle.value)
    return (panel,)


@app.cell
def _(mo, panel):
    sidebar = mo.sidebar(panel.sidebar())
    return (sidebar,)


@app.cell
def _(mo, pd, show_table):
    event_log = pd.DataFrame({
        "case:concept:name": ["c1", "c1", "c2"],
        "concept:name": ["Register", "Approve", "Register"],
        "duration": [12.5, 40.2, 8.1],
    })
    table = mo.ui.table(event_log)
    annotated_table = show_table(table, artifact_id="art-event-log", artifact_name="event_log.csv")
    annotated_table
    return (event_log,)


@app.cell
def _(mode_toggle, sidebar, panel):
    mode_toggle
    sidebar
    return


if __name__ == "__main__":
    app.run()
