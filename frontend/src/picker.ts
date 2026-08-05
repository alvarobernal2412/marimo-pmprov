import { resolveDetail } from "./resolvers";

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

function refineGranularity(
  taggedElement: HTMLElement,
  clickTarget: HTMLElement,
  path: EventTarget[],
): { granularity: string; detail: string | null } {
  // Table cells, chart marks, and anything else "inside" an artifact are
  // refined by pluggable resolvers (see resolvers.ts) — the picker itself
  // doesn't know what a table or a chart is.
  const resolved = resolveDetail(path, clickTarget);
  if (resolved) return resolved;

  return {
    granularity: taggedElement.dataset.pwGranularity ?? "dataset",
    detail: taggedElement.dataset.pwDetail ?? null,
  };
}

export function armPicker(
  model: AnyModel,
  onPicked: (selection: PickedSelection) => void,
  onCancel?: () => void,
): void {
  let lastHovered: HTMLElement | null = null;

  function onMouseMove(evt: MouseEvent): void {
    const target = findTaggedAncestor(evt.composedPath()[0] ?? evt.target);
    if (lastHovered && lastHovered !== target) {
      lastHovered.classList.remove("pw-picker-hover");
    }
    if (target) {
      target.classList.add("pw-picker-hover");
    }
    lastHovered = target;
  }

  function onClick(evt: MouseEvent): void {
    const path = evt.composedPath();
    const originalTarget = (path[0] ?? evt.target) as HTMLElement;
    const target = findTaggedAncestor(originalTarget);
    const clickTarget = originalTarget;
    cleanup();
    if (!target) {
      onCancel?.();
      return;
    }
    evt.preventDefault();
    evt.stopPropagation();
    const { granularity, detail } = refineGranularity(target, clickTarget, path);
    onPicked({
      artifactId: target.dataset.pwArtifactId!,
      artifactName: target.dataset.pwArtifactName ?? "",
      granularity,
      detail,
    });
  }

  function onKeyDown(evt: KeyboardEvent): void {
    if (evt.key === "Escape") {
      cleanup();
      onCancel?.();
    }
  }

  function cleanup(): void {
    document.removeEventListener("mousemove", onMouseMove, true);
    document.removeEventListener("click", onClick, true);
    document.removeEventListener("keydown", onKeyDown, true);
    if (lastHovered) lastHovered.classList.remove("pw-picker-hover");
  }

  document.addEventListener("mousemove", onMouseMove, true);
  document.addEventListener("click", onClick, true);
  document.addEventListener("keydown", onKeyDown, true);
}
