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
const TAB_SWITCH_MS = 300; // a tab opens on the next draw of the page
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

// A table or map inside a tab the reader is not on cannot be seen, so that tab is opened first. marimo keeps the content of every tab
// as a child of its tabs element (in the order of the tabs) and draws the content of the open tab only. Returns true when a tab was
// clicked, so that the caller gives the page a moment to draw it before it points at anything in it.
function revealTab(el: Element): boolean {
  let child: Node = el;
  while (child.parentNode) {
    const parent: Node = child.parentNode;
    if (parent instanceof HTMLElement && parent.localName === "marimo-tabs" && parent.shadowRoot) {
      const index = [...parent.children].indexOf(child as Element);
      const tab = parent.shadowRoot.querySelectorAll<HTMLElement>('[role="tab"]')[index];
      if (!tab || tab.getAttribute("aria-selected") === "true") return false;
      // marimo's tabs open on the press of the mouse button, not on the click
      for (const type of ["mousedown", "mouseup", "click"]) {
        tab.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, composed: true, button: 0 }));
      }
      return true;
    }
    child = parent instanceof ShadowRoot ? parent.host : parent;
  }
  return false;
}

// What is drawn on the page: the copy of a table that marimo keeps for a tab that is not open is not.
function shown(targets: Located[]): Located[] {
  const drawn = targets.filter((el) => el.getClientRects().length > 0);
  return drawn.length > 0 ? drawn : targets;
}

function flash(el: Located): void {
  if (el instanceof SVGElement) return flashSvg(el);
  if (!el.classList.contains("pw-annotatable")) return blinkElement(el); // a cell or a column, not the whole table
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
  // The pinned element inside the artifact when it can be found, else the whole artifact. A map is drawn again when the
  // step changes, which can take longer than the first look, so the pinned element is looked for until it shows up.
  const picked = refs.filter((ref) => ref.detail);
  highlightWhere(
    () =>
      findTargets(names).map(
        (root) => picked.map((ref) => locateDetail(root, ref.granularity ?? "", ref.detail ?? "")).find((el) => el) ?? root,
      ),
    (found) => picked.length === 0 || found.every((el) => !el.classList.contains("pw-annotatable")),
  );
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

function highlightWhere(find: () => Located[], settled: (found: Located[]) => boolean = () => true): void {
  stopBlinking(); // a new replay ends the previous one
  const started = Date.now();
  let flashed: Located[] = [];

  const look = () => {
    const targets = find();
    if (targets.length === 0) {
      if (Date.now() - started < GIVE_UP_MS) setTimeout(look, LOOK_EVERY_MS);
      return;
    }
    const onScreen = targets.some((el) => el.getClientRects().length > 0); // something to point at is already drawn
    if (!onScreen && targets.some(revealTab) && Date.now() - started < GIVE_UP_MS) {
      setTimeout(look, TAB_SWITCH_MS); // look again once the tab has opened
      return;
    }
    const drawn = shown(targets);
    flashed = drawn;
    drawn[0].scrollIntoView({ behavior: "smooth", block: "center" });
    drawn.forEach(flash);
    setTimeout(recheck, RECHECK_MS);
  };

  const recheck = () => {
    const now = shown(find());
    const replaced = now.filter((el) => !flashed.includes(el));
    if (replaced.length > 0) {
      flashed = now;
      replaced.forEach(flash);
    }
    if (!settled(now) && Date.now() - started < GIVE_UP_MS) setTimeout(recheck, LOOK_EVERY_MS);
  };

  setTimeout(look, FIRST_LOOK_MS);
}

// A node or a link of a map, a cell or a column of a table is small and a short pulse is easy to miss, so it blinks until the
// reviewer moves on: a click or Escape, the next replay, or BLINK_MAX_MS, so that an idle page does not blink forever.
const BLINK_PERIOD_MS = 700; // one way, on to off; a full blink takes twice this
const BLINK_MAX_MS = 60000;
const blinking = new Set<() => void>();

function stopBlinking(): void {
  for (const stop of [...blinking]) stop();
}

// Keeps what blinks on the page until the reader moves on: a click or Escape, the next replay, or BLINK_MAX_MS.
function untilDismissed(cleanup: () => void): void {
  const timer = setTimeout(stop, BLINK_MAX_MS);
  function stop(): void {
    clearTimeout(timer);
    blinking.delete(stop);
    document.removeEventListener("pointerdown", stop, true);
    document.removeEventListener("keydown", onKey, true);
    cleanup();
  }
  function onKey(event: KeyboardEvent): void {
    if (event.key === "Escape") stop();
  }
  blinking.add(stop);
  document.addEventListener("pointerdown", stop, true);
  document.addEventListener("keydown", onKey, true);
}

// Fades from fully on to nearly off and back, easing at both ends, so it reads as a soft pulse and not a flicker.
const BLINK_TIMING: KeyframeAnimationOptions = {
  duration: BLINK_PERIOD_MS,
  iterations: Infinity,
  direction: "alternate",
  easing: "ease-in-out",
};
const FLASH_FILL = "rgba(245, 158, 11, 0.45)";

// Plotly redraws and restyles its marks, so an SVG target is marked with a separate overlay clone, not by restyling it.
function flashSvg(el: SVGElement): void {
  const overlay = el.cloneNode(false) as SVGElement;
  overlay.removeAttribute("class");
  overlay.setAttribute(
    "style",
    `fill:${FLASH_COLOR};fill-opacity:0.35;stroke:${FLASH_COLOR};stroke-width:4;pointer-events:none;filter:drop-shadow(0 0 3px #000)`,
  );
  el.parentNode?.appendChild(overlay);
  const blink = overlay.animate([{ opacity: 1 }, { opacity: 0.12 }], BLINK_TIMING);
  untilDismissed(() => {
    blink.cancel();
    overlay.remove();
  });
}

// A table cell or a column is small too: it blinks with an amber outline and fill, drawn inside it so that the cells around it do
// not cover the outline.
function blinkElement(el: HTMLElement): void {
  const previous = { outline: el.style.outline, outlineOffset: el.style.outlineOffset, background: el.style.backgroundColor };
  el.style.outline = `3px solid ${FLASH_COLOR}`;
  el.style.outlineOffset = "-3px";
  const blink = el.animate(
    [
      { outlineColor: FLASH_COLOR, backgroundColor: FLASH_FILL },
      { outlineColor: "rgba(245, 158, 11, 0.15)", backgroundColor: "rgba(245, 158, 11, 0)" },
    ],
    BLINK_TIMING,
  );
  untilDismissed(() => {
    blink.cancel();
    el.style.outline = previous.outline;
    el.style.outlineOffset = previous.outlineOffset;
    el.style.backgroundColor = previous.background;
  });
}
