import { resolveDetail, type PickDetail } from "./resolvers";
import { markSteady } from "./highlight";
import { showEndSegments } from "./end-segments";
import { locateAll, type Located } from "./locators";
import { forgetMaps, mapTracesOf, plotOf, shortTraceName, traceLabel } from "./traces";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

interface PickedSelection {
  artifactId: string;
  artifactName: string;
  granularity: string;
  detail: string | null;
  snapshot?: unknown;
  figure?: string | null; // the watched figure it was picked in (see watched-figure.ts): it is drawn again when its nodes are dragged
}

// The id of the watched figure (`data-pw-arrangement`, see arrangement.py) an element is in, also from inside shadow roots.
function watchedFigure(element: Node | null): string | null {
  let node: Node | null = element;
  while (node) {
    const id = (node as HTMLElement).dataset?.pwArrangement;
    if (id) return id;
    node = node.parentNode ?? ((node as ShadowRoot).host as Node | undefined) ?? null;
  }
  return null;
}

// The first element that matches, also inside shadow roots (marimo draws some outputs, such as the contents of tabs, in one).
function findDeep(root: ParentNode, selector: string): HTMLElement | null {
  const hit = root.querySelector<HTMLElement>(selector);
  if (hit) return hit;
  for (const element of Array.from(root.querySelectorAll<HTMLElement>("*"))) {
    const inner = element.shadowRoot ? findDeep(element.shadowRoot, selector) : null;
    if (inner) return inner;
  }
  return null;
}

// What an element shows, for the report: its own snapshot, or the one made for it afterwards (`chart_snapshot` in display.py puts
// a chart's picture in a hidden element of its own, so that the chart does not wait for it).
export function readSnapshot(element: HTMLElement, page: ParentNode = document): unknown {
  let raw = element.dataset.pwSnapshot;
  const id = element.dataset.pwArtifactId;
  if (!raw && id) {
    try {
      raw = findDeep(page, `[data-pw-snapshot-for="${id.replace(/["\\]/g, "\\$&")}"]`)?.dataset.pwSnapshot;
    } catch {
      raw = undefined;
    }
  }
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function findTaggedAncestor(el: EventTarget | null): HTMLElement | null {
  let node = el as HTMLElement | null;
  while (node) {
    if (node.dataset && node.dataset.pwArtifactId) return node;
    if (node.parentElement) {
      node = node.parentElement;
    } else {
      const root = node.getRootNode();
      node = root instanceof ShadowRoot ? (root.host as HTMLElement) : null;
    }
  }
  return null;
}

function refineGranularity(
  taggedElement: HTMLElement,
  clickTarget: HTMLElement,
  path: EventTarget[],
  event?: MouseEvent,
): { granularity: string; detail: string | null } {
  // Table cells, chart marks, and anything else "inside" an artifact are
  // refined by pluggable resolvers (see resolvers.ts) — the picker itself
  // doesn't know what a table or a chart is.
  const resolved = resolveDetail(path, clickTarget, event);
  if (resolved) return resolved;

  return {
    granularity: taggedElement.dataset.pwGranularity ?? "dataset",
    detail: taggedElement.dataset.pwDetail ?? null,
  };
}

// The node or link of a map the pointer is over, if any.
function sankeyShapeIn(path: EventTarget[]): Element | null {
  for (const node of path) {
    if (!(node instanceof Element)) continue;
    if (node.classList.contains("sankey-node") || node.classList.contains("sankey-link")) return node;
  }
  return null;
}

function previewText(shape: Element, pick: PickDetail): string {
  if (pick.granularity === "trace") {
    const trace = mapTracesOf(shape).traces.find((t) => t.name === pick.detail);
    return trace ? traceLabel(trace) : `trace ${shortTraceName(pick.detail ?? "")}`;
  }
  return `${pick.granularity} ${pick.detail ?? ""}`;
}

function previewed(artifact: HTMLElement, shape: Element, pick: PickDetail): Located[] {
  if (pick.granularity === "trace") return locateAll(artifact, "trace", pick.detail ?? "");
  if (pick.granularity === "node") return [((shape.querySelector("rect") as SVGElement | null) ?? shape) as SVGElement];
  if (pick.granularity === "link") return [shape as SVGElement];
  return [];
}

// While the picker is armed, a map shows what a click would pick: marked as a replay would mark it, with a small label by the
// pointer. The pointer moves often, so the work is done only when what would be picked changes; on a link that is once per link,
// on a node it is looked at on every move (on the node where traces end, the height of the pointer chooses the trace).
function mapPreview() {
  let shape: Element | null = null;
  let alt = false;
  let shownKey: string | null = null;
  let undo = () => {};
  let label: HTMLElement | null = null;

  function clear(): void {
    undo();
    undo = () => {};
    shape = null;
    shownKey = null;
    label?.remove();
    label = null;
  }

  function show(artifact: HTMLElement, over: Element, pick: PickDetail | null): void {
    const key = pick ? `${pick.granularity}|${pick.detail}` : null;
    if (key === shownKey) return;
    shownKey = key;
    // The new mark first: it reads the page before it writes, and on the same map it replaces the old one itself. Undoing the old
    // one first would write before those reads and make the browser lay the page out in the middle of the move.
    let next = () => {};
    if (pick) {
      const elements = previewed(artifact, over, pick);
      // Plotly may draw the map again under the pointer: the pick is then looked for in the new drawing, and when it is not there
      // the preview is dropped and made again at the next move.
      const again = () => locateAll(artifact, pick.granularity, pick.detail ?? "");
      const lost = () => {
        undo = () => {};
        shape = null;
        shownKey = null;
      };
      if (elements.length > 0) next = markSteady(elements, plotOf(over) ?? artifact, again, lost);
    }
    undo();
    undo = next;
    if (!pick) {
      label?.remove();
      label = null;
      return;
    }
    if (!label) {
      label = document.createElement("div");
      label.setAttribute(
        "style",
        // a long name wraps within 60% of the window
        "position:fixed;z-index:2147483647;pointer-events:none;max-width:60vw;white-space:normal;overflow-wrap:anywhere;" +
          "padding:2px 6px;border-radius:4px;" +
          "background:#1F2937;color:#fff;font:12px/1.4 system-ui,sans-serif;box-shadow:0 1px 3px rgba(0,0,0,0.3)",
      );
      document.body.appendChild(label);
    }
    label.textContent = previewText(over, pick);
  }

  function update(artifact: HTMLElement | null, path: EventTarget[], evt: MouseEvent): void {
    const over = artifact ? sankeyShapeIn(path) : null;
    if (!artifact || !over) return clear();
    if (over !== shape || evt.altKey !== alt || over.classList.contains("sankey-node")) {
      shape = over;
      alt = evt.altKey;
      show(artifact, over, resolveDetail(path, path[0] as HTMLElement, evt));
    }
    if (label) {
      // Beside the pointer, from the event alone (reading the label's size would lay the page out again): on the right half of the
      // window it goes to the left of the pointer, on the lower half above it, so that it stays inside the window.
      const left = evt.clientX > window.innerWidth / 2;
      const up = evt.clientY > window.innerHeight / 2;
      label.style.left = `${left ? evt.clientX - 14 : evt.clientX + 14}px`;
      label.style.top = `${up ? evt.clientY - 14 : evt.clientY + 14}px`;
      label.style.transform = `translate(${left ? "-100%" : "0"}, ${up ? "-100%" : "0"})`;
    }
  }

  return { update, clear };
}

export function armPicker(
  model: AnyModel,
  onPicked: (selection: PickedSelection) => void,
  onCancel?: () => void,
): void {
  let lastHovered: HTMLElement | null = null;
  const preview = mapPreview();
  const segments = showEndSegments(); // where traces can be picked, on every map that stores them

  function onMouseMove(evt: MouseEvent): void {
    const path = evt.composedPath();
    const target = findTaggedAncestor(path[0] ?? evt.target);
    if (lastHovered && lastHovered !== target) {
      lastHovered.classList.remove("pw-picker-hover");
    }
    if (target) {
      target.classList.add("pw-picker-hover");
    }
    lastHovered = target;
    const shape = sankeyShapeIn(path);
    if (shape) segments.ensure(shape);
    preview.update(target, path, evt);
  }

  function onClick(evt: MouseEvent): void {
    const path = evt.composedPath();
    const originalTarget = (path[0] ?? evt.target) as HTMLElement;
    const target = findTaggedAncestor(originalTarget);
    const clickTarget = originalTarget;
    cleanup();
    if (!target) {
      onCancel?.();
      return;
    }
    evt.preventDefault();
    evt.stopPropagation();
    const { granularity, detail } = refineGranularity(target, clickTarget, path, evt);
    onPicked({
      artifactId: target.dataset.pwArtifactId!,
      artifactName: target.dataset.pwArtifactName ?? "",
      granularity,
      detail,
      snapshot: readSnapshot(target),
      figure: watchedFigure(target),
    });
  }

  // The pointer left the window (no move reaches the page any more) or the window lost focus: the preview goes.
  function onLeave(evt: MouseEvent): void {
    if (!evt.relatedTarget) preview.clear();
  }
  function onBlur(): void {
    preview.clear();
  }

  function onKeyDown(evt: KeyboardEvent): void {
    if (evt.key === "Escape") {
      cleanup();
      onCancel?.();
    }
  }

  function cleanup(): void {
    document.removeEventListener("mousemove", onMouseMove, true);
    document.removeEventListener("click", onClick, true);
    document.removeEventListener("keydown", onKeyDown, true);
    document.removeEventListener("mouseout", onLeave, true);
    window.removeEventListener("blur", onBlur);
    if (lastHovered) lastHovered.classList.remove("pw-picker-hover");
    preview.clear();
    segments.stop();
    forgetMaps();
  }

  document.addEventListener("mousemove", onMouseMove, true);
  document.addEventListener("click", onClick, true);
  document.addEventListener("keydown", onKeyDown, true);
  document.addEventListener("mouseout", onLeave, true);
  window.addEventListener("blur", onBlur);
}
