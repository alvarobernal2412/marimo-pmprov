from __future__ import annotations

from dataclasses import asdict

from provenance_widget.interfaces import ProvenanceTree


def tree_to_json(tree: ProvenanceTree) -> dict:
    nodes = {}
    for state_id, node in tree.nodes.items():
        node_dict = asdict(node)
        node_dict["operation"]["category"] = node.operation.category.value
        nodes[state_id] = {
            "stateId": node_dict["state_id"],
            "parentStateId": node_dict["parent_state_id"],
            "branchId": node_dict["branch_id"],
            "operation": {
                "operationId": node_dict["operation"]["operation_id"],
                "name": node_dict["operation"]["name"],
                "operationType": node_dict["operation"]["operation_type"],
                "commandName": node_dict["operation"]["command_name"],
                "category": node_dict["operation"]["category"],
            },
            "params": node_dict["params"],
            "delta": {
                "columnsAdded": node_dict["delta"]["columns_added"],
                "columnsRemoved": node_dict["delta"]["columns_removed"],
                "rowCountBefore": node_dict["delta"]["row_count_before"],
                "rowCountAfter": node_dict["delta"]["row_count_after"],
                "summary": node.delta.summary(),
            },
            "annotations": [
                {
                    "annotationId": a["annotation_id"],
                    "title": a["title"],
                    "note": a["note"],
                    "tags": a["tags"],
                    "artifacts": [
                        {
                            "artifactId": ar["artifact_id"],
                            "artifactName": ar["artifact_name"],
                            "granularity": ar["granularity"],
                            "detail": ar["detail"],
                        }
                        for ar in a["artifacts"]
                    ],
                    "author": a["author"],
                    "timestamp": a["timestamp"],
                }
                for a in node_dict["annotations"]
            ],
        }
    return {
        "rootId": tree.root_id,
        "branches": tree.branches,
        "nodes": nodes,
    }
