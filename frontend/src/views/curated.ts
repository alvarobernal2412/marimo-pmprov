import type { AnnotationJson, ProvenanceTreeJson } from "../types";
import { GRANULARITY_LABEL } from "../components/artifact-badge";
import { annotationCard } from "../components/annotation-card";
import { collectAnnotations } from "../annotations";
import { cursorStateId, latestStateId, moveCursor } from "../replay";
import { icon } from "../components/icons";
import { requestPdfExport } from "../export";
import { renderReplayBar } from "./replay-bar";
import type { TreeNavState } from "../nav-state";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

function renderTargetSelector(model: AnyModel): HTMLElement {
  const target = document.createElement("div");
  target.className = "pw-target-selector";

  const selection = (model.get("selection") as { artifact?: Record<string, unknown> })?.artifact ?? {};
  const artifactId = selection.artifactId ? String(selection.artifactId) : null;

  const label = document.createElement("div");
  label.className = "pw-target-selector-label";
  label.textContent = "Target";
  target.appendChild(label);

  const value = document.createElement("div");
  value.className = "pw-target-selector-value";
  target.appendChild(value);

  if (!artifactId) {
    // No pick = the annotation is about the analysis as a whole, attached to
    // the latest state: an immutable snapshot of the analysis right now.
    const tree = model.get("tree") as ProvenanceTreeJson;
    const latest = latestStateId(tree);
    value.textContent = "Whole analysis";
    value.classList.add("pw-target-whole");
    value.title = latest
      ? `Not tied to an output: linked to the latest analysis state (after "${tree.nodes[latest].operation.name}")`
      : "Not tied to an output";
    return target;
  }

  const artifactName = selection.artifactName ? String(selection.artifactName) : artifactId;
  const granularity = selection.granularity ? String(selection.granularity) : "dataset";
  const detail = selection.detail ? String(selection.detail) : null;
  const granularityLabel = GRANULARITY_LABEL[granularity] ?? granularity;

  value.textContent = detail
    ? `${artifactName} · ${granularityLabel}: ${detail}`
    : `${artifactName} · ${granularityLabel}`;
  value.title = `artifact id: ${artifactId}`;

  return target;
}

// × next to the Pick button: drop the picked output and annotate the whole analysis.
function renderClearButton(model: AnyModel): HTMLElement | null {
  const selection = (model.get("selection") as { artifact?: Record<string, unknown> })?.artifact ?? {};
  if (!selection.artifactId) return null;
  const clear = document.createElement("button");
  clear.type = "button";
  clear.className = "pw-target-clear";
  clear.setAttribute("aria-label", "Clear target (annotate the whole analysis)");
  clear.title = "Clear target: annotate the whole analysis";
  clear.appendChild(icon("x"));
  clear.addEventListener("click", () => {
    const { artifact: _dropped, ...rest } = (model.get("selection") as Record<string, unknown>) ?? {};
    model.set("selection", rest);
    model.save_changes();
  });
  return clear;
}

function renderComposer(model: AnyModel, pickButton?: HTMLElement): HTMLElement {
  const composer = document.createElement("div");
  composer.className = "pw-composer";

  // "Pick from notebook" belongs with the target it fills in.
  const targetRow = document.createElement("div");
  targetRow.className = "pw-target-row";
  targetRow.appendChild(renderTargetSelector(model));
  const actionGroup = document.createElement("div");
  actionGroup.className = "pw-target-actions";
  if (pickButton) actionGroup.appendChild(pickButton);
  const clearButton = renderClearButton(model);
  if (clearButton) actionGroup.appendChild(clearButton);
  targetRow.appendChild(actionGroup);
  composer.appendChild(targetRow);

  const nav = model as unknown as TreeNavState;
  const draft = (nav._pwDraft ??= { note: "", tags: "" });

  const noteField = document.createElement("textarea");
  noteField.placeholder = "Describe your reasoning for this step…";
  noteField.rows = 2;
  noteField.setAttribute("aria-label", "Annotation note");
  noteField.value = draft.note;
  noteField.addEventListener("input", () => (draft.note = noteField.value));
  composer.appendChild(noteField);

  const tagRow = document.createElement("div");
  tagRow.className = "pw-composer-row";
  composer.appendChild(tagRow);

  const tagField = document.createElement("input");
  tagField.placeholder = "#tags, separated by spaces";
  tagField.setAttribute("aria-label", "Annotation tags");
  tagField.value = draft.tags;
  tagField.addEventListener("input", () => (draft.tags = tagField.value));
  tagRow.appendChild(tagField);

  const commitBtn = document.createElement("button");
  commitBtn.className = "pw-commit-btn";
  commitBtn.textContent = "Add";
  commitBtn.title = "Add annotation (Ctrl+Enter)";
  const commit = (): void => {
    const selection = (model.get("selection") as { artifact?: Record<string, unknown> })?.artifact ?? {};
    const newAnnotation: AnnotationJson = {
      annotationId: `ann-${Date.now()}`,
      title: noteField.value.slice(0, 40) || "Untitled annotation",
      note: noteField.value,
      tags: tagField.value
        .split(/\s+/)
        .filter(Boolean)
        .map((name) => ({ name: name.replace(/^#/, ""), color: "#64748B" })),
      artifacts: selection.artifactId
        ? [{
            artifactId: String(selection.artifactId),
            artifactName: String(selection.artifactName ?? ""),
            granularity: String(selection.granularity ?? "dataset"),
            detail: (selection.detail as string) ?? null,
          }]
        : [],
      author: { agent_id: "agent-analyst", agent_type: "human", display_name: "A" },
      timestamp: new Date().toISOString(),
    };
    // Resolve which analysis state this annotation belongs to from the
    // artifact it targets — mirrors ProvenancePanel.commit_annotation()'s
    // server-side resolution (see pmprov_adapter.py's state_for_artifact):
    // an artifact_id built from a live pmprov state IS that state's id, so
    // if it matches a node in the tree, that node produced this artifact.
    const tree = model.get("tree") as ProvenanceTreeJson;
    const targetArtifactId = newAnnotation.artifacts[0]?.artifactId;
    const stateId =
      targetArtifactId && tree.nodes[targetArtifactId] ? targetArtifactId : (latestStateId(tree) ?? "composer");

    // Clear the draft first: setting "commits" re-renders the sidebar
    // synchronously, and the fresh composer would otherwise reload the old text.
    noteField.value = "";
    tagField.value = "";
    draft.note = "";
    draft.tags = "";

    const existing = model.get("commits") as unknown[];
    model.set("commits", [...existing, { stateId, annotation: newAnnotation }]);
    model.save_changes();
  };
  commitBtn.addEventListener("click", commit);
  noteField.addEventListener("keydown", (evt) => {
    if (evt.key === "Enter" && (evt.ctrlKey || evt.metaKey)) commit();
  });
  tagRow.appendChild(commitBtn);

  return composer;
}

function renderExportButton(model: AnyModel, annotationCount: number): HTMLElement {
  const pending = !!(model as unknown as TreeNavState)._pwExport?.pending;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "pw-export-btn";
  button.disabled = pending || annotationCount === 0;
  button.title = annotationCount === 0
    ? "Add an annotation to export"
    : "Export the annotation history as a PDF report";
  button.appendChild(icon("download", 12));
  button.appendChild(document.createTextNode(pending ? "Exporting…" : "Export PDF"));
  button.addEventListener("click", () => {
    requestPdfExport(model);
    button.disabled = true;
    button.lastChild!.textContent = "Exporting…";
  });
  return button;
}

export function renderCurated(container: HTMLElement, model: AnyModel, pickButton?: HTMLElement): void {
  // Remember which composer field had focus (and its caret) so a re-render
  // triggered by new provenance data doesn't also steal the user's cursor.
  const active = (container.getRootNode() as Document | ShadowRoot).activeElement;
  const focusedField = active?.closest(".pw-composer")
    ? { tag: active.tagName, start: (active as HTMLTextAreaElement).selectionStart, end: (active as HTMLTextAreaElement).selectionEnd }
    : null;
  container.innerHTML = "";
  const tree = model.get("tree") as ProvenanceTreeJson;
  const mode = model.get("mode") as string;
  const rows = collectAnnotations(model, tree);

  if (mode === "reviewer") renderReplayBar(container, model);

  if (mode === "analyst") {
    container.appendChild(renderComposer(model, pickButton));
    if (focusedField) {
      const field = container.querySelector<HTMLTextAreaElement | HTMLInputElement>(
        `.pw-composer ${focusedField.tag.toLowerCase()}`,
      );
      field?.focus();
      if (focusedField.start !== null) field?.setSelectionRange(focusedField.start, focusedField.end);
    }
  }

  const header = document.createElement("div");
  header.className = "pw-list-header";
  const title = document.createElement("span");
  title.className = "pw-list-title";
  title.textContent = "Annotations";
  header.appendChild(title);
  const count = document.createElement("span");
  count.className = "pw-list-count";
  count.textContent = String(rows.length);
  header.appendChild(count);
  const order = document.createElement("span");
  order.className = "pw-list-order";
  order.textContent = "oldest first";
  order.title = "Annotations are listed in the order they were written";
  if (mode !== "analyst") header.appendChild(order); // the analyst header has the export button instead
  if (mode === "analyst") {
    const exportButton = renderExportButton(model, rows.length);
    exportButton.style.marginLeft = "auto";
    header.appendChild(exportButton);
  }
  container.appendChild(header);
  const exportError = (model as unknown as TreeNavState)._pwExport?.error;
  if (mode === "analyst" && exportError) {
    const message = document.createElement("div");
    message.className = "pw-export-error";
    message.setAttribute("role", "alert");
    message.textContent = exportError;
    container.appendChild(message);
  }

  const cursor = mode === "reviewer" ? cursorStateId(model, tree) : null;
  const rail = document.createElement("div");
  rail.className = "pw-commit-rail";
  if (rows.length === 0) {
    const empty = document.createElement("div");
    empty.className = "pw-node-no-annotations";
    empty.textContent = mode === "analyst" ? "None yet. Add the first one above." : "No annotations in this analysis.";
    rail.appendChild(empty);
  }
  rows.forEach((row) =>
    rail.appendChild(
      annotationCard(row, {
        mode,
        model,
        isCurrent: cursor !== null && row.stateId === cursor,
        canReplay: !!tree.nodes[row.stateId],
        onReplay: () => moveCursor(model, tree, row.stateId),
      }),
    ),
  );
  container.appendChild(rail);
}
