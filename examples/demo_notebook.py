import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from provenance_widget.display import show_chart, show_table
    from provenance_widget.mock_source import MockProvenanceSource
    from provenance_widget.widget import ProvenancePanel

    return (
        MockProvenanceSource,
        ProvenancePanel,
        mo,
        pd,
        plt,
        show_chart,
        show_table,
    )


@app.cell
def _(MockProvenanceSource, ProvenancePanel):
    # Persona (student/reviewer) is switched from the widget's own "config"
    # tab, not a separate marimo control — this is just the initial value.
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="student")
    return (panel,)


@app.cell
def _(mo, panel):
    # mo.sidebar(...) must be the last bare expression in this cell to render —
    # it cannot be assigned to a variable and displayed from a different cell.
    mo.sidebar(panel.sidebar())
    return


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
def _(event_log, mo, plt, show_chart):
    # Five different visualization types, each picker-targetable at
    # "chart_selection" granularity (see provenance_widget/display.py).

    bar_fig, bar_ax = plt.subplots(figsize=(4, 3))
    event_log.groupby("concept:name")["duration"].mean().plot.bar(ax=bar_ax, color="#0EA5E9")
    bar_ax.set_title("Mean duration by activity")
    bar_ax.set_ylabel("hours")
    bar_chart = show_chart(
        mo.as_html(bar_fig), artifact_id="art-duration-bar", artifact_name="Chart_DurationByActivity"
    )

    line_fig, line_ax = plt.subplots(figsize=(4, 3))
    event_log["duration"].plot.line(ax=line_ax, color="#10B981", marker="o")
    line_ax.set_title("Duration across events")
    line_ax.set_ylabel("hours")
    line_chart = show_chart(
        mo.as_html(line_fig), artifact_id="art-duration-line", artifact_name="Chart_DurationTrend"
    )

    scatter_fig, scatter_ax = plt.subplots(figsize=(4, 3))
    scatter_ax.scatter(range(len(event_log)), event_log["duration"], c="#F59E0B")
    scatter_ax.set_title("Duration per event index")
    scatter_ax.set_ylabel("hours")
    scatter_chart = show_chart(
        mo.as_html(scatter_fig), artifact_id="art-duration-scatter", artifact_name="Chart_DurationScatter"
    )

    hist_fig, hist_ax = plt.subplots(figsize=(4, 3))
    hist_ax.hist(event_log["duration"], bins=5, color="#F43F5E")
    hist_ax.set_title("Duration distribution")
    hist_ax.set_xlabel("hours")
    hist_chart = show_chart(
        mo.as_html(hist_fig), artifact_id="art-duration-hist", artifact_name="Chart_DurationHistogram"
    )

    heatmap_fig, heatmap_ax = plt.subplots(figsize=(4, 3))
    pivot = event_log.pivot_table(
        index="case:concept:name", columns="concept:name", values="duration", aggfunc="mean"
    )
    im = heatmap_ax.imshow(pivot.fillna(0), cmap="viridis", aspect="auto")
    heatmap_ax.set_xticks(range(len(pivot.columns)))
    heatmap_ax.set_xticklabels(pivot.columns, rotation=45, ha="right")
    heatmap_ax.set_yticks(range(len(pivot.index)))
    heatmap_ax.set_yticklabels(pivot.index)
    heatmap_ax.set_title("Duration by case x activity")
    heatmap_fig.colorbar(im, ax=heatmap_ax)
    heatmap_chart = show_chart(
        mo.as_html(heatmap_fig), artifact_id="art-duration-heatmap", artifact_name="Chart_DurationHeatmap"
    )

    mo.vstack([
        mo.hstack([bar_chart, line_chart], justify="start"),
        mo.hstack([scatter_chart, hist_chart], justify="start"),
        heatmap_chart,
    ])
    return


if __name__ == "__main__":
    app.run()
