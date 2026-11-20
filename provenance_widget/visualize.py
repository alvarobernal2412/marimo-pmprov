"""Show marimo's Visualize button (its chart builder) on tables also when a notebook runs as an app.

marimo offers the chart builder only in edit mode: its table plugin sets ``show_chart_builder = app_mode == "edit"``. The builder
itself works in an app (the chart is drawn in the browser from data the table already carries), so this makes the table plugin see
"edit" mode. It touches a private name of marimo, so it never raises: if marimo changes, tables simply keep their stock toolbar.
"""
from __future__ import annotations


def enable_chart_builder() -> bool:
    """Make every table created from now on offer Visualize. Returns whether the switch was applied."""
    try:
        from marimo._plugins.ui._impl import table as table_plugin

        if not callable(getattr(table_plugin, "get_mode", None)):
            return False
        table_plugin.get_mode = lambda: "edit"
        return True
    except Exception:
        return False
