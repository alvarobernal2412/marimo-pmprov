export function segmentedControl(
  options: string[],
  active: string,
  onChange: (value: string) => void,
): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "pw-segmented-control";
  options.forEach((opt) => {
    const btn = document.createElement("button");
    btn.textContent = opt;
    btn.className = opt === active ? "pw-segment pw-segment-active" : "pw-segment";
    btn.addEventListener("click", () => onChange(opt));
    wrap.appendChild(btn);
  });
  return wrap;
}
