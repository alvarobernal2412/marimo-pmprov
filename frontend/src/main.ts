import "./theme.css";
import { segmentedControl } from "./components/segmented-control";
import { renderCurated } from "./views/curated";
import { renderTree } from "./views/tree";
import { renderInspect } from "./views/inspect";
import { armPicker } from "./picker";
import { armGutterAffordance } from "./gutter";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
  on(event: string, callback: () => void): void;
}

function render({ model, el }: { model: AnyModel; el: HTMLElement }): void {
  el.innerHTML = "";
  const root = document.createElement("div");
  root.className = "pw-root";
  el.appendChild(root);

  const tabs = document.createElement("div");
  root.appendChild(tabs);

  const restoreBanner = document.createElement("div");
  restoreBanner.className = "pw-restore-banner";
  restoreBanner.style.display = "none";
  root.appendChild(restoreBanner);

  const body = document.createElement("div");
  body.className = "pw-body";
  root.appendChild(body);

  const pickerRow = document.createElement("div");
  pickerRow.className = "pw-picker-row";
  const pickBtn = document.createElement("button");
  pickBtn.className = "pw-pick-btn";
  pickBtn.textContent = "Pick from notebook";
  let armed = false;
  function resetPickBtn(): void {
    armed = false;
    pickBtn.classList.remove("pw-pick-btn-armed");
    pickBtn.textContent = "Pick from notebook";
    document.body.classList.remove("pw-picking-active");
  }
  pickBtn.addEventListener("click", () => {
    if (armed) return;
    armed = true;
    pickBtn.classList.add("pw-pick-btn-armed");
    pickBtn.textContent = "Picking… (Esc to cancel)";
    document.body.classList.add("pw-picking-active");
    armPicker(
      model,
      (selection) => {
        resetPickBtn();
        const current = (model.get("selection") as Record<string, unknown>) ?? {};
        model.set("selection", { ...current, artifact: selection });
        model.save_changes();
        renderBody();
      },
      () => {
        resetPickBtn();
      },
    );
  });
  pickerRow.appendChild(pickBtn);

  function renderTabs(): void {
    tabs.innerHTML = "";
    const activeTab = model.get("active_tab") as string;
    tabs.appendChild(
      segmentedControl(["curated", "tree", "inspect"], activeTab, (value) => {
        model.set("active_tab", value);
        model.save_changes();
      }),
    );
  }

  function renderRestoreBanner(): void {
    const request = model.get("restore_request") as { tag?: string };
    if (model.get("mode") === "reviewer" && request && request.tag) {
      restoreBanner.style.display = "block";
      restoreBanner.textContent = `Restoring parameters to @${request.tag} — dependent marimo cells will re-run reactively.`;
    } else {
      restoreBanner.style.display = "none";
    }
  }

  function renderBody(): void {
    const activeTab = model.get("active_tab") as string;
    body.innerHTML = "";
    const view = document.createElement("div");
    body.appendChild(view);
    if (activeTab === "curated") {
      renderCurated(view, model);
      if (model.get("mode") === "student") body.appendChild(pickerRow);
    } else if (activeTab === "tree") {
      renderTree(view, model);
    } else {
      renderInspect(view, model);
    }
  }

  renderTabs();
  renderRestoreBanner();
  renderBody();

  model.on("change:active_tab", () => {
    renderTabs();
    renderBody();
  });
  model.on("change:mode", () => {
    renderBody();
    renderRestoreBanner();
  });
  model.on("change:tree", renderBody);
  model.on("change:commits", renderBody);
  model.on("change:restore_request", renderRestoreBanner);

  armGutterAffordance(model, (selection) => {
    if (model.get("active_tab") !== "curated") {
      model.set("active_tab", "curated");
    }
    const current = (model.get("selection") as Record<string, unknown>) ?? {};
    model.set("selection", { ...current, artifact: selection });
    model.save_changes();
    renderTabs();
    renderBody();
    body.querySelector<HTMLTextAreaElement>(".pw-composer textarea")?.focus();
  });
}

export default { render };
