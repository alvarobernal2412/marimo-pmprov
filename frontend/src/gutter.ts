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
    if (node.parentElement) {
      node = node.parentElement;
    } else {
      const root = node.getRootNode();
      node = root instanceof ShadowRoot ? (root.host as HTMLElement) : null;
    }
  }
  return null;
}

const armedModels = new WeakSet<AnyModel>();

// NOTE: this widget is designed as a single docked sidebar instance per notebook
// (per the design spec). If multiple ProvenanceWidget instances are ever rendered
// simultaneously in one notebook, their gutter listeners are not mutually isolated —
// each will react to hovers over any tagged element regardless of which widget
// instance "owns" it. This is a known limitation, not addressed in this pass.
export function armGutterAffordance(
  model: AnyModel,
  onPick: (selection: PickedSelection) => void,
): void {
  if (armedModels.has(model)) return;
  armedModels.add(model);

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
    if (model.get("mode") !== "student" || document.body.classList.contains("pw-picking-active")) {
      hideButton();
      return;
    }
    const target = findTaggedAncestor(evt.composedPath()[0] ?? evt.target);
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
    const target = findTaggedAncestor(evt.composedPath()[0] ?? evt.target);
    if (target !== currentTarget) return;
    hideButton();
  });
}
