"""The chart builder state marimo keeps in the browser, as the panel and the adapter exchange it.

marimo saves the chart tabs of each cell in the browser (localStorage). The page reads that for the cell of a table when a chart
settles and sends it with the chart: ``{"cellId": "MJUe", "tabs": [{"tabName": ..., "chartType": ..., "config": {...}}]}``. It is kept
with the recorded chart so that a browser that has never seen the analysis can be given the tabs back (see ``chart-restore.ts``).
The ``config`` is marimo's own and is stored untouched; only its outline is checked here, since it comes from a page.
"""
from __future__ import annotations

import json

MAX_BUILDER_JSON = 100_000  # characters; a real cell's tabs are a few thousand


def valid_builder_state(value: object) -> dict | None:
    """The builder state if it has the expected outline, else None (a malformed or oversized one is dropped, never an error)."""
    if not isinstance(value, dict):
        return None
    cell_id, tabs = value.get("cellId"), value.get("tabs")
    if not (isinstance(cell_id, str) and cell_id and isinstance(tabs, list) and tabs):
        return None
    for tab in tabs:
        if not (isinstance(tab, dict) and isinstance(tab.get("tabName"), str) and isinstance(tab.get("chartType"), str)
                and isinstance(tab.get("config"), dict)):
            return None
    try:
        if len(json.dumps(tabs)) > MAX_BUILDER_JSON:
            return None
    except (TypeError, ValueError):
        return None
    return {"cellId": cell_id, "tabs": tabs}
