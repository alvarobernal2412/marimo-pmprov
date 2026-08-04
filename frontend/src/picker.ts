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

export function armPicker(model: AnyModel, onPicked: (selection: PickedSelection) => void): void {
  let lastHovered: HTMLElement | null = null;

  function onMouseMove(evt: MouseEvent): void {
    const target = findTaggedAncestor(evt.target);
    if (lastHovered && lastHovered !== target) {
      lastHovered.classList.remove("pw-picker-hover");
    }
    if (target) {
      target.classList.add("pw-picker-hover");
    }
    lastHovered = target;
  }

  function onClick(evt: MouseEvent): void {
    const target = findTaggedAncestor(evt.target);
    cleanup();
    if (!target) return;
    evt.preventDefault();
    evt.stopPropagation();
    onPicked({
      artifactId: target.dataset.pwArtifactId!,
      artifactName: target.dataset.pwArtifactName ?? "",
      granularity: target.dataset.pwGranularity ?? "dataset",
      detail: target.dataset.pwDetail ?? null,
    });
  }

  function cleanup(): void {
    document.removeEventListener("mousemove", onMouseMove, true);
    document.removeEventListener("click", onClick, true);
    if (lastHovered) lastHovered.classList.remove("pw-picker-hover");
  }

  document.addEventListener("mousemove", onMouseMove, true);
  document.addEventListener("click", onClick, true);
}
