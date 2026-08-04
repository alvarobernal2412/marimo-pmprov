import type { ProvenanceNodeJson, ProvenanceTreeJson } from "../types";
import { tagChip } from "../components/tag-chip";

interface AnyModel {
  get(key: string): unknown;
}

function reproductionPath(tree: ProvenanceTreeJson, stateId: string): ProvenanceNodeJson[] {
  const path: ProvenanceNodeJson[] = [];
  let current: string | null = stateId;
  while (current) {
    const node: ProvenanceNodeJson = tree.nodes[current];
    path.unshift(node);
    current = node.parentStateId;
  }
  return path;
}

export function renderInspect(container: HTMLElement, model: AnyModel): void {
  container.innerHTML = "";
  const tree = model.get("tree") as ProvenanceTreeJson;
  const selection = (model.get("selection") as { node?: { pickedStateId?: string } }) ?? {};
  const pickedStateId = selection.node?.pickedStateId;
  if (pickedStateId === undefined) {
    const empty = document.createElement("div");
    empty.className = "pw-inspect-empty";
    empty.textContent = "Click a node in the Tree tab to inspect it here.";
    container.appendChild(empty);
    return;
  }
  const stateId = pickedStateId;
  const node = tree.nodes[stateId];

  const breadcrumb = document.createElement("div");
  breadcrumb.className = "pw-breadcrumb";
  breadcrumb.textContent = reproductionPath(tree, stateId)
    .map((n) => n.operation.commandName)
    .join(" -> ");
  container.appendChild(breadcrumb);

  const diffPane = document.createElement("div");
  diffPane.className = "pw-diff-pane";
  node.delta.columnsAdded.forEach((c) => {
    const line = document.createElement("div");
    line.className = "pw-diff-line pw-diff-added";
    line.textContent = `+ ${c.name}: ${c.dtype}`;
    diffPane.appendChild(line);
  });
  node.delta.columnsRemoved.forEach((c) => {
    const line = document.createElement("div");
    line.className = "pw-diff-line pw-diff-removed";
    line.textContent = `- ${c.name}: ${c.dtype}`;
    diffPane.appendChild(line);
  });
  const rowLine = document.createElement("div");
  rowLine.className = "pw-diff-line";
  rowLine.textContent = `rows: ${node.delta.rowCountBefore} -> ${node.delta.rowCountAfter}`;
  diffPane.appendChild(rowLine);
  container.appendChild(diffPane);

  const annotationPane = document.createElement("div");
  annotationPane.className = "pw-annotation-pane";
  node.annotations.forEach((a) => {
    const title = document.createElement("div");
    title.className = "pw-node-title";
    title.textContent = a.title;
    annotationPane.appendChild(title);
    const note = document.createElement("div");
    note.className = "pw-node-note";
    note.textContent = a.note;
    annotationPane.appendChild(note);
    const tags = document.createElement("div");
    tags.className = "pw-node-tags";
    a.tags.forEach((t) => tags.appendChild(tagChip(t)));
    annotationPane.appendChild(tags);
  });
  container.appendChild(annotationPane);
}
