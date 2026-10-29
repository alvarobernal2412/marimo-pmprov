import marimo as mo

from provenance_widget.display import show_chart, show_table


def test_show_table_wraps_table_with_artifact_data_attributes():
    table = mo.ui.table(data=[{"a": 1}, {"a": 2}])
    wrapped = show_table(table, artifact_id="art-event-log", artifact_name="event_log.csv")
    html = wrapped.text
    assert 'data-pw-artifact-id="art-event-log"' in html
    assert 'data-pw-artifact-name="event_log.csv"' in html
    assert 'data-pw-granularity="dataset"' in html


def test_show_chart_wraps_with_chart_selection_granularity():
    chart_html = mo.Html("<div>fake-chart</div>")
    wrapped = show_chart(chart_html, artifact_id="art-process-map", artifact_name="Chart_ProcessMap")
    html = wrapped.text
    assert 'data-pw-artifact-id="art-process-map"' in html
    assert 'data-pw-granularity="chart_selection"' in html


def test_show_table_carries_a_snapshot_of_the_table_for_the_report():
    import html as htmllib
    import json

    import pandas as pd

    frame = pd.DataFrame({"incidence": [3, 2], "keys": ["x", None]}, index=pd.Index(["A_Create", "O_Create"], name="activity"))
    wrapped = show_table(mo.ui.table(frame), artifact_id="s1", artifact_name="schema_usages")

    raw = wrapped.text.split('data-pw-snapshot="', 1)[1].split('"', 1)[0]
    snapshot = json.loads(htmllib.unescape(raw))
    assert snapshot["columns"] == ["activity", "incidence", "keys"]  # the named index is shown by marimo as a column
    assert snapshot["rows"][0] == ["A_Create", "3", "x"]
    assert snapshot["rows"][1][2] == ""  # a missing value
    assert snapshot["total_rows"] == 2


def test_show_table_without_readable_data_has_no_snapshot():
    class _Unreadable:
        text = "<div>table</div>"
        data = object()

    wrapped = show_table(_Unreadable(), artifact_id="s1", artifact_name="t")
    assert "data-pw-snapshot" not in wrapped.text


def test_snapshot_of_picks_the_kind_from_the_value():
    import pandas as pd
    from matplotlib.figure import Figure

    from provenance_widget.element_snapshot import snapshot_of

    assert snapshot_of(pd.DataFrame({"a": [1]}))["kind"] == "table"
    assert snapshot_of("12000") == {"kind": "text", "text": "12000"}
    assert snapshot_of({"median": 3})["kind"] == "text"
    figure = Figure()
    figure.subplots().plot([1, 2])
    assert snapshot_of(figure)["kind"] == "image"
    assert snapshot_of(object()) is None and snapshot_of(None) is None


def test_show_makes_any_element_pickable_with_a_snapshot_of_its_value():
    import html as htmllib
    import json

    from provenance_widget.display import show

    wrapped = show(mo.md("**median**"), artifact_id="s1", artifact_name="median", value="median = 12000")
    assert 'data-pw-artifact-name="median"' in wrapped.text
    raw = wrapped.text.split('data-pw-snapshot="', 1)[1].split('"', 1)[0]
    assert json.loads(htmllib.unescape(raw)) == {"kind": "text", "text": "median = 12000"}

    assert "data-pw-snapshot" not in show(mo.Html("<div>x</div>"), artifact_id="s1", artifact_name="x").text


def test_show_chart_with_a_figure_carries_an_image_snapshot():
    from matplotlib.figure import Figure

    figure = Figure()
    figure.subplots().plot([1, 2])
    wrapped = show_chart(mo.Html("<div>c</div>"), artifact_id="s1", artifact_name="c", figure=figure)
    assert "&quot;kind&quot;: &quot;image&quot;" in wrapped.text
