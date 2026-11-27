// Tests of highlight.ts's bookkeeping (Generations, MarksPerMap, pinnedFor), run with `npm test`. Elements
// are stood in for by plain objects. How the marks look is checked in a browser.
import assert from "node:assert/strict";
import { test } from "node:test";
import { build } from "esbuild";

const bundled = await build({
  entryPoints: [new URL("../src/highlight.ts", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")],
  bundle: true,
  format: "esm",
  write: false,
  logLevel: "silent",
});
const { Generations, MarksPerMap, pinnedFor } = await import("data:text/javascript;base64," + Buffer.from(bundled.outputFiles[0].text).toString("base64"));

test("a highlight that was waiting is no longer current once another starts or it is cancelled", () => {
  const generations = new Generations();
  const first = generations.start();
  assert.equal(generations.isCurrent(first), true);
  const second = generations.start();
  assert.equal(generations.isCurrent(first), false);
  assert.equal(generations.isCurrent(second), true);
  generations.cancel();
  assert.equal(generations.isCurrent(second), false);
});

test("marking a map that is already marked undoes the old mark before the new one is made", () => {
  const perMap = new MarksPerMap();
  const map = {};
  const link = { opacity: "" };
  // a stand-in mark that remembers what it found and gives it back on undo: stacked marks would leave the first one's value
  const mark = () => {
    const before = link.opacity;
    link.opacity = "0.25";
    return () => (link.opacity = before);
  };
  const undoFirst = perMap.replace(map, mark);
  const undoSecond = perMap.replace(map, mark);
  assert.equal(link.opacity, "0.25");
  undoSecond();
  assert.equal(link.opacity, "");
  undoFirst(); // already undone when the second replaced it: no effect
  assert.equal(link.opacity, "");
});

test("undoing a mark that was replaced leaves the new one in place, and clear undoes every map", () => {
  const perMap = new MarksPerMap();
  const log = [];
  const mark = (name) => () => (log.push(`mark ${name}`), () => log.push(`undo ${name}`));
  const undoA = perMap.replace("map", mark("a"));
  perMap.replace("map", mark("b"));
  undoA();
  perMap.replace("other", mark("c"));
  perMap.clear();
  assert.deepEqual(log, ["mark a", "undo a", "mark b", "mark c", "undo b", "undo c"]);
});

// Refs of one step on one map, and what each locates on it.
const onMap = {
  "trace A → K → Z": ["link 0", "link 1", "node K"],
  "trace A → Z": ["link 0", "link 3"],
  "node K": ["node K"],
};
const locate = (ref) => onMap[`${ref.granularity} ${ref.detail}`] ?? [];

test("the marks of a map are the union of everything its refs pin, and a whole-map ref among them is ignored", () => {
  const refs = [
    { granularity: "chart_selection", detail: null }, // the intent, about the whole map
    { granularity: "trace", detail: "A → K → Z" },
    { granularity: "trace", detail: "A → Z" },
    { granularity: "node", detail: "K" },
  ];
  assert.deepEqual(pinnedFor(refs, locate, "whole map"), ["link 0", "link 1", "node K", "link 3"]);
});

test("only whole-map refs give the whole map, and a pin that cannot be found adds it to what was found", () => {
  assert.deepEqual(pinnedFor([{ granularity: "chart_selection", detail: null }, { granularity: "dataset" }], locate, "whole map"), ["whole map"]);
  assert.deepEqual(pinnedFor([], locate, "whole map"), ["whole map"]);
  const refs = [{ granularity: "node", detail: "K" }, { granularity: "trace", detail: "not stored" }];
  assert.deepEqual(pinnedFor(refs, locate, "whole map"), ["whole map", "node K"]);
});
