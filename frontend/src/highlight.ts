// After a reviewer presses Replay on a note, point at what the note is about: scroll the targeted element of the
// notebook into view and flash an outline around it. A target is found by the name it was picked under
// (`data-pw-artifact-name`, set by show_table / show_chart / show).
//
// The outline is set inline and animated with the Web Animations API: the elements live in the notebook, outside
// the widget's shadow root, so the widget's stylesheet does not reach them.

import { locateDetail, type Located } from "./locators";

interface TargetRef {
  artifactName?: string;
  granularity?: string;
  detail?: string | null;
}

const FIRST_LOOK_MS = 500; // the notebook's cells re-run when the cursor moves; give them time to draw
const LOOK_EVERY_MS = 200;
const GIVE_UP_MS = 6000;
const RECHECK_MS = 1500; // a cell that finishes re-running late replaces the element that was flashed
const FLASH_COLOR = "#F59E0B";

function* inTree(root: Document | ShadowRoot): Generator<HTMLElement> {
  for (const el of root.querySelectorAll<HTMLElement>("*")) {
    yield el;
    if (el.shadowRoot) yield* inTree(el.shadowRoot);
  }
}

export function findTargets(names: string[]): HTMLElement[] {
  const wanted = new Set(names);
  const found: HTMLElement[] = [];
  for (const el of inTree(document)) {
    const name = el.dataset?.pwArtifactName;
    if (name && wanted.has(name) && el.classList.contains("pw-annotatable")) found.push(el);
  }
  return found;
}

function flash(el: Located): void {
  if (el instanceof SVGElement) return flashSvg(el);
  const previous = { outline: el.style.outline, outlineOffset: el.style.outlineOffset };
  el.style.outline = `3px solid ${FLASH_COLOR}`;
  el.style.outlineOffset = "4px";
  const pulse = el.animate(
    [{ outlineColor: FLASH_COLOR }, { outlineColor: "transparent" }, { outlineColor: FLASH_COLOR }, { outlineColor: "transparent" }],
    { duration: 2400, easing: "ease-in-out" },
  );
  const restore = () => {
    el.style.outline = previous.outline;
    el.style.outlineOffset = previous.outlineOffset;
  };
  pulse.onfinish = restore;
  pulse.oncancel = restore;
}

export function highlightTargets(refs: TargetRef[]): void {
  const names = refs.map((ref) => ref.artifactName ?? "").filter((name) => name !== "");
  if (names.length === 0) return;
  // The pinned element inside the artifact when it can be found, else the whole artifact.
  highlightWhere(() => {
    const picked = refs.filter((ref) => ref.detail);
    return findTargets(names).map(
      (root) => picked.map((ref) => locateDetail(root, ref.granularity ?? "", ref.detail ?? "")).find((el) => el) ?? root,
    );
  });
}

// Stepping through a recorded analysis: point at what the step reached (the tables and maps the notebook shows under
// this step's own state id), so it is easy to see where a step shows up in the notebook.
export function findProducedBy(stateId: string): HTMLElement[] {
  const found: HTMLElement[] = [];
  for (const el of inTree(document)) {
    if (el.dataset?.pwArtifactId === stateId && el.classList.contains("pw-annotatable")) found.push(el);
  }
  return found;
}

export function highlightProducedBy(stateId: string): void {
  highlightWhere(() => findProducedBy(stateId));
}

function highlightWhere(find: () => Located[]): void {
  const started = Date.now();
  let flashed: Located[] = [];

  const look = () => {
    const targets = find();
    if (targets.length === 0) {
      if (Date.now() - started < GIVE_UP_MS) setTimeout(look, LOOK_EVERY_MS);
      return;
    }
    flashed = targets;
    targets[0].scrollIntoView({ behavior: "smooth", block: "center" });
    targets.forEach(flash);
    setTimeout(recheck, RECHECK_MS);
  };

  const recheck = () => {
    const now = find();
    const replaced = now.filter((el) => !flashed.includes(el));
    if (replaced.length > 0) {
      flashed = now;
      replaced.forEach(flash);
    }
  };

  setTimeout(look, FIRST_LOOK_MS);
}

// Plotly redraws and restyles its marks, so an SVG target is marked with a separate overlay clone, not by restyling it.
function flashSvg(el: SVGElement): void {
  const overlay = el.cloneNode(false) as SVGElement;
  overlay.removeAttribute("class");
  overlay.setAttribute("style", `fill:none;stroke:${FLASH_COLOR};stroke-width:4;pointer-events:none`);
  el.parentNode?.appendChild(overlay);
  const pulse = overlay.animate([{ opacity: 1 }, { opacity: 0.15 }, { opacity: 1 }, { opacity: 0.15 }, { opacity: 1 }], { duration: 3200 });
  pulse.onfinish = pulse.oncancel = () => overlay.remove();
}
