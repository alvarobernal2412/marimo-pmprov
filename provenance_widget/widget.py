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

    def sidebar(self) -> ProvenanceWidget:
        return self.widget

    def tree_surface(self) -> ProvenanceWidget:
        return self.widget

    def commit_annotation(self, annotation_dict: dict) -> None:
        self.widget.commits = [*self.widget.commits, annotation_dict]

    def request_restore(self, tag: str) -> None:
        self.widget.restore_request = {"tag": tag}

    def acknowledge_restore(self) -> None:
        self.widget.restore_ack = {"acknowledged": True}
        self.widget.restore_request = {}
