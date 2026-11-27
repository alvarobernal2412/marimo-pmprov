// Tests of traces.ts's end segments and names, and of the plotly-sankey resolver picking a trace, run with `npm test`. Elements are
// stood in for by plain objects of a stand-in Element class: the resolver reads `classList`, the d3 `__data__`, the parents up to the
// Plotly graph div, and the node's box on the screen.
import assert from "node:assert/strict";
import { test } from "node:test";
import { build } from "esbuild";

globalThis.Element = class Element {};

async function load(file) {
  const bundled = await build({
    entryPoints: [new URL(`../src/${file}`, import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")],
    bundle: true,
    format: "esm",
    write: false,
    logLevel: "silent",
  });
  return import("data:text/javascript;base64," + Buffer.from(bundled.outputFiles[0].text).toString("base64"));
}

const { endingZone, pickZone, endSegments, dividerLines, traceAtPoint } = await load("traces.ts");
const { resolveDetail } = await load("resolvers.ts");

// A node as Plotly lays it out (seen in a browser): value, top and bottom (y0, y1) in the map's pixels, and the links that leave it
// with the centre (y0) and width of each where it leaves. Its outgoing links cover 316.5 to 435.4: the cases that end there are
// drawn in the 297.2 to 316.5 at the top.
const node7 = {
  value: 5152,
  y0: 297.2,
  y1: 435.4,
  sourceLinks: [
    { y0: 341.3, width: 49.6 },
    { y0: 391.7, width: 51.1 },
    { y0: 421.5, width: 8.5 },
    { y0: 430.5, width: 9.6 },
    { y0: 435.4, width: 0 },
  ],
};
const ending = [
  { name: "A → B", sequence: ["A", "B"], cases: 400, links: [0, 1], nodes: [0, 3, 7] },
  { name: "A → C → B", sequence: ["A", "C", "B"], cases: 200, links: [0, 2, 5], nodes: [0, 3, 5, 7] },
  { name: "A → B → D", sequence: ["A", "B", "D"], cases: 5, links: [0, 1, 6], nodes: [0, 3, 7, 8] },
  { name: "C → B", sequence: ["C", "B"], cases: 50, links: [3, 5], nodes: [0, 5, 7] },
];
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 0.05, `${actual} is not ${expected}`);

test("the ending zone of a node is the largest part of it that no outgoing link leaves from", () => {
  const zone = endingZone(node7);
  near(zone.top, 297.2);
  near(zone.bottom, 316.5);
  const last = { value: 10, y0: 0, y1: 50, sourceLinks: [] };
  assert.deepEqual(endingZone(last), { top: 0, bottom: 50 }); // no outgoing link: all of it
  const bottom = { value: 10, y0: 0, y1: 50, sourceLinks: [{ y0: 15, width: 30 }] };
  assert.deepEqual(endingZone(bottom), { top: 30, bottom: 50 });
  const full = { value: 10, y0: 0, y1: 50, sourceLinks: [{ y0: 25, width: 50 }] };
  assert.equal(endingZone(full), null); // every case goes on
  assert.equal(endingZone({ value: 0, y0: 0, y1: 0 }), null);
});

test("the segments fill the zone, most frequent first, by their cases, none thinner than 6 px", () => {
  // the zone is 19.3 px: 400, 200 and 50 cases would be 11.9, 5.9 and 1.5 px; the two small ones get 6 px each
  const segments = endSegments(ending, 7, node7);
  assert.deepEqual(segments.map((s) => s.trace.name), ["A → B", "A → C → B", "C → B"]); // "A → B → D" goes on to node 8
  near(segments[0].top, 297.2);
  near(segments[0].bottom, 304.5);
  near(segments[1].bottom, 310.5);
  near(segments[2].bottom, 316.5);
  for (const s of segments) assert.ok(s.bottom - s.top >= 6 - 1e-9);
  assert.deepEqual(endSegments(ending, 3, node7), []); // no trace ends at node 3
  assert.deepEqual(endSegments(ending, 7, { value: 10, y0: 0, y1: 50, sourceLinks: [{ y0: 25, width: 50 }] }), []);
  assert.deepEqual(endSegments([], 7, node7), []);
});

test("when they do not all fit at 6 px, only the most frequent that fit get a segment", () => {
  const node = { value: 100, y0: 0, y1: 100, sourceLinks: [{ y0: 60, width: 80 }] }; // zone 0 to 20: room for 3
  const many = [30, 25, 20, 15, 10].map((cases, i) => ({ name: `T${i}`, sequence: [], cases, links: [], nodes: [0, 1] }));
  const segments = endSegments(many, 1, node);
  assert.deepEqual(segments.map((s) => s.trace.name), ["T0", "T1", "T2"]);
  near(segments[0].top, 0);
  near(segments[2].bottom, 20);
});

test("a single trace gets the whole zone, and a zone under 8 px grows to 8 px toward the middle of the node", () => {
  const one = [{ name: "ER Triage", sequence: ["ER Triage"], cases: 35, links: [0], nodes: [0, 1] }];
  // 26 px node, its links leave from all but its last pixel
  const triage = { value: 1000, y0: 0, y1: 26, sourceLinks: [{ y0: 12.5, width: 25 }] };
  assert.deepEqual(endingZone(triage), { top: 25, bottom: 26 });
  assert.deepEqual(pickZone(triage), { top: 18, bottom: 26 });
  assert.deepEqual(endSegments(one, 1, triage).map((s) => [s.top, s.bottom]), [[18, 26]]);
  const atTop = { value: 1000, y0: 0, y1: 26, sourceLinks: [{ y0: 14, width: 24 }] }; // zone 0 to 2
  assert.deepEqual(pickZone(atTop), { top: 0, bottom: 8 });
  const short = { value: 10, y0: 0, y1: 5, sourceLinks: [{ y0: 2, width: 4 }] };
  assert.deepEqual(pickZone(short), { top: 0, bottom: 5 }); // a node under 8 px: all of it
  assert.deepEqual(pickZone(node7), endingZone(node7)); // wide enough already
  assert.equal(pickZone({ value: 10, y0: 0, y1: 50, sourceLinks: [{ y0: 25, width: 50 }] }), null);
});

test("the pointer picks the segment it is on, and nothing outside the segments", () => {
  const segments = endSegments(ending, 7, node7);
  assert.equal(traceAtPoint(segments, 300).name, "A → B");
  assert.equal(traceAtPoint(segments, 307).name, "A → C → B");
  assert.equal(traceAtPoint(segments, 315).name, "C → B");
  assert.equal(traceAtPoint(segments, 330), null); // where links leave: the node
  assert.equal(traceAtPoint([], 300), null);
});

test("lines are drawn around the zone and between the segments", () => {
  const segments = endSegments(ending, 7, node7);
  const lines = dividerLines(pickZone(node7), segments);
  assert.equal(lines.length, 4);
  near(lines[0], 297.2);
  near(lines[1], 304.5);
  near(lines[2], 310.5);
  near(lines[3], 316.5);
});

// A Plotly graph div with one Sankey trace holding the traces above, and node 7 of it on the screen from y 100 to 238.2 (the map
// drawn at its own size: one pixel on screen is one in the map).
function fakeMap() {
  const plot = Object.assign(new Element(), {
    classList: { contains: (c) => c === "js-plotly-plot" },
    data: [{ type: "sankey", meta: { lcm: { traces: ending, truncated: false } } }],
    parentNode: null,
    shadowRoot: null,
    querySelectorAll: () => [],
  });
  const node = (index, label, layout = node7) =>
    Object.assign(new Element(), {
      tagName: "g",
      classList: { contains: (c) => c === "sankey-node" },
      __data__: { index, node: { label, pointNumber: index, ...layout } },
      parentNode: plot,
      querySelector: () => null,
      closest: () => null,
      getBoundingClientRect: () => ({ top: 100, height: layout.y1 - layout.y0, bottom: 100 + layout.y1 - layout.y0 }),
    });
  return { plot, node };
}

const at = (y, altKey = false) => ({ clientY: y, altKey });
const screenY = (mapY) => 100 + (mapY - node7.y0);

test("over a node's end segment the resolver picks that trace, elsewhere on the node the node", () => {
  const end = fakeMap().node(7, "B");
  assert.deepEqual(resolveDetail([end], end, at(screenY(300))), { granularity: "trace", detail: "A → B" });
  assert.deepEqual(resolveDetail([end], end, at(screenY(307))), { granularity: "trace", detail: "A → C → B" });
  assert.deepEqual(resolveDetail([end], end, at(screenY(315))), { granularity: "trace", detail: "C → B" });
  assert.deepEqual(resolveDetail([end], end, at(screenY(400))), { granularity: "node", detail: "B" });
});

test("the start node and a node where no trace ends pick the node", () => {
  const map = fakeMap();
  const start = map.node(0, "START", { value: 5152, y0: 0, y1: 138.2, sourceLinks: [{ y0: 69.1, width: 138.2 }] });
  assert.deepEqual(resolveDetail([start], start, at(110)), { granularity: "node", detail: "START" });
  const inner = map.node(3, "A");
  assert.deepEqual(resolveDetail([inner], inner, at(screenY(300))), { granularity: "node", detail: "A" });
});

test("holding Alt, or having no pointer, picks the node itself", () => {
  const end = fakeMap().node(7, "B");
  assert.deepEqual(resolveDetail([end], end, at(screenY(300), true)), { granularity: "node", detail: "B" });
  assert.deepEqual(resolveDetail([end], end), { granularity: "node", detail: "B" });
});

const { shortTraceName, shownDetail } = await load("traces.ts");

const steps = (n) => Array.from({ length: n }, (_, i) => `S${i + 1}`).join(" → ");

test("a long trace name is shown by its first three and last two steps, with the number of steps", () => {
  assert.equal(shortTraceName(steps(11)), "S1 → S2 → S3 → … (11 steps) … → S10 → S11");
  assert.equal(shortTraceName(steps(7)), "S1 → S2 → S3 → … (7 steps) … → S6 → S7");
  const real = "W_Handle leads → W_Handle leads → W_Complete application → W_Call after offers → W_Call after offers → " +
    "W_Validate application → W_Validate application → W_Call incomplete files → W_Validate application → " +
    "W_Call after offers → W_Call after offers";
  assert.equal(
    shortTraceName(real),
    "W_Handle leads → W_Handle leads → W_Complete application → … (11 steps) … → W_Call after offers → W_Call after offers",
  );
});

test("a trace of six steps or fewer, and the empty trace, are shown whole", () => {
  assert.equal(shortTraceName(steps(6)), steps(6));
  assert.equal(shortTraceName("A"), "A");
  assert.equal(shortTraceName("EMPTY TRACE"), "EMPTY TRACE");
});

test("only a trace's detail is shortened for display", () => {
  assert.equal(shownDetail("trace", steps(9)), "S1 → S2 → S3 → … (9 steps) … → S8 → S9");
  assert.equal(shownDetail("node", steps(9)), steps(9));
  assert.equal(shownDetail("cell", "row 2, column amount = 30"), "row 2, column amount = 30");
});
