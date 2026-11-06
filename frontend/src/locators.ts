// The reverse of the detail resolvers (resolvers.ts): given the artifact's element and the granularity and detail that
// were recorded when a pick was made, find the element that was pinned. Returns null when it cannot be found with
// confidence, so the caller falls back to marking the whole artifact instead of pointing at the wrong thing.
import { cellText, headerName, parseCellDetail, sankeyLinkDetail } from "./resolvers";

export type Located = HTMLElement | SVGElement;

// Every element under `root`, looking through shadow roots (marimo tables and Plotly charts render inside them).
function elementsUnder(root: Element): Element[] {
  const out: Element[] = [];
  const walk = (node: Element | ShadowRoot) => {
    for (const el of node.querySelectorAll("*")) {
      out.push(el);
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(root);
  if (root.shadowRoot) walk(root.shadowRoot);
  return out;
}

// A table cell by its recorded position and value. The position alone breaks when the table is sorted, filtered or
// paged differently on replay, so the value must agree: the recorded position is used when it still holds the value,
// otherwise the one row that holds it. Several rows with that value, or none, give null rather than a guess.
// Details recorded before values were kept have no value to check and fall back to the position.
function locateCell(all: Element[], detail: string): Located | null {
  const ref = parseCellDetail(detail);
  const table = all.find((e) => e.tagName === "TABLE");
  if (!ref || !table) return null;
  const rows = Array.from(table.querySelectorAll("tbody tr"));
  let col = -1;
  if (ref.column !== null) {
    const headers = Array.from(table.querySelectorAll("thead tr:first-child > *"));
    col = headers.findIndex((h) => headerName(h) === ref.column);
    if (col < 0) return null;
  }
  const cellOf = (row: Element | undefined) => (col >= 0 ? row?.children[col] : row) as HTMLElement | undefined;
  if (ref.value === null) return cellOf(rows[ref.row]) ?? null;
  const matches = (row: Element | undefined) => {
    const cell = cellOf(row);
    return cell !== undefined && cellText(cell) === ref.value;
  };
  if (matches(rows[ref.row])) return cellOf(rows[ref.row]) ?? null;
  const holders = rows.filter((row) => matches(row));
  return holders.length === 1 ? (cellOf(holders[0]) ?? null) : null;
}

interface SankeyElement extends Element {
  __data__?: { index?: number; node?: { label?: string }; link?: unknown };
}

function locateSankey(all: Element[], granularity: string, detail: string): Located | null {
  const nodes = all.filter((e) => e.classList.contains("sankey-node")) as SankeyElement[];
  if (granularity === "node") {
    const hit = nodes.find((n) => n.__data__?.node?.label === detail);
    return (hit?.querySelector("rect") as SVGElement | null) ?? null;
  }
  const labels = (i: number) => String(nodes.find((n) => n.__data__?.index === i)?.__data__?.node?.label ?? i);
  const links = all.filter((e) => e.classList.contains("sankey-link")) as SankeyElement[];
  const hit = links.find((l) => l.__data__ && sankeyLinkDetail(l.__data__ as never, labels) === detail);
  return (hit as unknown as SVGElement | undefined) ?? null;
}

export function locateDetail(root: HTMLElement, granularity: string, detail: string): Located | null {
  const all = elementsUnder(root);
  switch (granularity) {
    case "cell":
      return locateCell(all, detail);
    case "column":
      return (all.find((e) => e.tagName === "TH" && headerName(e) === detail) as HTMLElement | undefined) ?? null;
    case "node":
    case "link":
      return locateSankey(all, granularity, detail);
    default:
      return null;
  }
}
