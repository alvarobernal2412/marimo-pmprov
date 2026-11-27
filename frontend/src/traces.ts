// Traces of a process map: the sequences of activities that cases follow through a Linear Continuous Process Mapper map. The map
// library writes them into the `meta` of the figure's Sankey trace, `{"lcm": {"traces": [...], "truncated": bool}}`, with the
// indexes of the links and nodes each trace runs through (`nodes[0]` is the root, the START node), most frequent first. A trace is
// picked on the node where it ends (see endSegments) and recorded by its name, so a pick survives a redraw.
//
// A trace is only ever marked when its elements on the page can be told with confidence: anything that does not add up gives no
// elements, and the caller then marks the whole map instead (never another trace).

export interface MapTrace {
  name: string;
  sequence: string[];
  cases: number;
  links: number[];
  nodes: number[];
}

interface MapTraces {
  traces: MapTrace[];
  truncated: boolean; // the map has more traces than it stores: the ones stored do not cover all its cases
}

interface SankeyData {
  type?: string;
  meta?: unknown;
  node?: { label?: unknown };
  link?: { source?: unknown; target?: unknown };
}

interface PlotElement {
  data?: SankeyData[];
  _fullData?: SankeyData[];
}

// The Plotly graph div an element is drawn in, also from inside shadow roots (marimo draws Plotly inside a custom element).
export function plotOf(element: Element | null): Element | null {
  let node: Node | null = element;
  while (node) {
    const classes = (node as Element).classList;
    if (classes && classes.contains("js-plotly-plot")) return node as Element;
    node = node.parentNode ?? ((node as ShadowRoot).host as Node | undefined) ?? null;
  }
  return null;
}

function sankeyTraces(list: unknown): SankeyData[] {
  return Array.isArray(list) ? list.filter((t): t is SankeyData => !!t && (t as SankeyData).type === "sankey") : [];
}

const isIndex = (value: unknown): value is number => typeof value === "number" && Number.isInteger(value) && value >= 0;
const indexes = (value: unknown): number[] | null => (Array.isArray(value) && value.every(isIndex) ? (value as number[]) : null);

function readTrace(raw: unknown): MapTrace | null {
  const t = raw as Partial<MapTrace> | null;
  if (!t || typeof t.name !== "string") return null;
  const links = indexes(t.links);
  const nodes = indexes(t.nodes);
  const cases = Number(t.cases);
  if (!links || !nodes || nodes.length === 0 || !(cases >= 0)) return null;
  const sequence = Array.isArray(t.sequence) ? t.sequence.map(String) : [];
  return { name: t.name, sequence, cases, links, nodes };
}

/** The traces stored in the map `element` is part of, and whether the map stores only some of them. */
export function mapTracesOf(element: Element | null): MapTraces {
  const plot = plotOf(element) as (Element & PlotElement) | null;
  // the figure as it was given (`data`) keeps `meta` as written; the drawn one (`_fullData`) is looked at when it does not
  const sankey = [...sankeyTraces(plot?.data), ...sankeyTraces(plot?._fullData)];
  for (const trace of sankey) {
    const lcm = (trace.meta as { lcm?: { traces?: unknown; truncated?: unknown } } | null)?.lcm;
    if (!lcm || !Array.isArray(lcm.traces)) continue;
    let read = alreadyRead.get(lcm);
    if (!read) {
      const traces = lcm.traces.map(readTrace).filter((t): t is MapTrace => t !== null);
      read = { traces, truncated: lcm.truncated === true || traces.length < lcm.traces.length };
      alreadyRead.set(lcm, read);
    }
    return read;
  }
  return { traces: [], truncated: false };
}

// The picker reads the traces at every move of the pointer over a node; a figure drawn again comes with new arrays.
const alreadyRead = new WeakMap<object, MapTraces>();

export function tracesOf(element: Element): MapTrace[] {
  return mapTracesOf(element).traces;
}

// Where a trace can be picked: on the node where it ends. The cases that end at a node are drawn in the part of the node that no
// outgoing link leaves from (its ending zone; not always at the bottom: Plotly orders the links by where they go). That zone is cut
// into one segment per stored trace that ends there, most frequent first from the top. The segments are made to be seen and hit,
// not to scale: on a real map a trace's share of a node is often under a pixel (a node's value counts every repetition of a
// self-loop), so the zone is at least 8 px, every segment at least 6 px, and they fill the zone.
//
// Plotly's layout of a node (seen in a browser, Plotly 7.1): `value`, `y0`/`y1` the node's top and bottom in the map's pixels, and
// `sourceLinks`, the links leaving it, each with `y0` the centre where it leaves and `width` its height there.
export interface NodeLayout {
  value?: number;
  y0?: number;
  y1?: number;
  sourceLinks?: { y0?: number; width?: number }[];
}

export interface Zone {
  top: number;
  bottom: number;
}

export interface EndSegment extends Zone {
  trace: MapTrace;
}

const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const MIN_ZONE_PX = 0.5; // gaps thinner than this between links are rounding, not cases that end
const MIN_ZONE_SHOWN_PX = 8; // a smaller zone is grown to this, so that it can be seen and hit
const MIN_SEGMENT_PX = 6; // no segment is thinner; traces that do not fit get none

/** The largest part of a node that no outgoing link leaves from, or null when every case goes on. */
export function endingZone(node: NodeLayout): Zone | null {
  const { y0, y1 } = node;
  if (!finite(y0) || !finite(y1) || !(y1 > y0)) return null;
  const covered = (node.sourceLinks ?? [])
    .filter((l) => finite(l.y0) && finite(l.width) && l.width > 0)
    .map((l) => [Math.max(y0, l.y0! - l.width! / 2), Math.min(y1, l.y0! + l.width! / 2)])
    .filter(([a, b]) => b > a)
    .sort((a, b) => a[0] - b[0]);
  let best: Zone | null = null;
  const consider = (top: number, bottom: number) => {
    if (bottom - top > MIN_ZONE_PX && (!best || bottom - top > best.bottom - best.top)) best = { top, bottom };
  };
  let cursor = y0;
  for (const [a, b] of covered) {
    if (a > cursor) consider(cursor, a);
    cursor = Math.max(cursor, b);
  }
  consider(cursor, y1);
  return best;
}

/**
 * Where the traces that end at a node are offered: its ending zone, grown to 8 px (toward the middle of the node, or the whole node
 * when it is shorter) so that it can be seen and hit. Null when every case goes on.
 */
export function pickZone(node: NodeLayout): Zone | null {
  const zone = endingZone(node);
  if (!zone) return null;
  const y0 = node.y0!;
  const y1 = node.y1!;
  if (zone.bottom - zone.top >= MIN_ZONE_SHOWN_PX) return zone;
  if (y1 - y0 <= MIN_ZONE_SHOWN_PX) return { top: y0, bottom: y1 };
  if ((zone.top + zone.bottom) / 2 < (y0 + y1) / 2) {
    const bottom = Math.min(y1, zone.top + MIN_ZONE_SHOWN_PX);
    return { top: bottom - MIN_ZONE_SHOWN_PX, bottom };
  }
  const top = Math.max(y0, zone.bottom - MIN_ZONE_SHOWN_PX);
  return { top, bottom: top + MIN_ZONE_SHOWN_PX };
}

// Heights that add up to `total`, each proportional to its weight but none under `least` (those are set to `least` and the rest is
// shared again among the others). The caller keeps `weights.length * least <= total`.
function shares(weights: number[], total: number, least: number): number[] {
  const out = weights.map(() => 0);
  const fixed = new Set<number>();
  for (;;) {
    const open = weights.map((_, i) => i).filter((i) => !fixed.has(i));
    const left = total - fixed.size * least;
    const sum = open.reduce((s, i) => s + Math.max(weights[i], 0), 0);
    const share = (i: number) => (sum > 0 ? (left * Math.max(weights[i], 0)) / sum : left / open.length);
    const small = open.filter((i) => share(i) < least);
    if (small.length === 0 || small.length === open.length) {
      for (const i of open) out[i] = small.length === 0 ? share(i) : left / open.length;
      for (const i of fixed) out[i] = least;
      return out;
    }
    small.forEach((i) => fixed.add(i));
  }
}

/**
 * The segments of node `nodeIndex`: its pick zone (see pickZone) filled by the stored traces that end there, most frequent first
 * from the top, each as high as its share of their cases but at least 6 px. When they do not all fit, only the most frequent that
 * fit get a segment; a single trace gets the whole zone.
 */
export function endSegments(traces: MapTrace[], nodeIndex: number, node: NodeLayout): EndSegment[] {
  const zone = pickZone(node);
  if (!zone) return [];
  const ending = traces.filter((t) => t.nodes[t.nodes.length - 1] === nodeIndex);
  const height = zone.bottom - zone.top;
  const kept = ending.slice(0, Math.max(1, Math.floor(height / MIN_SEGMENT_PX + 1e-9)));
  if (kept.length === 0) return [];
  const heights = shares(kept.map((t) => t.cases), height, Math.min(MIN_SEGMENT_PX, height / kept.length));
  const out: EndSegment[] = [];
  let top = zone.top;
  kept.forEach((trace, i) => {
    const bottom = i === kept.length - 1 ? zone.bottom : top + heights[i];
    out.push({ trace, top, bottom });
    top = bottom;
  });
  return out;
}

/** The trace whose segment is at `y` (in the map's pixels), or null. */
export function traceAtPoint(segments: EndSegment[], y: number): MapTrace | null {
  return segments.find((s) => y >= s.top && y <= s.bottom)?.trace ?? null;
}

/** Where to draw the lines that show the segments: the zone's top and the end of each segment (the last one is the zone's bottom). */
export function dividerLines(zone: Zone, segments: Zone[]): number[] {
  const lines = [zone.top];
  for (const y of [...segments.map((s) => s.bottom), zone.bottom]) {
    if (y - lines[lines.length - 1] > MIN_ZONE_PX) lines.push(y);
  }
  return lines;
}

// d3 data Plotly puts on the elements of a Sankey. `pointNumber` is the position in the figure's own node and link arrays: Plotly
// skips links without a value and nodes without links, so d3's own `index` of a link or of a node in a link need not be that.
interface NodeDatum {
  index?: number;
  pointNumber?: number;
  label?: unknown;
}
interface SankeyDatum {
  index?: number;
  pointNumber?: number;
  node?: NodeDatum;
  link?: { pointNumber?: number; source?: NodeDatum; target?: NodeDatum };
}

const datumOf = (el: Element) => (el as unknown as { __data__?: SankeyDatum }).__data__;

// Relied on (seen in a browser with Plotly 7 in marimo): a node's `__data__.node.pointNumber` and a link's
// `__data__.link.pointNumber` are their positions in the figure's node and link arrays, and a link's `link.source.pointNumber` /
// `link.target.pointNumber` are its ends there. d3's own `index` is not used: without `pointNumber` nothing is matched, and the
// caller marks the whole map.

/** The index in the figure's node arrays of a `sankey-node` element's datum, or null. */
export function nodeIndexOf(d: SankeyDatum | undefined): number | null {
  return isIndex(d?.node?.pointNumber) ? d.node.pointNumber : null;
}

function linkIndexOf(d: SankeyDatum | undefined): number | null {
  if (isIndex(d?.link?.pointNumber)) return d.link.pointNumber;
  return isIndex(d?.pointNumber) ? d.pointNumber : null;
}

function asList(value: unknown): unknown[] | null {
  if (Array.isArray(value)) return value;
  if (ArrayBuffer.isView(value)) return Array.from(value as unknown as ArrayLike<number>);
  return null;
}

function deepAll(root: Element): Element[] {
  const out: Element[] = [];
  const walk = (node: Element | ShadowRoot) => {
    for (const el of Array.from(node.querySelectorAll("*"))) {
      out.push(el);
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(root);
  if (root.shadowRoot) walk(root.shadowRoot);
  return out;
}

const flat = (label: unknown) => String(label ?? "").replace(/\s+/g, " ").trim();

/** Whether the end of a link drawn on the page is the node the figure gives as that end. */
export function sameNode(end: NodeDatum | undefined, figureIndex: unknown): boolean {
  return !!end && isIndex(figureIndex) && isIndex(end.pointNumber) && end.pointNumber === figureIndex;
}

export interface FigureArrays {
  sources: unknown[];
  targets: unknown[];
  labels: unknown[];
}

/** The figure's position of each link and node drawn on the page. */
export interface MapIndex {
  linkAt: Map<number, Element>;
  nodeAt: Map<number, Element>;
}

/**
 * Matches the links and nodes drawn on the page to the figure's arrays, or null when that cannot be done with confidence: an element
 * without `pointNumber`, two elements at one position, a link whose ends are not the figure's, a node whose label is not.
 */
export function buildMapIndex(links: Element[], nodes: Element[], figure: FigureArrays): MapIndex | null {
  const linkAt = new Map<number, Element>();
  for (const el of links) {
    const d = datumOf(el);
    const k = linkIndexOf(d);
    if (k === null || linkAt.has(k)) return null;
    if (!sameNode(d?.link?.source, figure.sources[k]) || !sameNode(d?.link?.target, figure.targets[k])) return null;
    linkAt.set(k, el);
  }
  const nodeAt = new Map<number, Element>();
  for (const el of nodes) {
    const d = datumOf(el);
    const k = nodeIndexOf(d);
    if (k === null || nodeAt.has(k)) return null;
    if (k < figure.labels.length && d?.node?.label !== undefined && flat(d.node.label) !== flat(figure.labels[k])) return null;
    nodeAt.set(k, el);
  }
  return { linkAt, nodeAt };
}

/** A trace's links, then the boxes of its nodes (the `rect` of each `g.sankey-node`); empty when one of them is not drawn. */
export function elementsOfTrace(index: MapIndex, trace: MapTrace): SVGElement[] {
  const out: SVGElement[] = [];
  for (const k of trace.links) {
    const el = index.linkAt.get(k);
    if (!el) return [];
    out.push(el as SVGElement);
  }
  for (const k of trace.nodes) {
    const el = index.nodeAt.get(k);
    if (!el) return [];
    out.push(((el.querySelector("rect") as SVGElement | null) ?? el) as SVGElement);
  }
  return out;
}

// The figure's link ends and node labels: from the drawn figure, which has the arrays decoded (Plotly 6 may send them as
// typed-array specs), else as given. One Sankey per figure only.
function figureArrays(plot: (Element & PlotElement) | null): FigureArrays | null {
  const drawn = sankeyTraces(plot?._fullData);
  const given = sankeyTraces(plot?.data);
  const sankey = drawn.length > 0 ? drawn : given;
  if (sankey.length !== 1) return null;
  const sources = asList(sankey[0].link?.source) ?? asList(given[0]?.link?.source);
  const targets = asList(sankey[0].link?.target) ?? asList(given[0]?.link?.target);
  const labels = asList(sankey[0].node?.label) ?? asList(given[0]?.node?.label) ?? [];
  return sources && targets ? { sources, targets, labels } : null;
}

// What is known about a map while it is drawn the same: built on first use by one walk of the map, kept until Plotly adds or removes
// a node or a link or is given another figure. A large map has thousands of elements: the picker looks things up here at every move
// of the pointer instead of walking it.
interface KnownMap {
  data: unknown;
  fullData: unknown;
  index: MapIndex | null;
  segments: Map<string, EndSegment[]>;
  observer: MutationObserver | null;
}

const known = new Map<Element, KnownMap>();

function forget(plot: Element): void {
  known.get(plot)?.observer?.disconnect();
  known.delete(plot);
}

/** Forgets every map (the picker calls it when it is done). */
export function forgetMaps(): void {
  for (const plot of [...known.keys()]) forget(plot);
}

// Whether a change in a map is Plotly drawing it: a node or a link added or removed, not a hover label or our own lines.
export function drawsMap(node: Node): boolean {
  const el = node as Element;
  if (!el.classList) return false;
  if (el.classList.contains("sankey-link") || el.classList.contains("sankey-node")) return true;
  return typeof el.querySelector === "function" && el.querySelector(".sankey-link, .sankey-node") !== null;
}

function knownMap(plot: Element): KnownMap {
  const figure = plot as Element & PlotElement;
  const entry = known.get(plot);
  if (entry && entry.data === figure.data && entry.fullData === figure._fullData) return entry;
  forget(plot);
  for (const other of [...known.keys()]) if (!other.isConnected) forget(other);
  const all = deepAll(plot);
  const arrays = figureArrays(figure);
  const index = arrays
    ? buildMapIndex(all.filter((e) => e.classList.contains("sankey-link")), all.filter((e) => e.classList.contains("sankey-node")), arrays)
    : null;
  const made: KnownMap = { data: figure.data, fullData: figure._fullData, index, segments: new Map(), observer: null };
  if (typeof MutationObserver !== "undefined") {
    made.observer = new MutationObserver((records) => {
      if (records.some((r) => [...r.addedNodes, ...r.removedNodes].some(drawsMap))) forget(plot);
    });
    made.observer.observe(plot, { childList: true, subtree: true });
  }
  known.set(plot, made);
  return made;
}

/** The segments of a node of the map `plot` (see endSegments), kept while the node keeps its place and size. */
export function segmentsAt(plot: Element, nodeIndex: number, layout: NodeLayout): EndSegment[] {
  const { segments } = knownMap(plot);
  const key = `${nodeIndex}|${layout.y0}|${layout.y1}|${layout.value}|${layout.sourceLinks?.length ?? 0}`;
  let found = segments.get(key);
  if (!found) {
    found = endSegments(mapTracesOf(plot).traces, nodeIndex, layout);
    segments.set(key, found);
  }
  return found;
}

// The Plotly graph div under an artifact's element, remembered (finding it walks the artifact, through shadow roots).
const plotUnder = new WeakMap<Element, Element>();

function plotIn(root: Element): Element | null {
  const remembered = plotUnder.get(root);
  if (remembered?.isConnected) return remembered;
  const first = deepAll(root).find((e) => e.classList.contains("sankey-node") || e.classList.contains("sankey-link")) ?? null;
  const plot = plotOf(first);
  if (plot) plotUnder.set(root, plot);
  return plot;
}

/**
 * The elements of `trace` in the map under `root`: its links (`path.sankey-link`) first, then the boxes of its nodes (the `rect` of
 * each `g.sankey-node`). Empty when the page's elements cannot be matched to the figure's arrays with confidence, or when a link or
 * a node of the trace is not drawn.
 */
export function traceElements(root: Element, trace: MapTrace): SVGElement[] {
  const plot = plotIn(root);
  const index = plot ? knownMap(plot).index : null;
  return index ? elementsOfTrace(index, trace) : [];
}

/** The one stored trace of the map under `root` with this name, or null (not stored, or stored twice). */
export function findTrace(root: Element, name: string): MapTrace | null {
  const found = mapTracesOf(plotIn(root)).traces.filter((t) => t.name === name);
  return found.length === 1 ? found[0] : null;
}

/** "trace A → K → L → Z · 2 cases", for the label that says what a click would pick. */
export function traceLabel(trace: MapTrace): string {
  return `trace ${shortTraceName(trace.name)} · ${trace.cases} ${trace.cases === 1 ? "case" : "cases"}`;
}

// A trace of a real log can have many steps, and its whole name does not fit in a label, a chip or a row of the panel. It is shown
// by its first three and last two steps and the number of steps; the recorded detail keeps the whole name (it is what is matched),
// and the element showing the short one carries the whole name in its title.
const SHOWN_WHOLE = 6;

/** A trace's name as it is shown: whole up to six steps, else `A → B → C → … (n steps) … → Y → Z`. */
export function shortTraceName(name: string): string {
  const parts = name.split(" → ");
  if (parts.length <= SHOWN_WHOLE) return name;
  return `${parts.slice(0, 3).join(" → ")} → … (${parts.length} steps) … → ${parts.slice(-2).join(" → ")}`;
}

/** A pin's detail as it is shown: a trace's name shortened, anything else as recorded. */
export function shownDetail(granularity: string | null | undefined, detail: string): string {
  return granularity === "trace" ? shortTraceName(detail) : detail;
}
