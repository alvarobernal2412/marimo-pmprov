import type { TagJson } from "../types";

export function tagChip(tag: TagJson): HTMLElement {
  const el = document.createElement("span");
  el.className = "pw-tag-chip";
  el.textContent = `#${tag.name}`;
  el.style.setProperty("--chip-color", tag.color);
  return el;
}
