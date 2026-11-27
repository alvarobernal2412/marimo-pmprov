import pytest

go = pytest.importorskip("plotly.graph_objects")

from provenance_widget.report_targets import FADED_ALPHA, MARK_COLOR, _alpha, describe, mark_sankey  # noqa: E402

NAME = "A → K → L → Z"


def _figure(meta=True):
    # nodes: A K L M Z ; links: A>K, A>M, K>L, M>Z, L>Z
    extra = {}
    if meta:
        extra["meta"] = {
            "lcm": {
                "traces": [
                    {"name": NAME, "sequence": ["A", "K", "L", "Z"], "cases": 2, "links": [0, 2, 4], "nodes": [0, 1, 2, 4]},
                ],
                "truncated": False,
            }
        }
    return go.Figure(
        go.Sankey(
            node={"label": ["A", "K", "L", "M", "Z"], "color": ["#112233"] * 5},
            link={
                "source": [0, 0, 1, 3, 2],
                "target": [1, 3, 2, 4, 4],
                "value": [2, 1, 2, 1, 2],
                "label": ["a", "b", "c", "d", "e"],
                "color": ["rgba(10, 20, 30, 0.5)"] * 5,
            },
            **extra,
        )
    )


def test_mark_sankey_marks_the_links_of_a_trace():
    figure = _figure()
    marked, done = mark_sankey(figure, "trace", NAME)
    assert done is True
    trace = marked.data[0]
    assert trace.link.color[0] == "rgba(10, 20, 30, 1)"
    assert trace.link.color[1] == f"rgba(10, 20, 30, {FADED_ALPHA})"
    # Plotly draws a Sankey's link outlines with one colour and width for all links (a list is drawn as a thin black line), so no
    # link gets an outline: the marked ones stand out by their full colour
    assert trace.link.line.color == "rgba(0, 0, 0, 0)" and trace.link.line.width == 0
    assert trace.node.color[1] == "rgba(17, 34, 51, 1)"
    assert trace.node.color[3] == f"rgba(17, 34, 51, {FADED_ALPHA})"
    assert figure.data[0].link.color[0] == "rgba(10, 20, 30, 0.5)"
    assert NAME in marked.layout.annotations[0].text and "2 cases" in marked.layout.annotations[0].text


def test_unknown_trace_is_not_marked():
    figure = _figure()
    assert mark_sankey(figure, "trace", "A → Z") == (figure, False)


def test_figure_without_traces_is_not_marked():
    figure = _figure(meta=False)
    assert mark_sankey(figure, "trace", NAME) == (figure, False)


def test_describe_words_a_trace():
    assert describe("trace", NAME, _figure()) == f"trace {NAME}, 2 cases"
    assert describe("trace", NAME) == f"trace {NAME}"
    assert describe("trace", NAME, _figure(meta=False)) == f"trace {NAME}"


def test_node_and_link_marks_are_unchanged():
    figure = _figure()
    marked, done = mark_sankey(figure, "node", "K")
    assert done and marked.data[0].link.color[0] == f"rgba(10, 20, 30, {FADED_ALPHA})"
    marked, done = mark_sankey(figure, "link", "A -> K (a)")
    assert done and marked.data[0].link.color[0] == MARK_COLOR
    assert describe("node", "K") == "node K"


def test_named_colours_keep_their_colour():
    assert _alpha("dimgrey", 1) == "rgba(105, 105, 105, 1)"
    assert _alpha("DimGray", 0.2) == "rgba(105, 105, 105, 0.2)"
    assert _alpha("white", 0.2) == "rgba(255, 255, 255, 0.2)"
    assert _alpha("lightgrey", 1) == _alpha("lightgray", 1) == "rgba(211, 211, 211, 1)"
    assert _alpha("black", 1) == "rgba(0, 0, 0, 1)"
    assert _alpha("#abc", 1) == "rgba(170, 187, 204, 1)"
    assert _alpha("no such colour", 1) == "rgba(148, 163, 184, 1)"


def test_marked_trace_nodes_keep_their_named_colours():
    figure = _figure()
    figure.data[0].node.color = ["white", "lightgrey", "dimgrey", "black", "black"]
    marked, done = mark_sankey(figure, "trace", NAME)
    assert done
    assert list(marked.data[0].node.color) == [
        "rgba(255, 255, 255, 1)", "rgba(211, 211, 211, 1)", "rgba(105, 105, 105, 1)", f"rgba(0, 0, 0, {FADED_ALPHA})", "rgba(0, 0, 0, 1)",
    ]


def test_a_long_trace_is_shortened_in_words():
    steps = [f"S{i}" for i in range(1, 12)]
    name = " → ".join(steps)
    assert describe("trace", name) == "trace S1 → S2 → S3 → … (11 steps) … → S10 → S11"
    assert describe("trace", " → ".join(steps[:6])) == "trace " + " → ".join(steps[:6])
