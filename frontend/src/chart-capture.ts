// Charts built in marimo's Visualize tab (its chart builder) live only in the browser: nothing about them reaches the kernel. This
// watches the page for a chart builder that has settled, reads its settings from the form, and hands them to the panel
// (`chart_event`), which records them as a step. It reads headings, labels and roles (not styling classes), and does nothing, never
// throws, when the page does not look the way it expects.
import { readBuilderState, withDisplayedAggregation } from "./chart-restore";
import { findTaggedAncestor } from "./picker";

export type ChartSettings = Record<string, string | boolean>;

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
  on(event: string, callback: () => void): void;
}

const SECTIONS: Record<string, string> = {
  "x-axis": "x",
  "y-axis": "y",
  "color by": "color",
  "faceting": "facet",
  "tooltips": "tooltips",
};
const PLACEHOLDERS = new Set(["select column", "select...", "none selected", ""]);

const slug = (text: string): string => text.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");

// The chart builder is open in this table when its form (headed "X-Axis") is on the page.
export function builderIsOpen(shadow: ShadowRoot): boolean {
  return Array.from(shadow.querySelectorAll("h2")).some((h) => slug(h.textContent ?? "") === "x_axis");
}

/**
 * The settings the chart builder in `shadow` currently shows: chart type, and per section (x, y, color, facet, tooltips) the chosen
 * column, its aggregation, and labelled options such as data type, sort or invert axis. Returns null when no builder is open or no
 * column has been chosen yet (an unfinished chart is not worth recording).
 */
export function readChartSettings(shadow: ShadowRoot): ChartSettings | null {
  try {
    if (!builderIsOpen(shadow)) return null;
    const settings: ChartSettings = {};
    const all = Array.from(shadow.querySelectorAll("*"));
    const firstHeading = all.findIndex((e) => e.tagName === "H2");
    // the chart type: the first dropdown before the form's first heading
    const typeButton = all
      .slice(0, firstHeading)
      .find((e) => e.tagName === "BUTTON" && e.getAttribute("role") === "combobox");
    const chartType = typeButton?.textContent?.trim();
    if (chartType) settings.chart_type = chartType;

    let section = "";
    let dropdowns = 0;
    let label = "";
    for (const element of all.slice(firstHeading)) {
      const tag = element.tagName;
      if (tag === "H2") {
        section = SECTIONS[(element.textContent ?? "").trim().toLowerCase()] ?? slug(element.textContent ?? "");
        dropdowns = 0;
        label = "";
      } else if (tag === "LABEL") {
        label = slug(element.textContent ?? "");
      } else if (tag === "BUTTON" && element.getAttribute("role") === "combobox" && section) {
        const text = (element.textContent ?? "").trim();
        const field = label || (dropdowns === 0 ? "" : "aggregation");
        dropdowns += 1;
        label = "";
        if (!PLACEHOLDERS.has(text.toLowerCase())) settings[field ? `${section}_${field}` : section] = text;
      } else if (tag === "BUTTON" && element.getAttribute("role") === "checkbox" && section && label) {
        settings[`${section}_${label}`] = element.getAttribute("aria-checked") === "true" || element.getAttribute("data-state") === "checked";
        label = "";
      } else if (tag === "INPUT" && section && label && (element as HTMLInputElement).type !== "hidden" && (element as HTMLInputElement).type !== "checkbox") {
        // a labelled number or text field, such as "Bin step" or "Max bins"; an empty one shows marimo's default
        const value = (element as HTMLInputElement).value.trim();
        if (value) settings[`${section}_${label}`] = value;
        label = "";
      }
    }
    const chosen = ["x", "y", "color", "facet"].some((s) => typeof settings[s] === "string");
    return chosen ? settings : null;
  } catch {
    return null;
  }
}

// Whether the analyst is typing in a field of the form (a bin step, a title). marimo takes the value and redraws the chart only when
// the field is left, so until then the chart on the page, and its picture, are still the old ones.
export function isEditing(shadow: ShadowRoot): boolean {
  const active = shadow.activeElement as HTMLInputElement | null;
  if (!active) return false;
  return active.tagName === "TEXTAREA" || (active.tagName === "INPUT" && !["checkbox", "radio", "hidden", "button"].includes(active.type));
}

// The chart tab the builder shows (its name), or "" when it cannot tell.
export function activeChartTab(shadow: ShadowRoot, tabNames: string[]): string {
  try {
    const selected = Array.from(shadow.querySelectorAll('[role="tab"]')).filter(
      (tab) => tab.getAttribute("aria-selected") === "true" || tab.getAttribute("data-state") === "active",
    );
    return selected.map((tab) => (tab.textContent ?? "").trim()).find((name) => tabNames.includes(name)) ?? "";
  } catch {
    return "";
  }
}

const text = (value: unknown): string | undefined =>
  typeof value === "string" ? value.trim() || undefined : typeof value === "number" && Number.isFinite(value) ? String(value) : undefined;
const field = (column: unknown): string | undefined => {
  const name = text((column as { field?: unknown } | undefined)?.field);
  return name && name !== "none" ? name : undefined;
};

/**
 * The settings marimo saved for one chart tab that the form does not always show: the Style tab (title, grid lines, axis labels,
 * width, height, colour), the bin step and maximum bins, and the faceting and tooltip sections, which are only on the page while
 * they are open. Keys match what `readChartSettings` reads from the open form ("x_bin_step", "x_max_bins"), so both agree. Values
 * left at marimo's defaults are not saved by marimo and so are absent here.
 */
export function savedChartSettings(config: unknown): ChartSettings {
  const settings: ChartSettings = {};
  const put = (key: string, value: string | boolean | undefined) => {
    if (value !== undefined) settings[key] = value;
  };
  try {
    const c = (config ?? {}) as Record<string, any>;
    const general = c.general ?? {};
    put("title", text(general.title));
    for (const [axis, key] of [["x", "xAxis"], ["y", "yAxis"]] as const) {
      const style = c[key] ?? {};
      put(`${axis}_label`, text(style.label));
      put(`${axis}_bin_step`, text(style.bin?.step));
      put(`${axis}_max_bins`, text(style.bin?.maxbins));
    }
    put("width", text(c.xAxis?.width));
    put("height", text(c.yAxis?.height));
    if (typeof c.style?.gridLines === "boolean") put("grid_lines", c.style.gridLines);
    put("facet_row", field(general.facet?.row));
    put("facet_column", field(general.facet?.column));
    const color = c.color ?? {};
    put("color_field", field(color));
    const scheme = text(color.scheme);
    if (scheme && scheme !== "default") put("color_scheme", scheme);
    if (Array.isArray(color.range) && color.range.length) put("color_range", color.range.map(String).join(" "));
    const tooltips = c.tooltips ?? {};
    if (tooltips.auto === false) {
      const names = Array.isArray(tooltips.fields) ? tooltips.fields.map((f: unknown) => field(f) ?? text(f)).filter(Boolean) : [];
      put("tooltips", names.length ? names.join(", ") : "none");
    }
  } catch {
    // a config of a shape this does not know adds nothing
  }
  return settings;
}

/**
 * What a chart is recorded with: the open form's settings joined with what marimo saved for the tab on show. The faceting and
 * tooltip sections come from the saved tab only (the form loses them when they are folded), and the saved values win over the
 * form's. `form` may be the form as last read while the Data tab was shown, when the analyst is on the Style tab now.
 */
export function chartSettings(form: ChartSettings, savedConfig: unknown | undefined): ChartSettings {
  if (savedConfig === undefined) return form;
  const settings: ChartSettings = {};
  for (const [key, value] of Object.entries(form)) {
    if (key === "facet" || key.startsWith("facet_") || key === "tooltips" || key.startsWith("tooltips_")) continue;
    settings[key] = value;
  }
  return { ...settings, ...savedChartSettings(savedConfig) };
}

// Every marimo table on the page that has a shadow root (the chart builder is drawn inside it), also those inside other shadow roots:
// marimo draws the contents of mo.ui.tabs, for one, inside its own.
function tablesWithShadow(): HTMLElement[] {
  const found: HTMLElement[] = [];
  const walk = (root: Document | ShadowRoot) => {
    for (const element of Array.from(root.querySelectorAll<HTMLElement>("*"))) {
      if (element.tagName === "MARIMO-TABLE" && element.shadowRoot) found.push(element);
      if (element.shadowRoot) walk(element.shadowRoot);
    }
  };
  walk(document);
  return found;
}

const PNG_MAX_WIDTH = 900;
const PNG_MAX_BASE64_CHARS = 450_000; // the report and the annotation carry it, and marimo's widget state has to move it

interface ChartPicture {
  png: string; // base64, no data: prefix
  container: HTMLElement; // the element that holds the drawn chart: this is what gets tagged so it can be anchored
}

// The chart as a picture, from the canvas the chart builder drew it on (on white, so it reads in a report), or null.
export function chartPicture(shadow: ShadowRoot): ChartPicture | null {
  try {
    const embed = shadow.querySelector<HTMLElement>(".vega-embed");
    const canvas = embed?.querySelector("canvas");
    if (!embed || !canvas || !canvas.width || !canvas.height) return null;
    for (const shrink of [1, 0.7, 0.5]) {
      const scale = Math.min(1, PNG_MAX_WIDTH / canvas.width) * shrink;
      const out = document.createElement("canvas");
      out.width = Math.max(1, Math.round(canvas.width * scale));
      out.height = Math.max(1, Math.round(canvas.height * scale));
      const context = out.getContext("2d");
      if (!context) return null;
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, out.width, out.height);
      context.drawImage(canvas, 0, 0, out.width, out.height);
      const png = out.toDataURL("image/png").split(",")[1] ?? "";
      if (png && png.length <= PNG_MAX_BASE64_CHARS) return { png, container: embed.parentElement ?? embed };
    }
  } catch {
    // a canvas the page does not let us read: the chart is recorded without a picture
  }
  return null;
}

interface Ack {
  eventId?: string;
  artifactId?: string | null;
  artifactName?: string;
}

// Mark the chart as the artifact it became, the way show_table marks a table, so the Anchor button can pick it.
function tagChart(container: HTMLElement, ack: Ack, png: string): void {
  container.dataset.pwArtifactId = ack.artifactId ?? "";
  container.dataset.pwArtifactName = ack.artifactName ?? "";
  container.dataset.pwGranularity = "chart_selection";
  container.dataset.pwSnapshot = JSON.stringify({ kind: "image", png });
  container.classList.add("pw-annotatable");
}

/**
 * Poll the page for charts that have settled and report them through `chart_event` (settings and a picture). A chart counts as
 * settled when its settings were the same on two polls in a row; only a settled chart that differs from the one last reported for
 * that table is sent. When the panel answers (`chart_ack`) with the artifact the chart became, the chart is tagged so it can be
 * anchored. Returns a function that stops the watching.
 */
export function armChartCapture(model: AnyModel, panelRoot: HTMLElement, pollMs = 600): () => void {
  const lastSeen = new WeakMap<HTMLElement, string>();
  const lastSent = new WeakMap<HTMLElement, string>();
  const lastForm = new WeakMap<HTMLElement, ChartSettings>(); // the form as the Data tab last showed it
  const waiting = new Map<string, { host: HTMLElement; png: string }>(); // chart_event id -> where it came from
  const tagged = new WeakMap<HTMLElement, { ack: Ack; png: string }>(); // what each table's current chart was tagged with
  let counter = 0;

  model.on("change:chart_ack", () => {
    if (!panelRoot.isConnected) return;
    const ack = (model.get("chart_ack") ?? {}) as Ack;
    const origin = ack.eventId ? waiting.get(ack.eventId) : undefined;
    if (!origin || !ack.artifactId) return;
    waiting.delete(ack.eventId as string);
    tagged.set(origin.host, { ack, png: origin.png });
    const picture = chartPicture(origin.host.shadowRoot as ShadowRoot);
    if (picture) tagChart(picture.container, ack, origin.png);
  });

  const tick = () => {
    if (!panelRoot.isConnected) return stop();
    // marimo mounts a sidebar widget twice (desktop and drawer); only the visible one reports
    if (!model.get("capture_charts") || panelRoot.offsetParent === null || document.hidden) return;
    for (const host of tablesWithShadow()) {
      const shadow = host.shadowRoot as ShadowRoot;
      if (isEditing(shadow)) {
        lastSeen.delete(host); // settled only once the field is left and the chart redrawn
        continue;
      }
      // on the Style tab the form's columns are not on the page: keep what the Data tab showed and add what marimo saved
      let form = readChartSettings(shadow);
      if (form) lastForm.set(host, form);
      else if (builderIsOpen(shadow)) form = lastForm.get(host) ?? null;
      if (!form) continue;
      const saved = readBuilderState(host);
      const tab = saved?.tabs.find((t) => t.tabName === activeChartTab(shadow, saved.tabs.map((s) => s.tabName)));
      const settings = chartSettings(form, tab?.config);
      const signature = JSON.stringify(settings);
      const settled = lastSeen.get(host) === signature;
      lastSeen.set(host, signature);
      // the chart builder redraws its chart now and then: keep the tag on whatever is drawn
      const current = tagged.get(host);
      if (current && lastSent.get(host) === signature) {
        const picture = chartPicture(shadow);
        if (picture && picture.container.dataset.pwArtifactId !== current.ack.artifactId) tagChart(picture.container, current.ack, current.png);
      }
      if (!settled || lastSent.get(host) === signature) continue;
      const tag = findTaggedAncestor(host);
      if (!tag) continue;
      lastSent.set(host, signature);
      counter += 1;
      const id = `${Date.now()}-${counter}`;
      const picture = chartPicture(shadow);
      if (picture) waiting.set(id, { host, png: picture.png });
      tagged.delete(host);
      // marimo's own saved tabs for this table's cell: what restoreChartBuilders writes back in a browser that has never seen them
      const builder = saved ? withDisplayedAggregation(saved, settings) : null;
      model.set("chart_event", {
        id,
        artifactId: tag.dataset.pwArtifactId ?? "",
        artifactName: tag.dataset.pwArtifactName ?? "",
        settings,
        ...(picture ? { image: picture.png } : {}),
        ...(builder ? { builder } : {}),
      });
      model.save_changes();
    }
  };
  const timer = window.setInterval(tick, pollMs);
  const stop = () => window.clearInterval(timer);
  return stop;
}
