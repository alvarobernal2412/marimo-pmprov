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

function refineGranularity(
  taggedElement: HTMLElement,
  clickTarget: HTMLElement,
): { granularity: string; detail: string | null } {
  const td = clickTarget.closest("td");
  if (td && taggedElement.contains(td)) {
    const tr = td.parentElement;
    const colIndex = tr ? Array.from(tr.children).indexOf(td) : -1;
    const table = td.closest("table");
    let columnName: string | null = null;
    if (table && colIndex >= 0) {
      const headerCell = table.querySelector("thead tr")?.children[colIndex];
      columnName = headerCell?.textContent?.trim() ?? null;
    }
    const tbody = tr?.parentElement;
    const rowIndex = tr && tbody ? Array.from(tbody.children).indexOf(tr) : -1;
    const detail = columnName ? `row ${rowIndex}, column ${columnName}` : `row ${rowIndex}`;
    return { granularity: "cell", detail };
  }

  const th = clickTarget.closest("th");
  if (th && taggedElement.contains(th)) {
    return { granularity: "column", detail: th.textContent?.trim() ?? null };
  }

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
    const clickTarget = evt.target as HTMLElement;
    cleanup();
    if (!target) {
      onCancel?.();
      return;
    }
    evt.preventDefault();
    evt.stopPropagation();
    const { granularity, detail } = refineGranularity(target, clickTarget);
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
