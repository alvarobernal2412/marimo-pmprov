// While the picker is armed, a map that stores its traces shows where they can be picked: thin lines across each node where traces
// end, around the zone they are picked in and between the segments of the traces that end there (see endSegments in traces.ts).
// Each line is a dark and a white line side by side, so that it shows on white, grey and black nodes alike. The lines are drawn in
// the overlay above the map, placed by each node's matrix, and drawn again whenever Plotly draws the map again or moves a node.
import { matrixAttr, overlays, svgElement, type Matrix } from "./overlay";
import { dividerLines, segmentsAt, pickZone, mapTracesOf, nodeIndexOf, plotOf, type NodeLayout } from "./traces";

const LINE_STYLES = [
  { offset: -0.5, style: "stroke:#111827;stroke-width:1;fill:none;pointer-events:none" },
  { offset: 0.5, style: "stroke:#ffffff;stroke-width:1;fill:none;pointer-events:none" },
];

function plotsUnder(root: Document | ShadowRoot | Element, out: Element[] = []): Element[] {
  for (const el of Array.from(root.querySelectorAll("*"))) {
    if (el.classList.contains("js-plotly-plot")) out.push(el);
    if (el.shadowRoot) plotsUnder(el.shadowRoot, out);
  }
  return out;
}

interface NodeDatum {
  node?: { pointNumber?: number } & NodeLayout;
}

// Where the lines of every node of one map go: per line its path in the node box's own units and the box's matrix in the SVG. Only
// reads the page; drawing comes after (see draw below), so that the page is not laid out again in between.
function measureLines(plot: Element): { svg: SVGSVGElement | null; lines: { d: string; style: string; matrix: Matrix }[] } {
  const lines: { d: string; style: string; matrix: Matrix }[] = [];
  let svg: SVGSVGElement | null = null;
  if (mapTracesOf(plot).traces.length === 0) return { svg, lines };
  for (const g of Array.from(plot.querySelectorAll("g.sankey-node"))) {
    const datum = (g as unknown as { __data__?: NodeDatum }).__data__;
    const index = nodeIndexOf(datum);
    const layout = datum?.node;
    if (index === null || !layout) continue;
    const segments = segmentsAt(plot, index, layout);
    const zone = pickZone(layout);
    const rect = g.querySelector("rect") as SVGGraphicsElement | null;
    if (segments.length === 0 || !zone || !rect) continue;
    const matrix = rect.getCTM();
    if (!matrix) continue;
    svg ??= rect.ownerSVGElement;
    // the rect's own box, in its own units; the map's pixels are scaled onto its height
    const x = Number(rect.getAttribute("x") ?? 0) || 0;
    const y = Number(rect.getAttribute("y") ?? 0) || 0;
    const width = Number(rect.getAttribute("width") ?? 0) || 0;
    const height = Number(rect.getAttribute("height") ?? 0) || 0;
    const scale = height / (layout.y1! - layout.y0!);
    for (const line of dividerLines(zone, segments)) {
      for (const { offset, style } of LINE_STYLES) {
        const at = Math.min(Math.max(y + (line - layout.y0!) * scale + offset, y + 0.5), y + height - 0.5); // inside the node
        lines.push({ d: `M${x},${at}H${x + width}`, style, matrix });
      }
    }
  }
  return { svg, lines };
}

// Whether a change in the map is Plotly drawing it (a node or a link added or removed), not our own lines or its hover label.
function drawsMap(node: Node, ours: WeakSet<Node>): boolean {
  if (ours.has(node) || !(node instanceof Element)) return false;
  if (node.classList.contains("sankey-link") || node.classList.contains("sankey-node")) return true;
  return node.querySelector(".sankey-link, .sankey-node") !== null;
}

// Whether an attribute change moved or resized a node: its group's transform, or its box.
function movesNode(target: Node): boolean {
  const classes = (target as Element).classList;
  return !!classes && (classes.contains("sankey-node") || classes.contains("node-rect"));
}

/**
 * Shows the end segments on every map of the page that stores traces, until the returned `stop` is called. `ensure(element)` also
 * shows them on the map the element is in (a map drawn after the picker was armed).
 */
export function showEndSegments(): { ensure: (element: Element) => void; stop: () => void } {
  const shown = new Map<Element, () => void>();

  const watch = (plot: Element) => {
    if (shown.has(plot) || mapTracesOf(plot).traces.length === 0) return;
    const ours = new WeakSet<Node>();
    let lines: SVGElement[] = [];
    let svg: SVGSVGElement | null = null;
    let frame = 0;
    // The lines go in the overlay above the map (overlay.ts), so that they show over the veil of a preview.
    const draw = () => {
      frame = 0;
      const measured = measureLines(plot);
      lines.forEach((l) => l.remove());
      lines = [];
      if (measured.svg !== svg) {
        if (svg) overlays.release(svg);
        svg = measured.svg;
        if (svg) overlays.acquire(svg);
      }
      const layer = svg ? overlays.peek(svg)?.lines : undefined;
      if (!layer) return;
      for (const { d, style, matrix } of measured.lines) {
        const path = svgElement("path");
        path.setAttribute("d", d);
        path.setAttribute("style", style);
        path.setAttribute("transform", matrixAttr(matrix));
        layer.appendChild(path);
        ours.add(path);
        lines.push(path);
      }
    };
    const observer = new MutationObserver((records) => {
      const changed = records.some((r) =>
        r.type === "childList"
          ? [...r.addedNodes, ...r.removedNodes].some((n) => drawsMap(n, ours))
          : movesNode(r.target),
      );
      if (changed && !frame) frame = requestAnimationFrame(draw);
    });
    draw();
    observer.observe(plot, { childList: true, subtree: true, attributes: true, attributeFilter: ["transform", "height", "y"] });
    shown.set(plot, () => {
      observer.disconnect();
      if (frame) cancelAnimationFrame(frame);
      lines.forEach((l) => l.remove());
      if (svg) overlays.release(svg);
    });
  };

  plotsUnder(document).forEach(watch);
  return {
    ensure(element: Element) {
      const plot = plotOf(element);
      if (plot) watch(plot);
    },
    stop() {
      for (const undo of shown.values()) undo();
      shown.clear();
    },
  };
}
