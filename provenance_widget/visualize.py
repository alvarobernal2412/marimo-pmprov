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


_LAYOUT_ESM = """
export default {
  render({ model, el }) {
    try {
      el.style.display = "none";
      const layout = model.get("layout") || "";
      const filename = (document.querySelector("marimo-filename")?.textContent || "").trim();
      if (!filename || !layout) return;
      const key = "marimo:charts:v2:" + filename, layoutKey = "pw-chart-layout:" + filename;
      if (localStorage.getItem(layoutKey) === layout) return;
      localStorage.setItem(layoutKey, layout);
      let saved = [];
      try { saved = JSON.parse(localStorage.getItem(key) || "[]"); } catch (e) {}
      if (!Array.isArray(saved) || !saved.length) return;
      localStorage.setItem(key, "[]");
      window.location.reload();  // marimo read the tabs when the page started
    } catch (e) {}
  },
};
"""


def charts_of_this_layout():
    """For a notebook that offers Visualize but has no panel: an element that shows nothing and makes a browser forget the chart
    tabs it saved for another layout of the notebook. Show it in a cell of its own (`mo.ui.anywidget(charts_of_this_layout())`).

    marimo keeps the chart tabs of a table in the browser, under the id of the table's cell, and an id is the position of the
    cell: after the notebook gained or lost a cell, the saved tabs would open on other tables. Such a notebook records nothing
    to put them back from, so the browser starts without them (the page is loaded again once). With a panel
    (`ProvenancePanel(capture_charts=True)`) this is not needed: the panel puts the recorded charts on their own tables.
    """
    import anywidget
    import traitlets

    from provenance_widget.chart_tables import chart_layout, notebook_cells

    class ChartsOfThisLayout(anywidget.AnyWidget):
        layout = traitlets.Unicode("").tag(sync=True)
        _esm = _LAYOUT_ESM

    return ChartsOfThisLayout(layout=chart_layout(notebook_cells()))
