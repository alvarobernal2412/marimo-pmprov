import type { ProvenanceTreeJson } from "../types";
import { cursorStateId, latestStateId, moveCursor, nextChoices, pathTo } from "../replay";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

function button(label: string, title: string, disabled: boolean, onClick: () => void): HTMLButtonElement {
  const btn = document.createElement("button");
  btn.className = "pw-replay-btn";
  btn.textContent = label;
  btn.title = title;
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
  const node = tree.nodes[cursor];
  const latest = latestStateId(tree);
  const choices = nextChoices(model, tree, cursor);
  const go = (id: string): void => moveCursor(model, tree, id);

  // Step numbers follow the branch being walked (root -> here -> onward along
  // the preferred child), so Back/Next always change the number by exactly 1.
  const stepNumber = pathTo(tree, cursor).length;
  let stepTotal = stepNumber;
  for (let ahead = nextChoices(model, tree, cursor)[0]; ahead; ahead = nextChoices(model, tree, ahead.stateId)[0]) {
    stepTotal += 1;
  }

  const heading = document.createElement("div");
  heading.className = "pw-replay-heading";
  const step = document.createElement("span");
  step.textContent = `Step ${stepNumber} of ${stepTotal}`;
  heading.appendChild(step);
  if (cursor === latest) {
    const live = document.createElement("span");
    live.className = "pw-replay-latest";
    live.textContent = "latest";
    heading.appendChild(live);
  }
  bar.appendChild(heading);

  const controls = document.createElement("div");
  controls.className = "pw-replay-controls";
  controls.appendChild(button("First", "Jump to the first state", cursor === tree.rootId, () => go(tree.rootId)));
  controls.appendChild(
    button("‹ Back", "Step back to the previous state", !node.parentStateId, () => go(node.parentStateId!)),
  );
  controls.appendChild(
    button("Next ›", "Step forward to the next state", choices.length === 0, () => go(choices[0].stateId)),
  );
  controls.appendChild(button("Latest", "Jump to the latest state", cursor === latest, () => go(latest!)));
  bar.appendChild(controls);
  bar.addEventListener("keydown", (evt) => {
    if (evt.key === "ArrowLeft" && node.parentStateId) go(node.parentStateId);
    else if (evt.key === "ArrowRight" && choices.length > 0) go(choices[0].stateId);
    else return;
    evt.preventDefault();
  });

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

  if (cursor !== latest) {
    const note = document.createElement("div");
    note.className = "pw-replay-note";
    note.textContent = "Viewing an earlier step. Notebook outputs still show the latest run.";
    bar.appendChild(note);
  }
}
