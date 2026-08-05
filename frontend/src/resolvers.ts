// Extension point for "how do I refine a pick to a specific element inside
// this artifact" — the picker itself has no built-in knowledge of any
// particular table or chart library. Each resolver gets first look at the
// click's full composedPath() (so it can see through shadow DOM/custom
// elements) and returns a refined { granularity, detail } if it recognizes
// something in that path, or null to let the next resolver (or the
// artifact's own baked-in granularity/detail) have a turn.
export interface PickDetail {
  granularity: string;
  detail: string | null;
}

export interface DetailResolver {
  name: string;
  resolve(path: EventTarget[], clickTarget: HTMLElement): PickDetail | null;
}

const resolvers: DetailResolver[] = [];

export function registerDetailResolver(resolver: DetailResolver): void {
  resolvers.push(resolver);
}

export function resolveDetail(path: EventTarget[], clickTarget: HTMLElement): PickDetail | null {
  for (const resolver of resolvers) {
    const result = resolver.resolve(path, clickTarget);
    if (result) return result;
  }
  return null;
}

function inPath(path: EventTarget[], candidate: Element | null): boolean {
  return candidate !== null && path.includes(candidate);
}

// Built in: plain HTML tables (mo.ui.table renders one inside its shadow
// root — composedPath is what lets us see it at all, see picker.ts).
registerDetailResolver({
  name: "html-table",
  resolve(path, clickTarget) {
    const td = clickTarget.closest("td");
    if (td && inPath(path, td)) {
      const tr = td.parentElement;
      const colIndex = tr ? Array.from(tr.children).indexOf(td) : -1;
      const table = td.closest("table");
      let columnName: string | null = null;
      if (table && colIndex >= 0) {
        const headerCell = table.querySelector("thead tr")?.children[colIndex];
        columnName = headerCell?.textContent?.trim() ?? null;
      }
      const tbody = tr?.parentElement;
      const rowIndex = tr && tbody ? Array.from(tbody.children).indexOf(tr) : -1;
      const detail = columnName ? `row ${rowIndex}, column ${columnName}` : `row ${rowIndex}`;
      return { granularity: "cell", detail };
    }

    const th = clickTarget.closest("th");
    if (th && inPath(path, th)) {
      return { granularity: "column", detail: th.textContent?.trim() ?? null };
    }

    return null;
  },
});

// Built in: any SVG-rendered chart whose individual marks carry an
// aria-label — this is the accessibility hook most SVG charting libraries
// already emit for free. Vega-Lite/Altair does this by default (each mark
// gets an aria-label like "x: Register; y: 12.5"), which is exactly the
// kind of chart library a third party would plug in without ever touching
// this file. Any other SVG-based library that tags its marks the same way
// (aria-label, or a plain data-pw-detail attribute) gets picked up too.
registerDetailResolver({
  name: "svg-mark",
  resolve(path) {
    for (const node of path) {
      if (!(node instanceof Element)) continue;
      if (node.closest("svg") === null && node.tagName.toLowerCase() !== "svg") continue;
      const explicitDetail = node.getAttribute("data-pw-detail");
      if (explicitDetail) {
        return { granularity: node.getAttribute("data-pw-granularity") ?? "mark", detail: explicitDetail };
      }
      const ariaLabel = node.getAttribute("aria-label");
      if (ariaLabel && node.getAttribute("role") === "graphics-symbol") {
        return { granularity: "mark", detail: ariaLabel };
      }
    }
    return null;
  },
});
