import type { TreeNavState } from "./nav-state";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

// Ask Python for the PDF; the answer arrives in `export_result` (see handleExportResult).
export function requestPdfExport(model: AnyModel): void {
  const nav = model as unknown as TreeNavState;
  if (nav._pwExport?.pending) return;
  const requestId = `pdf-${Date.now()}`;
  nav._pwExport = { pending: requestId };
  model.set("export_request", { requestId });
  model.save_changes();
}

// Save the PDF Python sent back, or remember its error for the button to show.
export function handleExportResult(model: AnyModel): void {
  const nav = model as unknown as TreeNavState;
  const result = (model.get("export_result") as Record<string, string>) ?? {};
  if (!result.requestId || result.requestId !== nav._pwExport?.pending) return;
  if (result.data) {
    const bytes = Uint8Array.from(atob(result.data), (c) => c.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = result.filename || "annotations.pdf";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
    nav._pwExport = {};
  } else {
    nav._pwExport = { error: result.error || "Export failed" };
  }
}
