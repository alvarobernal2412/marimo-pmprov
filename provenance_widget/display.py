from __future__ import annotations

import html
import json

import marimo as mo

from .element_snapshot import snapshot_of, table_snapshot  # noqa: F401  (table_snapshot is re-exported)


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
