// Shared, non-synced navigation state stashed directly on the anywidget
// model object (not a traitlet — it's pure client-side UI state, so it must
// survive re-renders without round-tripping through Python). Currently holds
// the tree tab's Miller-columns drill-down path: the confirmed chain of
// stateIds from the root down to whatever the user last clicked into. Other
// views (e.g. curated) read this to know "which branch is the user
// interacting with right now" without needing their own copy of it.
export interface TreeNavState {
  _pwTreePath?: string[];
}

export function getActivePath(model: unknown): string[] | null {
  const path = (model as TreeNavState)._pwTreePath;
  return path && path.length > 0 ? path : null;
}
