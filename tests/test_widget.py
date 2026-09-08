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
