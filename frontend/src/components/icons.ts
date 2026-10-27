const SVG_NS = "http://www.w3.org/2000/svg";

// Feather-style 24px stroke icons; inherit color via currentColor.
const PATHS: Record<string, string[]> = {
  edit: ["M12 20h9", "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"],
  trash: ["M3 6h18", "M8 6V4h8v2", "M19 6l-1 14H6L5 6", "M10 11v6", "M14 11v6"],
  x: ["M18 6L6 18", "M6 6l12 12"],
  note: ["M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"],
  // media-player controls, drawn filled (see FILLED below)
  skipBack: ["M19 20L9 12l10-8z", "M5 19V5"],
  stepBack: ["M18 4L6 12l12 8z"],
  stepForward: ["M6 4l12 8L6 20z"],
  skipForward: ["M5 4l10 8L5 20z", "M19 5v14"],
  crosshair: ["M12 2v4", "M12 18v4", "M2 12h4", "M18 12h4", "M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8"],
};

const FILLED = new Set<keyof typeof PATHS>(["skipBack", "stepBack", "stepForward", "skipForward"]);

export function icon(name: keyof typeof PATHS, size = 14): SVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("fill", FILLED.has(name) ? "currentColor" : "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  for (const d of PATHS[name]) {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    svg.appendChild(path);
  }
  return svg;
}
