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
