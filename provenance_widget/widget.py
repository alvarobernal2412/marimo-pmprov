from __future__ import annotations

import pathlib
import threading

import anywidget
import traitlets

from provenance_widget.interfaces import EmptyProvenanceSource, ProvenanceSource
from provenance_widget.serialize import tree_to_json

_STATIC_DIR = pathlib.Path(__file__).parent / "static"


class ProvenanceWidget(anywidget.AnyWidget):
    _esm = _STATIC_DIR / "widget.js"
    _css = _STATIC_DIR / "widget.css"

    tree = traitlets.Dict({}).tag(sync=True)
    mode = traitlets.Unicode("student").tag(sync=True)
    active_tab = traitlets.Unicode("curated").tag(sync=True)
    visible_tabs = traitlets.List(["curated", "tree", "config"]).tag(sync=True)
    selection = traitlets.Dict({}).tag(sync=True)
    commits = traitlets.List([]).tag(sync=True)
    restore_request = traitlets.Dict({}).tag(sync=True)
    restore_ack = traitlets.Dict({}).tag(sync=True)


_AUTO_REFRESH_INTERVAL_SECONDS = 0.75


class ProvenancePanel:
    """Python-side façade wrapping one ProvenanceWidget instance."""

    def __init__(
        self,
        source: ProvenanceSource | None = None,
        mode: str = "student",
        auto_refresh: bool = True,
        tabs: list[str] | None = None,
    ):
        self._source = source if source is not None else EmptyProvenanceSource()
        visible_tabs = tabs if tabs is not None else ["curated", "tree", "config"]
        active_tab = visible_tabs[0] if visible_tabs else "curated"
        self.widget = ProvenanceWidget(
            tree=tree_to_json(self._source.get_tree()),
            mode=mode,
            visible_tabs=visible_tabs,
            active_tab=active_tab,
        )
        self._auto_refresh_stop: threading.Event | None = None
        self._persisted_commit_count = 0
        self.widget.observe(self._on_commits_changed, names="commits")
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
            try:
                self._source.persist_annotation(commit.get("stateId"), commit.get("annotation") or {})
            except Exception:
                pass  # a persistence failure shouldn't break the widget's own UI state

    def commit_annotation(self, annotation_dict: dict, state_id: str | None = None) -> None:
        """Record an annotation, associating it with an analysis state.

        Pass state_id explicitly to force it. Otherwise this resolves it
        from the annotation's own targeted artifact(s), via the source's
        `state_for_artifact()` — the state that contains/produced the
        artifact the annotation is actually about. Falls back to "python"
        if no artifact resolves (e.g. a general note not tied to output).
        """
        if state_id is None:
            for ref in annotation_dict.get("artifacts") or []:
                resolved = self._source.state_for_artifact(ref.get("artifactId", ""))
                if resolved:
                    state_id = resolved
                    break
        if state_id is None:
            state_id = "python"
        self.widget.commits = [*self.widget.commits, {"stateId": state_id, "annotation": annotation_dict}]

    def request_restore(self, tag: str) -> None:
        self.widget.restore_request = {"tag": tag}

    def acknowledge_restore(self) -> None:
        self.widget.restore_ack = {"acknowledged": True}
        self.widget.restore_request = {}
