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

  const annotation = node.annotations[0];

  if (opts.collapsed) {
    const title = document.createElement("div");
    title.className = "pw-node-title";
    title.textContent = annotation ? annotation.title : node.operation.name;
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
  title.textContent = annotation ? annotation.title : node.operation.name;
  card.appendChild(title);

  if (annotation) {
    const note = document.createElement("div");
    note.className = "pw-node-note";
    note.textContent = annotation.note;
    card.appendChild(note);

    const tags = document.createElement("div");
    tags.className = "pw-node-tags";
    annotation.tags.forEach((t) => tags.appendChild(tagChip(t)));
    card.appendChild(tags);

    const artifacts = document.createElement("div");
    artifacts.className = "pw-node-artifacts";
    annotation.artifacts.forEach((a) => artifacts.appendChild(artifactBadge(a)));
    card.appendChild(artifacts);
  }

  if (opts.onSelect) {
    card.style.cursor = "pointer";
    card.title = "Click to expand";
    card.addEventListener("click", opts.onSelect);
  }

  return card;
}
