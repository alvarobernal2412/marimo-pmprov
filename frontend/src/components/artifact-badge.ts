import type { ArtifactRefJson } from "../types";
import { shownDetail } from "../traces";

export const GRANULARITY_LABEL: Record<string, string> = {
  dataset: "Whole dataset",
  column: "Column",
  row_subset: "Row subset",
  cell: "Cell",
  chart_selection: "Chart selection",
};

export function artifactBadge(ref: ArtifactRefJson): HTMLElement {
  const el = document.createElement("span");
  el.className = "pw-artifact-badge";
  const label = GRANULARITY_LABEL[ref.granularity] ?? ref.granularity;
  el.textContent = ref.detail
    ? `${ref.artifactName} · ${label}: ${shownDetail(ref.granularity, ref.detail)}`
    : `${ref.artifactName} · ${label}`;
  if (ref.detail && ref.granularity === "trace") el.title = ref.detail; // the whole name of a trace shown shortened
  el.dataset.artifactId = ref.artifactId;
  return el;
}
