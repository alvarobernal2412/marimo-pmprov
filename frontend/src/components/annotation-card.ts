import type { AnnotationJson } from "../types";
import { tagChip } from "./tag-chip";
import { artifactBadge } from "./artifact-badge";
import { formatTimestamp } from "../annotations";
import { icon } from "./icons";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

interface Row {
  stateId: string;
  annotation: AnnotationJson;
}

// Which rows are expanded survives re-renders (the sidebar rebuilds whenever
// provenance data changes), so a row you opened doesn't snap shut.
const expandedIds = new Set<string>();

function smallButton(label: string, className: string, onClick: () => void): HTMLButtonElement {
  const btn = document.createElement("button");
  btn.className = `pw-card-action ${className}`;
  btn.textContent = label;
  btn.addEventListener("click", (evt) => {
    evt.stopPropagation();
    onClick();
  });
  return btn;
}

// Icon-only button: the visible glyph is decorative, so the label goes in
// aria-label and the tooltip.
function iconButton(name: "edit" | "trash", label: string, className: string, onClick: () => void): HTMLButtonElement {
  const btn = smallButton("", `pw-icon-btn ${className}`, onClick);
  btn.appendChild(icon(name));
  btn.setAttribute("aria-label", label);
  btn.title = label;
  return btn;
}

function parseTags(raw: string): { name: string; color: string }[] {
  return raw
    .split(/\s+/)
    .filter(Boolean)
    .map((name) => ({ name: name.replace(/^#/, ""), color: "#64748B" }));
}

// One annotation in the history list, as a compact row: title + time, tag
// chips underneath, details on click. Analyst persona: edit / delete (inline
// two-step confirm, no browser dialogs). Reviewer persona: read-only, plus
// "Replay" to move the stepper to the state this annotation sits on.
export function annotationCard(
  row: Row,
  opts: { mode: string; model: AnyModel; isCurrent: boolean; canReplay: boolean; onReplay: () => void },
): HTMLElement {
  const { annotation } = row;
  const { mode, model } = opts;
  const id = annotation.annotationId;
  const card = document.createElement("div");
  card.className = "pw-ann";
  if (opts.isCurrent) card.classList.add("pw-ann-current");
  card.dataset.stateId = row.stateId;
  card.dataset.annotationId = id;

  const summary = document.createElement("button");
  summary.className = "pw-ann-summary";
  summary.type = "button";
  card.appendChild(summary);

  const details = document.createElement("div");
  details.className = "pw-ann-details";
  card.appendChild(details);

  function setExpanded(expanded: boolean): void {
    if (expanded) expandedIds.add(id);
    else expandedIds.delete(id);
    card.classList.toggle("pw-ann-open", expanded);
    summary.setAttribute("aria-expanded", String(expanded));
    details.hidden = !expanded;
  }

  function renderSummary(): void {
    summary.innerHTML = "";
    const line = document.createElement("span");
    line.className = "pw-ann-line";
    const title = document.createElement("span");
    title.className = "pw-ann-title";
    title.textContent = annotation.title;
    line.appendChild(title);
    const time = document.createElement("time");
    time.className = "pw-timestamp";
    time.dateTime = annotation.timestamp;
    time.title = annotation.timestamp;
    time.textContent = formatTimestamp(annotation.timestamp);
    line.appendChild(time);
    summary.appendChild(line);

    if (annotation.tags.length > 0) {
      const tags = document.createElement("span");
      tags.className = "pw-ann-tags";
      annotation.tags.forEach((t) => tags.appendChild(tagChip(t)));
      summary.appendChild(tags);
    }
  }

  const actions = document.createElement("div");
  actions.className = "pw-card-actions";

  function renderView(): void {
    details.innerHTML = "";
    actions.innerHTML = "";

    if (annotation.note && annotation.note !== annotation.title) {
      const note = document.createElement("div");
      note.className = "pw-annotation-note";
      note.textContent = annotation.note;
      details.appendChild(note);
    }

    if (annotation.artifacts.length > 0) {
      const artifacts = document.createElement("div");
      artifacts.className = "pw-node-artifacts";
      annotation.artifacts.forEach((a) => artifacts.appendChild(artifactBadge(a)));
      details.appendChild(artifacts);
    }
    details.appendChild(actions);

    if (mode === "reviewer") {
      const replayBtn = smallButton("Replay", "pw-replay-state-btn", opts.onReplay);
      replayBtn.disabled = !opts.canReplay;
      replayBtn.title = opts.canReplay
        ? "Replay: move the stepper to this annotation's state"
        : "No recorded state for this annotation";
      actions.appendChild(replayBtn);
      annotation.tags.forEach((t) => {
        const restoreBtn = smallButton(`↺ @${t.name}`, "pw-restore-btn", () => {
          model.set("restore_request", { tag: t.name });
          model.save_changes();
        });
        restoreBtn.title = `Restore parameters to the state tagged @${t.name}`;
        actions.appendChild(restoreBtn);
      });
      return;
    }
    actions.appendChild(iconButton("edit", "Edit annotation", "pw-edit-btn", renderEdit));
    actions.appendChild(iconButton("trash", "Delete annotation", "pw-delete-btn", renderConfirmDelete));
  }

  function renderConfirmDelete(): void {
    actions.innerHTML = "";
    const ask = document.createElement("span");
    ask.className = "pw-confirm-text";
    ask.textContent = "Delete this annotation?";
    actions.appendChild(ask);
    actions.appendChild(
      smallButton("Yes, delete", "pw-delete-btn", () => {
        expandedIds.delete(id);
        const removed = (model.get("removed_annotations") as string[]) ?? [];
        model.set("removed_annotations", [...removed, id]);
        model.save_changes();
      }),
    );
    actions.appendChild(smallButton("Cancel", "", renderView));
  }

  function renderEdit(): void {
    details.innerHTML = "";
    actions.innerHTML = "";
    const noteField = document.createElement("textarea");
    noteField.rows = 3;
    noteField.value = annotation.note;
    noteField.setAttribute("aria-label", "Annotation note");
    details.appendChild(noteField);
    const tagField = document.createElement("input");
    tagField.placeholder = "#tags";
    tagField.value = annotation.tags.map((t) => `#${t.name}`).join(" ");
    tagField.setAttribute("aria-label", "Annotation tags");
    details.appendChild(tagField);
    details.appendChild(actions);
    actions.appendChild(
      smallButton("Save", "pw-save-btn", () => {
        const edited = (model.get("edited_annotations") as Record<string, AnnotationJson>) ?? {};
        model.set("edited_annotations", {
          ...edited,
          [id]: {
            ...annotation,
            title: noteField.value.slice(0, 40) || "Untitled annotation",
            note: noteField.value,
            tags: parseTags(tagField.value),
          },
        });
        model.save_changes();
      }),
    );
    actions.appendChild(smallButton("Cancel", "", renderView));
    noteField.focus();
  }

  summary.addEventListener("click", () => setExpanded(!expandedIds.has(id)));
  renderSummary();
  renderView();
  setExpanded(expandedIds.has(id));
  return card;
}
