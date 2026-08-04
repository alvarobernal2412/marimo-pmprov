# tests/test_interfaces.py
from provenance_widget.interfaces import (
    Agent, ArtifactRef, ColumnAdded, ColumnRemoved, Delta, Operation,
    ProvenanceNode, ProvenanceTree, StepCategory, Tag, Annotation,
)


def _agent():
    return Agent(agent_id="a1", agent_type="human", display_name="Student")


def test_delta_summary_reports_column_and_row_changes():
    delta = Delta(
        columns_added=[ColumnAdded(name="duration", dtype="float64")],
        columns_removed=[],
        row_count_before=1000,
        row_count_after=940,
    )
    summary = delta.summary()
    assert "duration" in summary
    assert "940" in summary


def test_tree_children_of_returns_direct_children_only():
    root = ProvenanceNode(
        state_id="s0", parent_state_id=None, branch_id="main",
        operation=Operation(operation_id="op0", name="load_event_log",
                             operation_type="IMPORT", command_name="load_event_log",
                             category=StepCategory.DATA_LOADING),
        params={}, delta=Delta([], [], 0, 1000), annotations=[],
    )
    child = ProvenanceNode(
        state_id="s1", parent_state_id="s0", branch_id="main",
        operation=Operation(operation_id="op1", name="Filter",
                             operation_type="FILTER", command_name="filter_duration",
                             category=StepCategory.CLEANING),
        params={"threshold": 120}, delta=Delta([], [], 1000, 940),
        annotations=[Annotation(
            annotation_id="ann1", title="Truncate outliers", note="...",
            tags=[Tag(name="cleaning", color="#0EA5E9")],
            artifacts=[ArtifactRef(artifact_id="art1", artifact_name="event_log",
                                    granularity="column", detail="duration")],
            author=_agent(), timestamp="2026-08-04T10:42:00",
        )],
    )
    grandchild = ProvenanceNode(
        state_id="s2", parent_state_id="s1", branch_id="main",
        operation=child.operation, params={}, delta=Delta([], [], 940, 940),
        annotations=[],
    )
    tree = ProvenanceTree(
        nodes={"s0": root, "s1": child, "s2": grandchild},
        root_id="s0", branches={"main": "main"},
    )
    assert [n.state_id for n in tree.children_of("s0")] == ["s1"]
    assert [n.state_id for n in tree.children_of("s1")] == ["s2"]
    assert tree.children_of("s2") == []
