// Tests of replay.ts's annotationRefsOf, run with `npm test`: what stepping onto a state points at in the notebook.
import assert from "node:assert/strict";
import { test } from "node:test";
import { build } from "esbuild";

const bundled = await build({
  entryPoints: [new URL("../src/replay.ts", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")],
  bundle: true,
  format: "esm",
  write: false,
  logLevel: "silent",
});
const { annotationRefsOf } = await import("data:text/javascript;base64," + Buffer.from(bundled.outputFiles[0].text).toString("base64"));

const ref = (artifactName, granularity, detail) => ({ artifactId: "s2", artifactName, granularity, detail });
const node = (stateId, annotations) => ({ stateId, parentStateId: null, annotations });
const tree = {
  rootId: "s1",
  branches: {},
  nodes: {
    s1: node("s1", []),
    s2: node("s2", [
      { annotationId: "a1", artifacts: [ref("process_map", "trace", "A → K → L → Z")] },
      { annotationId: "a2", artifacts: [ref("process_map", "node", "K"), ref("case_log", "cell", "row 2, column amount = 30")] },
      { annotationId: "a3", artifacts: [] },
    ]),
    s3: node("s3", [{ annotationId: "a4" }]),
  },
};

test("the refs of every annotation of the state, in order", () => {
  assert.deepEqual(
    annotationRefsOf(tree, "s2").map((r) => [r.artifactName, r.granularity, r.detail]),
    [
      ["process_map", "trace", "A → K → L → Z"],
      ["process_map", "node", "K"],
      ["case_log", "cell", "row 2, column amount = 30"],
    ],
  );
});

test("a state without annotations, with annotations that pin nothing, or not in the tree has none", () => {
  assert.deepEqual(annotationRefsOf(tree, "s1"), []);
  assert.deepEqual(annotationRefsOf(tree, "s3"), []);
  assert.deepEqual(annotationRefsOf(tree, "nowhere"), []);
});
