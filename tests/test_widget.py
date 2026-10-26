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


def test_panel_defaults_to_student_mode():
    panel = ProvenancePanel(source=MockProvenanceSource())
    assert panel.widget.mode == "student"


def test_panel_reviewer_mode_is_settable_at_construction():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    assert panel.widget.mode == "reviewer"


def test_commit_annotation_appends_to_commits_list():
    panel = ProvenancePanel(source=MockProvenanceSource())
    assert panel.widget.commits == []
    panel.commit_annotation({"title": "New note", "note": "...", "tags": [], "artifacts": []})
    assert len(panel.widget.commits) == 1
    assert panel.widget.commits[0]["annotation"]["title"] == "New note"
    assert panel.widget.commits[0]["stateId"] == "python"


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
    panel.widget.mode = "student"
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
