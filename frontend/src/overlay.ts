// What we draw over a Plotly chart: one group at the end of the chart's SVG, above the map and below Plotly's hover layer (which is
// in another SVG on top). In it, in this order: the veil that fades a marked map, the copies of the marked links and node boxes
// that stay vivid above it, and the picker's end-segment lines, so that those show over the veil too. The group and everything in
// it ignore the pointer, so hovering, dragging and picking reach Plotly's own elements underneath. Nothing is ever written on
// Plotly's elements: on a map of a thousand links, restyling them all is what made a mark slow (the browser redraws every
// translucent element), while a veil and a few copies cost the same on any map.

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** An SVG transformation matrix (a, b, c, d, e, f), as `getCTM()` gives it. */
export interface Matrix {
  a: number;
  b: number;
  c: number;
  d: number;
  e: number;
  f: number;
}

/** A box in an element's own units, as it lies in the SVG once the element's matrix is applied (the box around its corners). */
export function boxInSvg(box: Box, m: Matrix): Box {
  const corners = [
    [box.x, box.y],
    [box.x + box.width, box.y],
    [box.x, box.y + box.height],
    [box.x + box.width, box.y + box.height],
  ].map(([x, y]) => [m.a * x + m.c * y + m.e, m.b * x + m.d * y + m.f]);
  const xs = corners.map((p) => p[0]);
  const ys = corners.map((p) => p[1]);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, width: Math.max(...xs) - x, height: Math.max(...ys) - y };
}

/** The box around all `boxes`, grown by `margin` on every side; null for none. */
export function unionBox(boxes: Box[], margin = 0): Box | null {
  if (boxes.length === 0) return null;
  const left = Math.min(...boxes.map((b) => b.x)) - margin;
  const top = Math.min(...boxes.map((b) => b.y)) - margin;
  const right = Math.max(...boxes.map((b) => b.x + b.width)) + margin;
  const bottom = Math.max(...boxes.map((b) => b.y + b.height)) + margin;
  return { x: left, y: top, width: right - left, height: bottom - top };
}

/**
 * Something several users share per key, made by the first and taken away by the last: the overlay group of an SVG is used by a
 * mark and by the picker's lines. `release` without an `acquire` does nothing.
 */
export class Shared<K, V> {
  private held = new Map<K, { count: number; value: V }>();
  constructor(
    private make: (key: K) => V,
    private destroy: (value: V) => void,
  ) {}
  acquire(key: K): V {
    const entry = this.held.get(key);
    if (entry) {
      entry.count++;
      return entry.value;
    }
    const value = this.make(key);
    this.held.set(key, { count: 1, value });
    return value;
  }
  release(key: K): void {
    const entry = this.held.get(key);
    if (!entry) return;
    if (--entry.count > 0) return;
    this.held.delete(key);
    this.destroy(entry.value);
  }
  /** The value held for `key`, without taking a share of it. */
  peek(key: K): V | undefined {
    return this.held.get(key)?.value;
  }
  get size(): number {
    return this.held.size;
  }
}

/** Replaces the copies `old` by new ones made from `originals`: every old copy is dropped, one new copy per original. */
export function swapClones<O, C>(old: C[], originals: O[], make: (original: O) => C | null, drop: (clone: C) => void): C[] {
  old.forEach(drop);
  return originals.map(make).filter((c): c is C => c !== null);
}

/**
 * The originals a mark watches for changes of shape or place: each marked element and the group it moves with (a node's box moves
 * with its `g.sankey-node`), each once. Nothing else of the map is watched.
 */
export function observedFor<T>(marked: T[], groupOf: (el: T) => T | null): T[] {
  const out: T[] = [];
  for (const el of marked) {
    for (const one of [el, groupOf(el)]) if (one !== null && !out.includes(one)) out.push(one);
  }
  return out;
}

export const matrixAttr = (m: Matrix) => `matrix(${m.a},${m.b},${m.c},${m.d},${m.e},${m.f})`;

const SVG_NS = "http://www.w3.org/2000/svg";

export interface Overlay {
  root: SVGGElement;
  veil: SVGGElement;
  vivid: SVGGElement;
  lines: SVGGElement;
}

function group(parent: Element): SVGGElement {
  const g = document.createElementNS(SVG_NS, "g") as SVGGElement;
  parent.appendChild(g);
  return g;
}

export const overlays = new Shared<SVGSVGElement, Overlay>(
  (svg) => {
    const root = document.createElementNS(SVG_NS, "g") as SVGGElement;
    root.setAttribute("data-pw-overlay", "");
    root.setAttribute("style", "pointer-events:none");
    const overlay = { root, veil: group(root), vivid: group(root), lines: group(root) };
    svg.appendChild(root);
    return overlay;
  },
  (overlay) => overlay.root.remove(),
);

export function svgElement(tag: string): SVGElement {
  return document.createElementNS(SVG_NS, tag) as SVGElement;
}

/** The colour behind a chart: the first background up from it (through shadow roots) that is not transparent, else white. */
export function backgroundOf(el: Element): string {
  let node: Node | null = el;
  while (node) {
    if (node instanceof Element) {
      const colour = getComputedStyle(node).backgroundColor;
      if (colour && colour !== "transparent" && !/^rgba\(.*,\s*0\)$/.test(colour)) return colour;
    }
    node = node.parentNode ?? ((node as ShadowRoot).host as Node | undefined) ?? null;
  }
  return "#ffffff";
}
