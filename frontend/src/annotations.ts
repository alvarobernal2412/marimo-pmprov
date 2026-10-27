import type { AnnotationJson, ProvenanceTreeJson } from "./types";

interface AnyModel {
  get(key: string): unknown;
}

export interface AnnotationRow {
  stateId: string;
  annotation: AnnotationJson;
}

// Merge node-attached annotations with widget commits, drop removed ones and
// apply edits. Mutates tree.nodes[*].annotations in place (the tree object is
// the model's own, shared with the tree/inspect views) and is idempotent.
// Returns every annotation in time order, oldest first — including commits
// whose stateId isn't a tree node (e.g. "python"), which have no node to hold them.
export function collectAnnotations(model: AnyModel, tree: ProvenanceTreeJson): AnnotationRow[] {
  const removed = new Set((model.get("removed_annotations") as string[]) ?? []);
  const edited = (model.get("edited_annotations") as Record<string, AnnotationJson>) ?? {};
  const commits = (model.get("commits") as AnnotationRow[]) ?? [];
  // The source's stored copy of a committed annotation also shows up on its
  // node; show the commit's own version only.
  const storedCopies = new Set(Object.values((model.get("annotation_aliases") as Record<string, string>) ?? {}));

  const seen = new Set<string>();
  const rows: AnnotationRow[] = [];
  const perNode = new Map<string, AnnotationJson[]>();

  const add = (stateId: string, annotation: AnnotationJson): void => {
    const id = annotation.annotationId;
    if (removed.has(id) || seen.has(id)) return;
    seen.add(id);
    const effective = edited[id] ? { ...annotation, ...edited[id] } : annotation;
    rows.push({ stateId, annotation: effective });
    if (tree.nodes[stateId]) {
      (perNode.get(stateId) ?? perNode.set(stateId, []).get(stateId)!).push(effective);
    }
  };

  for (const { stateId, annotation } of commits) add(stateId, annotation);
  for (const node of Object.values(tree.nodes)) {
    for (const annotation of node.annotations) {
      if (!storedCopies.has(annotation.annotationId)) add(node.stateId, annotation);
    }
  }

  for (const node of Object.values(tree.nodes)) node.annotations = perNode.get(node.stateId) ?? [];

  return rows.sort((a, b) => timeOf(a.annotation.timestamp) - timeOf(b.annotation.timestamp));
}

function timeOf(timestamp: string): number {
  const t = Date.parse(timestamp);
  return Number.isNaN(t) ? 0 : t;
}

// Short local time, e.g. "25 Oct, 14:32"; the full ISO string is the tooltip.
export function formatTimestamp(timestamp: string): string {
  const t = Date.parse(timestamp);
  if (Number.isNaN(t)) return timestamp;
  return new Date(t).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
