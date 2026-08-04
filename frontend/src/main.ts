import "./theme.css";
import { segmentedControl } from "./components/segmented-control";
import { renderCurated } from "./views/curated";
import { renderTree } from "./views/tree";
import { renderConfig } from "./views/config";
import { armPicker } from "./picker";
import { armGutterAffordance } from "./gutter";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
  on(event: string, callback: () => void): void;
}

function render({ model, el }: { model: AnyModel; el: HTMLElement }): void {
  (el as HTMLElement & { _pwTreePortal?: HTMLElement })._pwTreePortal?.remove();
  el.innerHTML = "";
  const root = document.createElement("div");
  root.className = "pw-root";
  el.appendChild(root);

  const content = document.createElement("div");
  content.className = "pw-content";
  root.appendChild(content);

  const tabs = document.createElement("div");
  content.appendChild(tabs);

  const restoreBanner = document.createElement("div");
  restoreBanner.className = "pw-restore-banner";
  restoreBanner.style.display = "none";
  content.appendChild(restoreBanner);

  const body = document.createElement("div");
  body.className = "pw-body";
  content.appendChild(body);

  // marimo's sidebar collapse just shrinks the host width — it doesn't
  // unmount our content — so watch our own width and hide ourselves once
  // there's no usable space, instead of leaving clipped text visible.
  const COLLAPSE_WIDTH_PX = 80;
  const collapseObserver = new ResizeObserver((entries) => {
    const width = entries[0]?.contentRect.width ?? root.clientWidth;
    root.classList.toggle("pw-collapsed", width < COLLAPSE_WIDTH_PX);
    // Collapsing/expanding the sidebar changes root's own width but fires no
    // window "resize" event, so the tree portal's left offset (anchored to
    // root's right edge) would otherwise go stale and leave a dead gap.
    if (treePortal.style.display !== "none") positionTreePortal();
  });
  collapseObserver.observe(root);

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
      segmentedControl(["curated", "tree", "config"], activeTab, (value) => {
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

  // The tree is a multi-column DAG — it needs landscape space the docked
  // sidebar can't offer, so it renders into a wide overlay anchored to the
  // sidebar's right edge instead of the narrow inline body.
  const treePortal = document.createElement("div");
  treePortal.className = "pw-tree-portal";
  // anywidget scopes our stylesheet to its shadow root, which this portal
  // (deliberately mounted on document.body, outside that root) can't see —
  // so its layout has to be set inline rather than via theme.css.
  Object.assign(treePortal.style, {
    display: "none",
    position: "fixed",
    top: "0",
    right: "0",
    bottom: "0",
    zIndex: "900",
    background: matchMedia("(prefers-color-scheme: dark)").matches ? "#0F172A" : "#F8FAFC",
    color: matchMedia("(prefers-color-scheme: dark)").matches ? "#F8FAFC" : "#0F172A",
    borderLeft: `1px solid ${matchMedia("(prefers-color-scheme: dark)").matches ? "#334155" : "#E2E8F0"}`,
    padding: "16px 24px",
    // The tree column area scrolls internally (see treeContent below) so the
    // inspect pane can stay pinned at the bottom instead of scrolling away.
    overflow: "hidden",
    fontFamily: "ui-sans-serif, system-ui, sans-serif",
  });
  // Our full stylesheet (theme.css) is injected by anywidget into el's shadow
  // root and doesn't cascade out to document.body, so clone it into a
  // dedicated child that survives renderTree()'s `container.innerHTML = ""`
  // (renderTree treats the portal as its own container, styles included).
  const treePortalStyles = document.createElement("div");
  const shadowRoot = el.getRootNode();
  if (shadowRoot instanceof ShadowRoot) {
    // anywidget applies our CSS via adoptedStyleSheets (constructable
    // stylesheets), not <style> tags, so it has to be re-serialized as text.
    shadowRoot.adoptedStyleSheets.forEach((sheet) => {
      const styleTag = document.createElement("style");
      styleTag.textContent = [...sheet.cssRules].map((rule) => rule.cssText).join("\n");
      treePortalStyles.appendChild(styleTag);
    });
    shadowRoot.querySelectorAll("style").forEach((styleTag) => {
      treePortalStyles.appendChild(styleTag.cloneNode(true));
    });
  }
  treePortal.appendChild(treePortalStyles);
  const treeContent = document.createElement("div");
  Object.assign(treeContent.style, {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    minHeight: "0",
  });
  treePortal.appendChild(treeContent);
  document.body.appendChild(treePortal);
  (el as HTMLElement & { _pwTreePortal?: HTMLElement })._pwTreePortal = treePortal;

  function positionTreePortal(): void {
    const rect = root.getBoundingClientRect();
    treePortal.style.left = `${rect.right}px`;
  }

  function renderBody(): void {
    const activeTab = model.get("active_tab") as string;
    body.innerHTML = "";
    // marimo mounts a docked-desktop and a drawer-mobile copy of this widget
    // simultaneously and toggles which one is visible via CSS breakpoints —
    // only the one currently laid out (offsetParent set) should own the portal.
    if (activeTab === "tree" && el.offsetParent !== null) {
      positionTreePortal();
      treePortal.style.display = "block";
      renderTree(treeContent, model);
      return;
    }
    treePortal.style.display = "none";
    treeContent.innerHTML = "";

    const view = document.createElement("div");
    body.appendChild(view);
    if (activeTab === "config") {
      renderConfig(view, model);
      return;
    }
    renderCurated(view, model);
    if (model.get("mode") === "student") body.appendChild(pickerRow);
  }

  window.addEventListener("resize", () => {
    if (treePortal.style.display !== "none") positionTreePortal();
  });

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
