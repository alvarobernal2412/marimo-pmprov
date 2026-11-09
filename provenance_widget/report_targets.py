"""What the report says about a pinned element: plain words for it, and its mark on a Plotly Sankey.

A pin is recorded as a granularity and a detail (see `resolvers.ts`): a node by its label, a link as
`source -> target (label)`, where the label of a Linear Continuous Process Mapper link is the activity it adds with the
number of cases, such as `A_Cancelled (6840)`. In the report a reader needs those in words, and needs to see which part of
the map the finding is about, so `describe()` words the pin and `mark_sankey()` draws the map with only that part in colour.
"""
from __future__ import annotations

import re
from typing import Any

MARK_COLOR = "rgba(245, 158, 11, 0.95)"
MARK_EDGE = "#B45309"
FADED_ALPHA = 0.2
_MAX_LABEL_CHARS = 70


def _flat(text: Any) -> str:
    """A label as one line of text: Plotly allows HTML and line breaks in labels."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(text))).strip()


def _split_link(detail: str) -> tuple[str, str, str] | None:
    """`source -> target (label)` as (source, target, label); a node label can hold commas and brackets."""
    source, arrow, rest = detail.partition(" -> ")
    if not arrow:
        return None
    if rest.startswith("{"):
        depth, end = 0, -1
        for index, char in enumerate(rest):
            depth += char == "{"
            depth -= char == "}"
            if depth == 0:
                end = index + 1
                break
        target, tail = rest[:end], rest[end:]
    else:
        target, _, tail = rest.partition(" (")
        tail = " (" + tail if tail else ""
    tail = tail.strip()
    if not (tail.startswith("(") and tail.endswith(")")):
        return None
    return source.strip(), target.strip(), tail[1:-1].strip()


def _activity_and_count(label: str) -> tuple[str, int | None]:
    match = re.fullmatch(r"(.*?)\s*\((\d[\d,]*)\)", label)
    if not match:
        return label, None
    return match.group(1), int(match.group(2).replace(",", ""))


def _shorten(label: str) -> str:
    if len(label) <= _MAX_LABEL_CHARS:
        return label
    names = [part.strip() for part in label.strip("{}").split(",")]
    return f"a state of {len(names)} activities"


def describe(granularity: str | None, detail: str | None) -> str | None:
    """The pin in words, or None when it is not a node or a link."""
    if not detail:
        return None
    if granularity == "node":
        return f"node {_shorten(detail)}"
    if granularity == "link":
        parts = _split_link(detail)
        if parts is None:
            return None
        source, target, label = parts
        activity, count = _activity_and_count(label)
        text = f"link into {activity}"
        if count is not None:
            text += f", {count:,} cases"
        if "{" not in source and "{" not in target:
            text += f" (from {source} to {target})"
        return text
    return None


def _alpha(color: Any, alpha: float) -> str:
    """The colour with another opacity; anything not understood becomes a neutral grey."""
    text = str(color or "").strip()
    match = re.fullmatch(r"#([0-9a-fA-F]{6})", text)
    if match:
        value = match.group(1)
        red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
        return f"rgba({red}, {green}, {blue}, {alpha})"
    match = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*[\d.]+\s*)?\)", text)
    if match:
        return f"rgba({match.group(1)}, {match.group(2)}, {match.group(3)}, {alpha})"
    return f"rgba(148, 163, 184, {alpha})"


def _per_mark(colors: Any, count: int) -> list:
    if isinstance(colors, str) or colors is None:
        return [colors] * count
    return list(colors)[:count] + [None] * max(count - len(colors), 0)


def _sankey(figure: Any):
    for trace in getattr(figure, "data", None) or ():
        if getattr(trace, "type", "") == "sankey":
            return trace
    return None


def _find(trace: Any, granularity: str, detail: str) -> int | None:
    """The index of the one node or link a pin names, or None when it is not there or is ambiguous."""
    labels = [_flat(label) for label in (trace.node.label or ())]
    wanted = _flat(detail)
    if granularity == "node":
        found = [i for i, label in enumerate(labels) if label == wanted]
    else:
        link_labels = trace.link.label
        if link_labels is None:
            return None
        sources, targets = trace.link.source or (), trace.link.target or ()
        found = [
            i
            for i in range(len(sources))
            if f"{labels[sources[i]]} -> {labels[targets[i]]} ({_flat(link_labels[i])})" == wanted
        ]
    return found[0] if len(found) == 1 else None


def mark_sankey(figure: Any, granularity: str | None, detail: str | None) -> tuple[Any, bool]:
    """(a copy of the figure with the pinned node or link emphasised and the rest faded, True), else (figure, False).

    The pin has to name exactly one node or link of the map. A figure that is not a Sankey, a pin of another kind, or a pin
    that cannot be found leaves the figure as it is, so the report never marks the wrong element.
    """
    if granularity not in ("node", "link") or not detail:
        return figure, False
    try:
        import plotly.graph_objects as go

        trace = _sankey(figure)
        if trace is None:
            return figure, False
        index = _find(trace, granularity, detail)
        if index is None:
            return figure, False
        marked = go.Figure(figure)
        marked_trace = _sankey(marked)
        node_count = len(marked_trace.node.label or ())
        link_count = len(marked_trace.link.source or ())
        node_colors = [_alpha(c, FADED_ALPHA) for c in _per_mark(marked_trace.node.color, node_count)]
        link_colors = [_alpha(c, FADED_ALPHA) for c in _per_mark(marked_trace.link.color, link_count)]
        node_lines = ["rgba(0, 0, 0, 0)"] * node_count
        link_lines = ["rgba(0, 0, 0, 0)"] * link_count
        node_widths, link_widths = [0] * node_count, [0] * link_count
        if granularity == "node":
            node_colors[index] = _alpha(_per_mark(trace.node.color, node_count)[index], 1)
            node_lines[index], node_widths[index] = MARK_EDGE, 4
        else:
            link_colors[index] = MARK_COLOR
            link_lines[index], link_widths[index] = MARK_EDGE, 3
        marked_trace.node.color = node_colors
        marked_trace.node.line = {"color": node_lines, "width": node_widths}
        marked_trace.link.color = link_colors
        marked_trace.link.line = {"color": link_lines, "width": link_widths}
        # A picture has no tooltip, so the number the reader would hover for is written on the figure.
        top = max((marked.layout.margin.t or 0), 60)
        marked.update_layout(margin={"t": top})
        marked.add_annotation(
            text=f"<b>Marked:</b> {describe(granularity, detail)}",
            xref="paper", yref="paper", x=0, y=1, yshift=14, xanchor="left", yanchor="bottom", showarrow=False,
            font={"size": 16, "color": MARK_EDGE},
        )
        return marked, True
    except Exception:
        return figure, False
