"""A chart built in Visualize comes back as it was left: on its own table, with its aggregation, and without new steps."""
import json
from types import SimpleNamespace

import pytest

from provenance_widget import chart_tables
from provenance_widget.chart_tables import as_drawn, chart_layout, recorded_chart_tabs, with_recorded_aggregations


def tab(name, kind, x=None, y=None):
    return {"tabName": name, "chartType": kind, "config": {"general": {"xColumn": x or {}, "yColumn": y or {}}}}


def of(table, *tabs):
    """The tabs as they are recorded since tabs are kept by table."""
    return [{**t, "table": table} for t in tabs]


BAR = tab("Bar Chart", "bar", {"field": "CreditScore", "aggregate": "bin"}, {"field": "__count__"})
SCATTER_MEAN = tab("Scatter Chart 2", "scatter", {"field": "CreditScore"}, {"field": "MonthlyCost", "aggregate": "mean"})
SCATTER_BARE = tab("Scatter Chart 2", "scatter", {"field": "CreditScore"}, {"field": "MonthlyCost"})
NO_X = tab("Bar Chart", "bar", {"field": ""}, {"field": "__count__"})  # what marimo makes of a tab on a table without its column

BAR_SETTINGS = {"chart_type": "Bar", "x": "CreditScore", "y": "Count of records"}
SCATTER_SETTINGS = {"chart_type": "Scatter", "x": "CreditScore", "y": "MonthlyCost", "y_aggregation": "Mean"}
PNG = bytes.fromhex("89504e470d0a1a0a") + b"a picture"


# --- the aggregation marimo shows but does not save ---------------------------------------------------------------------------


def test_a_tab_keeps_the_aggregation_it_was_recorded_with():
    assert with_recorded_aggregations([BAR, SCATTER_BARE], [BAR, SCATTER_MEAN]) == [BAR, SCATTER_MEAN]


def test_an_aggregation_the_analyst_chose_is_never_replaced():
    chosen = tab("Scatter Chart 2", "scatter", {"field": "CreditScore"}, {"field": "MonthlyCost", "aggregate": "none"})
    assert with_recorded_aggregations([chosen], [SCATTER_MEAN]) == [chosen]


def test_another_column_or_another_tab_gets_nothing():
    other_column = tab("Scatter Chart 2", "scatter", {"field": "CreditScore"}, {"field": "NumberOfTerms"})
    other_kind = tab("Scatter Chart 2", "line", {"field": "CreditScore"}, {"field": "MonthlyCost"})
    renamed = {**SCATTER_BARE, "tabName": "Scatter Chart 3"}
    for tabs in ([other_column], [other_kind], [renamed]):
        assert with_recorded_aggregations(tabs, [SCATTER_MEAN]) == tabs


def test_tabs_without_earlier_ones_or_of_an_unknown_shape_are_left_alone():
    odd = {"tabName": "x", "chartType": "bar", "config": {}}
    assert with_recorded_aggregations([SCATTER_BARE, odd], None) == [SCATTER_BARE, odd]
    assert with_recorded_aggregations([SCATTER_BARE, odd], [SCATTER_MEAN, odd])[1] == odd
    assert SCATTER_BARE["config"]["general"]["yColumn"] == {"field": "MonthlyCost"}  # nothing is changed in place


def test_the_defaults_marimo_writes_into_a_tab_it_shows_again_are_not_a_change():
    shown = tab(
        "Bar Chart", "bar", {"field": "CreditScore", "aggregate": "bin", "sort": "ascending"},
        {"field": "__count__", "sort": "ascending", "aggregate": "none"},
    )
    descending = tab("Bar Chart", "bar", {"field": "CreditScore", "aggregate": "bin", "sort": "descending"}, {"field": "__count__"})
    assert as_drawn([shown]) == as_drawn([BAR]) != as_drawn([descending])
    assert as_drawn(None) == [] and as_drawn([{"tabName": "x", "config": {}}]) == [{"tabName": "x", "config": {}}]


# --- which table a recorded tab belongs to --------------------------------------------------------------------------------------


def test_tabs_recorded_by_table_are_that_tables():
    charts = [
        ("local_attributes", {"cellId": "c1", "tabs": of("local_attributes", BAR)}),
        ("case_log", {"cellId": "c2", "tabs": of("case_log", SCATTER_MEAN)}),
        ("local_attributes", {"cellId": "c1", "tabs": of("local_attributes", BAR, SCATTER_BARE)}),
        ("event_log", None),  # a chart recorded without marimo's tabs
    ]
    assert recorded_chart_tabs(charts) == {"local_attributes": [BAR, SCATTER_BARE], "case_log": [SCATTER_MEAN]}


def test_the_cell_id_of_a_table_may_change_and_be_taken_by_another_table():
    charts = [
        ("local_attributes", {"cellId": "c1", "tabs": of("local_attributes", BAR)}),
        ("case_log", {"cellId": "c1", "tabs": of("case_log", SCATTER_MEAN)}),  # the notebook gained a cell in between
    ]
    assert recorded_chart_tabs(charts) == {"local_attributes": [BAR], "case_log": [SCATTER_MEAN]}


def test_a_tab_that_tables_shared_belongs_to_the_table_it_was_last_changed_on():
    """Before every table had its own cell, the tables of one cell showed the same tabs and each recorded them."""
    charts = [
        ("local_attributes", {"cellId": "old", "tabs": [BAR]}),
        ("local_attributes", {"cellId": "old", "tabs": [BAR, SCATTER_MEAN]}),
        ("local_attributes", {"cellId": "old", "tabs": [BAR, SCATTER_BARE]}),  # the bar chart looked at again: Mean was lost
        ("global_attributes", {"cellId": "old", "tabs": [BAR, SCATTER_BARE]}),  # looked at on another table: nothing changed
        ("loaded_event_log", {"cellId": "other", "tabs": [BAR]}),
    ]
    assert recorded_chart_tabs(charts) == {"local_attributes": [BAR, SCATTER_MEAN], "loaded_event_log": [BAR]}


def test_a_shared_tab_changed_on_another_table_moves_there_and_a_closed_one_is_gone():
    charts = [
        ("local_attributes", {"cellId": "old", "tabs": [BAR, SCATTER_MEAN]}),
        ("global_attributes", {"cellId": "old", "tabs": [NO_X, SCATTER_MEAN]}),
        ("global_attributes", {"cellId": "old", "tabs": [NO_X]}),
    ]
    assert recorded_chart_tabs(charts) == {"global_attributes": [NO_X]}


# --- where the tables are drawn -------------------------------------------------------------------------------------------------


def test_the_layout_names_where_the_tables_are_drawn():
    assert chart_layout({}) == "" and chart_layout([]) == ""
    assert chart_layout({"a": "c1", "b": "c2"}) == chart_layout({"b": "c2", "a": "c1"}) != chart_layout({"a": "c2", "b": "c1"})
    assert chart_layout(["c1", "c2"]) != chart_layout(["c1", "c2", "c3"])


def test_outside_a_running_notebook_no_cell_is_known():
    assert chart_tables.table_cells() == {} and chart_tables.notebook_cells() == []


def test_a_table_is_found_in_the_cell_that_names_it(monkeypatch):
    cells = {
        "Hbol": SimpleNamespace(code='show_table(du.table(log), artifact_id=state, artifact_name="case_log")'),
        "MJUe": SimpleNamespace(code="x = 1"),
        "vblA": SimpleNamespace(code="show_table(\n    t, artifact_id=s,\n    artifact_name = 'raw_events',\n)"),
    }
    import marimo._runtime.context as context

    monkeypatch.setattr(context, "get_context", lambda: SimpleNamespace(graph=SimpleNamespace(cells=cells)))
    assert chart_tables.table_cells() == {"case_log": "Hbol", "raw_events": "vblA"}
    assert chart_tables.notebook_cells() == ["Hbol", "MJUe", "vblA"]


# --- recording, with the real tracker ---------------------------------------------------------------------------------------------


@pytest.fixture
def opened(tmp_path):
    pytest.importorskip("tracker")
    from provenance_widget.pmprov_adapter import PmprovAdapter
    from tracker import init_marimo

    def open_it():
        rt = init_marimo(
            history_name="charts", branch_name="main", db_path=str(tmp_path / "provenance.db"),
            artifact_dir=str(tmp_path / "artifacts"), fresh=False,
        )
        return PmprovAdapter(rt)

    return open_it


def chart_steps(adapter):
    return [n for n in adapter.get_tree().nodes.values() if n.operation.name == "visualize_chart"]


def builder_of(step):
    return json.loads(step.params["builder"])


def test_a_recorded_tab_names_its_table_and_keeps_the_other_tabs_aggregations(opened):
    adapter = opened()
    adapter.record_chart("a", "local_attributes", SCATTER_SETTINGS, PNG, builder={"cellId": "c1", "tabs": [BAR, SCATTER_MEAN]})
    wider = tab("Bar Chart", "bar", {"field": "CreditScore", "aggregate": "bin"}, {"field": "MonthlyCost", "aggregate": "sum"})
    adapter.record_chart("a", "local_attributes", {**BAR_SETTINGS, "y": "MonthlyCost"}, PNG, builder={"cellId": "c1", "tabs": [wider, SCATTER_BARE]})
    assert builder_of(chart_steps(adapter)[-1]) == {"cellId": "c1", "tabs": of("local_attributes", wider, SCATTER_MEAN)}
    assert adapter.charts_to_restore({"local_attributes": "now"}) == {"now": [wider, SCATTER_MEAN]}
    assert adapter.charts_to_restore() == {"c1": [wider, SCATTER_MEAN]}  # without the cells: under the id it was recorded with


def test_a_chart_looked_at_again_is_not_a_step_and_can_still_be_anchored(opened):
    adapter = opened()
    bar = adapter.record_chart("a", "local_attributes", BAR_SETTINGS, PNG, builder={"cellId": "c1", "tabs": [BAR]})
    scatter = adapter.record_chart("a", "local_attributes", SCATTER_SETTINGS, PNG, builder={"cellId": "c1", "tabs": [BAR, SCATTER_MEAN]})
    assert bar["artifactId"] and scatter["artifactId"] and len(chart_steps(adapter)) == 2
    # the other tab, and marimo saved neither the "Mean" it showed nor, until now, its defaults
    shown = tab("Bar Chart", "bar", {"field": "CreditScore", "aggregate": "bin", "sort": "ascending"}, {"field": "__count__", "aggregate": "none"})
    assert adapter.record_chart("a", "local_attributes", BAR_SETTINGS, PNG, builder={"cellId": "c1", "tabs": [shown, SCATTER_BARE]}) == bar
    assert adapter.record_chart("a", "local_attributes", SCATTER_SETTINGS, PNG, builder={"cellId": "c1", "tabs": [BAR, SCATTER_BARE]}) == scatter
    assert len(chart_steps(adapter)) == 2


def test_after_a_restart_a_chart_is_recognised_under_the_cell_its_table_has_now(opened):
    first = opened().record_chart("a", "local_attributes", SCATTER_SETTINGS, PNG, builder={"cellId": "then", "tabs": [BAR, SCATTER_MEAN]})
    adapter = opened()  # the notebook is started again, with a cell more: the table is drawn by another cell
    assert adapter.charts_to_restore({"local_attributes": "now", "case_log": "other"}) == {"now": [BAR, SCATTER_MEAN]}
    assert adapter.record_chart("a", "local_attributes", SCATTER_SETTINGS, PNG, builder={"cellId": "now", "tabs": [BAR, SCATTER_BARE]}) == first
    assert len(chart_steps(adapter)) == 1
    summed = tab("Scatter Chart 2", "scatter", {"field": "CreditScore"}, {"field": "MonthlyCost", "aggregate": "sum"})
    adapter.record_chart("a", "local_attributes", {**SCATTER_SETTINGS, "y_aggregation": "Sum"}, PNG, builder={"cellId": "now", "tabs": [BAR, summed]})
    assert len(chart_steps(adapter)) == 2 and adapter.charts_to_restore({"local_attributes": "now"}) == {"now": [BAR, summed]}


def test_the_same_chart_on_another_table_is_recorded_and_the_tables_keep_their_own_tabs(opened):
    adapter = opened()
    adapter.record_chart("a", "local_attributes", BAR_SETTINGS, PNG, builder={"cellId": "c1", "tabs": [BAR]})
    adapter.record_chart("b", "case_log", BAR_SETTINGS, PNG, builder={"cellId": "c2", "tabs": [BAR, SCATTER_MEAN]})
    assert len(chart_steps(adapter)) == 2
    assert adapter.charts_to_restore({"local_attributes": "x", "case_log": "y"}) == {"x": [BAR], "y": [BAR, SCATTER_MEAN]}


def test_a_chart_recorded_without_a_picture_is_recorded_again_when_one_comes(opened):
    adapter = opened()
    first = adapter.record_chart("a", "local_attributes", BAR_SETTINGS, None, builder={"cellId": "c1", "tabs": [BAR]})
    assert first["artifactId"] is None
    assert adapter.record_chart("a", "local_attributes", BAR_SETTINGS, None, builder={"cellId": "c1", "tabs": [BAR]}) == first
    pictured = adapter.record_chart("a", "local_attributes", BAR_SETTINGS, PNG, builder={"cellId": "c1", "tabs": [BAR]})
    assert pictured["artifactId"] and len(chart_steps(adapter)) == 2
    assert adapter.record_chart("a", "local_attributes", BAR_SETTINGS, PNG, builder={"cellId": "c1", "tabs": [BAR]}) == pictured


def test_tabs_that_tables_shared_before_are_restored_on_the_table_they_belong_to(opened):
    """A history recorded before 0.16, by a notebook whose tables shared a cell: read as it was stored."""
    adapter = opened()
    for table, settings, tabs in [
        ("local_attributes", SCATTER_SETTINGS, [BAR, SCATTER_MEAN]),
        ("local_attributes", BAR_SETTINGS, [BAR, SCATTER_BARE]),
        ("global_attributes", BAR_SETTINGS, [BAR, SCATTER_BARE]),
    ]:
        adapter._rt.trace_step(
            func=lambda table, settings, builder=None: None, func_name="visualize_chart", raw_line="visualize_chart(...)",
            args=[table, settings, json.dumps({"cellId": "old", "tabs": tabs}, sort_keys=True)], kwargs={}, targets=[],
        )
    resumed = opened()
    cells = {"local_attributes": "new-local", "global_attributes": "new-global"}
    assert resumed.charts_to_restore(cells) == {"new-local": [BAR, SCATTER_MEAN]}
