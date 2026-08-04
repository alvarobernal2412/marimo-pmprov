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

  const header = document.createElement("div");
  header.className = "pw-tree-header";
  const title = document.createElement("div");
  title.className = "pw-tree-title";
  title.textContent = "Curated History — Provenance Tree";
  header.appendChild(title);
  const caption = document.createElement("div");
  caption.className = "pw-tree-caption";
  caption.textContent =
    "Click a card to drill into its branch. Use the legend below to highlight everything that touches one artifact.";
  header.appendChild(caption);
  container.appendChild(header);

  const breadcrumb = document.createElement("div");
  breadcrumb.className = "pw-breadcrumb";
  container.appendChild(breadcrumb);

  const artifacts = collectArtifacts(tree);
  let activeArtifact: string | null = null;
  if (artifacts.length === 0) {
    const legendEmpty = document.createElement("div");
    legendEmpty.className = "pw-legend-empty";
    legendEmpty.textContent = "No tagged artifacts yet";
    container.appendChild(legendEmpty);
  } else {
    const legend = document.createElement("div");
    legend.className = "pw-artifact-legend";
    artifacts.forEach((artifact) => {
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
  }

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
    // Render one column per path entry (already-selected nodes) plus one
    // trailing preview column showing the children of the deepest selection —
    // ready for the next click. Column 0 always shows just the root.
    for (let columnIndex = 0; columnIndex <= path.length; columnIndex++) {
      const children =
        columnIndex === 0
          ? [tree.nodes[path[0]]]
          : Object.values(tree.nodes).filter((n) => n.parentStateId === path[columnIndex - 1]);
      if (columnIndex > 0 && children.length === 0) break;

      const column = document.createElement("div");
      column.className = "pw-column";
      children.forEach((node) => {
        const card = nodeCard(node, {
          onSelect: () => {
            path.splice(columnIndex, path.length, node.stateId);
            const current = (model.get("selection") as Record<string, unknown>) ?? {};
            model.set("selection", { ...current, node: { pickedStateId: node.stateId } });
            model.save_changes();
            renderBreadcrumb();
            renderColumns();
            applyDimming();
          },
        });
        column.appendChild(card);
      });
      columnsWrap.appendChild(column);
    }
    applyDimming();
  }

  renderBreadcrumb();
  renderColumns();
}
