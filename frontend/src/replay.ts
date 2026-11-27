import type { ArtifactRefJson, ProvenanceNodeJson, ProvenanceTreeJson } from "./types";
import type { TreeNavState } from "./nav-state";
import { collectAnnotations } from "./annotations";
import { highlightProducedBy, highlightTargets } from "./highlight";
import { startReplayStatus } from "./replay-status";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

interface ReplayState {
  stateId?: string;
  isLatest?: boolean;
}

// The state before the first recorded step: nothing has been computed yet. A replay can start there, so that the first Next shows
// what step 1 made and the step number in the player is the step whose result is on screen. It is not a node of the tree.
export const INITIAL_STATE = "__initial__";

export function isInitial(stateId: string | null | undefined): boolean {
  return stateId === INITIAL_STATE;
}

// Time order = insertion order of tree.nodes (pmprov records states
// sequentially), so the last key is always the most recent state.
export function latestStateId(tree: ProvenanceTreeJson): string | null {
  const ids = Object.keys(tree.nodes);
  return ids.length > 0 ? ids[ids.length - 1] : null;
}

// Where the reviewer currently is. Before any step, or after jumping to
// "latest", they are following the live analysis, so the cursor tracks the
// newest state as the tree grows instead of pinning to a stale one.
export function cursorStateId(model: AnyModel, tree: ProvenanceTreeJson): string | null {
  const replay = (model.get("replay") as ReplayState) ?? {};
  if (replay.stateId === INITIAL_STATE) return INITIAL_STATE;
  if (!replay.stateId || replay.isLatest || !tree.nodes[replay.stateId]) return latestStateId(tree);
  return replay.stateId;
}

export function childrenOf(tree: ProvenanceTreeJson, stateId: string): ProvenanceNodeJson[] {
  return Object.values(tree.nodes).filter((n) => n.parentStateId === stateId);
}

export function pathTo(tree: ProvenanceTreeJson, stateId: string): string[] {
  const path: string[] = [];
  let cursor: string | null = stateId;
  while (cursor && tree.nodes[cursor]) {
    path.unshift(cursor);
    cursor = tree.nodes[cursor].parentStateId;
  }
  return path;
}

// Redo memory: the child last stepped away from, per parent, so Back then
// Next returns to the same branch. Non-synced UI state, like the tree path.
function forwardMemory(model: AnyModel): Record<string, string> {
  const nav = model as unknown as TreeNavState;
  return (nav._pwForward ??= {});
}

export function nextChoices(model: AnyModel, tree: ProvenanceTreeJson, stateId: string): ProvenanceNodeJson[] {
  const kids = childrenOf(tree, stateId);
  const remembered = forwardMemory(model)[stateId];
  return kids.sort((a, b) => (a.stateId === remembered ? -1 : b.stateId === remembered ? 1 : 0));
}

// What the annotations of a state are about: the refs of all of them, in order. Stepping onto the state points at these.
export function annotationRefsOf(tree: ProvenanceTreeJson, stateId: string): ArtifactRefJson[] {
  return (tree.nodes[stateId]?.annotations ?? []).flatMap((annotation) => annotation.artifacts ?? []);
}

export function moveCursor(model: AnyModel, tree: ProvenanceTreeJson, stateId: string, forget = false, highlight = true): void {
  const node = tree.nodes[stateId];
  if (!node) return;
  const previous = cursorStateId(model, tree);
  if (previous && !forget) {
    // stepping back from `previous` to its parent remembers `previous` for redo
    if (tree.nodes[previous]?.parentStateId === stateId) forwardMemory(model)[stateId] = previous;
  }
  const path = pathTo(tree, stateId);
  (model as unknown as TreeNavState)._pwTreePath = path;
  const selection = (model.get("selection") as Record<string, unknown>) ?? {};
  model.set("selection", { ...selection, node: { pickedStateId: stateId } });
  model.set("replay", { stateId, params: node.params, isLatest: stateId === latestStateId(tree) });
  model.save_changes();
  if (model.get("outputs_follow_cursor")) startReplayStatus(model, stateId); // says that the notebook is catching up
  // only a notebook that redraws per step shows what the step reached; a step with annotations points at what they are about
  if (highlight && model.get("outputs_follow_cursor")) {
    collectAnnotations(model, tree); // the annotations written in this session are on their states too
    const refs = annotationRefsOf(tree, stateId).filter((ref) => ref.artifactName); // a ref without a name cannot be found
    if (refs.length > 0) highlightTargets(refs);
    else highlightProducedBy(stateId);
  }
}

// Go back to before the first step.
export function moveToInitial(model: AnyModel): void {
  (model as unknown as TreeNavState)._pwTreePath = [];
  const { node: _left, ...selection } = (model.get("selection") as Record<string, unknown>) ?? {};
  model.set("selection", selection);
  model.set("replay", { stateId: INITIAL_STATE, params: {}, isLatest: false });
  model.save_changes();
  if (model.get("outputs_follow_cursor")) startReplayStatus(model, INITIAL_STATE, true);
}
