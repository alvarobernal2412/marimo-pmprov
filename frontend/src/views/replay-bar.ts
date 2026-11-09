import type { ProvenanceTreeJson } from "../types";
import { icon } from "../components/icons";
import { cursorStateId, isInitial, latestStateId, moveCursor, moveToInitial, nextChoices, pathTo } from "../replay";
import { onReplayStatus, replayStatus, type ReplayStatus } from "../replay-status";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

// Icon-only transport button: the glyph is decorative, the label is the
// tooltip and what screen readers announce.
function button(
  glyph: "skipBack" | "stepBack" | "stepForward" | "skipForward",
  label: string,
  disabled: boolean,
  onClick: () => void,
): HTMLButtonElement {
  const btn = document.createElement("button");
  btn.className = "pw-replay-btn";
  btn.appendChild(icon(glyph, 16));
  btn.title = label;
  btn.setAttribute("aria-label", label);
  btn.disabled = disabled;
  btn.addEventListener("click", onClick);
  return btn;
}

// Debugger-style stepper for the reviewer persona: walk the analysis one
// recorded state at a time (Back/Next along the tree, branch choice where it
// forks), jump to the first or the latest state, and see what each step did.
export function renderReplayBar(container: HTMLElement, model: AnyModel): void {
  const tree = model.get("tree") as ProvenanceTreeJson;
  const bar = document.createElement("div");
  bar.className = "pw-replay-bar";
  bar.tabIndex = 0;
  bar.setAttribute("role", "group");
  bar.setAttribute("aria-label", "Analysis replay. Left and right arrow keys step back and forward.");
  container.appendChild(bar);

  const cursor = cursorStateId(model, tree);
  if (!cursor) {
    bar.classList.add("pw-replay-bar-empty");
    bar.textContent = "Nothing to replay yet — no analysis states recorded.";
    return;
  }
  const initial = isInitial(cursor);
  const node = initial ? undefined : tree.nodes[cursor];
  const latest = latestStateId(tree);
  // before the first step the only way on is the first state
  const choices = initial ? [tree.nodes[tree.rootId]].filter(Boolean) : nextChoices(model, tree, cursor);
  const go = (id: string): void => moveCursor(model, tree, id);
  // Back from the first state goes to the one before it, where nothing has been computed yet
  const back = (): void => (node?.parentStateId ? go(node.parentStateId) : moveToInitial(model));

  // Step numbers follow the branch being walked (root -> here -> onward along
  // the preferred child), so Back/Next always change the number by exactly 1.
  // Step 0 is the initial state; step 1 is the state the first recorded step made.
  const stepNumber = initial ? 0 : pathTo(tree, cursor).length;
  let stepTotal = Math.max(stepNumber, 1);
  const start = initial ? tree.rootId : cursor;
  for (let ahead = nextChoices(model, tree, start)[0]; ahead; ahead = nextChoices(model, tree, ahead.stateId)[0]) {
    stepTotal += 1;
  }

  const heading = document.createElement("div");
  heading.className = "pw-replay-heading";
  const step = document.createElement("span");
  step.textContent = `Step ${stepNumber} of ${stepTotal}`;
  heading.appendChild(step);
  if (initial) {
    const first = document.createElement("span");
    first.className = "pw-replay-start";
    first.textContent = "start";
    heading.appendChild(first);
  } else if (cursor === latest) {
    const live = document.createElement("span");
    live.className = "pw-replay-latest";
    live.textContent = "latest";
    heading.appendChild(live);
  }
  bar.appendChild(heading);

  const controls = document.createElement("div");
  controls.className = "pw-replay-controls";
  controls.appendChild(button("skipBack", "Start: before the first step", initial, () => moveToInitial(model)));
  controls.appendChild(button("stepBack", "Back one step", initial, back));
  controls.appendChild(
    button("stepForward", "Next step", choices.length === 0, () => go(choices[0].stateId)),
  );
  controls.appendChild(button("skipForward", "Latest state", cursor === latest, () => go(latest!)));
  bar.appendChild(controls);
  bar.addEventListener("keydown", (evt) => {
    if (evt.key === "ArrowLeft" && !initial) back();
    else if (evt.key === "ArrowRight" && choices.length > 0) go(choices[0].stateId);
    else return;
    evt.preventDefault();
  });

  // While the notebook catches up with the step, and when it has: a step that draws nothing says so.
  if (model.get("outputs_follow_cursor")) bar.appendChild(statusLine(model, cursor, stepNumber));

  if (choices.length > 1) {
    const fork = document.createElement("div");
    fork.className = "pw-replay-fork";
    fork.appendChild(document.createTextNode("Branches ahead: "));
    choices.forEach((child) => {
      const chip = document.createElement("button");
      chip.className = "pw-filter-chip";
      chip.textContent = child.operation.name;
      chip.addEventListener("click", () => go(child.stateId));
      fork.appendChild(chip);
    });
    bar.appendChild(fork);
  }

  const detail = document.createElement("div");
  detail.className = "pw-replay-detail";
  if (!node) {
    const title = document.createElement("div");
    title.className = "pw-node-title";
    title.textContent = "Initial state";
    detail.appendChild(title);
    const nothing = document.createElement("div");
    nothing.className = "pw-replay-delta";
    nothing.textContent = "Nothing has been computed yet. Press Next to see what step 1 made.";
    detail.appendChild(nothing);
    bar.appendChild(detail);
    return;
  }
  const name = document.createElement("div");
  name.className = "pw-node-title";
  name.textContent = node.operation.name;
  detail.appendChild(name);
  const delta = document.createElement("div");
  delta.className = "pw-replay-delta";
  delta.textContent = node.delta.summary;
  detail.appendChild(delta);
  const params = Object.entries(node.params);
  if (params.length > 0) {
    const paramLine = document.createElement("div");
    paramLine.className = "pw-replay-params";
    paramLine.textContent = params.map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ");
    detail.appendChild(paramLine);
  }
  const count = document.createElement("div");
  count.className = "pw-replay-delta";
  count.textContent = `${node.annotations.length} annotation${node.annotations.length === 1 ? "" : "s"} on this state`;
  detail.appendChild(count);
  bar.appendChild(detail);

  // A notebook whose cells follow the cursor (reactive_cursor) redraws its outputs for the step; only one that does
  // not keeps showing the latest run.
  if (cursor !== latest && !model.get("outputs_follow_cursor")) {
    const note = document.createElement("div");
    note.className = "pw-replay-note";
    note.textContent = "Viewing an earlier step. Notebook outputs still show the latest run.";
    bar.appendChild(note);
  }
}

// "Rebuilding the notebook for step N" with a spinner while the page catches up; afterwards, for a step that drew no table or map of
// its own, a line that says so, so that a quiet step does not look like a stuck one. The line follows the status as it changes.
function statusLine(model: AnyModel, cursor: string, stepNumber: number): HTMLElement {
  const line = document.createElement("div");
  line.className = "pw-replay-status";
  line.setAttribute("role", "status");
  line.setAttribute("aria-live", "polite");
  const paint = (status: ReplayStatus): void => {
    line.replaceChildren();
    line.classList.remove("pw-replay-status-quiet");
    line.hidden = true;
    if (status.stateId !== cursor) return;
    if (status.phase === "working") {
      const spinner = document.createElement("span");
      spinner.className = "pw-spinner";
      spinner.setAttribute("aria-hidden", "true");
      const words = stepNumber === 0 ? "Going back to the start…" : `Rebuilding the notebook for step ${stepNumber}…`;
      line.append(spinner, document.createTextNode(words));
      line.hidden = false;
    } else if (status.phase === "done" && !status.visual && !isInitial(cursor)) {
      line.classList.add("pw-replay-status-quiet");
      line.textContent = "This step draws no table or map of its own; the page shows what the steps before it made.";
      line.hidden = false;
    }
  };
  paint(replayStatus(model));
  const stop = onReplayStatus(model, (status) => {
    if (!line.isConnected) return stop(); // the bar was drawn again
    paint(status);
  });
  return line;
}
