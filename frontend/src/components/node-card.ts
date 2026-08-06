import type { ProvenanceNodeJson } from "../types";
import { CATEGORY_COLOR } from "../types";
import { tagChip } from "./tag-chip";
import { artifactBadge } from "./artifact-badge";

export function nodeCard(
  node: ProvenanceNodeJson,
  opts: { onSelect?: () => void; selected?: boolean; collapsed?: boolean } = {},
): HTMLElement {
  const card = document.createElement("div");
  card.className = "pw-node-card";
  if (opts.collapsed) card.classList.add("pw-node-card-collapsed");
  if (opts.selected) card.classList.add("pw-node-card-selected");
  card.dataset.stateId = node.stateId;
  card.style.setProperty("--category-color", CATEGORY_COLOR[node.operation.category] ?? "#64748B");

  // The card's own identity is the pmprov state/step (operation.name) — an
  // annotation is separate metadata a user attached afterward, targeting a
  // specific artifact *produced by* this state. Never substitute one for
  // the other, or the tree stops representing actual pipeline lineage.
  if (opts.collapsed) {
    const title = document.createElement("div");
    title.className = "pw-node-title";
    title.textContent = node.operation.name;
    card.appendChild(title);
    if (opts.onSelect) {
      card.style.cursor = "pointer";
      card.title = "Click to expand";
      card.addEventListener("click", opts.onSelect);
    }
    return card;
  }

  const badge = document.createElement("div");
  badge.className = "pw-op-badge";
  badge.textContent = node.operation.category.replace("_", " ");
  card.appendChild(badge);

  const title = document.createElement("div");
  title.className = "pw-node-title";
  title.textContent = node.operation.name;
  card.appendChild(title);

  if (node.annotations.length === 0) {
    const empty = document.createElement("div");
    empty.className = "pw-node-no-annotations";
    empty.textContent = "No annotations on this state yet.";
    card.appendChild(empty);
  }

  node.annotations.forEach((annotation) => {
    const block = document.createElement("div");
    block.className = "pw-annotation-block";

    const annotationTitle = document.createElement("div");
    annotationTitle.className = "pw-annotation-title";
    annotationTitle.textContent = annotation.title;
    block.appendChild(annotationTitle);

    const note = document.createElement("div");
    note.className = "pw-node-note";
    note.textContent = annotation.note;
    block.appendChild(note);

    const tags = document.createElement("div");
    tags.className = "pw-node-tags";
    annotation.tags.forEach((t) => tags.appendChild(tagChip(t)));
    block.appendChild(tags);

    // What this annotation is actually about — the specific artifact (and
    // granularity within it) produced by this state, not the state itself.
    const artifacts = document.createElement("div");
    artifacts.className = "pw-node-artifacts";
    annotation.artifacts.forEach((a) => artifacts.appendChild(artifactBadge(a)));
    block.appendChild(artifacts);

    card.appendChild(block);
  });

  if (opts.onSelect) {
    card.style.cursor = "pointer";
    card.title = "Click to expand";
    card.addEventListener("click", opts.onSelect);
  }

  return card;
}
