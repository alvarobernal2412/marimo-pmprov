// Tests of chart-restore.ts, run with `npm test` (Node's own test runner; esbuild, already a dev dependency, turns the TypeScript into
// something Node can import). The page-reading parts (cell ids, <marimo-filename>) need a browser and are checked there.
import assert from "node:assert/strict";
import { test } from "node:test";
import { build } from "esbuild";

const bundled = await build({
  entryPoints: [new URL("../src/chart-restore.ts", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")],
  bundle: true,
  format: "esm",
  write: false,
  logLevel: "silent",
});
const { mergeBuilderStates, restoreChartBuilders, marimoChartsKey, withDisplayedAggregation, fillAggregations, keepAggregations } = await import(
  "data:text/javascript;base64," + Buffer.from(bundled.outputFiles[0].text).toString("base64")
);

const tab = (name, type = "bar", config = { general: {} }) => ({ tabName: name, chartType: type, config });
const model = (values) => ({ get: (key) => values[key] });
const memory = (initial = {}) => {
  const data = { ...initial };
  return {
    data,
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => {
      data[key] = String(value);
    },
  };
};

// What marimo saves when the analyst left Y on its default: no `aggregate`, although the form shows "Mean" (and a saved entry without
// it reloads as "None"). The scraped form knows what was shown.
const barTab = (config) => ({ tabName: "Bar Chart", chartType: "bar", config: { general: config } });
const shown = { chart_type: "Bar", x: "activity", y: "cost", y_aggregation: "Mean", x_aggregation: "None" };

test("an aggregation the form showed but marimo did not save is filled in, for the matching columns only", () => {
  const state = { cellId: "MJUe", tabs: [barTab({ xColumn: { field: "activity" }, yColumn: { field: "cost" } })] };
  const filled = withDisplayedAggregation(state, shown);
  assert.deepEqual(filled.tabs[0].config.general.yColumn, { field: "cost", aggregate: "mean" });
  assert.deepEqual(filled.tabs[0].config.general.xColumn, { field: "activity", aggregate: "none" });
  assert.equal(filled.cellId, "MJUe");
  assert.equal(state.tabs[0].config.general.yColumn.aggregate, undefined); // the input is not changed
});

test("an aggregation marimo did save is kept", () => {
  const state = { cellId: "MJUe", tabs: [barTab({ yColumn: { field: "cost", aggregate: "sum" } })] };
  assert.equal(withDisplayedAggregation(state, shown).tabs[0].config.general.yColumn.aggregate, "sum");
});

test("tabs of another chart type, columns that differ and labels it does not know are left alone", () => {
  const line = { tabName: "Line Chart", chartType: "line", config: { general: { yColumn: { field: "cost" } } } };
  const other = barTab({ yColumn: { field: "region" } });
  const state = { cellId: "MJUe", tabs: [line, other, barTab({ yColumn: { field: "cost" } })] };
  const filled = withDisplayedAggregation(state, { ...shown, y_aggregation: "Geometric wobble" });
  assert.deepEqual(filled.tabs, state.tabs);
  const real = withDisplayedAggregation(state, shown);
  assert.equal(real.tabs[0].config.general.yColumn.aggregate, undefined); // a line tab, the form showed a bar chart
  assert.equal(real.tabs[1].config.general.yColumn.aggregate, undefined); // another column
  assert.equal(real.tabs[2].config.general.yColumn.aggregate, "mean");
});

test("a config of an unexpected shape comes back untouched", () => {
  const state = { cellId: "MJUe", tabs: [{ tabName: "Bar Chart", chartType: "bar", config: "odd" }, { tabName: "B2", chartType: "bar", config: { general: null } }] };
  assert.deepEqual(withDisplayedAggregation(state, shown).tabs, state.tabs);
});

test("the key is the one marimo computes: charts version 2, scoped by the notebook file", () => {
  assert.equal(marimoChartsKey("C:\\work\\initial-analysis.py"), "marimo:charts:v2:C:\\work\\initial-analysis.py");
});

test("a cell without saved tabs gets the recorded ones", () => {
  const { json, changed } = mergeBuilderStates(null, { MJUe: [tab("Bar Chart")] });
  assert.equal(changed, true);
  assert.deepEqual(JSON.parse(json), [["MJUe", [tab("Bar Chart")]]]);
});

test("tabs the browser already has are kept as they are, even when the recorded config differs", () => {
  const existing = JSON.stringify([["MJUe", [tab("Bar Chart", "bar", { general: { newer: true } })]]]);
  const { json, changed } = mergeBuilderStates(existing, { MJUe: [tab("Bar Chart", "bar", { general: { older: true } })] });
  assert.equal(changed, false);
  assert.deepEqual(JSON.parse(json), JSON.parse(existing));
});

test("a recorded tab the browser lacks is added after its own tabs, and other cells stay", () => {
  const existing = JSON.stringify([["Hbol", [tab("Line Chart", "line")]], ["MJUe", [tab("Bar Chart")]]]);
  const { json, changed } = mergeBuilderStates(existing, { MJUe: [tab("Bar Chart"), tab("Pie Chart", "pie")] });
  assert.equal(changed, true);
  assert.deepEqual(JSON.parse(json), [["Hbol", [tab("Line Chart", "line")]], ["MJUe", [tab("Bar Chart"), tab("Pie Chart", "pie")]]]);
});

test("unreadable saved data is treated as empty, never thrown", () => {
  const { json, changed } = mergeBuilderStates("{not json", { MJUe: [tab("Bar Chart")] });
  assert.equal(changed, true);
  assert.deepEqual(JSON.parse(json), [["MJUe", [tab("Bar Chart")]]]);
});

test("restoring writes marimo's entry and reloads the page once", () => {
  const storage = memory();
  const session = memory();
  let reloads = 0;
  const env = { storage, session, filename: "nb.py", reload: () => (reloads += 1) };
  const m = model({ capture_charts: true, chart_restore: { MJUe: [tab("Bar Chart")] } });

  assert.equal(restoreChartBuilders(m, env), true);
  assert.deepEqual(JSON.parse(storage.data["marimo:charts:v2:nb.py"]), [["MJUe", [tab("Bar Chart")]]]);
  assert.equal(reloads, 1);

  storage.data["marimo:charts:v2:nb.py"] = "[]"; // something cleared it again: still no second reload in this tab
  assert.equal(restoreChartBuilders(m, env), false);
  assert.equal(reloads, 1);
});

test("nothing is written or reloaded when the browser already has the tabs", () => {
  const key = "marimo:charts:v2:nb.py";
  const storage = memory({ [key]: JSON.stringify([["MJUe", [tab("Bar Chart")]]]) });
  let reloads = 0;
  const env = { storage, session: memory(), filename: "nb.py", reload: () => (reloads += 1) };
  assert.equal(restoreChartBuilders(model({ capture_charts: true, chart_restore: { MJUe: [tab("Bar Chart")] } }), env), false);
  assert.equal(reloads, 0);
});

test("without capture, without recorded charts or without the notebook's file name, it does nothing", () => {
  const storage = memory();
  let reloads = 0;
  const env = (filename) => ({ storage, session: memory(), filename, reload: () => (reloads += 1) });
  assert.equal(restoreChartBuilders(model({ capture_charts: false, chart_restore: { MJUe: [tab("Bar Chart")] } }), env("nb.py")), false);
  assert.equal(restoreChartBuilders(model({ capture_charts: true, chart_restore: {} }), env("nb.py")), false);
  assert.equal(restoreChartBuilders(model({ capture_charts: true, chart_restore: { MJUe: [tab("Bar Chart")] } }), env(null)), false);
  assert.deepEqual(storage.data, {});
  assert.equal(reloads, 0);
});

test("a browser that refuses storage does not break the panel", () => {
  const broken = {
    getItem: () => {
      throw new Error("blocked");
    },
    setItem: () => {
      throw new Error("blocked");
    },
  };
  const env = { storage: broken, session: memory(), filename: "nb.py", reload: () => assert.fail("must not reload") };
  assert.equal(restoreChartBuilders(model({ capture_charts: true, chart_restore: { MJUe: [tab("Bar Chart")] } }), env), false);
});

// --- 0.16: the layout the saved tabs belong to, and the aggregations marimo does not save -------------------------------------

const column = (field, aggregate) => (aggregate === undefined ? { field } : { field, aggregate });
const scatter = (aggregate) => tab("Scatter Chart 2", "scatter", { general: { xColumn: column("score"), yColumn: column("cost", aggregate) } });
const layoutKey = "pw-chart-layout:nb.py";
const chartsKey = "marimo:charts:v2:nb.py";
const started = (values, saved, session = {}) => {
  const storage = memory(saved);
  let reloads = 0;
  const env = { storage, session: memory(session), filename: "nb.py", reload: () => (reloads += 1) };
  const reloaded = restoreChartBuilders(model({ capture_charts: true, ...values }), env);
  return { storage, env, reloaded, reloads: () => reloads };
};

test("a saved tab gets the recorded aggregation it lacks, and one that is saved is never changed", () => {
  const entries = [["c1", [scatter(), scatter("none")]], ["c2", [scatter()]]];
  entries[0][1][1].tabName = "Chosen";
  const recorded = { c1: [scatter("mean"), { ...scatter("mean"), tabName: "Chosen" }], c3: [scatter("mean")] };
  assert.equal(fillAggregations(entries, recorded), true);
  assert.equal(entries[0][1][0].config.general.yColumn.aggregate, "mean");
  assert.equal(entries[0][1][1].config.general.yColumn.aggregate, "none");
  assert.equal(entries[1][1][0].config.general.yColumn.aggregate, undefined); // another cell: not this table's tab
  assert.equal(fillAggregations(entries, recorded), false);
});

test("another column, another chart type or a tab of an unknown shape gets nothing", () => {
  const other = tab("Scatter Chart 2", "scatter", { general: { yColumn: column("terms") } });
  const line = tab("Scatter Chart 2", "line", { general: { yColumn: column("cost") } });
  const odd = tab("Scatter Chart 2", "scatter", null);
  for (const saved of [other, line, odd]) assert.equal(fillAggregations([["c1", [saved]]], { c1: [scatter("mean")] }), false);
});

test("a browser whose tabs were saved under another layout gets the recorded ones in their place", () => {
  const saved = { [chartsKey]: JSON.stringify([["old", [scatter()]], ["c1", [tab("Stale")]]]) };
  const values = { chart_layout: "L2", chart_restore_ready: true, chart_restore: { c1: [scatter("mean")] } };
  const { storage, reloaded, reloads } = started(values, saved);
  assert.equal(reloaded, true);
  assert.equal(reloads(), 1);
  assert.deepEqual(JSON.parse(storage.data[chartsKey]), [["c1", [scatter("mean")]]]);
  assert.equal(storage.data[layoutKey], "L2");
});

test("it waits until the recorded charts were read, so an unread history is not taken for an empty one", () => {
  const saved = { [chartsKey]: JSON.stringify([["old", [scatter()]]]) };
  const { storage, reloaded } = started({ chart_layout: "L2", chart_restore_ready: false, chart_restore: {} }, saved);
  assert.equal(reloaded, false);
  assert.equal(storage.data[layoutKey], undefined);
  assert.equal(storage.data[chartsKey], saved[chartsKey]);
});

test("a browser of another layout with nothing recorded starts without the tabs of other cells", () => {
  const saved = { [chartsKey]: JSON.stringify([["old", [scatter()]]]) };
  const { storage, reloaded } = started({ chart_layout: "L2", chart_restore_ready: true, chart_restore: {} }, saved);
  assert.equal(reloaded, true);
  assert.equal(storage.data[chartsKey], "[]");
});

test("a new browser takes the layout and the recorded tabs; one with nothing saved or recorded only takes the layout", () => {
  const fresh = started({ chart_layout: "L2", chart_restore_ready: true, chart_restore: { c1: [scatter("mean")] } }, {});
  assert.equal(fresh.reloaded, true);
  assert.deepEqual(JSON.parse(fresh.storage.data[chartsKey]), [["c1", [scatter("mean")]]]);
  const empty = started({ chart_layout: "L2", chart_restore_ready: true, chart_restore: {} }, {});
  assert.equal(empty.reloaded, false);
  assert.equal(empty.storage.data[layoutKey], "L2");
  assert.equal(chartsKey in empty.storage.data, false);
});

test("in the layout it was saved under, the browser keeps its tabs and only gets what it lacks", () => {
  const own = tab("Mine");
  const saved = { [layoutKey]: "L2", [chartsKey]: JSON.stringify([["c1", [own, scatter()]]]) };
  const values = { chart_layout: "L2", chart_restore_ready: true, chart_restore: { c1: [scatter("mean")], c2: [tab("Bar Chart")] } };
  const { storage, reloaded } = started(values, saved);
  assert.equal(reloaded, true);
  assert.deepEqual(JSON.parse(storage.data[chartsKey]), [["c1", [own, scatter("mean")]], ["c2", [tab("Bar Chart")]]]);
  // and the page it then loads has nothing left to do
  const again = started(values, storage.data);
  assert.equal(again.reloaded, false);
});

test("while the page is open the recorded aggregation is written into the saved tab, without loading anything again", () => {
  const storage = memory({ [chartsKey]: JSON.stringify([["c1", [scatter()]]]) });
  const open = model({ capture_charts: true, chart_restore: { c1: [scatter("mean")] } });
  assert.equal(keepAggregations(open, { storage, filename: "nb.py" }), true);
  assert.deepEqual(JSON.parse(storage.data[chartsKey]), [["c1", [scatter("mean")]]]);
  assert.equal(keepAggregations(open, { storage, filename: "nb.py" }), false);
  assert.equal(keepAggregations(model({ capture_charts: false, chart_restore: { c1: [scatter("mean")] } }), { storage, filename: "nb.py" }), false);
  assert.equal(keepAggregations(open, { storage, filename: null }), false);
});
