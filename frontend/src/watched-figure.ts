// A figure whose nodes the analyst can drag (see arrangement.py) is drawn again by the notebook after a drag, as a new artifact: the
// drag is recorded as a step and the figure comes back with the nodes where they were dragged to. Between the drag and that, the
// page already shows the new arrangement while the artifact on the page is still the old one, and the notebook may be busy with
// something else (the picture of the last figure, an export), which makes this last seconds. An annotation added in between would
// be attached to the figure as it was. So:
// - the watcher marks such a figure as pending (`data-pw-pending` on its frame) until it has been drawn again;
// - a picked selection remembers the figure it was picked in, and `currentSelection` gives the artifact that figure is now;
// - the composer waits with adding an annotation until nothing is pending (`whenRecorded`).
import { readSnapshot } from "./picker";

export interface Selection {
  artifactId?: string;
  artifactName?: string;
  granularity?: string;
  detail?: string | null;
  snapshot?: unknown;
  figure?: string | null; // the id of the watched figure it was picked in (`data-pw-arrangement`)
  [key: string]: unknown;
}

function deepAll(root: ParentNode, selector: string, out: HTMLElement[] = []): HTMLElement[] {
  out.push(...Array.from(root.querySelectorAll<HTMLElement>(selector)));
  for (const element of Array.from(root.querySelectorAll<HTMLElement>("*"))) {
    if (element.shadowRoot) deepAll(element.shadowRoot, selector, out);
  }
  return out;
}

interface FigureNow {
  pending: boolean;
  tagged: HTMLElement | null; // the artifact the figure is on the page now
  pictured: boolean; // whether a picture of it is made for the page (false: the report draws it from the recorded step)
}

/** What a watched figure is on the page now; null when it is not there. */
export function figureNow(figureId: string, page: ParentNode = document): FigureNow | null {
  const frame = deepAll(page, "[data-pw-arrangement]").find((e) => e.dataset.pwArrangement === figureId);
  if (!frame) return null;
  const tagged = deepAll(frame, "[data-pw-artifact-id]")[0] ?? null;
  return { pending: frame.dataset.pwPending === "1", tagged, pictured: frame.dataset.pwUnpictured !== "1" };
}

/** Whether a figure on the page was dragged and has not been drawn again yet. */
export function anyPending(page: ParentNode = document): boolean {
  return deepAll(page, "[data-pw-pending]").some((e) => e.dataset.pwPending === "1");
}

/**
 * `selection` as it is now: one picked in a watched figure names the artifact that figure has become (after a drag it was drawn
 * again as another artifact, with its own picture), and keeps what was picked in it (a node, a link). Anything else is unchanged.
 */
export function currentSelection(selection: Selection, now: FigureNow | null, snapshot: (element: HTMLElement) => unknown = readSnapshot): Selection {
  const tagged = now?.tagged;
  const id = tagged?.dataset.pwArtifactId;
  if (!selection.artifactId || !selection.figure || !tagged || !id || id === selection.artifactId) return selection;
  return {
    ...selection,
    artifactId: id,
    artifactName: tagged.dataset.pwArtifactName ?? selection.artifactName,
    snapshot: snapshot(tagged) ?? null,
  };
}

export const RECORDING_WAIT_MS = 120_000; // a notebook that never draws the figure again must not hold an annotation for ever
export const PICTURE_WAIT_MS = 15_000; // the picture of a figure is made after it is shown; without one the report draws the step

/**
 * Call `done` once the notebook has recorded what the page shows: no figure is pending, the selection's figure (if any) is on the
 * page as an artifact the panel knows (`known`), and its picture is there (waited for a shorter while: it may never come). Calls it
 * at once when there is nothing to wait for. `waiting` is told when it has to wait. Gives up after RECORDING_WAIT_MS and calls
 * `done` anyway. Returns a function that cancels it.
 */
export function whenRecorded(
  selection: () => Selection,
  known: (artifactId: string) => boolean,
  done: () => void,
  waiting?: () => void,
  everyMs = 250,
): () => void {
  const started = Date.now();
  let settledAt = 0;
  const ready = (): boolean => {
    const elapsed = Date.now() - started;
    if (elapsed > RECORDING_WAIT_MS) return true;
    if (anyPending()) return false;
    const picked = selection();
    if (!picked.figure) return true;
    const now = figureNow(picked.figure);
    const id = now?.tagged?.dataset.pwArtifactId;
    if (!now || !id || id === picked.artifactId) return true; // not drawn again: what was picked is what is shown
    if (!known(id)) return false;
    if (!now.pictured) return true; // no picture is made for the page: nothing more to wait for
    settledAt ||= Date.now();
    return readSnapshot(now.tagged as HTMLElement) !== null || Date.now() - settledAt > PICTURE_WAIT_MS;
  };
  if (ready()) {
    done();
    return () => {};
  }
  waiting?.();
  const timer = window.setInterval(() => {
    if (!ready()) return;
    window.clearInterval(timer);
    done();
  }, everyMs);
  return () => window.clearInterval(timer);
}
