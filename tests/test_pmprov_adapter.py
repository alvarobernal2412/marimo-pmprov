"""Tests for PmprovAdapter against a real pmprov RuntimeTracker."""
import pandas as pd
import pytest

from tracker.storage import DuckDBSQLiteBackend as StorageBackend
from tracker.runtime import RuntimeTracker
import tracker  # noqa: F401 — patches annotate()/tag() onto RuntimeTracker

from provenance_widget.pmprov_adapter import PmprovAdapter


@pytest.fixture
def rt(tmp_path):
    storage = StorageBackend(db_path=tmp_path / "prov.db", artifact_dir=tmp_path / "art")
    return RuntimeTracker(storage=storage, session_id="t", history_name="test")


@pytest.fixture
def event_log():
    return pd.DataFrame({"case:concept:name": ["A1", "A2"], "concept:name": ["Create", "Create"]})


def _settle(rt):
    rt.storage._executor.submit(lambda: None).result()


def test_get_tree_includes_no_annotations_by_default(rt, event_log):
    rt.trace_step(func=lambda df: df.assign(x=1), func_name="f", raw_line="df=f(df)",
                  args=[event_log], kwargs={})
    _settle(rt)

    tree = PmprovAdapter(rt).get_tree()

    assert len(tree.nodes) == 1
    node = next(iter(tree.nodes.values()))
    assert node.annotations == []


def test_get_tree_surfaces_pmprov_annotations_and_tags(rt, event_log):
    rt.trace_step(func=lambda df: df.assign(x=1), func_name="f", raw_line="df=f(df)",
                  args=[event_log], kwargs={})
    _settle(rt)
    state_id = rt._current_state_id

    from models.annotations import AnnotatableType
    rt.annotate([(AnnotatableType.ANALYSIS_STATE, state_id)], "worth revisiting")
    rt.tag(AnnotatableType.ANALYSIS_STATE, state_id, "reviewed")

    node = PmprovAdapter(rt).get_tree().nodes[state_id]

    assert len(node.annotations) == 1
    annotation = node.annotations[0]
    assert annotation.note == "worth revisiting"
    assert annotation.title == "worth revisiting"
    assert [t.name for t in annotation.tags] == ["reviewed"]
    assert annotation.author.agent_id == rt._agent.agent_id
    assert annotation.artifacts[0].artifact_id == state_id


def test_persist_annotation_round_trips_into_pmprov(rt, event_log):
    rt.trace_step(func=lambda df: df.assign(x=1), func_name="f", raw_line="df=f(df)",
                  args=[event_log], kwargs={})
    _settle(rt)
    state_id = rt._current_state_id
    adapter = PmprovAdapter(rt)

    annotation_id = adapter.persist_annotation(
        state_id, {"note": "committed from widget", "tags": [{"name": "outlier"}]}
    )

    assert annotation_id is not None
    node = adapter.get_tree().nodes[state_id]
    assert node.annotations[0].note == "committed from widget"
    assert [t.name for t in node.annotations[0].tags] == ["outlier"]


def test_persist_annotation_returns_none_for_unresolved_target(rt, event_log):
    adapter = PmprovAdapter(rt)
    assert adapter.persist_annotation("composer", {"note": "no target"}) is None
    assert adapter.persist_annotation("python", {"note": "no target"}) is None
    assert adapter.persist_annotation(None, {"note": "no target"}) is None


def test_persist_annotation_returns_none_for_empty_text(rt, event_log):
    rt.trace_step(func=lambda df: df.assign(x=1), func_name="f", raw_line="df=f(df)",
                  args=[event_log], kwargs={})
    _settle(rt)
    adapter = PmprovAdapter(rt)
    assert adapter.persist_annotation(rt._current_state_id, {"note": "", "title": ""}) is None
