interface AnyModel {
  get(key: string): unknown;
}

// The persona is chosen when the panel is created in Python
// (ProvenancePanel(mode=...)), not switchable from the UI: it decides which
// tools exist (annotate/edit/delete vs. replay), so readers can't escalate.
export function renderConfig(container: HTMLElement, model: AnyModel): void {
  container.innerHTML = "";

  const heading = document.createElement("div");
  heading.className = "pw-config-heading";
  heading.textContent = "Persona";
  container.appendChild(heading);

  const value = document.createElement("div");
  value.className = "pw-config-persona";
  value.textContent = String(model.get("mode"));
  container.appendChild(value);

  const hint = document.createElement("div");
  hint.className = "pw-tree-caption";
  hint.textContent = "Set when the panel was created: ProvenancePanel(mode=\"student\" | \"reviewer\").";
  container.appendChild(hint);
}
