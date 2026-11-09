import base64
import io

import pytest

pytest.importorskip("reportlab")
pypdf = pytest.importorskip("pypdf")
import pandas as pd  # noqa: E402

from provenance_widget.export_pdf import build_pdf, collect_rows  # noqa: E402
from provenance_widget.interfaces import EmptyProvenanceSource  # noqa: E402
from provenance_widget.widget import ProvenancePanel  # noqa: E402


def text_of(pdf: bytes) -> str:
    """The text of every page, whitespace collapsed (the embedded font hides it from a byte search)."""
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    return " ".join(" ".join(page.extract_text().split()) for page in reader.pages)


def _node(state_id, parent, name, params=None, annotations=()):
    return {
        "stateId": state_id,
        "parentStateId": parent,
        "operation": {"name": name},
        "params": params or {},
        "annotations": list(annotations),
    }


def _annotation(annotation_id, title, timestamp, tags=(), artifacts=(), note=None):
    return {
        "annotationId": annotation_id,
        "title": title,
        "note": note or title,
        "tags": [{"name": t, "color": "#64748B"} for t in tags],
        "artifacts": list(artifacts),
        "author": {"display_name": "A"},
        "timestamp": timestamp,
    }


TREE = {
    "nodes": {
        "s1": _node("s1", None, "load"),
        "s2": _node("s2", "s1", "filter", {"year": 2020}),
        "s3": _node("s3", "s2", "group"),
    }
}


def test_rows_are_ordered_by_time_with_step_numbers_and_settings():
    late = _annotation("b", "late", "2026-01-02T10:00:00Z")
    early = _annotation("a", "early", "2026-01-01T10:00:00Z")
    rows = collect_rows(
        TREE, [{"stateId": "s3", "annotation": late}, {"stateId": "s2", "annotation": early}], [], {}, {}
    )
    assert [r.annotation["title"] for r in rows] == ["early", "late"]
    assert [(r.step, r.operation) for r in rows] == [(2, "filter"), (3, "group")]
    assert rows[1].params == {"year": 2020}  # settings chosen earlier stay in force
    assert [r.own_params for r in rows] == [{"year": 2020}, {}]  # the report prints only the step's own


def test_rows_apply_removals_edits_and_hide_the_stored_copy_of_a_commit():
    kept = _annotation("kept", "kept", "2026-01-01T10:00:00Z")
    edited = _annotation("edited", "old title", "2026-01-02T10:00:00Z")
    gone = _annotation("gone", "gone", "2026-01-03T10:00:00Z")
    stored_copy = _annotation("src-1", "kept", "2026-01-01T10:00:00Z")
    tree = {"nodes": {**TREE["nodes"], "s2": _node("s2", "s1", "filter", annotations=[stored_copy])}}
    commits = [{"stateId": s, "annotation": a} for s, a in (("s2", kept), ("s3", edited), ("s3", gone))]
    rows = collect_rows(tree, commits, ["gone"], {"edited": {"title": "new title"}}, {"kept": "src-1"})
    assert [r.annotation["title"] for r in rows] == ["kept", "new title"]


def test_pdf_has_annotation_tags_target_step_and_table_caption():
    frame = pd.DataFrame({"activity": list("abc"), "n": [1, 2, 3]})
    ref = {"artifactId": "s2", "artifactName": "by_activity", "granularity": "dataset", "detail": None}
    rows = collect_rows(
        TREE,
        [{"stateId": "s2", "annotation": _annotation("a", "Peak", "2026-01-01T10:00:00Z", ["urgent"], [ref], "Unusual peak")}],
        [], {}, {},
    )
    pdf = build_pdf(rows, lambda row, ref: frame, compress=False)
    assert pdf.startswith(b"%PDF")
    text = text_of(pdf)
    for expected in ("Unusual peak", "#urgent", "Step 2: filter", "Target by_activity", "Table 1. by_activity at step 2", "first 3 of 3 rows"):
        assert expected in text, expected


def test_unrecoverable_target_is_reported_not_fatal():
    ref = {"artifactId": "s2", "artifactName": "gone_df", "granularity": "dataset", "detail": None}
    rows = collect_rows(TREE, [{"stateId": "s2", "annotation": _annotation("a", "x", "2026-01-01T10:00:00Z", artifacts=[ref])}], [], {}, {})
    assert "could not be recovered" in text_of(build_pdf(rows, lambda row, ref: None, compress=False))


def test_whole_analysis_annotation_and_empty_report():
    rows = collect_rows(TREE, [{"stateId": "s3", "annotation": _annotation("a", "overall", "2026-01-01T10:00:00Z")}], [], {}, {})
    assert "the whole analysis at this step" in text_of(build_pdf(rows, None, compress=False))
    assert "No annotations have been recorded yet" in text_of(build_pdf([], None, compress=False))


def test_matplotlib_figure_is_embedded_as_an_image():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.bar(["a", "b"], [1, 2])
    ref = {"artifactId": "s2", "artifactName": "chart", "granularity": "chart_selection", "detail": None}
    rows = collect_rows(TREE, [{"stateId": "s2", "annotation": _annotation("a", "x", "2026-01-01T10:00:00Z", artifacts=[ref])}], [], {}, {})
    pdf = build_pdf(rows, lambda row, ref: fig, compress=False)
    assert "Figure 1. chart at step 2" in text_of(pdf) and b"/Subtype /Image" in pdf
    plt.close(fig)


class _SnapshotSource(EmptyProvenanceSource):
    def __init__(self, values):
        self.values = values

    def snapshot_bindings(self, state_id):
        return set(self.values)

    def snapshot(self, state_id, names=None):
        return {n: v for n, v in self.values.items() if names is None or n in names}


def test_panel_exports_and_answers_the_sidebar_request(tmp_path):
    panel = ProvenancePanel(_SnapshotSource({"event_log": pd.DataFrame({"a": [1]})}), mode="analyst")
    panel.widget.tree = {"nodes": {"s1": _node("s1", None, "load")}}
    ref = {"artifactId": "s1", "artifactName": "event_log.csv", "granularity": "dataset", "detail": None}
    panel.widget.commits = [{"stateId": "s1", "annotation": _annotation("a", "First look", "2026-01-01T10:00:00Z", artifacts=[ref])}]

    out = tmp_path / "report.pdf"
    assert panel.export_pdf(out).startswith(b"%PDF") and out.read_bytes().startswith(b"%PDF")

    panel.widget.export_request = {"requestId": "r1"}
    result = panel.widget.export_result
    assert result["requestId"] == "r1" and result["filename"] == "annotated_analysis_report.pdf"
    assert base64.b64decode(result["data"]).startswith(b"%PDF")


def test_reviewer_cannot_export_through_the_sidebar():
    panel = ProvenancePanel(mode="reviewer")
    panel.widget.export_request = {"requestId": "r1"}
    assert panel.widget.export_result == {}


def test_demo_source_is_flagged_once_instead_of_failing_per_annotation(monkeypatch):
    ref = {"artifactId": "s2", "artifactName": "cost_model.pkl", "granularity": "dataset", "detail": None}
    rows = collect_rows(TREE, [{"stateId": "s2", "annotation": _annotation("a", "x", "2026-01-01T10:00:00Z", artifacts=[ref])}], [], {}, {})
    pdf = build_pdf(rows, lambda row, ref: None, compress=False, stores_outputs=False)
    text = text_of(pdf)
    assert "Demo source" in text and "could not be recovered" not in text

    panel = ProvenancePanel(mode="analyst")  # EmptyProvenanceSource: no snapshots
    panel.widget.tree = TREE
    panel.widget.commits = [{"stateId": "s2", "annotation": _annotation("a", "x", "2026-01-01T10:00:00Z", artifacts=[ref])}]
    seen = {}
    import provenance_widget.export_pdf as export_module

    real = export_module.build_pdf
    monkeypatch.setattr(export_module, "build_pdf", lambda *a, **kw: seen.update(kw) or real(*a, **kw))
    panel.export_pdf()
    assert seen["stores_outputs"] is False


def test_author_is_listed_per_entry_only_with_several_authors():
    def rows_by(*names):
        commits = [
            {"stateId": "s2", "annotation": {**_annotation(f"a{i}", f"n{i}", f"2026-01-0{i + 1}T10:00:00Z"), "author": {"display_name": name}}}
            for i, name in enumerate(names)
        ]
        return collect_rows(TREE, commits, [], {}, {})

    one = text_of(build_pdf(rows_by("Alice", "Alice"), None, compress=False, include_authors=True))
    assert one.count("Alice") == 1  # byline only
    two = text_of(build_pdf(rows_by("Alice", "Bob"), None, compress=False, include_authors=True))
    assert two.count("Alice") == 2 and two.count("Bob") == 2


def test_a_picked_table_is_drawn_from_its_snapshot_not_from_the_state_it_was_recorded_at():
    """A table built inside a display cell is bound to no step; what the analyst picked is what the report shows."""
    stored_for_the_step = pd.DataFrame({"unrelated": ["event log row"]})
    ref = {
        "artifactId": "s2", "artifactName": "schema_usages", "granularity": "dataset", "detail": "row 1",
        "snapshot": {"columns": ["activity", "incidence"], "rows": [["A_Create", "1538"], ["O_Create", "2082"]],
                     "total_rows": 24, "total_columns": 3},
    }
    rows = collect_rows(
        TREE, [{"stateId": "s2", "annotation": _annotation("a", "Schemas", "2026-01-01T10:00:00Z", artifacts=[ref])}],
        [], {}, {},
    )
    text = text_of(build_pdf(rows, lambda row, ref: stored_for_the_step, compress=False))
    assert "A_Create" in text and "2082" in text
    assert "event log row" not in text
    assert "first 2 of 24 rows" in text


def _picked(snapshot):
    ref = {"artifactId": "s2", "artifactName": "picked", "granularity": "dataset", "detail": None, "snapshot": snapshot}
    return collect_rows(
        TREE, [{"stateId": "s2", "annotation": _annotation("a", "note", "2026-01-01T10:00:00Z", artifacts=[ref])}],
        [], {}, {},
    )


def test_a_picked_text_is_drawn_as_text():
    rows = _picked({"kind": "text", "text": "median requested amount: 12000"})
    text = text_of(build_pdf(rows, lambda row, ref: pd.DataFrame({"unrelated": [1]}), compress=False))
    assert "median requested amount: 12000" in text and "Text 1." in text


def test_a_picked_image_is_drawn_as_a_figure():
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    from provenance_widget.element_snapshot import snapshot_of

    figure, axis = plt.subplots()
    axis.plot([1, 2, 3])
    rows = _picked(snapshot_of(figure))
    plt.close(figure)
    text = text_of(build_pdf(rows, None, compress=False))
    assert "Figure 1." in text


def test_authors_are_left_out_unless_asked_for():
    rows = collect_rows(TREE, [{"stateId": "s2", "annotation": _annotation("a", "x", "2026-01-01T10:00:00Z")}], [], {}, {})
    assert "A ·" not in text_of(build_pdf(rows, None, compress=False)).split("Annotations", 1)[0]


def test_settings_keep_short_scalars_and_drop_data_arguments():
    from provenance_widget.export_pdf import _operation_label, _readable_settings

    noisy = {
        "unit": "D", "case_count": 1500, "full_width": True, "frames": {"_cell_TXez_filtered_log": "<DataFrame 49x22>"},
        "data": "[{'rel_log_time': '49'...", "columns": ["a", "b"], "__receiver__": "x", "window_start": "2016-01-01 09:51:15+00:00",
        "iterable": "...te files', 'W_Handle leads',", "on_apply": None,
    }
    assert _readable_settings(noisy) == [
        ("unit", "D"), ("case count", "1500"), ("full width", "True"), ("window start", "2016-01-01 09:51:15+00:00"),
    ]
    assert _operation_label("_cell_TXez_filtered_log") == "filtered log"
    assert _operation_label("filter") == "filter"
    assert _operation_label("set_summary[['a', 'b']].sort_values(['a'], ascending=False).reset_index") == "set summary"
    assert _operation_label("x" * 60) == "x" * 39 + "…"


def test_settings_are_printed_only_when_asked_for():
    rows = collect_rows(TREE, [{"stateId": "s2", "annotation": _annotation("a", "x", "2026-01-01T10:00:00Z")}], [], {}, {})
    assert "year = 2020" not in text_of(build_pdf(rows, None, compress=False))
    assert "year = 2020" in text_of(build_pdf(rows, None, compress=False, include_settings=True))


class _TupleStepSource(_SnapshotSource):
    """A step that returned ``figure, meta = ...``: the annotation's variable cannot be told from the step alone."""

    def __init__(self, values, bound):
        super().__init__(values)
        self.bound = bound

    def snapshot_bindings(self, state_id):
        return set(self.values)

    def variable_for_artifact(self, state_id, artifact_id):
        return None

    def variables_for_artifact(self, state_id, artifact_id):
        return list(self.bound)


def _panel_with(source):
    panel = ProvenancePanel(source, mode="reviewer")
    panel.widget.tree = {"nodes": {"s1": _node("s1", None, "draw_map")}}
    ref = {"artifactId": "s1", "artifactName": "process_map", "granularity": "chart_selection", "detail": None}
    panel.widget.commits = [{"stateId": "s1", "annotation": _annotation("a", "x", "2026-01-01T10:00:00Z", artifacts=[ref])}]
    return panel


def test_a_tuple_step_shows_the_one_variable_that_is_a_table_or_figure():
    frame = pd.DataFrame({"a": [1, 2]})
    panel = _panel_with(_TupleStepSource({"map_table": frame, "map_meta": {"nodes": 3}}, ["map_table", "map_meta"]))
    text = text_of(panel.export_pdf())
    assert "could not be recovered" not in text and "Table 1. process_map at step 1" in text


def test_a_tuple_step_with_two_things_to_show_is_not_guessed():
    panel = _panel_with(_TupleStepSource({"one": pd.DataFrame({"a": [1]}), "two": pd.DataFrame({"b": [2]})}, ["one", "two"]))
    assert "could not be recovered" in text_of(panel.export_pdf())


# --- what the report says about a pin, and how it marks it ---------------------------------------------------------------


def _sankey():
    import plotly.graph_objects as go

    return go.Figure(go.Sankey(
        node={"label": ["START", "{A_Create Application}", "{A_Create Application, A_Concept}"], "color": ["#aaaaaa", "#ff7f0e", "#9467bd"]},
        link={"source": [0, 1], "target": [1, 2], "value": [10, 8], "label": ["A_Create Application (10)", "A_Concept (8)"],
              "color": ["rgba(255, 127, 14, 0.6)", "rgba(148, 103, 189, 0.6)"]},
    ))


def test_a_pinned_link_is_worded_for_a_reader():
    from provenance_widget.report_targets import describe

    assert describe("link", "START -> {A_Create Application} (A_Create Application (10))") == "link into A_Create Application, 10 cases"
    assert describe("link", "A_Incomplete -> A_Pending (A_Pending (4937))") == "link into A_Pending, 4,937 cases (from A_Incomplete to A_Pending)"
    assert describe("link", "{A, B} -> {A, B, O_Sent (mail and online)} (O_Sent (mail and online) (17228))") == "link into O_Sent (mail and online), 17,228 cases"
    assert describe("node", "{EMPTY TRACE}") == "node {EMPTY TRACE}"
    assert describe("cell", "row 1, column a = 2") is None and describe("link", None) is None


def test_the_pinned_link_is_in_colour_and_the_rest_is_faded():
    from provenance_widget.report_targets import mark_sankey

    figure = _sankey()
    marked, done = mark_sankey(figure, "link", "{A_Create Application} -> {A_Create Application, A_Concept} (A_Concept (8))")
    assert done and marked is not figure
    link = marked.data[0].link
    assert link.color[1].startswith("rgba(245, 158, 11") and link.color[0].endswith("0.2)")
    assert marked.data[0].node.color[0].endswith("0.2)")
    assert "A_Concept, 8 cases" in marked.layout.annotations[0].text
    assert figure.data[0].link.color[1] == "rgba(148, 103, 189, 0.6)"  # the recorded figure is not changed


def test_a_pinned_node_keeps_its_colour():
    from provenance_widget.report_targets import mark_sankey

    marked, done = mark_sankey(_sankey(), "node", "{A_Create Application}")
    assert done and marked.data[0].node.color[1] == "rgba(255, 127, 14, 1)" and marked.data[0].node.color[2].endswith("0.2)")


def test_a_pin_that_is_not_found_leaves_the_figure_alone():
    from provenance_widget.report_targets import mark_sankey

    figure = _sankey()
    for granularity, detail in (("link", "X -> Y (Z (1))"), ("node", "nowhere"), ("cell", "row 1"), ("link", None)):
        assert mark_sankey(figure, granularity, detail) == (figure, False)
    assert mark_sankey("not a figure", "link", "a -> b (c (1))") == ("not a figure", False)


def test_a_dict_of_counts_is_drawn_as_a_table():
    ref = {"artifactId": "s2", "artifactName": "summary", "granularity": "dataset", "detail": None}
    rows = collect_rows(TREE, [{"stateId": "s2", "annotation": _annotation("a", "x", "2026-01-01T10:00:00Z", artifacts=[ref])}], [], {}, {})
    text = text_of(build_pdf(rows, lambda row, ref: {"cases": 31509, "events": 1202267}, compress=False))
    assert "Table 1. summary at step 2" in text and "31,509" in text and "{'cases'" not in text


def test_entries_are_grouped_under_a_heading_per_task():
    def entry(annotation_id, stamp, tags):
        return {"stateId": "s2", "annotation": _annotation(annotation_id, annotation_id, stamp, tags=tags)}

    commits = [entry("first", "2026-01-01T10:00:00Z", ["task9"]), entry("second", "2026-01-01T10:01:00Z", ["task8"]),
               entry("third", "2026-01-01T10:02:00Z", ["task9"])]
    text = text_of(build_pdf(collect_rows(TREE, commits, [], {}, {}), None, compress=False))
    assert text.index("Task 9") < text.index("first") < text.index("third") < text.index("Task 8") < text.index("second")
    plain = text_of(build_pdf(collect_rows(TREE, [entry("only", "2026-01-01T10:00:00Z", [])], [], {}, {}), None, compress=False))
    assert "Task " not in plain and "Annotations" in plain


def test_a_map_drawn_for_the_same_step_and_element_is_drawn_once():
    ref = {"artifactId": "s2", "artifactName": "process_map", "granularity": "chart_selection", "detail": None}
    commits = [{"stateId": "s2", "annotation": _annotation(f"a{i}", "x", f"2026-01-01T10:0{i}:00Z", artifacts=[ref])} for i in range(2)]
    text = text_of(build_pdf(collect_rows(TREE, commits, [], {}, {}), lambda row, ref: pd.DataFrame({"a": [1]}), compress=False))
    assert text.count("Table 1. process_map") == 1 and "Same as Table 1." in text and "Table 2." not in text


def test_the_header_names_one_time_when_all_were_written_in_the_same_minute():
    def entry(annotation_id, stamp):
        return {"stateId": "s2", "annotation": _annotation(annotation_id, annotation_id, stamp)}

    same = text_of(build_pdf(collect_rows(TREE, [entry("a", "2026-01-01T10:00:05Z"), entry("b", "2026-01-01T10:00:50Z")], [], {}, {}), None, compress=False))
    assert "written between" not in same and "written 01 Jan 2026" in same
    apart = text_of(build_pdf(collect_rows(TREE, [entry("a", "2026-01-01T10:00:00Z"), entry("b", "2026-01-01T11:00:00Z")], [], {}, {}), None, compress=False))
    assert "written between" in apart

