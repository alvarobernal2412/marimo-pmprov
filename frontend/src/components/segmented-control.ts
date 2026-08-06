export function segmentedControl(
  options: { value: string; label: string }[],
  active: string,
  onChange: (value: string) => void,
): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "pw-segmented-control";
  options.forEach(({ value, label }) => {
    const btn = document.createElement("button");
    btn.textContent = label;
    btn.className = value === active ? "pw-segment pw-segment-active" : "pw-segment";
    btn.addEventListener("click", () => onChange(value));
    wrap.appendChild(btn);
  });
  return wrap;
}
