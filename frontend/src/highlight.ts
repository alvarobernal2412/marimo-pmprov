// After a reviewer presses Replay on a note, point at what the note is about: scroll the targeted element of the
// notebook into view and mark it. A target is found by the name it was picked under
// (`data-pw-artifact-name`, set by show_table / show_chart / show).
//
// A pinned part of a map (a node, a link, the links and nodes of a trace) keeps its colour and the rest of the map is faded, a pinned
// cell or column gets an amber outline and fill; these stay until the reviewer moves on. A whole table or map gets a short pulse.
// The marks are set inline: the elements live in the notebook, outside the widget's shadow root, so the widget's stylesheet does
// not reach them.

import { locateAll, type Located } from "./locators";
import { drawsMap, plotOf } from "./traces";
import { backgroundOf, boxInSvg, matrixAttr, observedFor, overlays, svgElement, swapClones, unionBox, type Box, type Matrix } from "./overlay";

interface TargetRef {
  artifactName?: string;
  granularity?: string;
  detail?: string | null;
}

const FIRST_LOOK_MS = 500; // the notebook's cells re-run when the cursor moves; give them time to draw
const LOOK_EVERY_MS = 200;
const GIVE_UP_MS = 6000;
const TAB_SWITCH_MS = 300; // a tab opens on the next draw of the page
const RECHECK_MS = 1500; // a cell that finishes re-running late replaces the element that was marked
const FLASH_COLOR = "#F59E0B";

function* inTree(root: Document | ShadowRoot): Generator<HTMLElement> {
  for (const el of root.querySelectorAll<HTMLElement>("*")) {
    yield el;
    if (el.shadowRoot) yield* inTree(el.shadowRoot);
  }
}

export function findTargets(names: string[]): HTMLElement[] {
  const wanted = new Set(names);
  const found: HTMLElement[] = [];
  for (const el of inTree(document)) {
    const name = el.dataset?.pwArtifactName;
    if (name && wanted.has(name) && el.classList.contains("pw-annotatable")) found.push(el);
  }
  return found;
}

// A table or map inside a tab the reader is not on cannot be seen, so that tab is opened first. marimo keeps the content of every tab
// as a child of its tabs element (in the order of the tabs) and draws the content of the open tab only. Returns true when a tab was
// clicked, so that the caller gives the page a moment to draw it before it points at anything in it.
function revealTab(el: Element): boolean {
  let child: Node = el;
  while (child.parentNode) {
    const parent: Node = child.parentNode;
    if (parent instanceof HTMLElement && parent.localName === "marimo-tabs" && parent.shadowRoot) {
      const index = [...parent.children].indexOf(child as Element);
      const tab = parent.shadowRoot.querySelectorAll<HTMLElement>('[role="tab"]')[index];
      if (!tab || tab.getAttribute("aria-selected") === "true") return false;
      // marimo's tabs open on the press of the mouse button, not on the click
      for (const type of ["mousedown", "mouseup", "click"]) {
        tab.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, composed: true, button: 0 }));
      }
      return true;
    }
    child = parent instanceof ShadowRoot ? parent.host : parent;
  }
  return false;
}

// What is drawn on the page: the copy of a table that marimo keeps for a tab that is not open is not.
function shown(targets: Located[]): Located[] {
  const drawn = targets.filter((el) => el.getClientRects().length > 0);
  return drawn.length > 0 ? drawn : targets;
}

// A whole table or map: a short pulse of its outline, enough to find it on the page.
function pulse(el: HTMLElement): void {
  const previous = { outline: el.style.outline, outlineOffset: el.style.outlineOffset };
  el.style.outline = `3px solid ${FLASH_COLOR}`;
  el.style.outlineOffset = "4px";
  const animation = el.animate(
    [{ outlineColor: FLASH_COLOR }, { outlineColor: "transparent" }, { outlineColor: FLASH_COLOR }, { outlineColor: "transparent" }],
    { duration: 2400, easing: "ease-in-out" },
  );
  const restore = () => {
    el.style.outline = previous.outline;
    el.style.outlineOffset = previous.outlineOffset;
  };
  animation.onfinish = restore;
  animation.oncancel = restore;
}

const isWhole = (el: Located) => el instanceof HTMLElement && el.classList.contains("pw-annotatable");

export function highlightTargets(refs: TargetRef[]): void {
  const names = refs.map((ref) => ref.artifactName ?? "").filter((name) => name !== "");
  if (names.length === 0) return stopMarks(); // nothing to point at: the previous marks go all the same
  // Every pinned element inside each artifact when it can be found (all the links and nodes of a trace), else the whole artifact.
  // A map is drawn again when the step changes, which can take longer than the first look, so the pinned elements are looked for
  // until they show up.
  const picked = refs.filter((ref) => ref.detail);
  highlightWhere(
    () => findTargets(names).flatMap((root) => pinnedIn(root, refs)),
    (found) => picked.length === 0 || found.every((el) => !isWhole(el)),
  );
}

// What the refs naming this artifact pin in it (see pinnedFor).
function pinnedIn(root: HTMLElement, refs: TargetRef[]): Located[] {
  const own = refs.filter((ref) => ref.artifactName === root.dataset.pwArtifactName);
  return pinnedFor(own, (ref) => locateAll(root, ref.granularity ?? "", ref.detail ?? ""), root);
}

/**
 * Everything `refs` pin in one artifact: the union of the elements each ref locates. A ref to the whole artifact (no detail, such as
 * a `chart_selection` of the whole map) adds nothing when other refs pin elements in it; the artifact itself (`whole`, which gets
 * the short pulse) comes back when only such refs are there, and also when a ref with a detail cannot be found, so that it is not
 * left out silently.
 */
export function pinnedFor<R extends { detail?: string | null }, T>(refs: R[], locate: (ref: R) => T[], whole: T): T[] {
  const found: T[] = [];
  let missing = false;
  for (const ref of refs) {
    if (!ref.detail) continue;
    const located = locate(ref);
    if (located.length === 0) missing = true;
    for (const el of located) if (!found.includes(el)) found.push(el);
  }
  return missing || found.length === 0 ? [whole, ...found] : found;
}

// Stepping through a recorded analysis: point at what the step reached (the tables and maps the notebook shows under
// this step's own state id), so it is easy to see where a step shows up in the notebook.
export function findProducedBy(stateId: string): HTMLElement[] {
  const found: HTMLElement[] = [];
  for (const el of inTree(document)) {
    if (el.dataset?.pwArtifactId === stateId && el.classList.contains("pw-annotatable")) found.push(el);
  }
  return found;
}

export function highlightProducedBy(stateId: string): void {
  highlightWhere(() => findProducedBy(stateId));
}

function highlightWhere(find: () => Located[], settled: (found: Located[]) => boolean = () => true): void {
  stopMarks(); // a new replay or step ends the previous one, also one still waiting for the notebook
  const started = Date.now();
  const token = generations.start();
  const live = () => generations.isCurrent(token);
  let marked: Located[] = [];
  let undo = () => {};
  let recheckUntil = 0;
  let watch = 0;

  // A click or Escape ends this highlight, also while it is still waiting to look.
  untilDismissed(() => {
    if (live()) generations.cancel();
    window.clearInterval(watch);
    undo();
    undo = () => {};
  });

  // A pinned element on a map that is drawn again is looked for in the new drawing (see markOnMap); one that is not there any more
  // leaves the whole artifact pulsing instead.
  const relocate = (scope: Element) => () =>
    live() ? find().filter((el): el is SVGElement => el instanceof SVGElement && plotOf(el) === scope) : [];
  const lost = (scope: Element) => () => {
    if (!live()) return;
    const whole = artifactOf(scope);
    if (whole) pulse(whole);
  };

  // Pulses the whole artifacts among `fresh`, and marks the pinned elements of `targets` steadily: all of them again, since the
  // map they are on may have been drawn again.
  const markAll = (targets: Located[], fresh: Located[]) => {
    fresh.filter(isWhole).forEach((el) => pulse(el as HTMLElement));
    undo();
    undo = markGroups(targets.filter((el) => !isWhole(el)), relocate, lost);
  };

  const look = () => {
    if (!live()) return;
    const targets = find();
    if (targets.length === 0) {
      if (Date.now() - started < GIVE_UP_MS) setTimeout(look, LOOK_EVERY_MS);
      return;
    }
    const onScreen = targets.some((el) => el.getClientRects().length > 0); // something to point at is already drawn
    if (!onScreen && targets.some(revealTab) && Date.now() - started < GIVE_UP_MS) {
      setTimeout(look, TAB_SWITCH_MS); // look again once the tab has opened
      return;
    }
    const drawn = shown(targets);
    marked = drawn;
    drawn[0].scrollIntoView({ behavior: "smooth", block: "center" });
    markAll(drawn, drawn);
    recheckUntil = Date.now() + GIVE_UP_MS;
    setTimeout(recheck, RECHECK_MS);
    // A cell that re-runs later (a slow map, the next redraw of the notebook) replaces what is marked; then look again for a while.
    watch = window.setInterval(() => {
      if (!live()) return window.clearInterval(watch);
      if (!marked.some((el) => !el.isConnected)) return;
      const waiting = Date.now() < recheckUntil;
      recheckUntil = Date.now() + GIVE_UP_MS;
      if (!waiting) recheck();
    }, WATCH_MS);
  };

  const recheck = () => {
    if (!live()) return;
    const now = shown(find());
    const replaced = now.filter((el) => !marked.includes(el));
    if (replaced.length > 0 || now.length < marked.length) {
      marked = now;
      markAll(now, replaced);
    }
    if (!settled(now) && Date.now() < recheckUntil) setTimeout(recheck, LOOK_EVERY_MS);
    else recheckUntil = 0;
  };

  setTimeout(look, FIRST_LOOK_MS);
}

const WATCH_MS = 1000;

// The table or map an element is part of, also from inside shadow roots.
function artifactOf(el: Element): HTMLElement | null {
  let node: Node | null = el;
  while (node) {
    if (node instanceof HTMLElement && node.classList.contains("pw-annotatable")) return node;
    node = node.parentNode ?? ((node as ShadowRoot).host as Node | undefined) ?? null;
  }
  return null;
}

/** Hands out a number per highlight; a timer of a highlight that is no longer the current one does nothing. */
export class Generations {
  private current = 0;
  start(): number {
    return ++this.current;
  }
  cancel(): void {
    this.current++;
  }
  isCurrent(token: number): boolean {
    return token === this.current;
  }
}

/**
 * At most one mark per map. Marking a map that is marked undoes the old mark first, so that two marks never stack on a map (the
 * older one's undo would take away the newer one's tags). The undo a mark returns does nothing once it was replaced.
 */
export class MarksPerMap<K> {
  private undos = new Map<K, () => void>();
  replace(scope: K, mark: () => () => void): () => void {
    this.undos.get(scope)?.();
    let undone = false;
    const inner = mark();
    const undo = () => {
      if (undone) return;
      undone = true;
      if (this.undos.get(scope) === undo) this.undos.delete(scope);
      inner();
    };
    this.undos.set(scope, undo);
    return undo;
  }
  clear(): void {
    for (const undo of [...this.undos.values()]) undo();
  }
}

const generations = new Generations();
const perMap = new MarksPerMap<Element>();

// The marks stay on the page until the reviewer moves on: a click or Escape, or the next replay or step.
const marks = new Set<() => void>();

function stopMarks(): void {
  generations.cancel();
  for (const stop of [...marks]) stop();
}

function untilDismissed(cleanup: () => void): void {
  function stop(): void {
    marks.delete(stop);
    document.removeEventListener("pointerdown", stop, true);
    document.removeEventListener("keydown", onKey, true);
    cleanup();
  }
  function onKey(event: KeyboardEvent): void {
    if (event.key === "Escape") stop();
  }
  marks.add(stop);
  document.addEventListener("pointerdown", stop, true);
  document.addEventListener("keydown", onKey, true);
}

// Marks elements map by map, so that the rest of a map is dimmed around everything marked on it.
function markGroups(
  elements: Located[],
  relocate: (scope: Element) => () => Located[],
  lost: (scope: Element) => () => void,
): () => void {
  const groups = new Map<Element, Located[]>();
  for (const el of elements) {
    const scope = el instanceof SVGElement ? (plotOf(el) ?? el.ownerSVGElement ?? el) : el;
    groups.set(scope, [...(groups.get(scope) ?? []), el]);
  }
  const undos = [...groups].map(([scope, group]) => markSteady(group, scope, relocate(scope), lost(scope)));
  return () => undos.forEach((u) => u());
}

// The amber of the report (report_targets.py) for a cell.
const CELL_FILL = "rgba(245, 158, 11, 0.3)";

// A map is marked by fading the rest under a veil: one rectangle of the page's background over the map at 0.75 (the rest shows at
// 0.25), and above it copies of the marked links and node boxes, placed exactly where the originals are (see overlay.ts).
const VEIL_OPACITY = 0.75;
const VEIL_MARGIN = 4;
const WATCHED = ["d", "transform", "style", "x", "y", "width", "height"];

// Everything a mark needs to read from the page, read before anything is written (a read after a write makes the browser lay the
// page out again in the middle of the mark).
interface MapPlan {
  svg: SVGSVGElement;
  colour: string;
  veil: Box | null;
  copies: { original: SVGElement; matrix: Matrix }[];
}

function closestClass(el: Element, name: string): Element | null {
  for (let node: Element | null = el; node; node = node.parentElement) if (node.classList.contains(name)) return node;
  return null;
}

function measure(shapes: SVGElement[], scope: Element, colour?: string): MapPlan | null {
  const svg = shapes[0]?.ownerSVGElement;
  if (!svg) return null;
  const copies = shapes
    .map((original) => ({ original, matrix: (original as SVGGraphicsElement).getCTM() }))
    .filter((c): c is { original: SVGElement; matrix: DOMMatrix } => c.matrix !== null);
  // the Sankey's own group (`g.sankey`), so that a legend beside the map is not veiled; without one, the whole SVG
  const sankey = closestClass(shapes[0], "sankey") as SVGGraphicsElement | null;
  const matrix = sankey?.getCTM();
  const whole = { x: 0, y: 0, width: Number(svg.getAttribute("width")) || 0, height: Number(svg.getAttribute("height")) || 0 };
  const veil = sankey && matrix ? unionBox([boxInSvg(sankey.getBBox(), matrix)], VEIL_MARGIN) : whole;
  return { svg, colour: colour ?? backgroundOf(scope), veil, copies };
}

/**
 * Marks `elements` steadily until the returned function is called. On a map (SVG elements) they keep their colour and the rest of
 * the map under `scope` is faded; a table cell or column gets an amber outline and fill; a whole artifact gets the short pulse.
 * When Plotly draws the map again, the marked elements are looked for with `relocate`; when they are not there any more the map's
 * mark is undone and `lost` is called (a map is never left faded with nothing marked).
 */
export function markSteady(
  elements: Located[],
  scope: Element,
  relocate: () => Located[] = () => [],
  lost: () => void = () => {},
): () => void {
  const undos: (() => void)[] = [];
  const shapes = elements.filter((el): el is SVGElement => el instanceof SVGElement);
  const plan = shapes.length > 0 ? measure(shapes, scope) : null; // read first: the marks below write
  for (const el of elements) {
    if (el instanceof SVGElement) continue;
    if (isWhole(el)) pulse(el as HTMLElement);
    else undos.push(markCell(el as HTMLElement));
  }
  if (plan) {
    const again = () => relocate().filter((el): el is SVGElement => el instanceof SVGElement);
    undos.push(perMap.replace(scope, () => markOnMap(plan, shapes, scope, again, lost)));
  }
  return () => undos.forEach((u) => u());
}

// Drawn inside the cell, so that the cells around it do not cover the outline.
function markCell(el: HTMLElement): () => void {
  const previous = { outline: el.style.outline, outlineOffset: el.style.outlineOffset, background: el.style.backgroundColor };
  el.style.outline = `3px solid ${FLASH_COLOR}`;
  el.style.outlineOffset = "-3px";
  el.style.backgroundColor = CELL_FILL;
  return () => {
    el.style.outline = previous.outline;
    el.style.outlineOffset = previous.outlineOffset;
    el.style.backgroundColor = previous.background;
  };
}

// The group a marked shape moves with: a node's box moves with its `g.sankey-node`; a link moves by its own `d`.
function groupOf(el: Element): Element | null {
  const parent = el.parentElement;
  return parent && parent.classList.contains("sankey-node") ? parent : null;
}

// While the mark is on, two observers follow the map: one on its children (Plotly drew it again: nodes or links added or removed),
// one on the attributes of the marked originals only (a node dragged, a link reshaped). Either makes the copies be made again, once
// per animation frame: the marked elements are looked for again if they were replaced, everything is measured, then written.
function markOnMap(first: MapPlan, firstShapes: SVGElement[], scope: Element, relocate: () => SVGElement[], lost: () => void): () => void {
  const overlay = overlays.acquire(first.svg);
  const colour = first.colour;
  let shapes = firstShapes;
  let copies: SVGElement[] = [];
  let done = false;
  let frame = 0;
  const veil = svgElement("rect");
  veil.setAttribute("style", `fill:${colour};fill-opacity:${VEIL_OPACITY};pointer-events:none`);
  overlay.veil.appendChild(veil);

  const draw = (plan: MapPlan) => {
    if (plan.veil) {
      veil.setAttribute("x", String(plan.veil.x));
      veil.setAttribute("y", String(plan.veil.y));
      veil.setAttribute("width", String(plan.veil.width));
      veil.setAttribute("height", String(plan.veil.height));
    }
    copies = swapClones(
      copies,
      plan.copies,
      ({ original, matrix }) => {
        const copy = original.cloneNode(false) as SVGElement;
        copy.removeAttribute("class"); // not a node or a link of the map for anything that looks for those
        copy.setAttribute("transform", matrixAttr(matrix));
        overlay.vivid.appendChild(copy);
        return copy;
      },
      (copy) => copy.remove(),
    );
  };

  const attributes = new MutationObserver(() => schedule());
  const watch = () => {
    attributes.disconnect();
    for (const el of observedFor<Element>(shapes, groupOf)) {
      attributes.observe(el, { attributes: true, attributeFilter: WATCHED });
    }
  };

  const apply = () => {
    frame = 0;
    if (done) return;
    if (shapes.some((el) => !el.isConnected)) {
      const found = relocate();
      if (found.length === 0) {
        undo();
        lost();
        return;
      }
      shapes = found;
    }
    const plan = measure(shapes, scope, colour);
    if (!plan) return;
    draw(plan);
    watch();
  };
  const schedule = () => {
    if (!done && !frame) frame = requestAnimationFrame(apply);
  };

  const children = new MutationObserver((records) => {
    if (records.some((r) => [...r.addedNodes, ...r.removedNodes].some(drawsMap))) schedule();
  });

  const undo = () => {
    if (done) return;
    done = true;
    children.disconnect();
    attributes.disconnect();
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    copies.forEach((c) => c.remove());
    copies = [];
    veil.remove();
    overlays.release(first.svg);
  };

  draw(first);
  watch();
  children.observe(scope, { childList: true, subtree: true });
  return undo;
}
