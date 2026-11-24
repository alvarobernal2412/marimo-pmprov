"""Which table a chart built in marimo's Visualize tab belongs to, and what its tabs were left as.

marimo keeps the chart tabs of a table in the browser, under the id of the cell that draws the table. Three things follow, and
this module is what the adapter and the panel use to deal with them:

- A cell id is the position of the cell in the notebook, so a notebook that gained or lost a cell has its tables under other
  ids. The recorded tabs are therefore kept by the *name* of their table (the ``artifact_name`` of ``show_table``), and
  `table_cells` finds the cell that draws each table in the notebook that is running.
- Tables that share a cell share its tabs. A notebook should draw each table in a cell of its own; tabs recorded while tables
  did share a cell are given to the table they were last changed on (`recorded_chart_tabs`).
- marimo shows an aggregation it has not saved (Y is "Mean" until the analyst chooses one) and loads a tab without one as
  "None". The page fills in the aggregation of the tab on show only, so a later chart's tabs lack the others'
  (`with_recorded_aggregations` puts them back). marimo also writes a column's default sort and aggregation into a tab when it
  merely shows it again, which is not a change (`as_drawn`).
"""
from __future__ import annotations

import hashlib
import json
import re

CHART_COLUMNS = ("xColumn", "yColumn", "colorByColumn")
TABLE_OF_TAB = "table"  # in a recorded tab: the name of the table it belongs to (tabs recorded before 0.16 have none)

_ARTIFACT_NAME = re.compile(r"""artifact_name\s*=\s*["']([^"']+)["']""")


def without_table(tab: dict) -> dict:
    """A recorded tab as marimo saves it: without the name of its table."""
    return {key: value for key, value in tab.items() if key != TABLE_OF_TAB}


def with_recorded_aggregations(tabs: list, earlier: list | None) -> list:
    """`tabs` (marimo's saved chart tabs of a table) with the aggregation each column was recorded with before, where marimo
    saved none for it. A tab is the earlier one when it has the same name and chart type; a column when it is the same field.
    An aggregation that is saved, also "none", is the analyst's choice and is kept. Nothing is changed in place."""
    before = {(t.get("tabName"), t.get("chartType")): t for t in (earlier or []) if isinstance(t, dict)}
    out = []
    for tab in tabs:
        old = before.get((tab.get("tabName"), tab.get("chartType")))
        general = (tab.get("config") or {}).get("general")
        old_general = ((old or {}).get("config") or {}).get("general")
        if not isinstance(general, dict) or not isinstance(old_general, dict):
            out.append(tab)
            continue
        patched = dict(general)
        for key in CHART_COLUMNS:
            column, old_column = general.get(key), old_general.get(key)
            if not isinstance(column, dict) or not isinstance(old_column, dict):
                continue
            same_field = column.get("field") and column.get("field") == old_column.get("field")
            if same_field and "aggregate" not in column and old_column.get("aggregate"):
                patched[key] = {**column, "aggregate": old_column["aggregate"]}
        out.append({**tab, "config": {**tab["config"], "general": patched}} if patched != general else tab)
    return out


def as_drawn(tabs: list | None) -> list:
    """`tabs` without what marimo writes into a tab when it only shows it again: a column's default sort ("ascending") and
    aggregation ("none"), which it leaves out until then. Two lists that are equal as drawn draw the same charts."""
    out = []
    for tab in tabs or []:
        general = (tab.get("config") or {}).get("general")
        if not isinstance(general, dict):
            out.append(tab)
            continue
        plain = dict(general)
        for key in CHART_COLUMNS:
            if isinstance(general.get(key), dict):
                plain[key] = {
                    k: v for k, v in general[key].items() if (k, v) not in (("sort", "ascending"), ("aggregate", "none"))
                }
        out.append({**tab, "config": {**tab["config"], "general": plain}})
    return out


def recorded_chart_tabs(charts: list) -> dict:
    """Name of a table -> the chart tabs it was left with, from the recorded charts, oldest first: `(table, builder)` with the
    builder state kept with the chart (None when it has none).

    A tab recorded since 0.16 says which table it belongs to. Before that, the tables that shared a cell shared its tabs, and
    looking at a tab on another table recorded it there too: such a tab belongs to the table it was last changed on (a tab
    that is only looked at does not change)."""
    tabs_of: dict = {}
    shared: dict = {}  # cell id -> {tab name: (tab, table)}: the tabs recorded before a tab said which table it belongs to
    for table, builder in charts:
        if not builder:
            continue
        cell, tabs = builder["cellId"], builder["tabs"]
        if all(isinstance(t, dict) and t.get(TABLE_OF_TAB) for t in tabs):
            for name in {t[TABLE_OF_TAB] for t in tabs} | {table}:
                mine = [without_table(t) for t in tabs if t[TABLE_OF_TAB] == name]
                tabs_of[name] = with_recorded_aggregations(mine, tabs_of.get(name))
            continue
        before = shared.get(cell, {})
        tabs = with_recorded_aggregations(tabs, [tab for tab, _ in before.values()])
        now = {}
        for tab in tabs:
            old = before.get(tab.get("tabName"))
            unchanged = old is not None and as_drawn([old[0]]) == as_drawn([tab])
            now[tab.get("tabName")] = (tab, old[1] if unchanged else table)
        shared[cell] = now
        for name in {owner for _, owner in before.values()} | {owner for _, owner in now.values()}:
            tabs_of[name] = [tab for tab, owner in now.values() if owner == name]
    return {name: tabs for name, tabs in tabs_of.items() if tabs}


def table_cells() -> dict:
    """Name of a table -> the id of the cell that draws it, in the marimo notebook that is running: the cells whose code has
    ``artifact_name="<name>"`` (as `show_table` is called). Call it while a cell runs. Empty outside marimo or when marimo
    cannot be asked (it reads a private part of marimo): the charts are then restored under the cell ids they were recorded
    with, as before 0.16."""
    try:
        from marimo._runtime.context import get_context

        found: dict = {}
        for cell_id, cell in get_context().graph.cells.items():
            for name in _ARTIFACT_NAME.findall(cell.code):
                found[name] = str(cell_id)
        return found
    except Exception:
        return {}


def notebook_cells() -> list:
    """The ids of the cells of the marimo notebook that is running, in their order; empty when marimo cannot be asked."""
    try:
        from marimo._runtime.context import get_context

        return [str(cell_id) for cell_id in get_context().graph.cells]
    except Exception:
        return []


def chart_layout(cells) -> str:
    """A short name for where the tables of a notebook are drawn (`table_cells()`, or `notebook_cells()` for a notebook whose
    tables have no name); "" for none. A browser that saved charts under another one has them on other cells."""
    return hashlib.sha256(json.dumps(cells, sort_keys=True).encode("utf8")).hexdigest()[:16] if cells else ""
