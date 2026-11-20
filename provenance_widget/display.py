from __future__ import annotations

import base64
import html
import json

import marimo as mo

from .element_snapshot import figure_png, image_snapshot, snapshot_of, table_snapshot  # noqa: F401  (table_snapshot is re-exported)


def _wrap(
    inner_html: str, artifact_id: str, artifact_name: str, granularity: str, snapshot: dict | None = None
) -> mo.Html:
    snapshot_attribute = (
        f' data-pw-snapshot="{html.escape(json.dumps(snapshot), quote=True)}"' if snapshot else ""
    )
    return mo.Html(
        f'<div class="pw-annotatable" '
        f'data-pw-artifact-id="{html.escape(artifact_id, quote=True)}" '
        f'data-pw-artifact-name="{html.escape(artifact_name, quote=True)}" '
        f'data-pw-granularity="{html.escape(granularity, quote=True)}"{snapshot_attribute}>'
        f"{inner_html}"
        f"</div>"
    )


def show_table(table: "mo.ui.table", artifact_id: str, artifact_name: str) -> mo.Html:
    return _wrap(
        table.text, artifact_id, artifact_name, granularity="dataset",
        snapshot=table_snapshot(getattr(table, "data", None)),
    )


def show_chart(chart_html: mo.Html, artifact_id: str, artifact_name: str, figure=None) -> mo.Html:
    """`figure` (matplotlib, Altair, Plotly or PIL) is drawn as an image in the report when this chart is picked."""
    return _wrap(
        chart_html.text, artifact_id, artifact_name, granularity="chart_selection",
        snapshot=snapshot_of(figure) if figure is not None else None,
    )


def show(
    element, artifact_id: str, artifact_name: str, value=None, granularity: str = "dataset"
) -> mo.Html:
    """Make any element pickable in the sidebar.

    `value` is what the element shows (a DataFrame, a figure, a PNG, text or a number); the exported report draws it
    as a table, an image or text. Without it, a marimo table is read from its data and anything else is pickable
    but drawn from the recorded step.
    """
    inner = getattr(element, "text", None)
    if inner is None:
        inner = mo.as_html(element).text
    if value is None:
        value = getattr(element, "data", None) if type(element).__module__.startswith("marimo") else element
    return _wrap(inner, artifact_id, artifact_name, granularity, snapshot=snapshot_of(value))


CHART_STEP = "visualize_chart"  # the step PmprovAdapter.record_chart records for a chart built in marimo's Visualize tab


def recorded_charts(source, state_id: str | None) -> list[dict]:
    """The charts recorded in the Visualize tab up to *state_id* (that step included), oldest first.

    Each is {"artifact_id" (the chart's step), "name", "table", "settings", "png"}. For a reviewer notebook: given the replay
    cursor it lists what the analyst had charted by then. Empty for a source that keeps no outputs, an unknown state, or None.
    """
    from .pmprov_adapter import _chart_title

    try:
        nodes = source.get_tree().nodes
        if not state_id or state_id not in nodes or not hasattr(source, "snapshot"):
            return []
        path, seen = [], set()
        node = nodes[state_id]
        while node is not None and node.state_id not in seen:  # the step history is a chain; guard against a cycle all the same
            seen.add(node.state_id)
            path.append(node)
            node = nodes.get(node.parent_state_id) if node.parent_state_id else None
        charts = []
        for node in reversed(path):
            if node.operation.name != CHART_STEP:
                continue
            table = str(node.params.get("table", ""))
            settings = node.params.get("settings") or {}
            picture = source.snapshot(node.state_id, ["chart_image"]).get("chart_image")
            png = figure_png(picture) if picture is not None else None
            charts.append(
                {"artifact_id": node.state_id, "name": _chart_title(table, settings), "table": table, "settings": settings, "png": png}
            )
        return charts
    except Exception:
        return []


def show_recorded_charts(source, state_id: str | None) -> mo.Html:
    """The charts recorded up to *state_id*, drawn and tagged like any other output, so a reviewer sees them and an annotation's
    "Jump to anchor" finds the chart it was written about. Draws nothing when there are none."""
    figures = []
    for chart in recorded_charts(source, state_id):
        settings = ", ".join(f"{key}: {value}" for key, value in chart["settings"].items())
        picture = (
            f'<img alt="{html.escape(chart["name"], quote=True)}" style="max-width:100%;height:auto" '
            f'src="data:image/png;base64,{base64.b64encode(chart["png"]).decode("ascii")}"/>'
            if chart["png"]
            else '<em>The picture of this chart was not kept.</em>'
        )
        inner = (
            f'<figure style="margin:0 0 1rem 0">{picture}'
            f'<figcaption><b>{html.escape(chart["name"])}</b><br><small>{html.escape(settings)}</small></figcaption></figure>'
        )
        figures.append(_wrap(inner, chart["artifact_id"], chart["name"], "chart_selection", image_snapshot(chart["png"])).text)
    return mo.Html("".join(figures))
