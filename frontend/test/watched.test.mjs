// Tests of watched-figure.ts's currentSelection, run with `npm test`. Elements are stood in for by plain objects: it only reads
// `dataset`. Waiting for the notebook (whenRecorded) reads the page and is checked in a browser.
import assert from "node:assert/strict";
import { test } from "node:test";
import { build } from "esbuild";

const bundled = await build({
  entryPoints: [new URL("../src/watched-figure.ts", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")],
  bundle: true,
  format: "esm",
  write: false,
  logLevel: "silent",
});
const { currentSelection } = await import("data:text/javascript;base64," + Buffer.from(bundled.outputFiles[0].text).toString("base64"));

const picture = { kind: "image", png: "new" };
const drawnAgain = { pending: false, pictured: true, tagged: { dataset: { pwArtifactId: "state-2", pwArtifactName: "process_map" } } };
const picked = { artifactId: "state-1", artifactName: "process_map", granularity: "link", detail: "a -> b", snapshot: { kind: "image", png: "old" }, figure: "map-1" };

test("a selection picked in a figure that was drawn again names the artifact the figure is now, with its picture", () => {
  const now = currentSelection(picked, drawnAgain, () => picture);
  assert.deepEqual(now, { ...picked, artifactId: "state-2", snapshot: picture });
  assert.equal(picked.artifactId, "state-1"); // the selection itself is not changed
});

test("what was picked in the figure is kept, and a figure without a picture yet has none", () => {
  const now = currentSelection(picked, drawnAgain, () => null);
  assert.equal(now.detail, "a -> b");
  assert.equal(now.granularity, "link");
  assert.equal(now.snapshot, null);
});

test("a selection is left as it is when its figure was not drawn again, is not on the page, or it was picked elsewhere", () => {
  const same = { pending: false, tagged: { dataset: { pwArtifactId: "state-1" } } };
  assert.equal(currentSelection(picked, same, () => picture), picked);
  assert.equal(currentSelection(picked, null, () => picture), picked);
  assert.equal(currentSelection(picked, { pending: true, tagged: null }, () => picture), picked);
  const table = { artifactId: "state-1", artifactName: "case_log", granularity: "dataset", detail: null };
  assert.equal(currentSelection(table, drawnAgain, () => picture), table);
  assert.deepEqual(currentSelection({}, drawnAgain, () => picture), {});
});
