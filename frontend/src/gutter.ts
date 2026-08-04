interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

interface PickedSelection {
  artifactId: string;
  artifactName: string;
  granularity: string;
  detail: string | null;
}

function findTaggedAncestor(el: EventTarget | null): HTMLElement | null {
  let node = el as HTMLElement | null;
  while (node) {
    if (node.dataset && node.dataset.pwArtifactId) return node;
    node = node.parentElement;
  }
  return null;
}

export function armGutterAffordance(
  model: AnyModel,
  onPick: (selection: PickedSelection) => void,
): void {
  let button: HTMLButtonElement | null = null;
  let currentTarget: HTMLElement | null = null;

  function ensureButton(): HTMLButtonElement {
    if (button) return button;
    button = document.createElement("button");
    button.className = "pw-gutter-plus";
    button.textContent = "+";
    button.style.position = "fixed";
    button.style.display = "none";
    button.addEventListener("click", (evt) => {
      evt.preventDefault();
      evt.stopPropagation();
      if (!currentTarget) return;
      const granularity = currentTarget.dataset.pwGranularity ?? "dataset";
      const detail = currentTarget.dataset.pwDetail ?? null;
      onPick({
        artifactId: currentTarget.dataset.pwArtifactId!,
        artifactName: currentTarget.dataset.pwArtifactName ?? "",
        granularity,
        detail,
      });
      hideButton();
    });
    document.body.appendChild(button);
    return button;
  }

  function hideButton(): void {
    if (button) button.style.display = "none";
    currentTarget = null;
  }

  function showButtonFor(target: HTMLElement): void {
    const btn = ensureButton();
    currentTarget = target;
    const rect = target.getBoundingClientRect();
    btn.style.display = "block";
    btn.style.top = `${rect.top}px`;
    btn.style.left = `${rect.right - 20}px`;
  }

  document.addEventListener("mouseover", (evt: MouseEvent) => {
    if (model.get("mode") !== "student") {
      hideButton();
      return;
    }
    const target = findTaggedAncestor(evt.target);
    if (target) {
      showButtonFor(target);
    }
  });

  document.addEventListener("mouseout", (evt: MouseEvent) => {
    if (!currentTarget) return;
    const related = evt.relatedTarget as HTMLElement | null;
    if (related && (currentTarget.contains(related) || related === button || button?.contains(related))) {
      return;
    }
    const target = findTaggedAncestor(evt.target);
    if (target !== currentTarget) return;
    hideButton();
  });
}
