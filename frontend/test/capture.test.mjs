// Tests of the settings a Visualize chart is recorded with (chart-capture.ts), run with `npm test`. Reading the form itself needs a
// browser and is checked there.
import assert from "node:assert/strict";
import { test } from "node:test";
import { build } from "esbuild";

const bundled = await build({
  entryPoints: [new URL("../src/chart-capture.ts", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")],
  bundle: true,
  format: "esm",
  write: false,
  logLevel: "silent",
});
const { savedChartSettings, chartSettings } = await import(
  "data:text/javascript;base64," + Buffer.from(bundled.outputFiles[0].text).toString("base64")
);

// What marimo 0.23 saved for a binned bar chart after the Style tab and the faceting section were filled in (copied from the page).
const styled = {
  general: {
    facet: {
      row: { linkYAxis: true, binned: true, maxbins: 6, field: "concept:name", type: "string", selectedDataType: "string" },
      column: { linkXAxis: true, binned: true, maxbins: 6 },
    },
    xColumn: { field: "amount", type: "number", selectedDataType: "number", aggregate: "bin" },
    yColumn: { field: "__count__", type: "", selectedDataType: "" },
    colorByColumn: {},
    title: "Amounts",
  },
  color: { field: "none", scheme: "default" },
  tooltips: { auto: true, fields: [] },
  xAxis: { bin: { binned: true, step: 5000 }, label: "Fine amount", width: 606 },
  style: { gridLines: true },
  yAxis: {},
};
const form = { chart_type: "Bar", x: "amount", x_aggregation: "Bin", x_data_type: "Number", x_sort: "Ascending", y: "Count of records" };

test("the bin step, the Style tab and the faceting marimo saved become settings", () => {
  assert.deepEqual(savedChartSettings(styled), {
    title: "Amounts",
    x_label: "Fine amount",
    x_bin_step: "5000",
    width: "606",
    grid_lines: true,
    facet_row: "concept:name",
  });
});

test("defaults marimo leaves out, or keeps as 'none' and 'default', add nothing", () => {
  const plain = { general: { facet: { row: {}, column: {} } }, color: { field: "none", scheme: "default" }, tooltips: { auto: true, fields: [] }, xAxis: { bin: { binned: true } }, yAxis: {} };
  assert.deepEqual(savedChartSettings(plain), {});
  assert.deepEqual(savedChartSettings(undefined), {});
  assert.deepEqual(savedChartSettings("not a config"), {});
});

test("colour, maximum bins, height and chosen tooltips are read", () => {
  const config = {
    color: { field: "region", scheme: "viridis", range: ["#ff0000", "#00ff00"] },
    yAxis: { bin: { maxbins: 20 }, height: 450, label: "Events" },
    tooltips: { auto: false, fields: [{ field: "amount" }, { field: "region" }] },
  };
  assert.deepEqual(savedChartSettings(config), {
    y_label: "Events",
    y_max_bins: "20",
    height: "450",
    color_field: "region",
    color_scheme: "viridis",
    color_range: "#ff0000 #00ff00",
    tooltips: "amount, region",
  });
});

test("a changed bin step changes the settings a chart is recorded with", () => {
  const before = chartSettings(form, { ...styled, xAxis: { bin: { binned: true } } });
  const after = chartSettings({ ...form, x_bin_step: "5000" }, styled);
  assert.notDeepEqual(before, after);
  assert.equal(after.x_bin_step, "5000");
});

test("the form's faceting and tooltip fields give way to the saved ones, so folding those sections changes nothing", () => {
  const unfolded = { ...form, facet: "concept:name", facet_data_type: "Categorical", facet_link_y_axes: true };
  assert.deepEqual(chartSettings(unfolded, styled), chartSettings(form, styled));
  assert.equal(chartSettings(unfolded, styled).facet_row, "concept:name");
});

test("the saved values win over the form's, and without a saved tab the form is used as it is", () => {
  assert.equal(chartSettings({ ...form, x_bin_step: "5,000" }, styled).x_bin_step, "5000");
  const alone = { ...form, x_bin_step: "5000", facet: "concept:name" };
  assert.deepEqual(chartSettings(alone, undefined), alone);
});
