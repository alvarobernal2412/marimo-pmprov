// Tests of picker.ts's readSnapshot, run with `npm test`. Elements are stood in for by plain objects: it only reads `dataset` and
// asks the page for one element.
import assert from "node:assert/strict";
import { test } from "node:test";
import { build } from "esbuild";

const bundled = await build({
  entryPoints: [new URL("../src/picker.ts", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")],
  bundle: true,
  format: "esm",
  write: false,
  logLevel: "silent",
});
const { readSnapshot } = await import("data:text/javascript;base64," + Buffer.from(bundled.outputFiles[0].text).toString("base64"));

const picture = { kind: "image", png: "abc" };
const page = (found) => ({ asked: [], querySelector(selector) { this.asked.push(selector); return found; }, querySelectorAll: () => [] });

test("an element's own snapshot is used", () => {
  const element = { dataset: { pwArtifactId: "s1", pwSnapshot: JSON.stringify(picture) } };
  assert.deepEqual(readSnapshot(element, page(null)), picture);
});

test("a chart shown without a picture finds the one made for it afterwards", () => {
  const holder = { dataset: { pwSnapshotFor: "s1", pwSnapshot: JSON.stringify(picture) } };
  const root = page(holder);
  assert.deepEqual(readSnapshot({ dataset: { pwArtifactId: "s1" } }, root), picture);
  assert.match(root.asked[0], /data-pw-snapshot-for="s1"/);
});

test("no picture anywhere is null, and so is one that cannot be read", () => {
  assert.equal(readSnapshot({ dataset: { pwArtifactId: "s1" } }, page(null)), null);
  assert.equal(readSnapshot({ dataset: { pwArtifactId: "s1", pwSnapshot: "{not json" } }, page(null)), null);
});
