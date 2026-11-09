// While a reviewer steps through an analysis the notebook redraws its tables and maps, which can take seconds, and a step may draw
// nothing at all. This keeps a small status for the player: "working" from the moment the reviewer moves until the notebook has
// finished redrawing, then whether the step drew a table or a map of its own.
//
// How it knows: the kernel handles messages one after another, and a move of the cursor redraws the notebook inside the message
// that carries it. So the player sends a second message, a ping, right behind the move; the kernel answers it (`replay_pong`) only
// once the redraw is over. The page is given a moment to show what arrived, and then the step is done.

import { findProducedBy } from "./highlight";

interface StatusModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
  on?(event: string, callback: () => void): void; // the anywidget model has it; a stand-in without it just never hears the pong
}

export interface ReplayStatus {
  phase: "idle" | "working" | "done";
  stateId?: string;
  visual?: boolean; // done: the step drew a table or a map of its own
}

const MIN_WORKING_MS = 600; // long enough to be seen
const SHOW_RESULT_MS = 450; // after the kernel is done, the page needs a moment to draw what arrived
const GIVE_UP_MS = 30000; // a kernel that never answers (an older notebook, a lost connection)

const statuses = new WeakMap<object, ReplayStatus>();
const listeners = new WeakMap<object, Set<(status: ReplayStatus) => void>>();
const waiting = new WeakMap<object, { token: string; finish: () => void }>();
let counter = 0;

export function replayStatus(model: object): ReplayStatus {
  return statuses.get(model) ?? { phase: "idle" };
}

export function onReplayStatus(model: object, listener: (status: ReplayStatus) => void): () => void {
  const set = listeners.get(model) ?? new Set();
  listeners.set(model, set);
  set.add(listener);
  return () => set.delete(listener);
}

function publish(model: object, status: ReplayStatus): void {
  statuses.set(model, status);
  listeners.get(model)?.forEach((listener) => listener(status));
}

const hooked = new WeakSet<object>();
function hook(model: StatusModel): void {
  if (hooked.has(model)) return;
  hooked.add(model);
  model.on?.("change:replay_pong", () => {
    const pong = (model.get("replay_pong") as { token?: string }) ?? {};
    const pending = waiting.get(model);
    if (pending && pong.token === pending.token) pending.finish();
  });
}

export function startReplayStatus(model: StatusModel, stateId: string, initial = false): void {
  hook(model);
  const token = `${Date.now()}-${++counter}`;
  const started = Date.now();
  let finished = false;
  const finish = (): void => {
    if (finished) return;
    finished = true;
    clearTimeout(giveUp);
    const wait = Math.max(MIN_WORKING_MS - (Date.now() - started), 0) + SHOW_RESULT_MS;
    setTimeout(() => {
      if (waiting.get(model)?.token !== token) return; // the reviewer has moved on again
      waiting.delete(model);
      publish(model, { phase: "done", stateId, visual: !initial && findProducedBy(stateId).length > 0 });
    }, wait);
  };
  const giveUp = setTimeout(finish, GIVE_UP_MS);
  waiting.set(model, { token, finish });
  publish(model, { phase: "working", stateId });
  // the ping goes in its own message, behind the one that moved the cursor
  model.set("replay_ping", { token });
  model.save_changes();
}
