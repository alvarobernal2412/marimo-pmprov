// A chart built in marimo's Visualize tab keeps its builder state (chart type, columns, aggregation, colors, ...) only in the browser:
// marimo writes the tabs of each cell to localStorage, under a key scoped by the notebook's file name. A browser that has never seen
// the analysis (another computer, another port, cleared site data) therefore opens every table with an empty builder, although the
// history recorded each chart. The tabs are recorded with each chart (`readBuilderState`) and handed back through `chart_restore`;
// `restoreChartBuilders` writes them where marimo reads them and reloads the page once, because marimo reads that storage when the
// page starts and takes no notice of a later write. Everything here reads the page defensively and never throws.

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
 * its Visualize tab as the analyst left it. Does nothing when this browser already has those tabs, which is the normal case after the
 * first time, and never reloads twice for the same recorded charts in one tab, so it cannot loop. Returns whether it reloaded.
 */
export function restoreChartBuilders(model: AnyModel, env?: RestoreEnv): boolean {
  try {
    if (!model.get("capture_charts")) return false;
    const restore = (model.get("chart_restore") ?? {}) as BuilderTabs;
    if (!restore || !Object.keys(restore).length) return false;
    const { storage, session, filename, reload } = env ?? browserEnv();
    if (!filename) return false;
    const key = marimoChartsKey(filename);
    const { json, changed } = mergeBuilderStates(storage.getItem(key), restore);
    if (!changed) return false;
    const guard = `pw-charts-restored:${key}`;
    const signature = hash(JSON.stringify(restore));
    if (session.getItem(guard) === signature) return false;
    storage.setItem(key, json);
    session.setItem(guard, signature);
    reload();
    return true;
  } catch {
    return false;
  }
}
