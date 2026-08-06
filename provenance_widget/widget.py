from __future__ import annotations

import pathlib

import anywidget
import traitlets

from provenance_widget.interfaces import ProvenanceSource
from provenance_widget.serialize import tree_to_json

_STATIC_DIR = pathlib.Path(__file__).parent / "static"


class ProvenanceWidget(anywidget.AnyWidget):
    _esm = _STATIC_DIR / "widget.js"
    _css = _STATIC_DIR / "widget.css"

    tree = traitlets.Dict({}).tag(sync=True)
    mode = traitlets.Unicode("student").tag(sync=True)
    active_tab = traitlets.Unicode("curated").tag(sync=True)
    selection = traitlets.Dict({}).tag(sync=True)
    commits = traitlets.List([]).tag(sync=True)
    restore_request = traitlets.Dict({}).tag(sync=True)
    restore_ack = traitlets.Dict({}).tag(sync=True)


class ProvenancePanel:
    """Python-side façade wrapping one ProvenanceWidget instance."""

    def __init__(self, source: ProvenanceSource, mode: str = "student"):
        self._source = source
        self.widget = ProvenanceWidget(tree=tree_to_json(source.get_tree()), mode=mode)

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
        opposed to MockProvenanceSource's fixed snapshot), call this after
        new steps have been recorded so the sidebar reflects them.
        """
        self.widget.tree = tree_to_json(self._source.get_tree())
        # Belt-and-braces: under marimo (unlike Jupyter), a Dict trait set
        # from a cell that isn't itself re-running doesn't reliably push a
        # fresh sync message to an already-displayed widget — force one.
        self.widget.send_state(["tree"])

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
