from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class StepCategory(str, Enum):
    DATA_LOADING = "DATA_LOADING"
    CLEANING = "CLEANING"
    FEATURE_ENGINEERING = "FEATURE_ENGINEERING"
    AGGREGATION = "AGGREGATION"
    COMPARISON = "COMPARISON"
    ANALYSIS = "ANALYSIS"


@dataclass
class Agent:
    agent_id: str
    agent_type: str
    display_name: str


@dataclass
class ColumnAdded:
    name: str
    dtype: str


@dataclass
class ColumnRemoved:
    name: str
    dtype: str


@dataclass
class Delta:
    columns_added: list[ColumnAdded]
    columns_removed: list[ColumnRemoved]
    row_count_before: int
    row_count_after: int

    def summary(self) -> str:
        parts = []
        for c in self.columns_added:
            parts.append(f"+{c.name}")
        for c in self.columns_removed:
            parts.append(f"-{c.name}")
        parts.append(f"rows {self.row_count_before}->{self.row_count_after}")
        return ", ".join(parts)


@dataclass
class Operation:
    operation_id: str
    name: str
    operation_type: str
    command_name: str
    category: StepCategory


@dataclass
class ArtifactRef:
    artifact_id: str
    artifact_name: str
    granularity: str
    detail: str | None = None


@dataclass
class Tag:
    name: str
    color: str


@dataclass
class Annotation:
    annotation_id: str
    title: str
    note: str
    tags: list[Tag]
    artifacts: list[ArtifactRef]
    author: Agent
    timestamp: str


@dataclass
class ProvenanceNode:
    state_id: str
    parent_state_id: str | None
    branch_id: str
    operation: Operation
    params: dict
    delta: Delta
    annotations: list[Annotation] = field(default_factory=list)


@dataclass
class ProvenanceTree:
    nodes: dict[str, ProvenanceNode]
    root_id: str
    branches: dict[str, str]

    def children_of(self, state_id: str) -> list[ProvenanceNode]:
        return [n for n in self.nodes.values() if n.parent_state_id == state_id]


class ProvenanceSource(Protocol):
    def get_tree(self) -> ProvenanceTree: ...

    def state_for_artifact(self, artifact_id: str) -> str | None:
        """Return the state_id of the analysis state that contains/produced
        this artifact, or None if the source can't resolve it.

        Used to associate a new annotation with the right tree node purely
        from the artifact it targets, without the caller having to thread a
        state_id through by hand.
        """
        ...
