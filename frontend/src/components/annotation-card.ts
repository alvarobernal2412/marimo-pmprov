import type { AnnotationJson } from "../types";
import { tagChip } from "./tag-chip";
import { artifactBadge } from "./artifact-badge";
import { formatTimestamp } from "../annotations";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

interface Row {
  stateId: string;
  annotation: AnnotationJson;
}

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

function parseTags(raw: string): { name: string; color: string }[] {
  return raw
    .split(/\s+/)
    .filter(Boolean)
    .map((name) => ({ name: name.replace(/^#/, ""), color: "#64748B" }));
}

// One annotation in the history feed. Student persona: edit / delete (inline
// two-step confirm, no browser dialogs). Reviewer persona: read-only, plus
// "Replay state" to move the stepper to the state this annotation sits on.
export function annotationCard(
  row: Row,
  opts: { mode: string; model: AnyModel; isCurrent: boolean; canReplay: boolean; onReplay: () => void },
): HTMLElement {
  const { annotation } = row;
  const { mode, model } = opts;
  const card = document.createElement("div");
  card.className = "pw-commit-card";
  if (opts.isCurrent) card.classList.add("pw-commit-card-current");
  card.dataset.stateId = row.stateId;
  card.dataset.annotationId = annotation.annotationId;

  const head = document.createElement("div");
  head.className = "pw-card-head";
  const title = document.createElement("div");
  title.className = "pw-node-title";
  title.textContent = annotation.title;
  head.appendChild(title);
  const time = document.createElement("time");
  time.className = "pw-timestamp";
  time.dateTime = annotation.timestamp;
  time.title = annotation.timestamp;
  time.textContent = formatTimestamp(annotation.timestamp);
  head.appendChild(time);
  card.appendChild(head);

  const body = document.createElement("div");
  card.appendChild(body);

  const actions = document.createElement("div");
  actions.className = "pw-card-actions";
  card.appendChild(actions);

  function renderView(): void {
    body.innerHTML = "";
    actions.innerHTML = "";

    if (annotation.note && annotation.note !== annotation.title) {
      const note = document.createElement("div");
      note.className = "pw-annotation-note";
      note.textContent = annotation.note;
      body.appendChild(note);
    }

    const tags = document.createElement("div");
    tags.className = "pw-node-tags";
    annotation.tags.forEach((t) => tags.appendChild(tagChip(t)));
    body.appendChild(tags);

    const artifacts = document.createElement("div");
    artifacts.className = "pw-node-artifacts";
    annotation.artifacts.forEach((a) => artifacts.appendChild(artifactBadge(a)));
    body.appendChild(artifacts);

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
    actions.appendChild(smallButton("Edit", "pw-edit-btn", renderEdit));
    actions.appendChild(smallButton("Delete", "pw-delete-btn", renderConfirmDelete));
  }

  function renderConfirmDelete(): void {
    actions.innerHTML = "";
    const ask = document.createElement("span");
    ask.className = "pw-confirm-text";
    ask.textContent = "Delete this annotation?";
    actions.appendChild(ask);
    actions.appendChild(
      smallButton("Yes, delete", "pw-delete-btn", () => {
        const removed = (model.get("removed_annotations") as string[]) ?? [];
        model.set("removed_annotations", [...removed, annotation.annotationId]);
        model.save_changes();
      }),
    );
    actions.appendChild(smallButton("Cancel", "", renderView));
  }

  function renderEdit(): void {
    body.innerHTML = "";
    actions.innerHTML = "";
    const noteField = document.createElement("textarea");
    noteField.value = annotation.note;
    body.appendChild(noteField);
    const tagField = document.createElement("input");
    tagField.placeholder = "#tags";
    tagField.value = annotation.tags.map((t) => `#${t.name}`).join(" ");
    body.appendChild(tagField);
    actions.appendChild(
      smallButton("Save", "pw-save-btn", () => {
        const edited = (model.get("edited_annotations") as Record<string, AnnotationJson>) ?? {};
        model.set("edited_annotations", {
          ...edited,
          [annotation.annotationId]: {
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

  renderView();
  return card;
}
