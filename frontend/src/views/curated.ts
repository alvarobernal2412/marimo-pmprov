import type { AnnotationJson, ProvenanceTreeJson } from "../types";
import { tagChip } from "../components/tag-chip";
import { artifactBadge, GRANULARITY_LABEL } from "../components/artifact-badge";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

// Sequential order: oldest first, most recently created appended last.
function allAnnotationsInSequence(tree: ProvenanceTreeJson): { stateId: string; annotation: AnnotationJson }[] {
  const rows: { stateId: string; annotation: AnnotationJson }[] = [];
  for (const node of Object.values(tree.nodes)) {
    for (const annotation of node.annotations) {
      rows.push({ stateId: node.stateId, annotation });
    }
  }
  for (const commit of model_commits) rows.push(commit);
  return rows.sort((a, b) => (a.annotation.timestamp < b.annotation.timestamp ? -1 : 1));
}

let model_commits: { stateId: string; annotation: AnnotationJson }[] = [];

function renderCommitCard(row: { stateId: string; annotation: AnnotationJson }, mode: string, model: AnyModel): HTMLElement {
  const card = document.createElement("div");
  card.className = "pw-commit-card";
  card.dataset.stateId = row.stateId;

  const title = document.createElement("div");
  title.className = "pw-node-title";
  title.textContent = row.annotation.title;
  card.appendChild(title);

  const tags = document.createElement("div");
  tags.className = "pw-node-tags";
  row.annotation.tags.forEach((t) => {
    const chip = tagChip(t);
    if (mode === "reviewer") {
      const restoreBtn = document.createElement("button");
      restoreBtn.className = "pw-restore-btn";
      restoreBtn.textContent = `Restore to @${t.name}`;
      restoreBtn.addEventListener("click", (evt) => {
        evt.stopPropagation();
        model.set("restore_request", { tag: t.name });
        model.save_changes();
      });
      chip.appendChild(restoreBtn);
    }
    tags.appendChild(chip);
  });
  card.appendChild(tags);

  const artifacts = document.createElement("div");
  artifacts.className = "pw-node-artifacts";
  row.annotation.artifacts.forEach((a) => artifacts.appendChild(artifactBadge(a)));
  card.appendChild(artifacts);

  return card;
}

function renderTargetSelector(model: AnyModel): HTMLElement {
  const target = document.createElement("div");
  target.className = "pw-target-selector";

  const selection = (model.get("selection") as { artifact?: Record<string, unknown> })?.artifact ?? {};
  const artifactId = selection.artifactId ? String(selection.artifactId) : null;

  if (!artifactId) {
    target.classList.add("pw-target-selector-empty");
    target.textContent = "No target selected — use \"Pick from notebook\" or hover an element's \"+\".";
    return target;
  }

  const artifactName = selection.artifactName ? String(selection.artifactName) : artifactId;
  const granularity = selection.granularity ? String(selection.granularity) : "dataset";
  const detail = selection.detail ? String(selection.detail) : null;
  const granularityLabel = GRANULARITY_LABEL[granularity] ?? granularity;

  const label = document.createElement("div");
  label.className = "pw-target-selector-label";
  label.textContent = "Target";
  target.appendChild(label);

  const value = document.createElement("div");
  value.className = "pw-target-selector-value";
  value.textContent = detail
    ? `${artifactName} · ${granularityLabel}: ${detail}`
    : `${artifactName} · ${granularityLabel}`;
  value.title = `artifact id: ${artifactId}`;
  target.appendChild(value);

  return target;
}

function renderComposer(container: HTMLElement, model: AnyModel): HTMLElement {
  const composer = document.createElement("div");
  composer.className = "pw-composer";

  composer.appendChild(renderTargetSelector(model));

  const noteField = document.createElement("textarea");
  noteField.placeholder = "Describe reasoning for this analytical step...";
  composer.appendChild(noteField);

  const tagField = document.createElement("input");
  tagField.placeholder = "#tags";
  composer.appendChild(tagField);

  const commitBtn = document.createElement("button");
  commitBtn.className = "pw-commit-btn";
  commitBtn.textContent = "Commit annotation";
  commitBtn.addEventListener("click", () => {
    const selection = (model.get("selection") as { artifact?: Record<string, unknown> })?.artifact ?? {};
    const newAnnotation: AnnotationJson = {
      annotationId: `ann-${Date.now()}`,
      title: noteField.value.slice(0, 40) || "Untitled annotation",
      note: noteField.value,
      tags: tagField.value
        .split(" ")
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
      author: { agent_id: "agent-student", agent_type: "human", display_name: "S" },
      timestamp: new Date().toISOString(),
    };
    // Resolve which analysis state this annotation belongs to from the
    // artifact it targets — mirrors ProvenancePanel.commit_annotation()'s
    // server-side resolution (see pmprov_adapter.py's state_for_artifact):
    // an artifact_id built from a live pmprov state IS that state's id, so
    // if it matches a node in the tree, that node produced this artifact.
    const tree = model.get("tree") as ProvenanceTreeJson;
    const targetArtifactId = newAnnotation.artifacts[0]?.artifactId;
    const stateId = targetArtifactId && tree.nodes[targetArtifactId] ? targetArtifactId : "composer";

    const existing = model.get("commits") as unknown[];
    model.set("commits", [...existing, { stateId, annotation: newAnnotation }]);
    model.save_changes();
    noteField.value = "";
    tagField.value = "";
  });
  composer.appendChild(commitBtn);

  return composer;
}

export function renderCurated(container: HTMLElement, model: AnyModel): void {
  container.innerHTML = "";
  const tree = model.get("tree") as ProvenanceTreeJson;
  const mode = model.get("mode") as string;
  model_commits = model.get("commits") as { stateId: string; annotation: AnnotationJson }[];

  const header = document.createElement("div");
  header.className = "pw-tree-header";
  const title = document.createElement("div");
  title.className = "pw-tree-title";
  title.textContent = "Annotation History";
  header.appendChild(title);
  const caption = document.createElement("div");
  caption.className = "pw-tree-caption";
  caption.textContent = "Every annotation made in this analysis, oldest first.";
  header.appendChild(caption);
  container.appendChild(header);

  const rail = document.createElement("div");
  rail.className = "pw-commit-rail";
  allAnnotationsInSequence(tree).forEach((row) => rail.appendChild(renderCommitCard(row, mode, model)));
  container.appendChild(rail);

  if (mode === "student") {
    container.appendChild(renderComposer(container, model));
  }
}
