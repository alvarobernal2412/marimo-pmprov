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

        explore_threshold = ProvenanceNode(
            state_id="s1b", parent_state_id="s0", branch_id="branch-explore",
            operation=_op("op1b", "Filter long traces (60h)", "FILTER", "filter_duration",
                          StepCategory.CLEANING),
            params={"threshold_hours": 60},
            delta=Delta([], [], row_count_before=15214, row_count_after=11800),
            annotations=[Annotation(
                annotation_id="ann-e771", title="Tighter threshold experiment",
                note="Tried a stricter 60h cutoff; dropped too many valid cases, abandoned.",
                tags=[Tag(name="cleaning", color="#0EA5E9"), Tag(name="exploration", color="#A855F7")],
                artifacts=[ArtifactRef(artifact_id="art-event-log", artifact_name="event_log.csv",
                                        granularity="row_subset", detail="rows 1-11800")],
                author=_STUDENT, timestamp="2026-08-04T10:47:00",
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

        pruned_rules = ProvenanceNode(
            state_id="s4a", parent_state_id="s3a", branch_id="branch-a",
            operation=_op("op4a", "Prune rule set", "RULE_PRUNING", "prune_rules",
                          StepCategory.ANALYSIS),
            params={"max_depth": 2, "min_support": 0.05},
            delta=Delta([], [], row_count_before=14032, row_count_after=14032),
            annotations=[Annotation(
                annotation_id="ann-b552", title="Pruned rule set",
                note="Capped depth at 2; resource attribute no longer dominates the split.",
                tags=[Tag(name="rules", color="#F59E0B"), Tag(name="v1.2", color="#94A3B8")],
                artifacts=[ArtifactRef(artifact_id="art-rule-report", artifact_name="rule_report.json",
                                        granularity="dataset")],
                author=_STUDENT, timestamp="2026-08-04T11:35:00",
            )],
        )

        cost_aggregation = ProvenanceNode(
            state_id="s4b", parent_state_id="s3b", branch_id="branch-b",
            operation=_op("op4b", "Aggregate cost by outcome", "GROUP_AGGREGATE", "groupby_agg",
                          StepCategory.AGGREGATION),
            params={"group_by": "fitness_bucket", "agg": "mean(case_cost)"},
            delta=Delta([ColumnAdded("mean_case_cost", "float64")], [],
                        row_count_before=14032, row_count_after=6),
            annotations=[Annotation(
                annotation_id="ann-9a10", title="Cost by conformance bucket",
                note="Non-conformant cases cost 2.3x more on average — worth flagging to reviewer.",
                tags=[Tag(name="cost", color="#10B981"), Tag(name="conformance", color="#F43F5E")],
                artifacts=[ArtifactRef(artifact_id="art-event-log", artifact_name="event_log.csv",
                                        granularity="column", detail="case_cost")],
                author=_STUDENT, timestamp="2026-08-04T11:48:00",
            )],
        )

        reviewer_check = ProvenanceNode(
            state_id="s5a", parent_state_id="s4a", branch_id="branch-a",
            operation=_op("op5a", "Reviewer sign-off", "REVIEW", "review_annotation",
                          StepCategory.COMPARISON),
            params={"reviewer": "agent-reviewer-1"},
            delta=Delta([], [], row_count_before=14032, row_count_after=14032),
            annotations=[Annotation(
                annotation_id="ann-7c31", title="Reviewer approved pruning",
                note="Confirmed the pruned rule set generalizes on a held-out fold.",
                tags=[Tag(name="rules", color="#F59E0B"), Tag(name="review", color="#3B82F6")],
                artifacts=[ArtifactRef(artifact_id="art-rule-report", artifact_name="rule_report.json",
                                        granularity="dataset")],
                author=Agent(agent_id="agent-reviewer-1", agent_type="human", display_name="R"),
                timestamp="2026-08-04T13:05:00",
            )],
        )

        cost_model = ProvenanceNode(
            state_id="s5b", parent_state_id="s4b", branch_id="branch-b",
            operation=_op("op5b", "Fit cost prediction model", "MODEL_FIT", "fit_regressor",
                          StepCategory.FEATURE_ENGINEERING),
            params={"model": "gradient_boost", "target": "mean_case_cost"},
            delta=Delta([ColumnAdded("predicted_cost", "float64")], [],
                        row_count_before=6, row_count_after=6),
            annotations=[Annotation(
                annotation_id="ann-1de4", title="Cost prediction model",
                note="R^2 0.81 on the 6 conformance buckets; small sample, treat as directional.",
                tags=[Tag(name="cost", color="#10B981"), Tag(name="v1.2", color="#94A3B8")],
                artifacts=[ArtifactRef(artifact_id="art-cost-model", artifact_name="cost_model.pkl",
                                        granularity="dataset")],
                author=_STUDENT, timestamp="2026-08-04T12:15:00",
            )],
        )

        return ProvenanceTree(
            nodes={n.state_id: n for n in [
                root, filtered, explore_threshold, enriched,
                rule_induction, conformance, pruned_rules, cost_aggregation,
                reviewer_check, cost_model,
            ]},
            root_id="s0",
            branches={
                "main": "main",
                "branch-explore": "explore-threshold",
                "branch-a": "rule-induction",
                "branch-b": "conformance",
            },
        )

    def state_for_artifact(self, artifact_id: str) -> str | None:
        """Best-effort: MockProvenanceSource has no artifact registry either
        (its ArtifactRefs are just hand-authored strings) — fall back to
        whichever node's own baked-in annotations already reference this
        artifact_id, since that's the closest thing to "produced it" here.
        """
        for node in self.get_tree().nodes.values():
            for annotation in node.annotations:
                if any(a.artifact_id == artifact_id for a in annotation.artifacts):
                    return node.state_id
        return None
