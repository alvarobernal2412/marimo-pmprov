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

import ast
from collections import OrderedDict
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

_SNAPSHOT_CACHE_SIZE = 6  # restored artifact versions kept in memory
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
        # annotation_id -> (state_id, tag names) for annotations persisted
        # through this adapter, so update_annotation() can diff tags.
        self._persisted_tags: dict[str, tuple[str, set[str]]] = {}
        # artifact_state_id -> restored object, LRU (see snapshot())
        self._values: OrderedDict[str, Any] = OrderedDict()
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
                params=self._readable_params(detail.get("params", [])),
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
        names = self._tag_names(annotation_dict)
        for name in names:
            self._rt.tag(AnnotatableType.ANALYSIS_STATE, state_id, name)
        self._persisted_tags[annotation_id] = (state_id, names)
        return annotation_id

    @staticmethod
    def _tag_names(annotation_dict: dict) -> set[str]:
        return {
            tag["name"]
            for tag in annotation_dict.get("tags") or []
            if isinstance(tag, dict) and tag.get("name")
        }

    def _annotation_state(self, annotation_id: str) -> str | None:
        """The state an annotation is attached to (searched when it was persisted in an earlier session)."""
        known = self._persisted_tags.get(annotation_id)
        if known:
            return known[0]
        graph = self._rt.storage.load_graph(self._rt._history.history_id)
        for state in graph["states"]:
            stored = self._rt.storage.load_annotations("analysis_state", state["state_id"])
            if any(a["annotation_id"] == annotation_id for a in stored):
                return state["state_id"]
        return None

    def _state_tag_names(self, state_id: str) -> set[str]:
        return {t["name"] for t in self._rt.storage.load_tags("analysis_state", state_id)}

    def remove_annotation(self, annotation_id: str) -> None:
        """Delete an annotation from pmprov, together with the tags that belonged to it.

        pmprov tags hang off the state, not the annotation. Within a session the
        adapter knows which tags an annotation added, and removes those no other
        annotation on the state still carries. For an annotation persisted in an
        earlier session that record is gone, so the tags the UI showed on it (the
        state's tags) are removed only when it was the last annotation on the
        state; otherwise they stay, since another annotation shows them too.
        """
        from models.annotations import AnnotatableType

        state_id = self._annotation_state(annotation_id)
        owned = self._persisted_tags.get(annotation_id, (None, None))[1]
        self._rt.remove_annotation(annotation_id)
        self._persisted_tags.pop(annotation_id, None)
        if state_id is None:
            return
        remaining = [a["annotation_id"] for a in self._rt.storage.load_annotations("analysis_state", state_id)]
        if owned is None:
            stale = self._state_tag_names(state_id) if not remaining else set()
        elif any(other not in self._persisted_tags for other in remaining):
            stale = set()  # an annotation of unknown ownership may still need them
        else:
            stale = owned - set().union(*(self._persisted_tags[o][1] for o in remaining)) if remaining else owned
        for name in stale:
            self._rt.untag(AnnotatableType.ANALYSIS_STATE, state_id, name)

    def update_annotation(self, annotation_id: str, annotation_dict: dict) -> None:
        """Replace an annotation's text and sync its tags in pmprov.

        Tags are the state's, so for an annotation from an earlier session the
        change is made against the tags the UI showed on it (the state's tags).
        """
        text = annotation_dict.get("note") or annotation_dict.get("title") or ""
        if not text:
            return

        from models.annotations import AnnotatableType

        self._rt.update_annotation(annotation_id, text)
        state_id = self._annotation_state(annotation_id)
        if state_id is None:
            return
        known = self._persisted_tags.get(annotation_id)
        old_names = known[1] if known else self._state_tag_names(state_id)
        new_names = self._tag_names(annotation_dict)
        for name in new_names - old_names:
            self._rt.tag(AnnotatableType.ANALYSIS_STATE, state_id, name)
        for name in old_names - new_names:
            self._rt.untag(AnnotatableType.ANALYSIS_STATE, state_id, name)
        self._persisted_tags[annotation_id] = (state_id, new_names)

    @staticmethod
    def _readable_params(raw_params: list[dict]) -> dict:
        """pmprov's parameter records as plain `name: value`.

        Drops references to input artifacts (the data a step ran on, not a
        setting) and the "function:" prefix on parameter ids, so the sidebar
        shows what the analyst chose, e.g. `year = 2008`.
        """
        params: dict = {}
        for record in raw_params:
            value = record.get("value")
            if isinstance(value, dict) and "value_type" in value:
                if value["value_type"] == "artifact_state_ref":
                    continue
                value = value.get("value")
            params[record["param_id"].split(":", 1)[-1]] = value
        return params

    def _bindings(self, state_id: str) -> dict[str, str]:
        """Variable name -> artifact version bound at *state_id* ({} before pmprov 0.8 / for old histories)."""
        loader = getattr(self._rt.storage, "load_state_bindings", None)
        return loader(state_id) if loader else {}

    def _restore(self, state_id: str, name: str) -> Any:
        """One variable of one state. pmprov < 0.8 cannot restore a single name, so it loads the state and picks it."""
        try:
            return self._rt.restore_state(state_id, names=[name]).variables.get(name)
        except TypeError:  # an older restore_state() without the names argument
            return self._rt.restore_state(state_id).variables.get(name)

    @staticmethod
    def _assigned_name(raw_line: str | None) -> str | None:
        """Name bound by a single-target ``name = call(...)`` step line."""
        if not raw_line:
            return None
        try:
            node = ast.parse(raw_line.strip()).body[0]
        except (SyntaxError, IndexError):
            return None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            return node.targets[0].id
        return None

    def _legacy_sources(self, state_id: str) -> dict[str, str]:
        """For a state recorded before pmprov 0.8 (no bindings): variable name ->
        output state of the newest step on the path that assigned it.

        A step's own output restores exactly even in old histories, and the
        namespace at a state is the latest output of each variable along its
        path, so this is exact (pmprov's old per-state restore was not).
        """
        graph = self._rt.storage.load_graph(self._rt._history.history_id)
        by_output = {s["output_state_id"]: s for s in graph["steps"]}
        sources: dict[str, str] = {}
        current = state_id
        while current in by_output:  # newest first: the first assignment of a name wins
            step = by_output[current]
            name = self._assigned_name(step.get("raw_line"))
            if name and name not in sources:
                sources[name] = step["output_state_id"]
            current = step["input_state_id"]
        return sources

    def snapshot_bindings(self, state_id: str) -> set[str]:
        """Names of the variables bound at *state_id*, without loading any data."""
        self.settle()
        bindings = self._bindings(state_id)
        return set(bindings) if bindings else set(self._legacy_sources(state_id))

    def snapshot(self, state_id: str, names: list[str] | None = None) -> dict[str, Any]:
        """The variables bound at *state_id*, exactly as they were (all, or just *names*).

        Works with every pmprov: 0.8+ records exact bindings per state; older
        pmprov (and histories recorded before 0.8) are rebuilt from the step
        that last assigned each variable, which is also exact but loads more.
        Names that are not bound there, or whose value pmprov could not load,
        are simply absent. Loaded values are cached by artifact version, so a
        frame that many states share (the raw event log) is read once. Treat
        the returned objects as read-only: they are shared with the cache.
        """
        self.settle()
        bindings = self._bindings(state_id)
        legacy = {} if bindings else self._legacy_sources(state_id)
        known = bindings or legacy
        wanted = list(known) if names is None else [n for n in names if n in known]
        variables: dict[str, Any] = {}
        for name in wanted:
            version = bindings[name] if bindings else f"{legacy[name]}:{name}"
            if version in self._values:
                self._values.move_to_end(version)
                variables[name] = self._values[version]
                continue
            source_state = state_id if bindings else legacy[name]
            value = self._restore(source_state, name)
            if value is not None:
                self._values[version] = value
                variables[name] = value
        while len(self._values) > _SNAPSHOT_CACHE_SIZE:
            self._values.popitem(last=False)
        return variables
