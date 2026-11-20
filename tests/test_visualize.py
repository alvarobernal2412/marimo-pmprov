import pytest

from provenance_widget.visualize import enable_chart_builder

table_plugin = pytest.importorskip("marimo._plugins.ui._impl.table", reason="marimo's table plugin not importable")


def test_enable_chart_builder_makes_the_table_plugin_see_edit_mode(monkeypatch):
    monkeypatch.setattr(table_plugin, "get_mode", lambda: "run")  # restored after the test
    assert enable_chart_builder() is True
    assert table_plugin.get_mode() == "edit"


def test_enable_chart_builder_never_raises_when_marimo_changes(monkeypatch):
    monkeypatch.delattr(table_plugin, "get_mode")  # a marimo without that name: restored after the test
    assert enable_chart_builder() is False
    assert not hasattr(table_plugin, "get_mode")  # and nothing was added in its place
