from __future__ import annotations

import marimo as mo


def _wrap(inner_html: str, artifact_id: str, artifact_name: str, granularity: str) -> mo.Html:
    return mo.Html(
        f'<div class="pw-annotatable" '
        f'data-pw-artifact-id="{artifact_id}" '
        f'data-pw-artifact-name="{artifact_name}" '
        f'data-pw-granularity="{granularity}">'
        f"{inner_html}"
        f"</div>"
    )


def show_table(table: "mo.ui.table", artifact_id: str, artifact_name: str) -> mo.Html:
    return _wrap(table.text, artifact_id, artifact_name, granularity="dataset")


def show_chart(chart_html: mo.Html, artifact_id: str, artifact_name: str) -> mo.Html:
    return _wrap(chart_html.text, artifact_id, artifact_name, granularity="chart_selection")
