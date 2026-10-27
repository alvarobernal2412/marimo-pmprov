"""Tests for PmprovAdapter against a real pmprov RuntimeTracker.

pmprov is an optional dependency (see README's "Connecting a real
pmprov-backed history") — CI doesn't install it, so this whole module is
skipped there rather than failing collection.
"""
import pandas as pd
import pytest

pytest.importorskip("tracker", reason="pmprov not installed")

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


def _traced_state(rt, event_log):
    rt.trace_step(func=lambda df: df.assign(x=1), func_name="f", raw_line="df=f(df)",
                  args=[event_log], kwargs={})
    _settle(rt)
    return rt._current_state_id


def test_update_annotation_changes_text_and_tags_in_pmprov(rt, event_log):
    state_id = _traced_state(rt, event_log)
    adapter = PmprovAdapter(rt)
    annotation_id = adapter.persist_annotation(
        state_id, {"note": "first", "tags": [{"name": "old"}]}
    )

    adapter.update_annotation(annotation_id, {"note": "second", "tags": [{"name": "new"}]})

    annotation = adapter.get_tree().nodes[state_id].annotations[0]
    assert annotation.note == "second"
    assert [t.name for t in annotation.tags] == ["new"]


def test_remove_annotation_deletes_it_from_pmprov(rt, event_log):
    state_id = _traced_state(rt, event_log)
    adapter = PmprovAdapter(rt)
    annotation_id = adapter.persist_annotation(state_id, {"note": "gone soon"})

    adapter.remove_annotation(annotation_id)

    assert adapter.get_tree().nodes[state_id].annotations == []


needs_bindings = pytest.mark.skipif(
    not hasattr(StorageBackend, "load_state_bindings"), reason="needs pmprov >= 0.8.0 (state bindings)"
)


@needs_bindings
def test_snapshot_gives_each_variable_as_bound_at_that_state(rt, event_log):
    rt.trace_step(func=lambda df: df.assign(x=1), func_name="add_x", raw_line="with_x = add_x(event_log)",
                  args=[event_log], kwargs={})
    first_state = rt._current_state_id
    rt.trace_step(func=lambda df: df.head(1), func_name="first_row", raw_line="small = first_row(with_x)",
                  args=[event_log.assign(x=1)], kwargs={})
    second_state = rt._current_state_id
    _settle(rt)
    adapter = PmprovAdapter(rt)

    earlier = adapter.snapshot(first_state)
    later = adapter.snapshot(second_state)

    assert set(earlier) == {"with_x"} and len(earlier["with_x"]) == 2
    assert set(later) == {"with_x", "small"}
    assert len(later["with_x"]) == 2 and len(later["small"]) == 1
    assert adapter.snapshot_bindings(second_state) == {"with_x", "small"}


@needs_bindings
def test_snapshot_loads_only_the_requested_names(rt, event_log):
    rt.trace_step(func=lambda df: df.assign(x=1), func_name="add_x", raw_line="with_x = add_x(event_log)",
                  args=[event_log], kwargs={})
    _settle(rt)
    adapter = PmprovAdapter(rt)

    assert set(adapter.snapshot(rt._current_state_id, names=["with_x", "nope"])) == {"with_x"}
    assert adapter.snapshot(rt._current_state_id, names=["nope"]) == {}


@needs_bindings
def test_snapshot_of_a_history_recorded_without_bindings_is_still_exact(rt, event_log, monkeypatch):
    """Histories recorded before pmprov 0.8 have no bindings; they replay from each step's own output."""
    rt.trace_step(func=lambda df: df.assign(x=1), func_name="add_x", raw_line="with_x = add_x(event_log)",
                  args=[event_log], kwargs={})
    first_state = rt._current_state_id
    rt.trace_step(func=lambda df: df.head(1), func_name="first_row", raw_line="small = first_row(with_x)",
                  args=[event_log.assign(x=1)], kwargs={})
    second_state = rt._current_state_id
    _settle(rt)
    monkeypatch.setattr(rt.storage, "load_state_bindings", lambda state_id: {})
    adapter = PmprovAdapter(rt)

    assert adapter.snapshot_bindings(first_state) == {"with_x"}
    assert set(adapter.snapshot(second_state)) == {"with_x", "small"}
    assert len(adapter.snapshot(first_state)["with_x"]) == 2
    assert len(adapter.snapshot(second_state, names=["small"])["small"]) == 1


def test_snapshot_works_on_a_pmprov_that_has_neither_bindings_nor_selective_restore(rt, event_log, monkeypatch):
    """Simulates pmprov < 0.8: no load_state_bindings, restore_state() without `names`."""
    rt.trace_step(func=lambda df: df.assign(x=1), func_name="add_x", raw_line="with_x = add_x(event_log)",
                  args=[event_log], kwargs={})
    first_state = rt._current_state_id
    rt.trace_step(func=lambda df: df.head(1), func_name="first_row", raw_line="small = first_row(with_x)",
                  args=[event_log.assign(x=1)], kwargs={})
    second_state = rt._current_state_id
    _settle(rt)
    real_restore = rt.restore_state

    def old_restore(state_id, **kwargs):
        if "names" in kwargs:
            raise TypeError("restore_state() got an unexpected keyword argument 'names'")
        return real_restore(state_id)

    monkeypatch.setattr(rt, "restore_state", old_restore)
    adapter = PmprovAdapter(rt)
    monkeypatch.setattr(adapter, "_bindings", lambda state_id: {})  # no bindings recorded

    assert adapter.snapshot_bindings(second_state) == {"with_x", "small"}
    assert len(adapter.snapshot(first_state)["with_x"]) == 2
    assert len(adapter.snapshot(second_state, names=["small"])["small"]) == 1


def test_readable_params_drops_artifact_refs_and_function_prefix():
    raw = [
        {"param_id": "f:event_log", "value": {"value_type": "artifact_state_ref", "artifact_state_id": "x"}},
        {"param_id": "f:year", "value": {"value_type": "scalar", "value": 2008}},
        {"param_id": "f:activities", "value": {"value_type": "list", "value": ["a", "b"]}},
        {"param_id": "g:plain", "value": 3},
    ]
    assert PmprovAdapter._readable_params(raw) == {"year": 2008, "activities": ["a", "b"], "plain": 3}


def _state_with_two_annotations(rt, event_log):
    rt.trace_step(func=lambda df: df.assign(x=1), func_name="f", raw_line="df=f(df)", args=[event_log], kwargs={})
    _settle(rt)
    state_id = rt._current_state_id
    adapter = PmprovAdapter(rt)
    first = adapter.persist_annotation(state_id, {"note": "first", "tags": [{"name": "shared"}, {"name": "only-first"}]})
    second = adapter.persist_annotation(state_id, {"note": "second", "tags": [{"name": "shared"}]})
    return adapter, state_id, first, second


def test_removing_an_annotation_removes_the_tags_only_it_carried(rt, event_log):
    adapter, state_id, first, _ = _state_with_two_annotations(rt, event_log)

    adapter.remove_annotation(first)

    assert adapter._state_tag_names(state_id) == {"shared"}  # "only-first" went, "shared" is still needed


def test_removing_the_last_annotation_removes_its_tags(rt, event_log):
    adapter, state_id, first, second = _state_with_two_annotations(rt, event_log)

    adapter.remove_annotation(first)
    adapter.remove_annotation(second)

    assert adapter._state_tag_names(state_id) == set()


def test_deleting_an_annotation_from_an_earlier_session_cleans_up_when_it_was_the_last(rt, event_log):
    adapter, state_id, first, second = _state_with_two_annotations(rt, event_log)
    adapter.remove_annotation(second)  # keep one annotation on the state

    restarted = PmprovAdapter(rt)  # a new session: the adapter no longer knows who carried which tag
    restarted.remove_annotation(first)

    assert restarted._state_tag_names(state_id) == set()


def test_deleting_one_of_two_annotations_after_a_restart_keeps_the_tags(rt, event_log):
    adapter, state_id, first, second = _state_with_two_annotations(rt, event_log)

    restarted = PmprovAdapter(rt)
    restarted.remove_annotation(second)

    assert restarted._state_tag_names(state_id) == {"shared", "only-first"}


def test_editing_tags_of_an_annotation_from_an_earlier_session_takes_effect(rt, event_log):
    adapter, state_id, first, second = _state_with_two_annotations(rt, event_log)
    adapter.remove_annotation(first)

    restarted = PmprovAdapter(rt)
    restarted.update_annotation(second, {"note": "second, edited", "tags": [{"name": "renamed"}]})

    assert restarted._state_tag_names(state_id) == {"renamed"}
    assert restarted.get_tree().nodes[state_id].annotations[0].note == "second, edited"
