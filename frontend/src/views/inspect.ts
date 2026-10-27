import type { ProvenanceNodeJson, ProvenanceTreeJson } from "../types";
import { CATEGORY_COLOR } from "../types";
import { tagChip } from "../components/tag-chip";
import { formatTimestamp } from "../annotations";

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

function line(className: string, text: string): HTMLElement {
  const el = document.createElement("div");
  el.className = className;
  el.textContent = text;
  return el;
}

// Details of one analysis state: what ran, what it changed, the parameters it
// ran with, how to reproduce it, and the annotations attached to it. Shows the
// state passed in, or else the one picked in the tree.
export function renderInspect(container: HTMLElement, model: AnyModel, stateIdOverride?: string | null): void {
  container.innerHTML = "";
  const tree = model.get("tree") as ProvenanceTreeJson;
  const selection = (model.get("selection") as { node?: { pickedStateId?: string } }) ?? {};
  const stateId = stateIdOverride ?? selection.node?.pickedStateId;
  const node = stateId ? tree.nodes[stateId] : undefined;
  if (!node) {
    container.appendChild(line("pw-inspect-empty", "Select a step to see its details."));
    return;
  }

  const head = document.createElement("div");
  head.className = "pw-inspect-head";
  head.style.setProperty("--category-color", CATEGORY_COLOR[node.operation.category] ?? "#64748B");
  head.appendChild(line("pw-inspect-title", node.operation.name));
  head.appendChild(line("pw-inspect-command", `${node.operation.commandName} · ${node.operation.category.replace("_", " ").toLowerCase()}`));
  container.appendChild(head);

  const changes = document.createElement("div");
  changes.className = "pw-inspect-chips";
  node.delta.columnsAdded.forEach((c) => changes.appendChild(line("pw-diff-added pw-inspect-chip", `+ ${c.name}`)));
  node.delta.columnsRemoved.forEach((c) => changes.appendChild(line("pw-diff-removed pw-inspect-chip", `- ${c.name}`)));
  changes.appendChild(line("pw-inspect-chip", `rows ${node.delta.rowCountBefore} → ${node.delta.rowCountAfter}`));
  container.appendChild(changes);

  const params = Object.entries(node.params);
  if (params.length > 0) {
    const paramRow = document.createElement("div");
    paramRow.className = "pw-inspect-chips";
    params.forEach(([key, value]) => paramRow.appendChild(line("pw-inspect-chip pw-inspect-param", `${key} = ${JSON.stringify(value)}`)));
    container.appendChild(paramRow);
  }

  const path = reproductionPath(tree, node.stateId);
  if (path.length > 1) {
    const repro = line("pw-inspect-repro", path.map((n) => n.operation.commandName).join(" → "));
    repro.title = "Steps that produce this state, in order";
    container.appendChild(repro);
  }

  const annotations = document.createElement("div");
  annotations.className = "pw-annotation-pane";
  if (node.annotations.length === 0) {
    annotations.appendChild(line("pw-node-no-annotations", "No annotations on this step."));
  }
  node.annotations.forEach((a) => {
    const row = document.createElement("div");
    row.className = "pw-inspect-annotation";
    const top = document.createElement("div");
    top.className = "pw-ann-line";
    top.appendChild(line("pw-ann-title pw-ann-title-wrap", a.title));
    const time = line("pw-timestamp", formatTimestamp(a.timestamp));
    time.title = a.timestamp;
    top.appendChild(time);
    row.appendChild(top);
    if (a.note && a.note !== a.title) row.appendChild(line("pw-annotation-note", a.note));
    if (a.tags.length > 0) {
      const tags = document.createElement("div");
      tags.className = "pw-ann-tags";
      a.tags.forEach((t) => tags.appendChild(tagChip(t)));
      row.appendChild(tags);
    }
    annotations.appendChild(row);
  });
  container.appendChild(annotations);
}
