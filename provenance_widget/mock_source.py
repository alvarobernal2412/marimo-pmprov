from __future__ import annotations

from provenance_widget.interfaces import (
    Agent, Annotation, ArtifactRef, ColumnAdded, ColumnRemoved, Delta,
    Operation, ProvenanceNode, ProvenanceTree, StepCategory, Tag,
)

_STUDENT = Agent(agent_id="agent-student", agent_type="human", display_name="S")


def _op(op_id: str, name: str, op_type: str, command: str, category: StepCategory) -> Operation:
    return Operation(operation_id=op_id, name=name, operation_type=op_type,
                      command_name=command, category=category)


class MockProvenanceSource:
    """Deterministic in-memory ProvenanceSource for demoing the widget without pmprov."""

    def get_tree(self) -> ProvenanceTree:
        root = ProvenanceNode(
            state_id="s0", parent_state_id=None, branch_id="main",
            operation=_op("op0", "Load event log", "IMPORT", "load_event_log",
                          StepCategory.DATA_LOADING),
            params={"filepath": "data/rtfm_full.csv"},
            delta=Delta([ColumnAdded("case:concept:name", "object"),
                         ColumnAdded("concept:name", "object"),
                         ColumnAdded("time:timestamp", "datetime64[ns]")],
                        [], row_count_before=0, row_count_after=15214),
            annotations=[],
        )

        filtered = ProvenanceNode(
            state_id="s1", parent_state_id="s0", branch_id="main",
            operation=_op("op1", "Filter long traces", "FILTER", "filter_duration",
                          StepCategory.CLEANING),
            params={"threshold_hours": 120},
            delta=Delta([], [], row_count_before=15214, row_count_after=14032),
            annotations=[Annotation(
                annotation_id="ann-c8f2", title="Truncate outliers",
                note="Removed traces longer than 120h; distorted the mean duration.",
                tags=[Tag(name="cleaning", color="#0EA5E9"), Tag(name="v1.1", color="#94A3B8")],
                artifacts=[ArtifactRef(artifact_id="art-event-log", artifact_name="event_log.csv",
                                        granularity="column", detail="duration")],
                author=_STUDENT, timestamp="2026-08-04T10:42:00",
            )],
        )

        enriched = ProvenanceNode(
            state_id="s2", parent_state_id="s1", branch_id="main",
            operation=_op("op2", "Calculate case cost", "ENRICHMENT", "add_attribute",
                          StepCategory.FEATURE_ENGINEERING),
            params={"output_col": "case_cost", "source": "resource_wage_matrix"},
            delta=Delta([ColumnAdded("case_cost", "float64")], [],
                        row_count_before=14032, row_count_after=14032),
            annotations=[Annotation(
                annotation_id="ann-a911", title="Calculate case cost",
                note="Joined hourly wage matrix with resource trace logs.",
                tags=[Tag(name="cost", color="#10B981"), Tag(name="enrichment", color="#10B981")],
                artifacts=[ArtifactRef(artifact_id="art-event-log", artifact_name="event_log.csv",
                                        granularity="dataset")],
                author=_STUDENT, timestamp="2026-08-04T10:58:00",
            )],
        )

        rule_induction = ProvenanceNode(
            state_id="s3a", parent_state_id="s2", branch_id="branch-a",
            operation=_op("op3a", "Induce decision rules", "RULE_INDUCTION", "induce_rules",
                          StepCategory.ANALYSIS),
            params={"target_col": "is_long_case", "max_depth": 4},
            delta=Delta([ColumnAdded("predicted_outcome", "bool")], [],
                        row_count_before=14032, row_count_after=14032),
            annotations=[Annotation(
                annotation_id="ann-d213", title="First rule set",
                note="Depth-4 tree overfits on resource attribute; needs pruning.",
                tags=[Tag(name="rules", color="#F59E0B")],
                artifacts=[ArtifactRef(artifact_id="art-event-log", artifact_name="event_log.csv",
                                        granularity="row_subset", detail="rows 1-4032")],
                author=_STUDENT, timestamp="2026-08-04T11:10:00",
            )],
        )

        conformance = ProvenanceNode(
            state_id="s3b", parent_state_id="s2", branch_id="branch-b",
            operation=_op("op3b", "Conformance check", "CONFORMANCE_CHECK", "check_conformance",
                          StepCategory.COMPARISON),
            params={"model": "petri_net_v1"},
            delta=Delta([ColumnAdded("fitness", "float64")], [],
                        row_count_before=14032, row_count_after=14032),
            annotations=[Annotation(
                annotation_id="ann-f004", title="Baseline fitness",
                note="Fitness 0.87 against the reference Petri net.",
                tags=[Tag(name="conformance", color="#F43F5E"), Tag(name="v1.1", color="#94A3B8")],
                artifacts=[ArtifactRef(artifact_id="art-process-map", artifact_name="Chart_ProcessMap",
                                        granularity="chart_selection")],
                author=_STUDENT, timestamp="2026-08-04T11:22:00",
            )],
        )

        return ProvenanceTree(
            nodes={n.state_id: n for n in [root, filtered, enriched, rule_induction, conformance]},
            root_id="s0",
            branches={"main": "main", "branch-a": "rule-induction", "branch-b": "conformance"},
        )
