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


def test_request_restore_sets_restore_request_with_tag():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    panel.request_restore("v1.1")
    assert panel.widget.restore_request == {"tag": "v1.1"}


def test_acknowledge_restore_clears_request_and_sets_ack():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    panel.request_restore("v1.1")
    panel.acknowledge_restore()
    assert panel.widget.restore_request == {}
    assert panel.widget.restore_ack == {"acknowledged": True}


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
