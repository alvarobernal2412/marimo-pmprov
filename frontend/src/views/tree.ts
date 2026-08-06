import type { ProvenanceNodeJson, ProvenanceTreeJson } from "../types";
import { nodeCard } from "../components/node-card";
import { renderInspect } from "./inspect";
import type { TreeNavState } from "../nav-state";

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

  // renderTree() is invoked fresh on every "tree"/"commits" trait change (a
  // selection click alone re-triggers one via save_changes()) — without
  // stashing this on the model (see nav-state.ts), the local drill-down path
  // would reset to the root on every such event, undoing the very click that
  // just extended it. The curated view reads the same stashed path to know
  // which branch is "active" — see views/curated.ts.
  const navState = model as unknown as TreeNavState;
  if (!navState._pwTreePath || navState._pwTreePath[0] !== tree.rootId) {
    navState._pwTreePath = [tree.rootId];
  }
  const path = navState._pwTreePath;

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

  // Depth = distance from the tree root along parentStateId edges. Every
  // node in the whole tree gets grouped by depth (not just descendants of
  // the confirmed path) so the landscape shows every branch at once, the
  // way the columns used to only show the branch being drilled into.
  function depthOf(stateId: string, cache: Map<string, number>): number {
    const cached = cache.get(stateId);
    if (cached !== undefined) return cached;
    const node = tree.nodes[stateId];
    const depth = node.parentStateId ? depthOf(node.parentStateId, cache) + 1 : 0;
    cache.set(stateId, depth);
    return depth;
  }

  function drawConnectors(cardEls: Map<string, HTMLElement>): void {
    columnsWrap.querySelector("svg.pw-tree-lines")?.remove();
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "pw-tree-lines");
    svg.setAttribute("width", String(columnsWrap.scrollWidth));
    svg.setAttribute("height", String(columnsWrap.scrollHeight));

    const containerRect = columnsWrap.getBoundingClientRect();
    for (const [stateId, el] of cardEls) {
      const node = tree.nodes[stateId];
      const parentEl = node.parentStateId ? cardEls.get(node.parentStateId) : undefined;
      if (!parentEl) continue;
      const r1 = parentEl.getBoundingClientRect();
      const r2 = el.getBoundingClientRect();
      const x1 = r1.right - containerRect.left + columnsWrap.scrollLeft;
      const y1 = r1.top + r1.height / 2 - containerRect.top + columnsWrap.scrollTop;
      const x2 = r2.left - containerRect.left + columnsWrap.scrollLeft;
      const y2 = r2.top + r2.height / 2 - containerRect.top + columnsWrap.scrollTop;
      const midX = (x1 + x2) / 2;
      const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
      line.setAttribute("d", `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`);
      line.setAttribute("class", path.includes(stateId) && path.includes(node.parentStateId ?? "")
        ? "pw-tree-line-active"
        : "pw-tree-line");
      svg.appendChild(line);
    }
    columnsWrap.insertBefore(svg, columnsWrap.firstChild);
  }

  function renderColumns(): void {
    columnsWrap.innerHTML = "";
    const selection = (model.get("selection") as { node?: { pickedStateId?: string } }) ?? {};
    const pickedStateId = selection.node?.pickedStateId;

    const depthCache = new Map<string, number>();
    const byDepth = new Map<number, ProvenanceNodeJson[]>();
    let maxDepth = 0;
    for (const node of Object.values(tree.nodes)) {
      const depth = depthOf(node.stateId, depthCache);
      maxDepth = Math.max(maxDepth, depth);
      (byDepth.get(depth) ?? byDepth.set(depth, []).get(depth)!).push(node);
    }

    const cardEls = new Map<string, HTMLElement>();
    for (let depth = 0; depth <= maxDepth; depth++) {
      const column = document.createElement("div");
      column.className = "pw-column";
      (byDepth.get(depth) ?? []).forEach((node) => {
        // Everything collapses to a single line by default — only the nodes
        // on the path the user has actually clicked into render in full.
        const onPath = path.includes(node.stateId);
        const collapsed = !onPath || (filtersActive() && !nodeMatchesFilters(node));
        const card = nodeCard(node, {
          collapsed,
          selected: node.stateId === pickedStateId,
          onSelect: () => {
            path.splice(depth, path.length, node.stateId);
            const current = (model.get("selection") as Record<string, unknown>) ?? {};
            model.set("selection", { ...current, node: { pickedStateId: node.stateId } });
            model.save_changes();
            renderBreadcrumb();
            renderColumns();
          },
        });
        cardEls.set(node.stateId, card);
        column.appendChild(card);
      });
      columnsWrap.appendChild(column);
    }
    drawConnectors(cardEls);
    renderInspectPane();
  }

  renderTagFilters();
  renderArtifactFilters();
  renderBreadcrumb();
  renderColumns();
}
