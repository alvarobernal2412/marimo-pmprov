"""Where the analyst dragged the nodes of a Plotly Sankey figure, so that a notebook can record it as a step.

Dragging a node happens in the browser only: no cell runs, so nothing is recorded, an annotation written after it is attached
to the figure as it was drawn, and the report shows that figure. A notebook uses this module to make the arrangement a step:

    arrangement = mo.ui.anywidget(NodeArrangement())            # a cell of its own, shown (it draws nothing)

    positions = reported(arrangement.value, figure_state)       # None until the nodes of *this* figure are dragged
    shown = record(["arranged"], arranged, figure, positions) if positions else figure

    watched(mo, show_chart(mo.as_html(shown), ...), figure_state)   # the figure on the page, marked so it is watched

`figure_state` names the figure as it was drawn (the recorded state that produced it): positions reported for a figure that
was drawn again since do not apply to the new one. What `arranged` returns has the nodes at the reported positions, which the
page then sees as the figure's own, so drawing it again reports nothing.
"""
from __future__ import annotations

import html
import json

import anywidget
import traitlets


class NodeArrangement(anywidget.AnyWidget):
    """Reports where the nodes of the figures on the page that `watched` wraps were dragged to. Nothing is shown.

    When the nodes of a figure have moved and stay where they are, `moved` is set to {"figure": the id given to `watched`,
    "positions": JSON of one {"x", "y"} per Sankey trace (shares of the width and height, to four decimals), "n": a new value
    each time}."""

    moved = traitlets.Dict({}).tag(sync=True)
    _esm = """
    function deep(root, out = []) {
      for (const element of root.querySelectorAll("*")) {
        out.push(element);
        if (element.shadowRoot) deep(element.shadowRoot, out);
      }
      return out;
    }
    const rounded = (values) => (values && values.length ? Array.from(values, (v) => Math.round(Number(v) * 1e4) / 1e4) : null);
    export default {
      render({ model, el }) {
        el.style.display = "none";
        // figure id -> the artifact it is on the page, the positions the notebook drew it with, those last seen and last told
        const seen = {};
        let waiting = false;  // whether a figure was pending at the last look: it is then looked at more often
        const grace = {};  // figure id -> until when a drag that just ended in it counts as a move, seen or not
        let count = 0;
        const look = () => {
          try {
            if (document.hidden) return;
            let pending = false;
            for (const frame of deep(document).filter((e) => e.dataset && e.dataset.pwArrangement)) {
              const plot = deep(frame).find((e) => e.classList && e.classList.contains("js-plotly-plot") && Array.isArray(e.data));
              if (!plot) { pending = pending || frame.dataset.pwPending === "1"; continue; }  // being drawn
              const positions = plot.data
                .filter((trace) => trace && trace.type === "sankey")
                .map((trace) => ({ x: rounded(trace.node && trace.node.x), y: rounded(trace.node && trace.node.y) }));
              const now = JSON.stringify(positions);
              const id = frame.dataset.pwArrangement;
              const tagged = deep(frame).find((e) => e.dataset && e.dataset.pwArtifactId);
              const artifact = tagged ? tagged.dataset.pwArtifactId : "";
              let state = seen[id];
              // as a figure is first seen, and each time the notebook has drawn it again, is how the notebook drew it: not a move
              if (!state || state.artifact !== artifact) {
                state = seen[id] = { artifact, drawn: now, last: now, told: now, since: 0 };
                grace[id] = 0;  // drawn again: what the page shows is recorded, whatever drag came before
              }
              // Dragged and not drawn again yet: the page shows what the notebook has not recorded. The panel waits with adding
              // an annotation while a figure says so (not for ever: a notebook that does not record it must not block it).
              if (now !== state.drawn || Date.now() < (grace[id] || 0)) {
                state.since = state.since || Date.now();
                if (Date.now() - state.since < 180000) {
                  frame.dataset.pwPending = "1";
                  pending = true;
                } else delete frame.dataset.pwPending;
              } else {
                state.since = 0;
                delete frame.dataset.pwPending;
              }
              const settled = state.last === now;
              state.last = now;
              if (!settled || state.told === now || !positions.some((p) => p.x && p.y)) continue;
              state.told = now;
              count += 1;
              model.set("moved", { figure: id, positions: now, n: Date.now() + "-" + count });
              model.save_changes();
            }
            waiting = pending;
          } catch (e) {}
        };
        // while a figure waits to be drawn again, look often: an annotation is waiting for exactly that
        const quick = setInterval(() => { if (waiting) look(); }, 150);
        const timer = setInterval(() => {
          if (!el.isConnected) {
            clearInterval(timer);
            clearInterval(quick);
            document.removeEventListener("pointerup", soon, true);
            document.removeEventListener("pointerdown", pressed, true);
            return;
          }
          look();
        }, 700);
        // A drag ends with the pointer going up, and Plotly sets the positions a moment later. A pointer that went down in a
        // figure and came up elsewhere marks the figure at once, so that it is marked before anything else is clicked; looking
        // at it then says whether a node did move (the mark goes when none did).
        let down = null;
        const figureOf = (event) => (event.composedPath ? event.composedPath() : []).find((e) => e.dataset && e.dataset.pwArrangement);
        const pressed = (event) => {
          const frame = figureOf(event);
          down = frame ? { frame, x: event.clientX, y: event.clientY } : null;
        };
        const soon = (event) => {
          if (down && Math.hypot(event.clientX - down.x, event.clientY - down.y) > 3) {
            grace[down.frame.dataset.pwArrangement] = Date.now() + 2000;
            down.frame.dataset.pwPending = "1";
            setTimeout(look, 2100);
          }
          down = null;
          // the positions are told once two looks agree: three in half a second, instead of waiting for the next rounds
          for (const after of [60, 250, 500]) setTimeout(look, after);
        };
        document.addEventListener("pointerdown", pressed, true);
        document.addEventListener("pointerup", soon, true);
      },
    };
    """


def watched(mo, chart, figure_id: str, pictured: bool = True):
    """`chart` (a figure as it is shown, e.g. what `show_chart` returns) marked as the figure `figure_id`, so that a
    `NodeArrangement` on the page reports the nodes dragged in it.

    `pictured=False` says that no picture of this figure is made for the page (no `figure=` in `show_chart`, no
    `chart_snapshot`): the panel then does not wait for one before it adds an annotation, and the report draws the figure from
    the recorded step. Drawing a Plotly figure as a picture takes seconds; a notebook that draws the figure again after every
    drag saves them this way."""
    without = "" if pictured else ' data-pw-unpictured="1"'
    return mo.Html(f'<div data-pw-arrangement="{html.escape(str(figure_id), quote=True)}"{without}>{chart.text}</div>')


def reported(value: dict | None, figure_id: str) -> str | None:
    """The positions a `NodeArrangement` reported (its `.value`) when they are of the figure `figure_id`, else None."""
    moved = (value or {}).get("moved") or {}
    positions = moved.get("positions")
    return positions if moved.get("figure") == figure_id and isinstance(positions, str) and positions else None


def arranged(figure, positions: str):
    """`figure` (Plotly) with its nodes where the analyst dragged them: `positions` is what `NodeArrangement` reports, the JSON
    of one {"x", "y"} per Sankey trace. A trace whose positions are missing or not one per node is left as it is. The figure
    itself is not changed."""
    result = type(figure)(figure)
    try:
        places = json.loads(positions)
    except (TypeError, ValueError):
        return result
    traces = [trace for trace in result.data if trace.type == "sankey"]
    for trace, place in zip(traces, places if isinstance(places, list) else []):
        x, y = (place or {}).get("x"), (place or {}).get("y")
        nodes = len(trace.node.label or [])
        if isinstance(x, list) and isinstance(y, list) and len(x) == len(y) == nodes and nodes:
            trace.node.x, trace.node.y = [float(v) for v in x], [float(v) for v in y]
    return result
