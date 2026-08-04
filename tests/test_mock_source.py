from provenance_widget.interfaces import StepCategory
from provenance_widget.mock_source import MockProvenanceSource


def test_mock_tree_has_import_root():
    tree = MockProvenanceSource().get_tree()
    root = tree.nodes[tree.root_id]
    assert root.operation.category == StepCategory.DATA_LOADING
    assert root.parent_state_id is None


def test_mock_tree_branches_into_rule_induction_and_conformance():
    tree = MockProvenanceSource().get_tree()
    categories = {n.operation.category for n in tree.nodes.values()}
    assert StepCategory.CLEANING in categories
    assert StepCategory.FEATURE_ENGINEERING in categories
    branch_names = set(tree.branches.values())
    assert len(branch_names) >= 2


def test_mock_tree_nodes_carry_annotations_with_tags_and_artifacts():
    tree = MockProvenanceSource().get_tree()
    annotated = [n for n in tree.nodes.values() if n.annotations]
    assert annotated, "expected at least one annotated node"
    ann = annotated[0].annotations[0]
    assert ann.tags
    assert ann.artifacts
    assert ann.artifacts[0].granularity in {
        "dataset", "column", "row_subset", "cell", "chart_selection",
    }


def test_get_tree_is_deterministic_across_calls():
    source = MockProvenanceSource()
    tree_a = source.get_tree()
    tree_b = source.get_tree()
    assert set(tree_a.nodes.keys()) == set(tree_b.nodes.keys())
