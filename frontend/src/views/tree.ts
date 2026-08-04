import type { ProvenanceNodeJson, ProvenanceTreeJson } from "../types";
import { nodeCard } from "../components/node-card";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

function collectArtifacts(tree: ProvenanceTreeJson): { id: string; name: string }[] {
  const seen = new Map<string, string>();
  for (const node of Object.values(tree.nodes)) {
    for (const annotation of node.annotations) {
      for (const ref of annotation.artifacts) {
        seen.set(ref.artifactId, ref.artifactName);
      }
    }
  }
  return [...seen.entries()].map(([id, name]) => ({ id, name }));
}

function nodeTouchesArtifact(node: ProvenanceNodeJson, artifactId: string): boolean {
  return node.annotations.some((a) => a.artifacts.some((r) => r.artifactId === artifactId));
}

export function renderTree(container: HTMLElement, model: AnyModel): void {
  container.innerHTML = "";
  const tree = model.get("tree") as ProvenanceTreeJson;

  const breadcrumb = document.createElement("div");
  breadcrumb.className = "pw-breadcrumb";
  container.appendChild(breadcrumb);

  const legend = document.createElement("div");
  legend.className = "pw-artifact-legend";
  let activeArtifact: string | null = null;
  collectArtifacts(tree).forEach((artifact) => {
    const entry = document.createElement("button");
    entry.className = "pw-legend-entry";
    entry.textContent = artifact.name;
    entry.addEventListener("click", () => {
      activeArtifact = activeArtifact === artifact.id ? null : artifact.id;
      applyDimming();
    });
    legend.appendChild(entry);
  });
  container.appendChild(legend);

  const columnsWrap = document.createElement("div");
  columnsWrap.className = "pw-columns";
  container.appendChild(columnsWrap);

  const path: string[] = [tree.rootId];

  function applyDimming(): void {
    columnsWrap.querySelectorAll<HTMLElement>(".pw-node-card").forEach((card) => {
      const stateId = card.dataset.stateId;
      if (!stateId) return;
      const node = tree.nodes[stateId];
      const dim = activeArtifact !== null && !nodeTouchesArtifact(node, activeArtifact);
      card.classList.toggle("pw-dimmed", dim);
    });
  }

  function renderBreadcrumb(): void {
    breadcrumb.innerHTML = "";
    path.forEach((stateId, i) => {
      const node = tree.nodes[stateId];
      const crumb = document.createElement("span");
      crumb.className = "pw-breadcrumb-item";
      crumb.textContent = node.annotations[0]?.title ?? node.operation.name;
      breadcrumb.appendChild(crumb);
      if (i < path.length - 1) {
        const sep = document.createElement("span");
        sep.className = "pw-breadcrumb-sep";
        sep.textContent = ">";
        breadcrumb.appendChild(sep);
      }
    });
  }

  function renderColumns(): void {
    columnsWrap.innerHTML = "";
    path.forEach((stateId, columnIndex) => {
      const column = document.createElement("div");
      column.className = "pw-column";
      const children =
        columnIndex === 0
          ? [tree.nodes[stateId]]
          : Object.values(tree.nodes).filter((n) => n.parentStateId === path[columnIndex - 1]);
      children.forEach((node) => {
        const card = nodeCard(node, {
          onSelect: () => {
            if (node.stateId === path[columnIndex]) return;
            path.splice(columnIndex + 1, path.length, node.stateId);
            model.set("selection", { pickedStateId: node.stateId });
            model.save_changes();
            renderBreadcrumb();
            renderColumns();
            applyDimming();
          },
        });
        column.appendChild(card);
      });
      columnsWrap.appendChild(column);
    });
    applyDimming();
  }

  renderBreadcrumb();
  renderColumns();
}
