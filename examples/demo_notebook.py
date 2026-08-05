import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import matplotlib
    import altair as alt
    import vl_convert as vlc
    import plotly.express as px

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from provenance_widget.display import show_chart, show_table
    from provenance_widget.mock_source import MockProvenanceSource
    from provenance_widget.widget import ProvenancePanel

    return (
        MockProvenanceSource,
        ProvenancePanel,
        alt,
        mo,
        pd,
        plt,
        px,
        show_chart,
        show_table,
        vlc,
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


@app.cell
def _(alt, event_log, mo, show_chart, vlc):
    # Unlike the matplotlib charts above (flat PNGs), Vega-Lite/Altair marks
    # each bar with an aria-label carrying its data ("concept:name: Register;
    # duration: 12.5; ..."), which the picker's "svg-mark" resolver
    # (frontend/src/resolvers.ts) reads off directly — no extra wiring needed.
    #
    # marimo's default mo.as_html(chart) embeds Vega-Lite as an interactive
    # <canvas> (or a rasterized <img>), neither of which has per-mark DOM
    # nodes to click on — so here the chart is rendered straight to real
    # inline SVG via vl-convert instead, which is what makes those
    # aria-labeled <path> marks actually present in the page.
    altair_chart = alt.Chart(event_log).mark_bar().encode(
        x=alt.X(field="concept:name", type="nominal"),
        y=alt.Y(field="duration", type="quantitative"),
        color=alt.Color(field="case:concept:name", type="nominal"),
    )
    altair_svg = vlc.vegalite_to_svg(altair_chart.to_json())
    annotated_altair_chart = show_chart(
        mo.Html(altair_svg), artifact_id="art-duration-altair", artifact_name="Chart_DurationAltair"
    )
    annotated_altair_chart
    return


@app.cell
def _(mo, show_chart):
    # A hand-authored SVG, tagged by hand rather than relying on a charting
    # library's own accessibility output. This is the general-purpose escape
    # hatch: any visualization — a custom D3 diagram, a process map, a
    # network graph — can be picked down to individual elements by putting
    # data-pw-detail (and optionally data-pw-granularity) directly on the
    # SVG nodes. The picker's "svg-mark" resolver (resolvers.ts) looks for
    # exactly that attribute, so no picker code changes were needed for this.
    #
    # Reuses artifact_id="art-process-map" — the same artifact the "Baseline
    # fitness" annotation in mock_source.py already references, so picking
    # a node here and the tree's "Chart_ProcessMap" filter chip line up.
    process_steps = ["Register", "Approve", "Archive"]
    box_w, box_h, gap = 120, 48, 60
    svg_width = len(process_steps) * box_w + (len(process_steps) - 1) * gap
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{box_h + 20}" '
        f'viewBox="0 0 {svg_width} {box_h + 20}">',
        '<defs><marker id="pw-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" '
        'orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#64748B" /></marker></defs>',
    ]
    for i, step in enumerate(process_steps):
        x = i * (box_w + gap)
        svg_parts.append(
            f'<g data-pw-detail="{step}" data-pw-granularity="node" role="graphics-symbol" '
            f'aria-label="Process step: {step}">'
            f'<rect x="{x}" y="0" width="{box_w}" height="{box_h}" rx="6" '
            f'fill="#EFF6FF" stroke="#0EA5E9" stroke-width="2" />'
            f'<text x="{x + box_w / 2}" y="{box_h / 2}" text-anchor="middle" '
            f'dominant-baseline="middle" font-family="sans-serif" font-size="13">{step}</text>'
            f"</g>"
        )
        if i < len(process_steps) - 1:
            line_x1, line_x2 = x + box_w, x + box_w + gap
            svg_parts.append(
                f'<line x1="{line_x1}" y1="{box_h / 2}" x2="{line_x2 - 8}" y2="{box_h / 2}" '
                f'stroke="#64748B" stroke-width="2" marker-end="url(#pw-arrow)" />'
            )
    svg_parts.append("</svg>")
    process_map_svg = "".join(svg_parts)

    annotated_process_map = show_chart(
        mo.Html(process_map_svg), artifact_id="art-process-map", artifact_name="Chart_ProcessMap"
    )
    annotated_process_map
    return


@app.cell
def _(event_log, mo, px, show_chart):
    # A fourth chart library, for contrast: mo.ui.plotly renders inline
    # (a <marimo-plotly> custom element — not the CDN-loading <iframe> that
    # mo.as_html(plotly_fig) produces), so at least "chart_selection"-level
    # picking works out of the box like any other artifact. Plotly's own SVG
    # marks don't carry the aria-label convention Vega-Lite does, so unlike
    # the Altair chart above, per-bar picking isn't automatic here — it's
    # exactly the kind of case that would need its own resolver (see
    # frontend/src/resolvers.ts) reading Plotly's "plotly_click" event data
    # instead of guessing from the DOM.
    plotly_fig = px.bar(
        event_log.groupby("concept:name", as_index=False)["duration"].mean(),
        x="concept:name",
        y="duration",
        color="concept:name",
        title="Mean duration by activity (Plotly)",
    )
    annotated_plotly_chart = show_chart(
        mo.ui.plotly(plotly_fig), artifact_id="art-duration-plotly", artifact_name="Chart_DurationPlotly"
    )
    annotated_plotly_chart
    return


if __name__ == "__main__":
    app.run()
