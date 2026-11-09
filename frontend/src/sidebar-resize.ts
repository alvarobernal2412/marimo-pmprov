// marimo's sidebar opens and collapses but has a fixed width. When the panel is in the sidebar, this puts a thin handle on the
// sidebar's right edge: hovering it shows the resize cursor and a line, dragging it changes the width, double-clicking it goes back
// to marimo's width. The chosen width is remembered in the browser.
//
// The sidebar (an <aside>) belongs to marimo and lives outside the widget's shadow root, so the handle is styled inline.

const MIN_WIDTH_PX = 220;
const MAX_SHARE_OF_WINDOW = 0.7;
const COLLAPSED_BELOW_PX = 80; // marimo collapses the sidebar by shrinking it; leave that alone
const STORAGE_KEY = "pmprov-sidebar-width";
const LINE = "#0EA5E9";

function sidebarAround(el: Element): HTMLElement | null {
  for (let node: Node | null = el; node; node = node.parentNode instanceof ShadowRoot ? node.parentNode.host : node.parentNode) {
    if (node instanceof HTMLElement && node.localName === "aside") return node;
  }
  return null;
}

function remembered(): number | null {
  try {
    const value = Number(localStorage.getItem(STORAGE_KEY));
    return Number.isFinite(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

function remember(width: number | null): void {
  try {
    if (width === null) localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, String(Math.round(width)));
  } catch {
    // a browser that does not allow storage just forgets the width
  }
}

const armed = new WeakSet<HTMLElement>();

export function armSidebarResize(root: HTMLElement): void {
  const aside = sidebarAround(root);
  if (!aside || armed.has(aside)) return;
  armed.add(aside);

  const marimoWidth = aside.getBoundingClientRect().width; // what double-click goes back to
  const limit = (width: number): number => Math.min(Math.max(width, MIN_WIDTH_PX), window.innerWidth * MAX_SHARE_OF_WINDOW);
  let chosen = remembered();
  let writing = false;

  const apply = (width: number): void => {
    writing = true;
    aside.style.width = `${Math.round(width)}px`;
    queueMicrotask(() => (writing = false));
  };

  if (getComputedStyle(aside).position === "static") aside.style.position = "relative";
  const handle = document.createElement("div");
  handle.setAttribute("role", "separator");
  handle.setAttribute("aria-orientation", "vertical");
  handle.setAttribute("aria-label", "Resize the sidebar");
  handle.title = "Drag to resize the sidebar; double-click to reset";
  Object.assign(handle.style, {
    position: "absolute",
    top: "0",
    bottom: "0",
    right: "-4px",
    width: "9px",
    cursor: "col-resize",
    zIndex: "60",
    touchAction: "none",
    background: "transparent",
    transition: "background 120ms",
  });
  const paint = (on: boolean): void => {
    handle.style.background = on ? `linear-gradient(to right, transparent 3px, ${LINE} 3px, ${LINE} 6px, transparent 6px)` : "transparent";
  };
  handle.addEventListener("pointerenter", () => paint(true));
  handle.addEventListener("pointerleave", () => {
    if (dragging === null) paint(false);
  });

  let dragging: number | null = null;
  handle.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    dragging = event.pointerId;
    handle.setPointerCapture(event.pointerId);
    document.body.style.userSelect = "none";
    aside.style.transition = "none"; // the sidebar follows the pointer, not marimo's width animation
    event.preventDefault();
  });
  handle.addEventListener("pointermove", (event) => {
    if (dragging !== event.pointerId) return;
    chosen = limit(event.clientX - aside.getBoundingClientRect().left);
    apply(chosen);
  });
  const stop = (event: PointerEvent): void => {
    if (dragging !== event.pointerId) return;
    dragging = null;
    document.body.style.userSelect = "";
    aside.style.transition = "";
    if (chosen !== null) remember(chosen);
    paint(false);
  };
  handle.addEventListener("pointerup", stop);
  handle.addEventListener("pointercancel", stop);
  handle.addEventListener("dblclick", () => {
    chosen = null;
    remember(null);
    apply(marimoWidth);
  });
  aside.appendChild(handle);

  if (chosen !== null) apply(limit(chosen));

  // Collapsing and opening the sidebar makes marimo set its own width again (the box animates, so what marimo asked for is read from
  // the style, not from the box). Once it asks for an open width, the chosen width goes back on.
  new MutationObserver(() => {
    if (writing || chosen === null) return;
    const asked = parseFloat(aside.style.width);
    if (asked >= COLLAPSED_BELOW_PX && Math.abs(asked - limit(chosen)) > 1) apply(limit(chosen));
  }).observe(aside, { attributes: true, attributeFilter: ["style"] });

  window.addEventListener("resize", () => {
    if (chosen !== null && parseFloat(aside.style.width) >= COLLAPSED_BELOW_PX) apply(limit(chosen));
  });
}
