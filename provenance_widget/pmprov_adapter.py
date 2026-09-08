"""ProvenanceSource adapter backed by a live pmprov RuntimeTracker.

pmprov (https://github.com/alvarobernal2412/pmprov) records provenance
automatically at the AST level, and — since pmprov 0.5.0 — also has its own
Annotation/Tag concept (models.annotations), storable against any state/step
via `rt.annotate()` / `rt.tag()`. This adapter translates pmprov's state/step
graph into the ProvenanceTree shape this widget renders, including those
annotations/tags (see `_load_annotations`), and persists new ones committed
through `ProvenancePanel.commit_annotation()` / the sidebar's composer back
into pmprov via `persist_annotation()`.

Only imports pmprov lazily inside methods — marimo-pmprov itself has no
hard dependency on pmprov (see the `pmprov` extra in pyproject.toml).
"""

from __future__ import annotations

from typing import Any

from provenance_widget.interfaces import (
    Agent,
    Annotation,
    ArtifactRef,
    ColumnAdded,
    ColumnRemoved,
    Delta,
    Operation,
    ProvenanceNode,
    ProvenanceTree,
    StepCategory,
    Tag,
)

_DEFAULT_TAG_COLOR = "#64748B"
_TITLE_MAX_LEN = 40

_DEFAULT_CATEGORY = StepCategory.ANALYSIS


def _map_category(name: str | None) -> StepCategory:
    """Map a pmprov step_category name onto this widget's fixed enum.

    Register pmprov step categories with the exact StepCategory member names
    (DATA_LOADING, CLEANING, FEATURE_ENGINEERING, AGGREGATION, COMPARISON,
    ANALYSIS) via `tracker.step_category(...)` for a 1:1 mapping — anything
    else (including pmprov's "unknown" default) falls back to ANALYSIS.
    """
    if not name:
        return _DEFAULT_CATEGORY
    try:
        return StepCategory[name.upper()]
    except KeyError:
        return _DEFAULT_CATEGORY


class PmprovAdapter:
    """Reads a pmprov RuntimeTracker's history as a ProvenanceTree.

    Unlike MockProvenanceSource's fixed snapshot, this tree grows as the
    notebook runs. Every read here settles the tracker's async storage queue
    first (see `settle()`), so callers never need to do it themselves —
    combined with ProvenancePanel's auto-refresh (see widget.py), tracked
    cells don't need any provenance_widget-specific calls at all.
    """

    def __init__(self, tracker: Any) -> None:
        self._rt = tracker
        self._author = Agent(
            agent_id=tracker._agent.agent_id,
            agent_type=tracker._agent.agent_type.value,
            display_name=tracker._agent.username or tracker._agent.agent_id,
        )

    def settle(self) -> None:
        """Block until every write queued so far has landed in storage.

        rt.storage runs writes through an async executor — without this,
        a read immediately after a just-run tracked step can see the graph
        as it was *before* that step, since the write may not have landed
        yet. A single no-op task submitted to the same (FIFO, single-worker)
        executor only completes once everything ahead of it has.
        """
        self._rt.storage._executor.submit(lambda: None).result()

    def get_tree(self) -> ProvenanceTree:
        self.settle()
        history_id = self._rt._history.history_id
        graph = self._rt.storage.load_graph(history_id)
        states_by_id = {s["state_id"]: s for s in graph["states"]}
        steps = sorted(graph["steps"], key=lambda s: s["timestamp"])

        if not steps:
            # Nothing tracked yet — a genuinely empty tree, not a
            # placeholder node (pmprov's own internal root state doesn't
            # represent an analyst-visible step, so it's never shown).
            return ProvenanceTree(nodes={}, root_id="", branches={})

        # pmprov's DuckDB/SQLite backend stores this as "" (empty string),
        # not NULL, for the root state — falsy check, not an `is None` one.
        tracker_root_id = next(
            (s["state_id"] for s in states_by_id.values() if not s["produced_by_step_id"]), None
        )

        nodes: dict[str, ProvenanceNode] = {}
        branches: dict[str, str] = {}

        # deltas only carry a net rows_delta, not before/after counts, so
        # row counts are approximated by walking the pipeline in order and
        # accumulating from 0 at the root — accurate for the common linear
        # case this adapter is meant for, not for arbitrary branch topologies.
        running_rows: dict[str, int] = {tracker_root_id: 0}

        # The first tracked step's output becomes the *displayed* root —
        # pmprov's own tracker_root_id (its synthetic pre-tracking marker)
        # is never added to `nodes`, so it never renders as a fake
        # "session start" card. Any other step whose input was the tracker
        # root gets reparented onto the display root instead (keeps the
        # tree valid for the common single-branch case; see the note above).
        display_root_id: str | None = None

        for step in steps:
            output_id = step["output_state_id"]
            state = states_by_id.get(output_id)
            if state is None:
                continue

            detail = self._rt.storage.load_state_detail(output_id)
            op_info = detail.get("operation") or {}
            delta_info = detail.get("delta") or {}
            branch_name = detail.get("branch_name") or state["branch_id"]
            branches.setdefault(state["branch_id"], branch_name)

            parent_id = step["input_state_id"]
            is_first_real_step = parent_id == tracker_root_id
            if is_first_real_step and display_root_id is None:
                display_root_id = output_id
                parent_id = None
            elif is_first_real_step:
                parent_id = display_root_id

            rows_before = running_rows.get(parent_id, 0) if parent_id is not None else 0
            rows_after = rows_before + (delta_info.get("rows_delta") or 0)
            running_rows[output_id] = rows_after

            nodes[output_id] = ProvenanceNode(
                state_id=output_id,
                parent_state_id=parent_id,
                branch_id=state["branch_id"],
                operation=Operation(
                    operation_id=step["step_id"],
                    name=op_info.get("name") or step["func_name"],
                    operation_type=op_info.get("type") or "unknown",
                    command_name=step["func_name"],
                    category=_map_category(op_info.get("category")),
                ),
                params={p["param_id"]: p["value"] for p in detail.get("params", [])},
                delta=Delta(
                    columns_added=[ColumnAdded(name=c, dtype="") for c in delta_info.get("columns_added", [])],
                    columns_removed=[
                        ColumnRemoved(name=c, dtype="") for c in delta_info.get("columns_removed", [])
                    ],
                    row_count_before=rows_before,
                    row_count_after=rows_after,
                ),
                annotations=self._load_annotations(output_id),
            )

        return ProvenanceTree(nodes=nodes, root_id=display_root_id or "", branches=branches)

    def state_for_artifact(self, artifact_id: str) -> str | None:
        """pmprov has no separate artifact registry — a "state" *is* the
        DataFrame/artifact a step produced, so an artifact_id built from
        `latest_state_id()` (the convention this adapter's callers use, see
        the demo notebook) is already a real state_id. Confirm it still
        exists in the current graph before handing it back.
        """
        self.settle()
        history_id = self._rt._history.history_id
        graph = self._rt.storage.load_graph(history_id)
        if any(s["state_id"] == artifact_id for s in graph["states"]):
            return artifact_id
        return None

    def latest_state_id(self, func_name: str | None = None) -> str | None:
        """Return the output_state_id of the most recent step.

        Pass func_name to disambiguate ("the last time X ran") if steps have
        happened since; omit it to just mean "whatever ran last". Convenience
        for notebooks that want to annotate "the step I just ran" without
        threading state_ids through by hand.
        """
        self.settle()
        history_id = self._rt._history.history_id
        steps = self._rt.storage.load_graph(history_id)["steps"]
        candidates = steps if func_name is None else [s for s in steps if s["func_name"] == func_name]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s["timestamp"])["output_state_id"]

    def _load_annotations(self, state_id: str) -> list[Annotation]:
        """Translate pmprov's stored annotations/tags for *state_id* into this
        widget's Annotation/Tag dataclasses.

        pmprov tags aren't attached to individual annotations — they're
        attached to the same (target_type, target_id) a state's annotations
        are — so every annotation on a state shows that state's full tag set.
        """
        raw_annotations = self._rt.storage.load_annotations("analysis_state", state_id)
        if not raw_annotations:
            return []

        tags = [
            Tag(name=t["name"], color=_DEFAULT_TAG_COLOR)
            for t in self._rt.storage.load_tags("analysis_state", state_id)
        ]
        artifacts = [ArtifactRef(artifact_id=state_id, artifact_name=state_id, granularity="dataset")]

        return [
            Annotation(
                annotation_id=a["annotation_id"],
                title=(a["text"][:_TITLE_MAX_LEN] or "Untitled annotation"),
                note=a["text"],
                tags=tags,
                artifacts=artifacts,
                author=self._author,
                timestamp=a["created_at"],
            )
            for a in raw_annotations
        ]

    def persist_annotation(self, state_id: str, annotation_dict: dict) -> str | None:
        """Persist a committed annotation (from `ProvenancePanel.commit_annotation()`
        or the sidebar composer) into pmprov via `rt.annotate()` / `rt.tag()`.

        Returns the new annotation's annotation_id, or None if state_id
        doesn't resolve to a real state (e.g. the composer's "composer"
        placeholder when nothing was targeted) or there's no text to save.
        """
        if not state_id or state_id in ("composer", "python"):
            return None
        text = annotation_dict.get("note") or annotation_dict.get("title") or ""
        if not text:
            return None

        from models.annotations import AnnotatableType

        annotation_id = self._rt.annotate([(AnnotatableType.ANALYSIS_STATE, state_id)], text)
        for tag in annotation_dict.get("tags") or []:
            name = tag.get("name") if isinstance(tag, dict) else None
            if name:
                self._rt.tag(AnnotatableType.ANALYSIS_STATE, state_id, name)
        return annotation_id
