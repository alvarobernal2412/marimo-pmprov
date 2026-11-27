// Tests of overlay.ts, the veil and copies drawn over a marked map, run with `npm test`: the veil's box, who shares the overlay,
// which originals a mark watches, and copies being replaced and taken away. Elements are stood in for by plain objects; how the
// veil looks is checked in a browser.
import assert from "node:assert/strict";
import { test } from "node:test";
import { build } from "esbuild";

const bundled = await build({
  entryPoints: [new URL("../src/overlay.ts", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")],
  bundle: true,
  format: "esm",
  write: false,
  logLevel: "silent",
});
const { boxInSvg, unionBox, Shared, swapClones, observedFor } = await import(
  "data:text/javascript;base64," + Buffer.from(bundled.outputFiles[0].text).toString("base64")
);

const identity = { a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 };

test("a box is placed in the SVG by its element's matrix", () => {
  assert.deepEqual(boxInSvg({ x: 0, y: 0, width: 10, height: 20 }, identity), { x: 0, y: 0, width: 10, height: 20 });
  // the Sankey's group translated by (80, 100)
  assert.deepEqual(boxInSvg({ x: 5, y: 5, width: 10, height: 20 }, { ...identity, e: 80, f: 100 }), { x: 85, y: 105, width: 10, height: 20 });
  // scaled by 2 and turned a quarter: the box around the turned corners
  const turned = boxInSvg({ x: 0, y: 0, width: 10, height: 20 }, { a: 0, b: 2, c: -2, d: 0, e: 0, f: 0 });
  assert.deepEqual(turned, { x: -40, y: 0, width: 40, height: 20 });
});

test("the veil covers the boxes it is given and a margin, and nothing without boxes", () => {
  assert.deepEqual(unionBox([{ x: 10, y: 20, width: 100, height: 50 }], 4), { x: 6, y: 16, width: 108, height: 58 });
  assert.deepEqual(unionBox([{ x: 0, y: 0, width: 10, height: 10 }, { x: 20, y: 5, width: 10, height: 10 }]), { x: 0, y: 0, width: 30, height: 15 });
  assert.equal(unionBox([]), null);
});

test("the overlay of an SVG is made by its first user and removed with its last, so a teardown leaves nothing", () => {
  const log = [];
  const shared = new Shared((svg) => (log.push(`make ${svg}`), { svg }), (value) => log.push(`remove ${value.svg}`));
  const forMark = shared.acquire("svg 1");
  const forLines = shared.acquire("svg 1"); // the picker's lines on the same map
  assert.equal(forMark, forLines);
  assert.equal(shared.peek("svg 1"), forMark);
  shared.release("svg 1");
  assert.deepEqual(log, ["make svg 1"]);
  shared.release("svg 1");
  shared.release("svg 1"); // more releases than users change nothing
  assert.deepEqual(log, ["make svg 1", "remove svg 1"]);
  assert.equal(shared.size, 0);
  assert.equal(shared.peek("svg 1"), undefined);
});

test("a change of mark replaces every copy: the old ones are dropped, one new copy per marked original", () => {
  const dropped = [];
  const make = (original) => ({ copyOf: original });
  const first = swapClones([], ["link 1", "link 2"], make, (c) => dropped.push(c.copyOf));
  assert.deepEqual(first.map((c) => c.copyOf), ["link 1", "link 2"]);
  const next = swapClones(first, ["link 3"], make, (c) => dropped.push(c.copyOf));
  assert.deepEqual(next.map((c) => c.copyOf), ["link 3"]);
  assert.deepEqual(dropped, ["link 1", "link 2"]);
  const none = swapClones(next, [], make, (c) => dropped.push(c.copyOf)); // undo
  assert.deepEqual(none, []);
  assert.deepEqual(dropped, ["link 1", "link 2", "link 3"]);
  assert.deepEqual(swapClones([], ["gone"], () => null, () => {}), []); // an original that cannot be copied gives no copy
});

test("a mark watches only its marked originals and the node groups they move with, each once", () => {
  const groups = { "box A": "node A", "box K": "node K" };
  const groupOf = (el) => groups[el] ?? null;
  assert.deepEqual(observedFor(["link 0", "box A", "link 3", "box K"], groupOf), ["link 0", "box A", "node A", "link 3", "box K", "node K"]);
  assert.deepEqual(observedFor(["box A", "box A"], groupOf), ["box A", "node A"]);
  assert.deepEqual(observedFor([], groupOf), []);
});
