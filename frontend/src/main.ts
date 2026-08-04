import "./theme.css";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
  on(event: string, callback: () => void): void;
}

function render({ model, el }: { model: AnyModel; el: HTMLElement }): void {
  const root = document.createElement("div");
  root.className = "pw-root";
  root.textContent = "provenance widget loading...";
  el.appendChild(root);
}

export default { render };
