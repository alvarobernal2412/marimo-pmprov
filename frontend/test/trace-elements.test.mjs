// Tests of how traces.ts finds a trace's elements on the page (traceElements, findTrace, sameNode, nodeIndexOf) and of locators.ts's
// locateAll, run with `npm test`. These decide that a wrong trace is never marked: whatever does not agree with the figure gives no
// elements. A map is stood in for by plain objects: a graph div with the figure's arrays, and links and nodes carrying d3 data the
// way Plotly puts it (`pointNumber`, confirmed in a browser).
import assert from "node:assert/strict";
import { test } from "node:test";
import { build } from "esbuild";

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

const { traceElements, findTrace, sameNode, nodeIndexOf, buildMapIndex, elementsOfTrace } = await load("traces.ts");
const { locateAll } = await load("locators.ts");

// START 0, A 1, K 2, Z 3. Links: 0 START->A, 1 A->K, 2 K->Z, 3 A->Z.
const labels = ["START", "A", "K", "Z"];
const sources = [0, 1, 2, 1];
const targets = [1, 2, 3, 3];
const traces = [
  { name: "A → K → Z", sequence: ["A", "K", "Z"], cases: 2, links: [0, 1, 2], nodes: [0, 1, 2, 3] },
  { name: "A → Z", sequence: ["A", "Z"], cases: 1, links: [0, 3], nodes: [0, 1, 3] },
];

const fakeClass = (name) => ({ contains: (c) => c === name });

// `change` can alter what is drawn: { linkEnds: [k, source, target] } makes one drawn link disagree with the figure.
function fakeMap({ stored = traces, linkEnds = null, noPointNumber = false, typed = false } = {}) {
  const arrays = (list) => (typed ? Int32Array.from(list) : list);
  const plot = {
    classList: fakeClass("js-plotly-plot"),
    parentNode: null,
    data: [{ type: "sankey", meta: { lcm: { traces: stored, truncated: false } }, node: { label: labels }, link: { source: sources, target: targets } }],
    _fullData: [{ type: "sankey", node: { label: labels }, link: { source: arrays(sources), target: arrays(targets) } }],
  };
  const end = (i) => ({ pointNumber: i, label: labels[i] });
  const nodes = labels.map((label, i) => {
    const rect = { tagName: "rect", classList: fakeClass("node-rect"), id: `rect ${label}`, parentNode: null, shadowRoot: null };
    const g = {
      tagName: "g",
      classList: fakeClass("sankey-node"),
      parentNode: plot,
      shadowRoot: null,
      __data__: { index: i, node: noPointNumber ? { label } : { label, pointNumber: i } },
      querySelector: (s) => (s === "rect" ? rect : null),
    };
    rect.parentNode = g;
    return g;
  });
  const links = sources.map((s, k) => {
    let [source, target] = [end(s), end(targets[k])];
    if (linkEnds && linkEnds[0] === k) [source, target] = [end(linkEnds[1]), end(linkEnds[2])];
    return {
      tagName: "path",
      id: `link ${k}`,
      classList: fakeClass("sankey-link"),
      parentNode: plot,
      shadowRoot: null,
      __data__: { pointNumber: k, link: { pointNumber: k, source, target } },
    };
  });
  const all = [...links, ...nodes, ...nodes.map((n) => n.querySelector("rect"))];
  Object.assign(plot, { shadowRoot: null, querySelectorAll: () => all });
  const root = { classList: fakeClass("pw-annotatable"), shadowRoot: null, querySelectorAll: () => all };
  return { root, plot, links, nodes };
}

const ids = (elements) => elements.map((e) => e.id);

test("a trace's elements are its links, then the boxes of its nodes", () => {
  const { root } = fakeMap();
  assert.deepEqual(ids(traceElements(root, traces[1])), ["link 0", "link 3", "rect START", "rect A", "rect Z"]);
  assert.deepEqual(ids(traceElements(root, traces[0])), ["link 0", "link 1", "link 2", "rect START", "rect A", "rect K", "rect Z"]);
});

test("the figure's arrays may be typed arrays", () => {
  const { root } = fakeMap({ typed: true });
  assert.deepEqual(ids(traceElements(root, traces[1])), ["link 0", "link 3", "rect START", "rect A", "rect Z"]);
});

test("one drawn link whose ends disagree with the figure gives no elements", () => {
  const { root } = fakeMap({ linkEnds: [2, 2, 1] });
  assert.deepEqual(traceElements(root, traces[1]), []); // not even for a trace that does not use that link
  assert.deepEqual(traceElements(root, traces[0]), []);
});

test("without pointNumber on the nodes the mapping is not established", () => {
  assert.equal(nodeIndexOf({ index: 2, node: { label: "K" } }), null);
  assert.equal(nodeIndexOf({ index: 2, node: { label: "K", pointNumber: 2 } }), 2);
  assert.deepEqual(traceElements(fakeMap({ noPointNumber: true }).root, traces[1]), []);
});

test("a link's end is the figure's node only by its pointNumber", () => {
  assert.equal(sameNode({ pointNumber: 3, label: "Z" }, 3), true);
  assert.equal(sameNode({ pointNumber: 2, label: "Z" }, 3), false);
  assert.equal(sameNode({ label: "Z" }, 3), false);
  assert.equal(sameNode(undefined, 3), false);
  assert.equal(sameNode({ pointNumber: 3 }, undefined), false);
});

test("a trace using a link that is not drawn gives no elements", () => {
  const { root } = fakeMap();
  const ghost = { name: "A → Q", sequence: ["A", "Q"], cases: 1, links: [0, 9], nodes: [0, 1] };
  assert.deepEqual(traceElements(root, ghost), []);
});

test("findTrace gives the one stored trace with the name, else null", () => {
  assert.equal(findTrace(fakeMap().root, "A → Z").name, "A → Z");
  assert.equal(findTrace(fakeMap().root, "B → Z"), null);
  assert.equal(findTrace(fakeMap({ stored: [traces[1], traces[1]] }).root, "A → Z"), null);
});

test("locateAll finds every element of a stored trace, nothing for one not stored, one element for a node", () => {
  const { root } = fakeMap();
  assert.deepEqual(ids(locateAll(root, "trace", "A → Z")), ["link 0", "link 3", "rect START", "rect A", "rect Z"]);
  assert.deepEqual(locateAll(root, "trace", "B → Z"), []);
  assert.deepEqual(locateAll(fakeMap({ stored: [traces[0]] }).root, "trace", "A → Z"), []); // truncated: not stored
  assert.deepEqual(ids(locateAll(root, "node", "K")), ["rect K"]);
  assert.deepEqual(locateAll(fakeMap({ linkEnds: [2, 2, 1] }).root, "trace", "A → Z"), []);
});

test("the index of a map gives each figure position its element, and a trace is looked up in it", () => {
  const { links, nodes } = fakeMap();
  const index = buildMapIndex(links, nodes, { sources, targets, labels });
  assert.deepEqual([...index.linkAt.keys()], [0, 1, 2, 3]);
  assert.equal(index.nodeAt.get(2), nodes[2]);
  assert.deepEqual(ids(elementsOfTrace(index, traces[1])), ["link 0", "link 3", "rect START", "rect A", "rect Z"]);
  const wrong = fakeMap({ linkEnds: [2, 2, 1] });
  assert.equal(buildMapIndex(wrong.links, wrong.nodes, { sources, targets, labels }), null);
  assert.equal(buildMapIndex([links[0], links[0]], nodes, { sources, targets, labels }), null); // two at one position
});
