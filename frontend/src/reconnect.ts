// What the analyst writes in the page reaches the notebook as an update of the widget's state, sent when it is written. While
// the browser is offline that send fails and marimo does not repeat it: the annotation stays on the page but never reaches the
// notebook, so it is lost on a reload. Once the browser is back online the page sends what it holds again. Sending a list the
// notebook already has changes nothing there.

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

const WRITTEN_BY_THE_ANALYST = ["commits", "removed_annotations", "edited_annotations"];
const AGAIN_AFTER_MS = [0, 3000, 10000]; // the network is not always usable the moment the browser says it is back
const armed = new WeakSet<object>();

export function sendAgain(model: AnyModel): void {
  for (const key of WRITTEN_BY_THE_ANALYST) {
    const value = model.get(key);
    if (value === undefined || value === null) continue;
    model.set(key, Array.isArray(value) ? [...value] : { ...(value as object) });
  }
  model.save_changes();
}

export function sendAgainWhenBackOnline(model: AnyModel): void {
  if (armed.has(model)) return;
  armed.add(model);
  window.addEventListener("online", () => AGAIN_AFTER_MS.forEach((delay) => setTimeout(() => sendAgain(model), delay)));
}
