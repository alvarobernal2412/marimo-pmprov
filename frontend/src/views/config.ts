interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

function sectionHeading(text: string): HTMLElement {
  const heading = document.createElement("div");
  heading.className = "pw-config-heading";
  heading.textContent = text;
  return heading;
}

// The persona is chosen when the panel is created in Python
// (ProvenancePanel(mode=...)), not switchable from the UI: it decides which
// tools exist (annotate/edit/delete vs. replay), so readers can't escalate.
// View preferences, like the Tree tab, are fair game for the reader.
export function renderConfig(container: HTMLElement, model: AnyModel): void {
  container.innerHTML = "";

  container.appendChild(sectionHeading("Persona"));
  const value = document.createElement("div");
  value.className = "pw-config-persona";
  value.textContent = String(model.get("mode"));
  container.appendChild(value);

  const hint = document.createElement("div");
  hint.className = "pw-tree-caption";
  hint.textContent = "Set when the panel was created: ProvenancePanel(mode=\"student\" | \"reviewer\").";
  container.appendChild(hint);

  container.appendChild(sectionHeading("View"));
  const label = document.createElement("label");
  label.className = "pw-config-radio";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = Boolean(model.get("show_tree"));
  input.addEventListener("change", () => {
    model.set("show_tree", input.checked);
    model.save_changes();
  });
  label.appendChild(input);
  const text = document.createElement("span");
  text.textContent = "Show Tree tab";
  label.appendChild(text);
  container.appendChild(label);
}
