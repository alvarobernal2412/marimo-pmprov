interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

const PERSONAS = ["student", "reviewer"] as const;

export function renderConfig(container: HTMLElement, model: AnyModel): void {
  container.innerHTML = "";

  const heading = document.createElement("div");
  heading.className = "pw-config-heading";
  heading.textContent = "Persona";
  container.appendChild(heading);

  const mode = model.get("mode") as string;
  PERSONAS.forEach((persona) => {
    const label = document.createElement("label");
    label.className = "pw-config-radio";

    const input = document.createElement("input");
    input.type = "radio";
    input.name = "pw-persona";
    input.value = persona;
    input.checked = mode === persona;
    input.addEventListener("change", () => {
      model.set("mode", persona);
      model.save_changes();
    });
    label.appendChild(input);

    const text = document.createElement("span");
    text.textContent = persona;
    label.appendChild(text);

    container.appendChild(label);
  });
}
