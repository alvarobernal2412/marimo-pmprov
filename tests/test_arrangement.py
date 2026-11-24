"""Where the analyst dragged the nodes of a Sankey figure can be recorded as a step."""
import json
from types import SimpleNamespace

import pytest

go = pytest.importorskip("plotly.graph_objects")

from provenance_widget.arrangement import NodeArrangement, arranged, reported, watched  # noqa: E402


def a_figure():
    return go.Figure([
        go.Sankey(node=dict(label=["a", "b", "c"]), link=dict(source=[0, 1], target=[1, 2], value=[1, 1])),
        go.Scatter(x=[0], y=[0]),
    ])


MOVED = json.dumps([{"x": [0.1, 0.5, 0.9], "y": [0.2, 0.7, 0.4]}])


def test_the_nodes_are_drawn_where_they_were_dragged_and_the_figure_itself_is_not_changed():
    figure = a_figure()
    result = arranged(figure, MOVED)
    assert list(result.data[0].node.x) == [0.1, 0.5, 0.9] and list(result.data[0].node.y) == [0.2, 0.7, 0.4]
    assert figure.data[0].node.x is None and result is not figure
    assert len(result.data) == 2 and list(result.data[0].node.label) == ["a", "b", "c"]


@pytest.mark.parametrize("positions", [
    "not json", None, json.dumps({"x": [1]}), json.dumps([{"x": [0.1], "y": [0.2]}]), json.dumps([{"x": None, "y": None}]), json.dumps([None]),
])
def test_positions_that_do_not_fit_the_figure_leave_it_as_it_was_drawn(positions):
    result = arranged(a_figure(), positions)
    assert result.data[0].node.x is None and result.data[0].node.y is None


def test_positions_count_only_for_the_figure_they_were_dragged_in():
    value = {"moved": {"figure": "state-1", "positions": MOVED, "n": "1"}}
    assert reported(value, "state-1") == MOVED
    assert reported(value, "state-2") is None  # the figure was drawn again since
    assert reported({"moved": {}}, "state-1") is None and reported(None, "state-1") is None


def test_the_figure_is_marked_so_that_the_page_can_tell_which_one_was_dragged():
    mo = SimpleNamespace(Html=lambda text: SimpleNamespace(text=text))
    framed = watched(mo, SimpleNamespace(text="<p>the figure</p>"), 'state "1"')
    assert framed.text == '<div data-pw-arrangement="state &quot;1&quot;"><p>the figure</p></div>'
    # a figure whose picture is not made for the page says so: the panel does not wait for one
    plain = watched(mo, SimpleNamespace(text="<p>x</p>"), "s", pictured=False)
    assert plain.text == '<div data-pw-arrangement="s" data-pw-unpictured="1"><p>x</p></div>'


def test_the_widget_reports_through_one_value_and_watches_the_marked_figures():
    widget = NodeArrangement()
    assert widget.moved == {}
    assert "pwArrangement" in widget._esm and 'model.set("moved"' in widget._esm
    # a figure that was dragged and not drawn again yet is marked, so the panel waits with adding an annotation
    assert "pwPending" in widget._esm and "pointerup" in widget._esm
