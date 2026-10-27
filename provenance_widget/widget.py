from __future__ import annotations

import pathlib
import threading
import warnings

import anywidget
import traitlets

from provenance_widget.interfaces import EmptyProvenanceSource, ProvenanceSource
from provenance_widget.serialize import tree_to_json
from provenance_widget.snapshot import Snapshot

_STATIC_DIR = pathlib.Path(__file__).parent / "static"


class ProvenanceWidget(anywidget.AnyWidget):
    _esm = _STATIC_DIR / "widget.js"
    _css = _STATIC_DIR / "widget.css"

    tree = traitlets.Dict({}).tag(sync=True)
    mode = traitlets.Unicode("analyst").tag(sync=True)
    active_tab = traitlets.Unicode("curated").tag(sync=True)
    visible_tabs = traitlets.List(["curated", "tree"]).tag(sync=True)
    # The Tree tab is opt-in and fixed at construction (ProvenancePanel(show_tree=...)).
    show_tree = traitlets.Bool(False).tag(sync=True)
    selection = traitlets.Dict({}).tag(sync=True)
    commits = traitlets.List([]).tag(sync=True)
    restore_request = traitlets.Dict({}).tag(sync=True)
    restore_ack = traitlets.Dict({}).tag(sync=True)
    # Annotation ids hidden by the user, and id -> replacement annotation for
    # edited ones. Overlays on top of tree/commits so they work uniformly for
    # annotations that live on tree nodes and ones committed from the widget.
    # commit annotation id -> id the source stored it under. The source's copy
    # comes back in the tree too; the frontend shows the commit's version only.
    annotation_aliases = traitlets.Dict({}).tag(sync=True)
    removed_annotations = traitlets.List([]).tag(sync=True)
    edited_annotations = traitlets.Dict({}).tag(sync=True)
    # Reviewer replay cursor: {"stateId", "params", "isLatest"} — the analysis
    # state the reviewer has stepped to. Empty until the first step.
    replay = traitlets.Dict({}).tag(sync=True)


_AUTO_REFRESH_INTERVAL_SECONDS = 0.75
_VALID_MODES = ("analyst", "reviewer")


class ProvenancePanel:
    """Python-side façade wrapping one ProvenanceWidget instance.

    `mode` ("analyst" or "reviewer") is fixed at construction: it decides
    which UI exists (annotation composer/edit/delete vs. read-only replay
    stepper), so a reader of the notebook cannot switch themselves into it.
    The Tree tab is hidden unless `show_tree=True` (or `tabs` includes
    "tree"); like the persona, it can't be changed from the UI.
    """

    def __init__(
        self,
        source: ProvenanceSource | None = None,
        mode: str = "analyst",
        auto_refresh: bool = True,
        tabs: list[str] | None = None,
        show_tree: bool | None = None,
    ):
        self._source = source if source is not None else EmptyProvenanceSource()
        if mode == "student":  # the analyst persona's former name
            warnings.warn(
                'mode="student" is deprecated; use mode="analyst"', DeprecationWarning, stacklevel=2
            )
            mode = "analyst"
        if mode not in _VALID_MODES:
            raise ValueError(f"mode must be one of {_VALID_MODES}, got {mode!r}")
        self._mode = mode
        # Hidden by default. An explicit `tabs` that names "tree" counts as
        # opting in.
        if show_tree is None:
            show_tree = tabs is not None and "tree" in tabs
        self._show_tree = show_tree
        # "config" was a tab in earlier versions; it no longer exists.
        visible_tabs = [t for t in tabs if t != "config"] if tabs is not None else ["curated", "tree"]
        active_tab = visible_tabs[0] if visible_tabs else "curated"
        self.widget = ProvenanceWidget(
            tree=tree_to_json(self._source.get_tree()),
            mode=mode,
            visible_tabs=visible_tabs,
            active_tab=active_tab,
            show_tree=show_tree,
        )
        self._auto_refresh_stop: threading.Event | None = None
        self._persisted_commit_count = 0
        # frontend annotation id -> id the source assigned when persisting it
        self._source_ids: dict[str, str] = {}
        self._handled_removals: set[str] = set()
        self._handled_edits: dict[str, dict] = {}
        self.widget.observe(self._on_commits_changed, names="commits")
        self.widget.observe(self._on_removed_changed, names="removed_annotations")
        self.widget.observe(self._on_edited_changed, names="edited_annotations")
        self.widget.observe(self._on_mode_changed, names="mode")
        self.widget.observe(self._on_show_tree_changed, names="show_tree")
        # Sources like PmprovAdapter grow on their own as the notebook runs
        # (a live pmprov RuntimeTracker being traced in the background) — for
        # those, poll and push updates automatically so tracked cells don't
        # need to call refresh() themselves. Sources with a fixed snapshot
        # (MockProvenanceSource, EmptyProvenanceSource) have no settle()
        # method and are skipped — there's nothing new to poll for.
        if auto_refresh and hasattr(self._source, "settle"):
            self._start_auto_refresh()

    def _start_auto_refresh(self) -> None:
        stop = threading.Event()
        self._auto_refresh_stop = stop

        def poll() -> None:
            while not stop.wait(_AUTO_REFRESH_INTERVAL_SECONDS):
                try:
                    self.refresh()
                except Exception:
                    pass  # widget/comm may already be closed (kernel shutdown, cell re-run)

        threading.Thread(target=poll, daemon=True).start()

    def stop_auto_refresh(self) -> None:
        """Stop the background poll thread, if one is running.

        Each ProvenancePanel(...) call with an auto-refreshing source starts
        its own thread; re-running that cell during interactive development
        leaks the previous one unless this is called first. Not needed for
        a notebook that constructs the panel once per session.
        """
        if self._auto_refresh_stop is not None:
            self._auto_refresh_stop.set()
            self._auto_refresh_stop = None

    @property
    def source(self) -> ProvenanceSource:
        return self._source

    def sidebar(self) -> ProvenanceWidget:
        return self.widget

    def tree_surface(self) -> ProvenanceWidget:
        return self.widget

    def refresh(self) -> None:
        """Re-pull the tree from the source.

        For sources whose history grows over time (e.g. a live pmprov
        RuntimeTracker being driven by an in-progress notebook run, as
        opposed to MockProvenanceSource's fixed snapshot), this picks up
        newly recorded steps. Called automatically by the auto-refresh
        thread for sources that support it (see __init__); safe to call
        manually too, e.g. to force an immediate update instead of waiting
        for the next poll.
        """
        self.widget.tree = tree_to_json(self._source.get_tree())
        # Belt-and-braces: under marimo (unlike Jupyter), a Dict trait set
        # from a cell that isn't itself re-running doesn't reliably push a
        # fresh sync message to an already-displayed widget — force one.
        self.widget.send_state(["tree"])

    def _on_commits_changed(self, change: dict) -> None:
        """Persist newly added commits through the source, if it supports it.

        Fires for every growth of the `commits` trait — whether it came from
        `commit_annotation()` below or the sidebar's JS composer setting the
        trait directly — so both write paths persist through one place.
        Sources without a `persist_annotation()` method (MockProvenanceSource,
        EmptyProvenanceSource) are left exactly as ephemeral as before.
        """
        commits = change["new"] or []
        new_commits = commits[self._persisted_commit_count:]
        self._persisted_commit_count = len(commits)
        if not hasattr(self._source, "persist_annotation"):
            return
        for commit in new_commits:
            annotation = commit.get("annotation") or {}
            try:
                source_id = self._source.persist_annotation(commit.get("stateId"), annotation)
            except Exception:
                continue  # a persistence failure shouldn't break the widget's own UI state
            if source_id and annotation.get("annotationId"):
                self._source_ids[annotation["annotationId"]] = source_id
                self.widget.annotation_aliases = {
                    **self.widget.annotation_aliases,
                    annotation["annotationId"]: source_id,
                }

    def _on_mode_changed(self, change: dict) -> None:
        # The persona is fixed at construction; undo any frontend attempt to change it.
        if change["new"] != self._mode:
            self.widget.mode = self._mode

    def _on_show_tree_changed(self, change: dict) -> None:
        # Like the persona, fixed at construction; undo any frontend change.
        if change["new"] != self._show_tree:
            self.widget.show_tree = self._show_tree

    def _on_removed_changed(self, change: dict) -> None:
        removed = change["new"] or []
        if self._mode == "reviewer":  # read-only persona: always empty
            if removed:
                self.widget.removed_annotations = []
            return
        for annotation_id in removed:
            if annotation_id in self._handled_removals:
                continue
            self._handled_removals.add(annotation_id)
            source_id = self._source_ids.get(annotation_id, annotation_id)
            if hasattr(self._source, "remove_annotation"):
                try:
                    self._source.remove_annotation(source_id)
                except Exception:
                    pass
            if source_id != annotation_id and source_id not in removed:
                # the source's own copy of it shows up in the tree under its id
                self._handled_removals.add(source_id)
                self.widget.removed_annotations = [*removed, source_id]

    def _on_edited_changed(self, change: dict) -> None:
        edited = change["new"] or {}
        if self._mode == "reviewer":
            if edited:
                self.widget.edited_annotations = {}
            return
        for annotation_id, annotation in edited.items():
            if self._handled_edits.get(annotation_id) == annotation:
                continue
            self._handled_edits[annotation_id] = annotation
            if hasattr(self._source, "update_annotation"):
                try:
                    self._source.update_annotation(
                        self._source_ids.get(annotation_id, annotation_id), annotation
                    )
                except Exception:
                    pass

    def remove_annotation(self, annotation_id: str) -> None:
        """Remove an annotation (hides it in the UI and deletes it in the source)."""
        if annotation_id not in self.widget.removed_annotations:
            self.widget.removed_annotations = [*self.widget.removed_annotations, annotation_id]

    def update_annotation(self, annotation_id: str, annotation_dict: dict) -> None:
        """Replace an annotation's content (title/note/tags) everywhere it shows."""
        self.widget.edited_annotations = {**self.widget.edited_annotations, annotation_id: annotation_dict}

    @property
    def latest_state_id(self) -> str | None:
        """The most recently recorded analysis state (last node in time order)."""
        nodes = self.widget.tree.get("nodes") or {}
        return next(reversed(nodes), None) if nodes else None

    @property
    def cursor_state_id(self) -> str | None:
        """The state the reviewer has stepped to, or None before any replay."""
        return self.widget.replay.get("stateId")

    def go_to(self, state_id: str) -> None:
        """Move the replay cursor to a state (what the sidebar's stepper does)."""
        node = (self.widget.tree.get("nodes") or {}).get(state_id)
        if node is None:
            raise KeyError(state_id)
        self.widget.replay = {
            "stateId": state_id,
            "params": node["params"],
            "isLatest": state_id == self.latest_state_id,
        }

    def go_latest(self) -> None:
        latest = self.latest_state_id
        if latest is not None:
            self.go_to(latest)

    def commit_annotation(self, annotation_dict: dict, state_id: str | None = None) -> None:
        """Record an annotation, associating it with an analysis state.

        Pass state_id explicitly to force it. Otherwise this resolves it
        from the annotation's own targeted artifact(s), via the source's
        `state_for_artifact()` — the state that contains/produced the
        artifact the annotation is actually about. Falls back to the latest
        recorded state if no artifact resolves (a note about the whole
        analysis), and to "python" only when nothing is recorded yet.
        """
        if state_id is None:
            for ref in annotation_dict.get("artifacts") or []:
                resolved = self._source.state_for_artifact(ref.get("artifactId", ""))
                if resolved:
                    state_id = resolved
                    break
        if state_id is None:
            # Not about a specific output: it's about the analysis as a whole,
            # so attach it to the latest state — an immutable snapshot of the
            # analysis as it stands now. "python" only if nothing is recorded yet.
            state_id = self.latest_state_id or "python"
        self.widget.commits = [*self.widget.commits, {"stateId": state_id, "annotation": annotation_dict}]

    def request_restore(self, tag: str) -> None:
        self.widget.restore_request = {"tag": tag}

    def acknowledge_restore(self) -> None:
        self.widget.restore_ack = {"acknowledged": True}
        self.widget.restore_request = {}

    def _cursor_from(self, replay: dict) -> str | None:
        """The recorded state a reviewer is looking at.

        Reviewers always look at the recorded history (the latest recorded
        state until they step elsewhere): a freshly opened notebook's live
        variables are not that history. Analysts work on the live analysis,
        so their cursor is None.
        """
        if self._mode != "reviewer":
            return None
        nodes = self.widget.tree.get("nodes") or {}
        state_id = replay.get("stateId")
        if state_id in nodes:
            return state_id
        return self.latest_state_id

    def on_replay(self, callback) -> None:
        """Call `callback(state_id)` whenever the reviewer steps to another
        recorded state (always the state itself, `Latest` included). Analysts
        get None."""
        self.widget.observe(lambda change: callback(self._cursor_from(change["new"])), names="replay")

    def reactive_cursor(self, state_factory):
        """Bind the replay cursor to a marimo state and return its getter.

        Pass `mo.state`. A cell that calls the getter re-runs each time the
        reviewer steps (or clicks Replay on an annotation), so notebook cells
        can render the snapshot for that step. Starts at the latest recorded
        state for a reviewer.
        """
        get_cursor, set_cursor = state_factory(self._cursor_from(self.widget.replay))
        self.on_replay(set_cursor)
        return get_cursor

    def snapshot(self, state_id: str | None = None) -> Snapshot:
        """The whole analysis at *state_id*, or a live snapshot when None.

        Needs a source that implements `snapshot(state_id, names)` and
        `snapshot_bindings(state_id)` (PmprovAdapter does, with pmprov >= 0.8).
        Other sources give an empty snapshot, so every variable reads as
        "not computed yet". Values load lazily, per name.
        """
        if state_id is None:
            return Snapshot(state_id=None)
        node = (self.widget.tree.get("nodes") or {}).get(state_id, {})
        bound: frozenset[str] | None = None
        error: str | None = None
        loader = None
        if hasattr(self._source, "snapshot"):
            source = self._source

            def loader(names: list[str]) -> dict:
                try:
                    return source.snapshot(state_id, names)
                except Exception:
                    return {}

            if hasattr(source, "snapshot_bindings"):
                try:
                    bound = frozenset(source.snapshot_bindings(state_id))
                except Exception as exc:  # e.g. a pmprov too old to record bindings
                    error = f"{type(exc).__name__}: {exc}"
        nodes = self.widget.tree.get("nodes") or {}
        path: list[dict] = []
        current = state_id
        while current in nodes:
            path.append(nodes[current])
            current = nodes[current].get("parentStateId")
        # settings in force at this state: the latest value of each parameter
        # along the path (e.g. the filter chosen several steps earlier)
        params: dict = {}
        for path_node in reversed(path):
            params.update(path_node.get("params") or {})
        path_length = len(path)
        return Snapshot(
            state_id=state_id,
            bound=bound,
            error=error,
            loader=loader,
            operation=(node.get("operation") or {}).get("name"),
            params=params,
            step=path_length or None,
        )
