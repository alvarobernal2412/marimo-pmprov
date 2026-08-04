from __future__ import annotations

import html

import marimo as mo


def _wrap(inner_html: str, artifact_id: str, artifact_name: str, granularity: str) -> mo.Html:
    return mo.Html(
        f'<div class="pw-annotatable" '
        f'data-pw-artifact-id="{html.escape(artifact_id, quote=True)}" '
        f'data-pw-artifact-name="{html.escape(artifact_name, quote=True)}" '
        f'data-pw-granularity="{html.escape(granularity, quote=True)}">'
        f"{inner_html}"
        f"</div>"
    )


def show_table(table: "mo.ui.table", artifact_id: str, artifact_name: str) -> mo.Html:
    return _wrap(table.text, artifact_id, artifact_name, granularity="dataset")


def show_chart(chart_html: mo.Html, artifact_id: str, artifact_name: str) -> mo.Html:
    return _wrap(chart_html.text, artifact_id, artifact_name, granularity="chart_selection")
