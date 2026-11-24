// A chart built in marimo's Visualize tab keeps its builder state (chart type, columns, aggregation, colors, ...) only in the browser:
// marimo writes the tabs of each cell to localStorage, under a key scoped by the notebook's file name. A browser that has never seen
// the analysis (another computer, another port, cleared site data) therefore opens every table with an empty builder, although the
// history recorded each chart. The tabs are recorded with each chart (`readBuilderState`) and handed back through `chart_restore`;
// `restoreChartBuilders` writes them where marimo reads them and reloads the page once, because marimo reads that storage when the
// page starts and takes no notice of a later write. Everything here reads the page defensively and never throws.
//
// Two more things keep a resumed analysis the one that was left:
// - marimo saves the tabs under the id of the table's cell, and an id is the position of the cell. `chart_layout` names where the
//   tables are drawn now; a browser that saved its tabs under another layout has them under the ids of other cells, so they are
//   replaced by the recorded ones, which the panel gives by the cells of now.
// - marimo shows an aggregation it has not saved (Y is "Mean") and loads a tab without one as "None". The recorded tabs have it,
//   and `keepAggregations` writes it into the saved ones while the page is open, so the next start finds it and loads nothing twice.

export interface BuilderTab {
  tabName: string;
  chartType: string;
  config: unknown;
}
export type BuilderTabs = Record<string, BuilderTab[]>; // cell id -> the tabs of that cell
export interface BuilderState {
  cellId: string;
  tabs: BuilderTab[];
}
interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}
interface AnyModel {
  get(key: string): unknown;
}
export interface RestoreEnv {
  storage: StorageLike; // marimo's own (localStorage)
  session: StorageLike; // remembers, per tab, what was already restored (sessionStorage)
  filename: string | null;
  reload: () => void;
}

export const marimoChartsKey = (filename: string): string => `marimo:charts:v2:${filename}`;
/** Where this browser remembers the layout (see `chart_layout`) its saved tabs of a notebook belong to. */
export const chartLayoutKey = (filename: string): string => `pw-chart-layout:${filename}`;

/** The notebook's file name as marimo's page states it (a hidden element), which is what marimo scopes its storage key by. */
export function notebookFilename(): string | null {
  const text = document.querySelector("marimo-filename")?.textContent?.trim();
  return text ? text : null;
}

/** The id of the marimo cell whose output contains `node`, also from inside shadow roots (marimo draws tabs in their own). */
export function cellIdOf(node: Node | null): string | null {
  let current: Node | null = node;
  while (current) {
    if (current instanceof Element) {
      const match = /^(?:output|cell)-(.+)$/.exec(current.id);
      if (match) return match[1];
    }
    current = current.parentNode ?? (current instanceof ShadowRoot ? current.host : null);
  }
  return null;
}

/** marimo's own saved tabs for the cell of `host` (its table), or null when there are none or the page does not look as expected. */
export function readBuilderState(host: HTMLElement): BuilderState | null {
  try {
    const filename = notebookFilename();
    const cellId = cellIdOf(host);
    if (!filename || !cellId) return null;
    const entries = JSON.parse(window.localStorage.getItem(marimoChartsKey(filename)) ?? "[]");
    const tabs = Array.isArray(entries) ? entries.find((entry) => Array.isArray(entry) && entry[0] === cellId)?.[1] : undefined;
    return Array.isArray(tabs) && tabs.length ? { cellId, tabs } : null;
  } catch {
    return null;
  }
}

// marimo's aggregation names, as the lower-cased words the form shows them in
const AGGREGATIONS = new Set(["none", "count", "sum", "mean", "median", "min", "max", "distinct", "valid", "stdev", "stdevp", "variance", "variancep"]);
const COLUMNS: [section: string, key: string][] = [
  ["x", "xColumn"],
  ["y", "yColumn"],
  ["color", "colorByColumn"],
];

/**
 * `state` with the aggregation the chart builder was *showing* filled in where marimo's saved entry has none. marimo shows Y as "Mean"
 * by default but saves no `aggregate` until the analyst picks one, and an entry without it reloads as "None": a restored chart would
 * then plot sums where the analyst saw means. `settings` is what the scraped form showed (chart type, then per axis its column and
 * `<axis>_aggregation`); only a tab of that chart type whose column is the shown one is touched. Returns a new state; never throws.
 */
export function withDisplayedAggregation(state: BuilderState, settings: Record<string, string | boolean>): BuilderState {
  const chartType = String(settings.chart_type ?? "").toLowerCase();
  const tabs = state.tabs.map((tab) => {
    try {
      const config = tab.config as { general?: Record<string, unknown> } | null;
      const general = config?.general;
      if (tab.chartType !== chartType || !general || typeof general !== "object") return tab;
      let patched = general;
      for (const [section, key] of COLUMNS) {
        const column = general[key] as Record<string, unknown> | undefined;
        const shown = settings[`${section}_aggregation`];
        if (!column || typeof column !== "object" || column.field !== settings[section] || column.aggregate !== undefined) continue;
        const value = typeof shown === "string" ? shown.trim().toLowerCase() : "";
        if (AGGREGATIONS.has(value)) patched = { ...patched, [key]: { ...column, aggregate: value } };
      }
      return patched === general ? tab : { ...tab, config: { ...config, general: patched } };
    } catch {
      return tab;
    }
  });
  return { ...state, tabs };
}

/**
 * `existingJson` (what marimo saved in this browser) with the recorded tabs added. What the browser already has is kept as it is:
 * a tab of the same name in the same cell is left alone, so work done here since is never overwritten. `changed` says whether
 * anything was added.
 */
export function mergeBuilderStates(existingJson: string | null, restore: BuilderTabs): { json: string; changed: boolean } {
  let entries: [string, BuilderTab[]][] = [];
  try {
    const parsed = JSON.parse(existingJson ?? "[]");
    if (Array.isArray(parsed)) {
      entries = parsed.filter((e) => Array.isArray(e) && typeof e[0] === "string" && Array.isArray(e[1])) as [string, BuilderTab[]][];
    }
  } catch {
    // unreadable saved data counts as none
  }
  let changed = false;
  for (const [cellId, tabs] of Object.entries(restore)) {
    const at = entries.findIndex(([id]) => id === cellId);
    if (at < 0) {
      entries.push([cellId, tabs]);
      changed = true;
      continue;
    }
    const have = new Set(entries[at][1].map((tab) => tab.tabName));
    const missing = tabs.filter((tab) => !have.has(tab.tabName));
    if (missing.length) {
      entries[at] = [cellId, [...entries[at][1], ...missing]];
      changed = true;
    }
  }
  return { json: JSON.stringify(entries), changed };
}

function savedEntries(json: string | null): [string, BuilderTab[]][] {
  try {
    const parsed = JSON.parse(json ?? "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((e) => Array.isArray(e) && typeof e[0] === "string" && Array.isArray(e[1])) as [string, BuilderTab[]][];
  } catch {
    return [];
  }
}

/**
 * Gives the saved tabs (`entries`, changed in place) the recorded aggregations they lack: a column of a saved tab (same cell, tab
 * name and chart type, same field) without an `aggregate` gets the recorded one. An aggregation that is saved, also "none", is the
 * analyst's choice and is never changed. Returns whether it added one.
 */
export function fillAggregations(entries: [string, BuilderTab[]][], restore: BuilderTabs): boolean {
  let added = false;
  for (const [cellId, tabs] of entries) {
    const recorded = restore[cellId];
    if (!Array.isArray(recorded)) continue;
    for (const tab of tabs) {
      try {
        const old = recorded.find((t) => t && t.tabName === tab.tabName && t.chartType === tab.chartType);
        const general = (tab.config as { general?: Record<string, any> } | null)?.general;
        const oldGeneral = (old?.config as { general?: Record<string, any> } | null)?.general;
        if (!general || !oldGeneral) continue;
        for (const [, key] of COLUMNS) {
          const column = general[key];
          const earlier = oldGeneral[key];
          if (!column || !earlier || !column.field || column.field !== earlier.field) continue;
          if (column.aggregate !== undefined || !earlier.aggregate) continue;
          column.aggregate = earlier.aggregate;
          added = true;
        }
      } catch {
        // a tab of a shape this does not know is left alone
      }
    }
  }
  return added;
}

const hash = (text: string): string => {
  let h = 5381;
  for (let i = 0; i < text.length; i += 1) h = ((h << 5) + h + text.charCodeAt(i)) | 0;
  return String(h >>> 0);
};

function browserEnv(): RestoreEnv {
  return {
    storage: window.localStorage,
    session: window.sessionStorage,
    filename: notebookFilename(),
    reload: () => window.location.reload(),
  };
}

/**
 * Put the charts the history recorded (`chart_restore`) back into marimo's storage and reload the page once, so every table opens
 * its Visualize tab as the analyst left it. Call it when the page starts. Does nothing when this browser already has those tabs,
 * which is the normal case after the first time, and never reloads twice for the same recorded charts in one tab, so it cannot
 * loop. Returns whether it reloaded.
 *
 * With a `chart_layout`, a browser whose saved tabs belong to another layout (or to none: saved before 0.16) has them replaced by
 * the recorded ones, once `chart_restore_ready` says these were read: the saved ids name other cells now. Otherwise the recorded
 * tabs the browser lacks are added, and the saved ones get the recorded aggregations they lack.
 */
export function restoreChartBuilders(model: AnyModel, env?: RestoreEnv): boolean {
  try {
    if (!model.get("capture_charts")) return false;
    const restore = ((model.get("chart_restore") ?? {}) || {}) as BuilderTabs;
    const layout = String(model.get("chart_layout") ?? "");
    const { storage, session, filename, reload } = env ?? browserEnv();
    if (!filename) return false;
    const key = marimoChartsKey(filename);
    const existing = storage.getItem(key);
    let json: string | null = null;
    if (layout) {
      if (model.get("chart_restore_ready") !== true) return false; // an empty chart_restore may only not have been read yet
      if (storage.getItem(chartLayoutKey(filename)) !== layout) {
        storage.setItem(chartLayoutKey(filename), layout);
        const recorded = Object.entries(restore).filter(([, tabs]) => Array.isArray(tabs) && tabs.length);
        if (savedEntries(existing).length || recorded.length) json = JSON.stringify(recorded);
      }
    }
    if (json === null) {
      if (!Object.keys(restore).length) return false;
      const merged = mergeBuilderStates(existing, restore);
      const entries = savedEntries(merged.json);
      const filled = fillAggregations(entries, restore);
      if (!merged.changed && !filled) return false;
      json = JSON.stringify(entries);
    }
    if (json === existing) return false;
    const guard = `pw-charts-restored:${key}`;
    const signature = hash(layout + JSON.stringify(restore));
    if (session.getItem(guard) === signature) return false;
    storage.setItem(key, json);
    session.setItem(guard, signature);
    reload();
    return true;
  } catch {
    return false;
  }
}

/**
 * While the page is open: write the recorded aggregations into the saved tabs that lack them (see `fillAggregations`). marimo does
 * not read its storage again, so nothing changes on the page; the next start finds the aggregation and has nothing to reload for.
 * Returns whether it wrote.
 */
export function keepAggregations(model: AnyModel, env?: Pick<RestoreEnv, "storage" | "filename">): boolean {
  try {
    if (!model.get("capture_charts")) return false;
    const restore = (model.get("chart_restore") ?? {}) as BuilderTabs;
    if (!restore || !Object.keys(restore).length) return false;
    const { storage, filename } = env ?? browserEnv();
    if (!filename) return false;
    const key = marimoChartsKey(filename);
    const entries = savedEntries(storage.getItem(key));
    if (!fillAggregations(entries, restore)) return false;
    storage.setItem(key, JSON.stringify(entries));
    return true;
  } catch {
    return false;
  }
}

/**
 * Restore the recorded charts once the panel has them (`restoreChartBuilders`, which may reload the page), and from then on keep
 * the saved tabs' aggregations (`keepAggregations`, which never does): after a chart is recorded, every few seconds and as the page
 * is left. marimo mounts a sidebar widget twice, and a widget is drawn again now and then: the page is restored once, whoever asks.
 * Returns a function that stops it.
 */
export function armChartRestore(model: AnyModel & { on(event: string, callback: () => void): void }, panelRoot: HTMLElement, everyMs = 3000): () => void {
  const page = window as unknown as { __pwChartsRestored?: boolean };
  const update = () => {
    if (!panelRoot.isConnected) return;
    if (page.__pwChartsRestored) {
      keepAggregations(model);
      return;
    }
    const has = Object.keys((model.get("chart_restore") ?? {}) as object).length > 0;
    const layout = String(model.get("chart_layout") ?? "");
    // a live history is read in a thread: wait for it (a panel before 0.16 has no layout and says nothing until it has charts)
    if (!(model.get("chart_restore_ready") === true || (!layout && has))) return;
    page.__pwChartsRestored = true;
    restoreChartBuilders(model);
  };
  update();
  model.on("change:chart_restore", update);
  model.on("change:chart_restore_ready", update);
  const leaving = () => {
    if (page.__pwChartsRestored) keepAggregations(model);
  };
  window.addEventListener("pagehide", leaving);
  const timer = window.setInterval(() => {
    if (!panelRoot.isConnected) return stop();
    if (page.__pwChartsRestored) keepAggregations(model);
  }, everyMs);
  const stop = () => {
    window.clearInterval(timer);
    window.removeEventListener("pagehide", leaving);
  };
  return stop;
}
