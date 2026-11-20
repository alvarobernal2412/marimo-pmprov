"""Charts recorded from marimo's Visualize tab, shown again for a reviewer (needs pmprov, like test_pmprov_adapter)."""
import io

import pytest

pytest.importorskip("tracker", reason="pmprov not installed")

from PIL import Image
from tracker.runtime import RuntimeTracker
from tracker.storage import DuckDBSQLiteBackend as StorageBackend
import tracker  # noqa: F401 — patches annotate()/tag() onto RuntimeTracker

from provenance_widget.display import recorded_charts, show_recorded_charts
from provenance_widget.pmprov_adapter import PmprovAdapter


@pytest.fixture
def adapter(tmp_path):
    storage = StorageBackend(db_path=tmp_path / "prov.db", artifact_dir=tmp_path / "art")
    rt = RuntimeTracker(storage=storage, session_id="t", history_name="test")
    rt.trace_step(func=lambda: 1, func_name="make", raw_line="x = make()", args=[], kwargs={}, targets=["x"])
    return PmprovAdapter(rt)


def _png(color):
    buffer = io.BytesIO()
    Image.new("RGB", (30, 20), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _two_charts(adapter):
    first = adapter.record_chart("t", "case_log", {"chart_type": "Bar", "x": "c"}, png=_png((200, 0, 0)))
    second = adapter.record_chart("t", "case_log", {"chart_type": "Line", "x": "c", "y": "a"}, png=_png((0, 0, 200)))
    return first, second


def test_recorded_charts_lists_the_charts_up_to_the_cursor_oldest_first(adapter):
    first, second = _two_charts(adapter)

    upto_second = recorded_charts(adapter, second["stateId"])
    upto_first = recorded_charts(adapter, first["stateId"])

    assert [c["artifact_id"] for c in upto_second] == [first["stateId"], second["stateId"]]
    assert [c["artifact_id"] for c in upto_first] == [first["stateId"]]
    assert upto_second[1]["settings"] == {"chart_type": "Line", "x": "c", "y": "a"}
    assert upto_second[1]["table"] == "case_log"
    assert upto_second[1]["png"][:4] == b"\x89PNG"


def test_recorded_charts_is_empty_before_any_chart_and_for_an_unknown_state(adapter):
    assert recorded_charts(adapter, adapter.latest_state_id()) == []
    assert recorded_charts(adapter, "no-such-state") == []
    assert recorded_charts(adapter, None) == []


def test_show_recorded_charts_tags_each_chart_so_it_can_be_anchored_and_jumped_to(adapter):
    first, second = _two_charts(adapter)

    html = show_recorded_charts(adapter, second["stateId"]).text

    assert html.count("data-pw-artifact-id=") == 2
    assert f'data-pw-artifact-id="{second["stateId"]}"' in html
    assert 'data-pw-granularity="chart_selection"' in html
    assert "Line chart of case_log" in html and "data:image/png;base64," in html


def test_show_recorded_charts_says_nothing_when_there_are_no_charts(adapter):
    assert "data-pw-artifact-id" not in show_recorded_charts(adapter, adapter.latest_state_id()).text
