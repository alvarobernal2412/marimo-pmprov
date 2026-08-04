import json

from provenance_widget.mock_source import MockProvenanceSource
from provenance_widget.serialize import tree_to_json


def test_tree_to_json_is_json_serializable():
    tree = MockProvenanceSource().get_tree()
    payload = tree_to_json(tree)
    json.dumps(payload)  # raises if not serializable


def test_tree_to_json_preserves_node_count_and_root():
    tree = MockProvenanceSource().get_tree()
    payload = tree_to_json(tree)
    assert payload["rootId"] == tree.root_id
    assert len(payload["nodes"]) == len(tree.nodes)


def test_tree_to_json_node_has_flat_operation_category_string():
    tree = MockProvenanceSource().get_tree()
    payload = tree_to_json(tree)
    node = payload["nodes"][tree.root_id]
    assert isinstance(node["operation"]["category"], str)
    assert node["operation"]["category"] == "DATA_LOADING"


def test_tree_to_json_node_includes_annotations_and_artifacts():
    tree = MockProvenanceSource().get_tree()
    payload = tree_to_json(tree)
    node = payload["nodes"]["s1"]
    assert node["annotations"][0]["title"] == "Truncate outliers"
    assert node["annotations"][0]["tags"][0]["name"] == "cleaning"
    assert node["annotations"][0]["artifacts"][0]["granularity"] == "column"
