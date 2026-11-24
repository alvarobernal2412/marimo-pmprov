from provenance_widget.mock_source import MockProvenanceSource
from provenance_widget.interfaces import EmptyProvenanceSource
from provenance_widget.widget import ProvenancePanel, ProvenanceWidget


class _RecordingSource(EmptyProvenanceSource):
    """A ProvenanceSource that implements persist_annotation(), for testing
    that ProvenancePanel calls through to it on every commits-trait growth."""

    def __init__(self):
        self.persisted: list[tuple[str, dict]] = []

    def persist_annotation(self, state_id, annotation_dict):
        self.persisted.append((state_id, annotation_dict))
        return "ann-1"


def test_panel_loads_tree_from_source_into_widget():
    panel = ProvenancePanel(source=MockProvenanceSource())
    assert isinstance(panel.widget, ProvenanceWidget)
    assert panel.widget.tree["rootId"] == "s0"
    assert "s1" in panel.widget.tree["nodes"]


def test_panel_defaults_to_analyst_mode():
    panel = ProvenancePanel(source=MockProvenanceSource())
    assert panel.widget.mode == "analyst"


def test_panel_reviewer_mode_is_settable_at_construction():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    assert panel.widget.mode == "reviewer"


def test_commit_annotation_appends_to_commits_list():
    panel = ProvenancePanel(source=MockProvenanceSource())
    assert panel.widget.commits == []
    panel.commit_annotation({"title": "New note", "note": "...", "tags": [], "artifacts": []})
    assert len(panel.widget.commits) == 1
    assert panel.widget.commits[0]["annotation"]["title"] == "New note"
    # no target artifact: attaches to the latest state (whole-analysis note)
    assert panel.widget.commits[0]["stateId"] == panel.latest_state_id


def test_commit_annotation_persists_through_source_that_supports_it():
    source = _RecordingSource()
    panel = ProvenancePanel(source=source)

    panel.commit_annotation({"title": "New note", "note": "..."}, state_id="s1")

    assert source.persisted == [("s1", {"title": "New note", "note": "..."})]


def test_commit_from_frontend_composer_also_persists():
    """Mirrors what the JS composer does: set the commits trait directly,
    not via commit_annotation() — the observer must catch this path too."""
    source = _RecordingSource()
    panel = ProvenancePanel(source=source)

    panel.widget.commits = [
        *panel.widget.commits,
        {"stateId": "s2", "annotation": {"note": "from js"}},
    ]

    assert source.persisted == [("s2", {"note": "from js"})]


def test_source_without_persist_annotation_is_left_ephemeral():
    panel = ProvenancePanel(source=MockProvenanceSource())
    panel.commit_annotation({"title": "New note", "note": "..."})
    assert len(panel.widget.commits) == 1  # no error, no persistence attempted


def test_sidebar_and_tree_surface_return_the_same_widget_instance():
    panel = ProvenancePanel(source=MockProvenanceSource())
    assert panel.sidebar() is panel.tree_surface()


def test_outputs_do_not_follow_the_cursor_until_a_notebook_binds_it():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    assert panel.widget.outputs_follow_cursor is False


def test_binding_the_cursor_to_marimo_state_marks_the_outputs_as_following_it():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    panel.reactive_cursor(lambda initial: (lambda: initial, lambda value: None))
    assert panel.widget.outputs_follow_cursor is True


def test_the_restore_request_api_is_gone():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    assert not hasattr(panel, "request_restore") and not hasattr(panel, "acknowledge_restore")


class _EditableSource(_RecordingSource):
    def __init__(self):
        super().__init__()
        self.removed: list[str] = []
        self.updated: list[tuple[str, dict]] = []

    def persist_annotation(self, state_id, annotation_dict):
        super().persist_annotation(state_id, annotation_dict)
        return "src-1"

    def remove_annotation(self, annotation_id):
        self.removed.append(annotation_id)

    def update_annotation(self, annotation_id, annotation_dict):
        self.updated.append((annotation_id, annotation_dict))


def test_invalid_mode_is_rejected():
    import pytest

    with pytest.raises(ValueError):
        ProvenancePanel(source=MockProvenanceSource(), mode="admin")


def test_mode_cannot_be_changed_after_construction():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    panel.widget.mode = "analyst"
    assert panel.widget.mode == "reviewer"


def test_remove_annotation_deletes_through_source_using_its_own_id():
    source = _EditableSource()
    panel = ProvenancePanel(source=source)
    panel.commit_annotation({"annotationId": "ann-1", "note": "x"}, state_id="s1")

    panel.remove_annotation("ann-1")

    assert source.removed == ["src-1"]
    assert panel.widget.removed_annotations == ["ann-1", "src-1"]


def test_update_annotation_goes_through_source():
    source = _EditableSource()
    panel = ProvenancePanel(source=source)
    panel.commit_annotation({"annotationId": "ann-1", "note": "x"}, state_id="s1")

    panel.update_annotation("ann-1", {"annotationId": "ann-1", "note": "y"})

    assert source.updated == [("src-1", {"annotationId": "ann-1", "note": "y"})]


def test_reviewer_cannot_remove_or_edit_annotations():
    source = _EditableSource()
    panel = ProvenancePanel(source=source, mode="reviewer")

    panel.remove_annotation("ann-1")
    panel.update_annotation("ann-1", {"note": "y"})

    assert panel.widget.removed_annotations == []
    assert panel.widget.edited_annotations == {}
    assert source.removed == [] and source.updated == []


def test_latest_state_is_last_recorded_and_go_to_sets_cursor():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    node_ids = list(panel.widget.tree["nodes"])
    assert panel.latest_state_id == node_ids[-1]
    assert panel.cursor_state_id is None

    panel.go_to(node_ids[0])
    assert panel.cursor_state_id == node_ids[0]
    assert panel.widget.replay["isLatest"] is False

    panel.go_latest()
    assert panel.cursor_state_id == node_ids[-1]
    assert panel.widget.replay["isLatest"] is True


def test_tree_tab_is_hidden_by_default():
    assert ProvenancePanel(source=MockProvenanceSource()).widget.show_tree is False


def test_show_tree_can_be_enabled_at_construction():
    assert ProvenancePanel(source=MockProvenanceSource(), show_tree=True).widget.show_tree is True


def test_explicit_tabs_including_tree_opt_in():
    panel = ProvenancePanel(source=MockProvenanceSource(), tabs=["curated", "tree"])
    assert panel.widget.show_tree is True


def test_commit_annotation_without_nodes_falls_back_to_python():
    panel = ProvenancePanel(source=EmptyProvenanceSource())
    panel.commit_annotation({"title": "t", "note": "n"})
    assert panel.widget.commits[0]["stateId"] == "python"


def test_student_is_a_deprecated_alias_for_analyst():
    import pytest

    with pytest.warns(DeprecationWarning):
        panel = ProvenancePanel(source=MockProvenanceSource(), mode="student")
    assert panel.widget.mode == "analyst"


def test_show_tree_cannot_be_changed_after_construction():
    panel = ProvenancePanel(source=MockProvenanceSource())
    panel.widget.show_tree = True
    assert panel.widget.show_tree is False


def test_config_tab_no_longer_exists():
    panel = ProvenancePanel(source=MockProvenanceSource(), tabs=["curated", "config"])
    assert panel.widget.visible_tabs == ["curated"]
    assert "config" not in ProvenancePanel(source=MockProvenanceSource()).widget.visible_tabs


def test_persisted_commit_records_alias_to_the_sources_id():
    source = _EditableSource()
    panel = ProvenancePanel(source=source)
    panel.commit_annotation({"annotationId": "ann-1", "note": "x"}, state_id="s1")
    assert panel.widget.annotation_aliases == {"ann-1": "src-1"}


class _SnapshotSource(EmptyProvenanceSource):
    def __init__(self):
        self.loads = []

    def snapshot_bindings(self, state_id):
        return {"df", "model"}

    def snapshot(self, state_id, names=None):
        self.loads.append(names)
        return {n: f"{n}@{state_id}" for n in (names or ["df", "model"]) if n == "df"}


def test_on_replay_reports_the_recorded_state_latest_included():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    seen = []
    panel.on_replay(seen.append)
    nodes = list(panel.widget.tree["nodes"])

    panel.go_to(nodes[1])
    panel.go_latest()

    assert seen == [nodes[1], nodes[-1]]


def test_analyst_cursor_is_always_live():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="analyst")
    seen = []
    panel.on_replay(seen.append)
    panel.go_to(list(panel.widget.tree["nodes"])[1])
    assert seen == [None]


def test_reactive_cursor_binds_replay_to_a_state_getter():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    box = {}

    def fake_state(initial):
        box["value"] = initial
        return (lambda: box["value"]), (lambda v: box.update(value=v))

    get_cursor = panel.reactive_cursor(fake_state)
    assert get_cursor() == panel.latest_state_id  # a reviewer starts at the latest recorded state
    first = list(panel.widget.tree["nodes"])[0]
    panel.go_to(first)
    assert get_cursor() == first


def test_snapshot_is_live_without_a_cursor():
    snap = ProvenancePanel(source=MockProvenanceSource()).snapshot(None)
    assert snap.is_live and snap.get("df", "live value") == "live value"


def test_snapshot_at_a_state_uses_the_sources_variables():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    panel._source = _SnapshotSource()
    first = list(panel.widget.tree["nodes"])[0]

    snap = panel.snapshot(first)

    assert not snap.is_live
    assert snap.get("df", "live value") == f"df@{first}"
    assert snap.get("missing", "live value") is None
    assert snap.step == 1 and "Snapshot of the analysis" in snap.banner()


def test_snapshot_without_source_support_is_empty():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    first = list(panel.widget.tree["nodes"])[0]
    assert panel.snapshot(first).variables == {}


def test_snapshot_loads_lazily_and_only_once_per_name():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    source = _SnapshotSource()
    panel._source = source
    snap = panel.snapshot(list(panel.widget.tree["nodes"])[0])

    assert source.loads == []  # nothing read yet
    snap.get("df")
    snap.get("df")
    assert source.loads == [["df"]]


def test_snapshot_tells_not_stored_from_not_computed():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    panel._source = _SnapshotSource()
    snap = panel.snapshot(list(panel.widget.tree["nodes"])[0])

    assert snap.status("df") == "ok"
    assert snap.status("model") == "not_stored"  # bound at the state, but no loadable value
    assert snap.status("never_defined") == "not_computed"
    assert "not stored" in snap.missing("model")
    assert "Not computed yet" in snap.missing("never_defined")
    assert snap.status("anything") != "live" and panel.snapshot(None).status("x") == "live"


def test_snapshot_reports_why_it_is_unavailable():
    class _OldPmprov(EmptyProvenanceSource):
        def snapshot_bindings(self, state_id):
            raise RuntimeError("needs pmprov >= 0.8.0")

        def snapshot(self, state_id, names=None):
            return {}

    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    panel._source = _OldPmprov()
    snap = panel.snapshot(list(panel.widget.tree["nodes"])[0])

    assert "needs pmprov >= 0.8.0" in snap.missing("df")


class _GrowingSource(_RecordingSource):
    """A live history that is empty when the panel is built and records a step later."""

    def __init__(self):
        super().__init__()
        self.states: list[str] = []

    def get_tree(self):
        from provenance_widget.interfaces import ProvenanceNode, ProvenanceTree

        nodes = {
            sid: ProvenanceNode(
                state_id=sid, parent_state_id=None, branch_id="main",
                operation=MockProvenanceSource().get_tree().nodes["s0"].operation,
                params={}, delta=MockProvenanceSource().get_tree().nodes["s0"].delta,
            )
            for sid in self.states
        }
        return ProvenanceTree(nodes=nodes, root_id=self.states[0] if self.states else "", branches={})


def test_composer_commit_is_saved_on_the_latest_state_the_source_has_recorded():
    """The sidebar sends "composer" when its tree was empty; the source may have recorded steps since."""
    source = _GrowingSource()
    panel = ProvenancePanel(source=source, auto_refresh=False)
    source.states = ["s1", "s2"]

    panel.widget.commits = [*panel.widget.commits, {"stateId": "composer", "annotation": {"note": "whole analysis"}}]

    assert source.persisted == [("s2", {"note": "whole analysis"})]


def test_commit_made_before_any_step_is_saved_when_the_first_step_is_recorded(caplog):
    source = _GrowingSource()
    panel = ProvenancePanel(source=source, auto_refresh=False)

    with caplog.at_level("WARNING"):
        panel.widget.commits = [*panel.widget.commits, {"stateId": "composer", "annotation": {"note": "early"}}]
    assert source.persisted == []
    assert "only in the sidebar for now" in caplog.text

    source.states = ["s1"]
    panel.refresh()

    assert source.persisted == [("s1", {"note": "early"})]


def test_failing_persistence_is_logged_not_silent(caplog):
    class _Failing(_RecordingSource):
        def persist_annotation(self, state_id, annotation_dict):
            raise RuntimeError("disk full")

    panel = ProvenancePanel(source=_Failing())
    with caplog.at_level("WARNING"):
        panel.commit_annotation({"annotationId": "a1", "note": "x"}, state_id="s1")

    assert "Could not save annotation" in caplog.text and "disk full" in caplog.text


class _SlowLiveSource(_EditableSource):
    """A live source (has settle()) whose writes wait on a gate, like pmprov's storage queue behind artifact writes."""

    def __init__(self):
        super().__init__()
        import threading

        self.gate = threading.Event()
        self.order: list[str] = []

    def settle(self):  # marks it as a live source
        pass

    def persist_annotation(self, state_id, annotation_dict):
        self.gate.wait(timeout=10)
        self.order.append(f"add:{annotation_dict.get('note')}")
        return super().persist_annotation(state_id, annotation_dict)

    def update_annotation(self, annotation_id, annotation_dict):
        self.order.append(f"edit:{annotation_dict.get('note')}")
        super().update_annotation(annotation_id, annotation_dict)


def test_a_slow_live_source_does_not_hold_up_the_caller():
    """The observer runs on marimo's kernel thread; waiting there for the source froze every UI element."""
    import time

    source = _SlowLiveSource()
    panel = ProvenancePanel(source=source, auto_refresh=False)

    started = time.monotonic()
    panel.widget.commits = [{"stateId": "s1", "annotation": {"annotationId": "a1", "note": "first"}}]
    assert time.monotonic() - started < 1  # returned although the source is still blocked
    assert source.persisted == []

    source.gate.set()
    panel.wait_for_persistence(timeout=10)
    assert source.persisted == [("s1", {"annotationId": "a1", "note": "first"})]


def test_writes_to_a_live_source_keep_their_order():
    source = _SlowLiveSource()
    panel = ProvenancePanel(source=source, auto_refresh=False)

    panel.widget.commits = [{"stateId": "s1", "annotation": {"annotationId": "a1", "note": "first"}}]
    panel.widget.edited_annotations = {"a1": {"annotationId": "a1", "note": "second"}}
    source.gate.set()
    panel.wait_for_persistence(timeout=10)

    assert source.order == ["add:first", "edit:second"]


def test_refresh_does_not_resend_an_unchanged_tree():
    sent = []
    panel = ProvenancePanel(source=MockProvenanceSource(), auto_refresh=False)
    panel.widget.send_state = lambda keys=None: sent.append(keys)

    panel.refresh()
    panel.refresh()

    assert sent == []  # nothing changed since the panel was built


def test_the_first_tree_of_a_live_source_is_not_read_on_the_callers_thread():
    import threading
    import time

    reads: list[str] = []

    class _Live(MockProvenanceSource):
        def settle(self):  # marks it as a live source
            pass

        def get_tree(self):
            reads.append(threading.current_thread().name)
            return super().get_tree()

    panel = ProvenancePanel(source=_Live(), auto_refresh=True)
    try:
        assert threading.current_thread().name not in reads  # the constructor did not read it
        deadline = time.monotonic() + 5
        while not panel.widget.tree.get("nodes") and time.monotonic() < deadline:
            time.sleep(0.05)
        assert panel.widget.tree.get("nodes")  # the poll thread filled it in
        assert threading.current_thread().name not in reads
    finally:
        panel.stop_auto_refresh()


def test_pdf_export_from_a_live_source_does_not_hold_up_the_caller():
    import threading
    import time

    class _Live(MockProvenanceSource):
        def settle(self):  # marks it as a live source
            pass

    panel = ProvenancePanel(source=_Live(), auto_refresh=False)
    gate = threading.Event()
    original = panel.export_pdf
    panel.export_pdf = lambda *a, **k: (gate.wait(10), original(*a, **k))[1]

    began = time.monotonic()
    panel.widget.export_request = {"requestId": "r1"}
    assert time.monotonic() - began < 1  # returned although the export is still waiting
    assert panel.widget.export_result == {}

    gate.set()
    panel.wait_for_persistence(timeout=20)
    assert panel.widget.export_result.get("requestId") == "r1"


def test_pdf_export_does_not_wait_for_the_source_storage_queue():
    import threading

    class _Live(MockProvenanceSource):
        def settle(self):  # marks it as a live source
            pass

    panel = ProvenancePanel(source=_Live(), auto_refresh=False)
    blocked = threading.Event()
    panel._run_write(lambda: blocked.wait(30))  # a write stuck behind the source's backlog

    panel.widget.export_request = {"requestId": "r2"}
    deadline = threading.Event()
    for _ in range(100):
        if panel.widget.export_result.get("requestId") == "r2":
            break
        deadline.wait(0.1)
    try:
        assert panel.widget.export_result.get("requestId") == "r2"  # finished although the write has not
        assert not blocked.is_set()
    finally:
        blocked.set()
        panel.wait_for_persistence(timeout=20)


def test_panel_empty_hint_is_empty_unless_the_notebook_sets_one():
    assert ProvenancePanel().widget.empty_hint == ""
    assert ProvenancePanel(empty_hint="Press Pick, then Add.").widget.empty_hint == "Press Pick, then Add."


# --- the initial state, before the first recorded step ------------------------------------------------------------------------------


def test_a_reviewer_can_stand_before_the_first_step():
    from provenance_widget.snapshot import INITIAL_STATE

    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    assert panel._cursor_from({"stateId": INITIAL_STATE}) == INITIAL_STATE
    assert panel._cursor_from({}) == panel.latest_state_id  # a replay that never moved is at the latest state
    assert ProvenancePanel(source=MockProvenanceSource(), mode="analyst")._cursor_from({"stateId": INITIAL_STATE}) is None


def test_nothing_is_computed_at_the_initial_state():
    from provenance_widget.snapshot import INITIAL_STATE

    snap = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer").snapshot(INITIAL_STATE)
    assert snap.step == 0 and not snap.is_live
    assert snap.status("event_log") == "not_computed" and snap.get("event_log") is None
    assert "Not computed yet" in snap.missing("event_log")


def test_the_replay_cursor_follows_the_reviewer_to_the_initial_state():
    from provenance_widget.snapshot import INITIAL_STATE

    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    seen = []
    panel.on_replay(seen.append)
    panel.widget.replay = {"stateId": INITIAL_STATE, "params": {}, "isLatest": False}
    assert seen == [INITIAL_STATE]


def test_the_kernel_answers_the_players_ping_so_it_can_stop_saying_it_is_rebuilding():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    assert panel.widget.replay_pong == {}
    panel.widget.replay_ping = {"token": "1700000000000-1"}
    assert panel.widget.replay_pong == {"token": "1700000000000-1"}
    panel.widget.replay_ping = {"token": "1700000000000-2"}
    assert panel.widget.replay_pong == {"token": "1700000000000-2"}


# --- charts built in marimo's Visualize tab -------------------------------------------------------------------------------------


import base64

_PNG = base64.b64encode(b"\x89PNG" + bytes([13, 10, 26, 10]) + b"tiny").decode("ascii")


class _ChartSource(EmptyProvenanceSource):
    """A source that records charts (optional, like persist_annotation)."""

    def __init__(self):
        self.charts: list[tuple[str, str, dict, bytes | None]] = []

    def record_chart(self, artifact_id, artifact_name, settings, png=None):
        self.charts.append((artifact_id, artifact_name, settings, png))
        return {"stateId": "chart-state", "artifactId": "chart-state", "artifactName": "Bar chart of case_log"}


def _chart_event(event_id="e1", image=None, **settings):
    event = {"id": event_id, "artifactId": "s1", "artifactName": "case_log", "settings": {"chart_type": "Bar", "x": "c", **settings}}
    if image is not None:
        event["image"] = image
    return event


def test_capture_charts_is_off_by_default_and_ignores_chart_events():
    source = _ChartSource()
    panel = ProvenancePanel(source=source)
    assert panel.widget.capture_charts is False
    panel.widget.chart_event = _chart_event()
    panel.wait_for_persistence()
    assert source.charts == []


def test_a_chart_event_is_recorded_through_the_source_with_its_picture():
    source = _ChartSource()
    panel = ProvenancePanel(source=source, capture_charts=True)
    assert panel.widget.capture_charts is True
    panel.widget.chart_event = _chart_event(image=_PNG)
    panel.wait_for_persistence()
    assert len(source.charts) == 1
    artifact_id, name, settings, png = source.charts[0]
    assert (artifact_id, name, settings) == ("s1", "case_log", {"chart_type": "Bar", "x": "c"})
    assert png == base64.b64decode(_PNG)


def test_the_page_is_told_which_artifact_the_chart_became():
    panel = ProvenancePanel(source=_ChartSource(), capture_charts=True)
    panel.widget.chart_event = _chart_event("e7", image=_PNG)
    panel.wait_for_persistence()
    assert panel.widget.chart_ack == {"eventId": "e7", "stateId": "chart-state", "artifactId": "chart-state", "artifactName": "Bar chart of case_log"}


def test_a_chart_without_a_usable_picture_is_still_recorded_without_one():
    source = _ChartSource()
    panel = ProvenancePanel(source=source, capture_charts=True)
    panel.widget.chart_event = _chart_event("a", image="not base64 !!")
    panel.widget.chart_event = _chart_event("b", image=base64.b64encode(b"x" * 700_000).decode("ascii"))  # over the snapshot size limit
    panel.wait_for_persistence()
    assert [c[3] for c in source.charts] == [None, None]


def test_the_same_chart_event_id_is_recorded_once():
    source = _ChartSource()
    panel = ProvenancePanel(source=source, capture_charts=True)
    panel.widget.chart_event = _chart_event("same")
    panel.widget.chart_event = {**_chart_event("same"), "settings": {"chart_type": "Bar", "x": "c"}}  # re-sent: same id
    panel.widget.chart_event = _chart_event("other", y="count")
    panel.wait_for_persistence()
    assert [c[2].get("y") for c in source.charts] == [None, "count"]


def test_a_reviewer_never_records_charts():
    source = _ChartSource()
    panel = ProvenancePanel(source=source, mode="reviewer", capture_charts=True)
    panel.widget.chart_event = _chart_event()
    panel.wait_for_persistence()
    assert source.charts == []


# --- restoring the chart builder after a restart ----------------------------------------------------------------------------------

BUILDER = {"cellId": "MJUe", "tabs": [{"tabName": "Bar Chart", "chartType": "bar", "config": {"general": {}}}]}


class _BuilderSource(_ChartSource):
    """A source that also keeps marimo's builder state and hands it back to restore (what PmprovAdapter does)."""

    def __init__(self, restore=None):
        super().__init__()
        self.builders = []
        self._restore = restore or {}

    def record_chart(self, artifact_id, artifact_name, settings, png=None, builder=None):
        self.builders.append(builder)
        return super().record_chart(artifact_id, artifact_name, settings, png)

    def charts_to_restore(self):
        return self._restore


def test_a_chart_event_hands_marimos_builder_state_to_a_source_that_takes_it():
    source = _BuilderSource()
    panel = ProvenancePanel(source=source, capture_charts=True)
    panel.widget.chart_event = {**_chart_event(), "builder": BUILDER}
    panel.wait_for_persistence()
    assert source.builders == [BUILDER]


def test_a_chart_event_still_records_for_a_source_that_does_not_take_the_builder_state():
    source = _ChartSource()  # the older record_chart signature
    panel = ProvenancePanel(source=source, capture_charts=True)
    panel.widget.chart_event = {**_chart_event(), "builder": BUILDER}
    panel.wait_for_persistence()
    assert len(source.charts) == 1


def test_a_malformed_builder_state_is_dropped_but_the_chart_is_recorded():
    source = _BuilderSource()
    panel = ProvenancePanel(source=source, capture_charts=True)
    panel.widget.chart_event = {**_chart_event("a"), "builder": {"cellId": 5}}
    panel.widget.chart_event = {**_chart_event("b", y="count"), "builder": "nope"}
    panel.wait_for_persistence()
    assert source.builders == [None, None] and len(source.charts) == 2


def test_the_stored_builder_states_are_handed_to_the_page_to_restore():
    stored = {"MJUe": BUILDER["tabs"]}
    panel = ProvenancePanel(source=_BuilderSource(stored), capture_charts=True)
    assert panel.widget.chart_restore == stored


def test_nothing_is_restored_without_capture_for_a_reviewer_or_from_a_failing_source():
    stored = {"MJUe": BUILDER["tabs"]}
    assert ProvenancePanel(source=_BuilderSource(stored)).widget.chart_restore == {}
    assert ProvenancePanel(source=_BuilderSource(stored), mode="reviewer", capture_charts=True).widget.chart_restore == {}

    class Failing(_BuilderSource):
        def charts_to_restore(self):
            raise RuntimeError("storage unavailable")

    assert ProvenancePanel(source=Failing(), capture_charts=True).widget.chart_restore == {}


def test_malformed_chart_events_and_sources_without_record_chart_are_ignored():
    source = _ChartSource()
    panel = ProvenancePanel(source=source, capture_charts=True)
    for bad in ({"id": "x"}, {"id": "y", "artifactId": "s1", "artifactName": "t", "settings": "not a dict"}, {}):
        panel.widget.chart_event = bad
    panel.wait_for_persistence()
    assert source.charts == []
    ProvenancePanel(source=EmptyProvenanceSource(), capture_charts=True).widget.chart_event = _chart_event()  # no error


def test_capture_charts_switches_on_marimo_visualize(monkeypatch):
    import provenance_widget.widget as widget_module

    called = []
    monkeypatch.setattr(widget_module, "enable_chart_builder", lambda: called.append(True) or True)
    ProvenancePanel(source=_ChartSource(), capture_charts=True)
    ProvenancePanel(source=_ChartSource())
    assert called == [True]  # only the panel that asked for it


# --- 0.16: the charts are restored by the cells that draw their tables now ------------------------------------------------------


class _TableSource(_BuilderSource):
    """A source that keeps the charts by table, as PmprovAdapter does."""

    def __init__(self, by_table=None):
        super().__init__()
        self.by_table = by_table or {}
        self.asked = []

    def charts_to_restore(self, cells=None):
        self.asked.append(cells)
        return {cells[table]: tabs for table, tabs in self.by_table.items() if table in cells} if cells else {"as-recorded": []}


def test_the_panel_asks_for_the_charts_by_the_cells_of_this_notebook_and_tells_the_page_the_layout(monkeypatch):
    import provenance_widget.widget as widget_module

    monkeypatch.setattr(widget_module, "table_cells", lambda: {"case_log": "Hbol", "raw_events": "vblA"})
    source = _TableSource({"case_log": BUILDER["tabs"], "a_table_that_is_gone": BUILDER["tabs"]})
    panel = ProvenancePanel(source=source, capture_charts=True)
    assert source.asked == [{"case_log": "Hbol", "raw_events": "vblA"}]
    assert panel.widget.chart_restore == {"Hbol": BUILDER["tabs"]}
    assert panel.widget.chart_layout == widget_module.chart_layout({"case_log": "Hbol", "raw_events": "vblA"}) != ""
    assert panel.widget.chart_restore_ready is True


def test_outside_marimo_or_with_an_older_source_the_charts_are_restored_as_they_were_recorded(monkeypatch):
    import provenance_widget.widget as widget_module

    stored = {"MJUe": BUILDER["tabs"]}
    panel = ProvenancePanel(source=_BuilderSource(stored), capture_charts=True)  # no cell is known: not in a notebook
    assert panel.widget.chart_layout == "" and panel.widget.chart_restore == stored and panel.widget.chart_restore_ready is True
    monkeypatch.setattr(widget_module, "table_cells", lambda: {"case_log": "Hbol"})
    older = ProvenancePanel(source=_BuilderSource(stored), capture_charts=True)  # its charts_to_restore() takes no cells
    assert older.widget.chart_restore == stored and older.widget.chart_layout != ""


def test_the_page_is_told_that_nothing_was_recorded_and_is_not_told_when_the_history_cannot_be_read(monkeypatch):
    import provenance_widget.widget as widget_module

    monkeypatch.setattr(widget_module, "table_cells", lambda: {"case_log": "Hbol"})
    empty = ProvenancePanel(source=_TableSource(), capture_charts=True)
    assert empty.widget.chart_restore == {} and empty.widget.chart_restore_ready is True

    class Failing(_TableSource):
        def charts_to_restore(self, cells=None):
            raise RuntimeError("storage unavailable")

    assert ProvenancePanel(source=Failing(), capture_charts=True).widget.chart_restore_ready is False
    assert ProvenancePanel(source=_TableSource(), mode="reviewer", capture_charts=True).widget.chart_layout == ""


def test_after_a_chart_is_recorded_the_page_is_given_the_charts_again(monkeypatch):
    import provenance_widget.widget as widget_module

    monkeypatch.setattr(widget_module, "table_cells", lambda: {"case_log": "Hbol"})
    source = _TableSource()
    panel = ProvenancePanel(source=source, capture_charts=True)
    assert panel.widget.chart_restore == {}
    source.by_table = {"case_log": BUILDER["tabs"]}  # what recording the chart leaves in the source
    panel.widget.chart_event = {**_chart_event(), "builder": BUILDER}
    panel.wait_for_persistence()
    assert panel.widget.chart_restore == {"Hbol": BUILDER["tabs"]}
