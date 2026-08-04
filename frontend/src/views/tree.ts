import type { ProvenanceNodeJson, ProvenanceTreeJson } from "../types";
import { nodeCard } from "../components/node-card";
import { renderInspect } from "./inspect";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

interface ArtifactOption {
  id: string;
  name: string;
}

function collectArtifacts(tree: ProvenanceTreeJson): ArtifactOption[] {
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

function collectTags(tree: ProvenanceTreeJson): string[] {
  const seen = new Set<string>();
  for (const node of Object.values(tree.nodes)) {
    for (const annotation of node.annotations) {
      for (const tag of annotation.tags) seen.add(tag.name);
    }
  }
  return [...seen].sort();
}

function nodeTouchesArtifact(node: ProvenanceNodeJson, artifactId: string): boolean {
  return node.annotations.some((a) => a.artifacts.some((r) => r.artifactId === artifactId));
}

function nodeHasTag(node: ProvenanceNodeJson, tagName: string): boolean {
  return node.annotations.some((a) => a.tags.some((t) => t.name === tagName));
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
    "Click a card to drill into its branch and inspect it. Use the filters below to spotlight matching steps — the rest collapse to a single line.";
  header.appendChild(caption);
  container.appendChild(header);

  const activeTags = new Set<string>();
  let activeArtifact: string | null = null;

  const filterBar = document.createElement("div");
  filterBar.className = "pw-filter-bar";
  container.appendChild(filterBar);

  const tagFilterRow = document.createElement("div");
  tagFilterRow.className = "pw-filter-row";
  const tagFilterLabel = document.createElement("span");
  tagFilterLabel.className = "pw-filter-label";
  tagFilterLabel.textContent = "Tags";
  tagFilterRow.appendChild(tagFilterLabel);
  filterBar.appendChild(tagFilterRow);

  const artifactFilterRow = document.createElement("div");
  artifactFilterRow.className = "pw-filter-row";
  const artifactFilterLabel = document.createElement("span");
  artifactFilterLabel.className = "pw-filter-label";
  artifactFilterLabel.textContent = "Linked artifact";
  artifactFilterRow.appendChild(artifactFilterLabel);
  filterBar.appendChild(artifactFilterRow);

  const breadcrumb = document.createElement("div");
  breadcrumb.className = "pw-breadcrumb";
  container.appendChild(breadcrumb);

  const columnsScroll = document.createElement("div");
  columnsScroll.className = "pw-columns-scroll";
  container.appendChild(columnsScroll);

  const columnsWrap = document.createElement("div");
  columnsWrap.className = "pw-columns";
  columnsScroll.appendChild(columnsWrap);

  const inspectPane = document.createElement("div");
  inspectPane.className = "pw-tree-inspect-pane";
  const inspectPaneLabel = document.createElement("div");
  inspectPaneLabel.className = "pw-tree-inspect-pane-label";
  inspectPaneLabel.textContent = "Inspect";
  inspectPane.appendChild(inspectPaneLabel);
  const inspectPaneBody = document.createElement("div");
  inspectPane.appendChild(inspectPaneBody);
  container.appendChild(inspectPane);

  const path: string[] = [tree.rootId];

  function nodeMatchesFilters(node: ProvenanceNodeJson): boolean {
    const tagOk = activeTags.size === 0 || [...activeTags].some((t) => nodeHasTag(node, t));
    const artifactOk = activeArtifact === null || nodeTouchesArtifact(node, activeArtifact);
    return tagOk && artifactOk;
  }

  function filtersActive(): boolean {
    return activeTags.size > 0 || activeArtifact !== null;
  }

  function renderInspectPane(): void {
    const selection = (model.get("selection") as { node?: { pickedStateId?: string } }) ?? {};
    if (selection.node?.pickedStateId === undefined) {
      inspectPaneBody.classList.add("pw-tree-inspect-pane-empty");
      inspectPaneBody.textContent = "Click a card above to inspect it here.";
      return;
    }
    inspectPaneBody.classList.remove("pw-tree-inspect-pane-empty");
    renderInspect(inspectPaneBody, model);
  }

  function renderTagFilters(): void {
    tagFilterRow.querySelectorAll(".pw-filter-chip").forEach((el) => el.remove());
    const tags = collectTags(tree);
    if (tags.length === 0) {
      const empty = document.createElement("span");
      empty.className = "pw-filter-chip pw-filter-chip-empty";
      empty.textContent = "none yet";
      tagFilterRow.appendChild(empty);
      return;
    }
    tags.forEach((tagName) => {
      const chip = document.createElement("button");
      chip.className = activeTags.has(tagName) ? "pw-filter-chip pw-filter-chip-active" : "pw-filter-chip";
      chip.textContent = `#${tagName}`;
      chip.addEventListener("click", () => {
        if (activeTags.has(tagName)) activeTags.delete(tagName);
        else activeTags.add(tagName);
        renderTagFilters();
        renderColumns();
      });
      tagFilterRow.appendChild(chip);
    });
  }

  function renderArtifactFilters(): void {
    artifactFilterRow.querySelectorAll(".pw-filter-chip").forEach((el) => el.remove());
    const artifacts = collectArtifacts(tree);
    if (artifacts.length === 0) {
      const empty = document.createElement("span");
      empty.className = "pw-filter-chip pw-filter-chip-empty";
      empty.textContent = "none yet";
      artifactFilterRow.appendChild(empty);
      return;
    }
    artifacts.forEach((artifact) => {
      const chip = document.createElement("button");
      chip.className =
        activeArtifact === artifact.id ? "pw-filter-chip pw-filter-chip-active" : "pw-filter-chip";
      chip.textContent = artifact.name;
      chip.addEventListener("click", () => {
        activeArtifact = activeArtifact === artifact.id ? null : artifact.id;
        renderArtifactFilters();
        renderColumns();
      });
      artifactFilterRow.appendChild(chip);
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
    const selection = (model.get("selection") as { node?: { pickedStateId?: string } }) ?? {};
    const pickedStateId = selection.node?.pickedStateId;
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
        const collapsed = filtersActive() && !nodeMatchesFilters(node);
        const card = nodeCard(node, {
          collapsed,
          selected: node.stateId === pickedStateId,
          onSelect: () => {
            path.splice(columnIndex, path.length, node.stateId);
            const current = (model.get("selection") as Record<string, unknown>) ?? {};
            model.set("selection", { ...current, node: { pickedStateId: node.stateId } });
            model.save_changes();
            renderBreadcrumb();
            renderColumns();
          },
        });
        column.appendChild(card);
      });
      columnsWrap.appendChild(column);
    }
    renderInspectPane();
  }

  renderTagFilters();
  renderArtifactFilters();
  renderBreadcrumb();
  renderColumns();
}
