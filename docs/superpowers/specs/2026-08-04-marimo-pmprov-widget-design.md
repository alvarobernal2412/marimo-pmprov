# marimo-pmprov: provenance & annotation sidebar widget — design

## Purpose

A marimo anywidget plugin that gives process-mining analysts a git-style
"Source Control" panel embedded in a marimo notebook: a curated commit rail
of annotations, a Miller-columns provenance tree (mindmap of which artifacts
each analysis step touches), and a diff inspector — plus a read-only
Reviewer mode with tag-based state restore.

This iteration builds a **functional widget running against mock data**
that mirrors pmprov's real model shapes, decoupled from the `pmprov` library
itself. No `pmprov` import happens anywhere in this package.

## Non-goals (this iteration)

- No real `pmprov`-backed adapter (would be untested/half-finished — left
  as a documented extension point).
- No real marimo `mo.state` rewiring for "Restore to @tag" — the reviewer
  restore flow is simulated (confirmation + path highlight + fake
  reconstructing progress), matching the interface the real integration
  would later drive.
- No persistence — mock data is regenerated in memory each run.

## Architecture: decoupling from pmprov

```
provenance_widget/
  interfaces.py     # ProvenanceSource protocol + plain dataclasses
  mock_source.py     # MockProvenanceSource: realistic example tree
  display.py          # pw.show_table / pw.show_chart wrapper functions
  widget.py            # AnyWidget subclass + ProvenancePanel façade
  static/               # bundled dist/widget.js + widget.css (checked in)
frontend/
  src/                   # TS source, esbuild config (dev-only, not shipped)
examples/
  demo_notebook.py         # marimo notebook using MockProvenanceSource
```

`provenance_widget/interfaces.py` defines a `ProvenanceSource` `Protocol`
with one method, `get_tree() -> ProvenanceTree`. The dataclasses in that
module (`ProvenanceNode`, `Operation`, `Delta`, `Agent`, `ArtifactRef`,
`Annotation`, `Tag`, `StepCategory`) reuse pmprov's real field names and
semantics (`operationType`, `commandName`, `params`, `delta`,
`parentStates`, `stepId`, columns/dtype delta shape, `StepCategory`
enum values, etc., per pmprov's `MODEL.md`) so a future adapter is a
straight translation, not a redesign. `Annotation` and `Tag` are new —
pmprov has no such concept — modeled as attached to a `ProvenanceNode`
(1 node : 0..N annotations, annotations carry 0..N tags).

This is the only contract `widget.py` and the frontend depend on. Swapping
`MockProvenanceSource` for a real `PmprovAdapter(ProvenanceSource)` later
requires no changes to the widget or frontend code.

`pmprov` is **not** a dependency of the base package. `pyproject.toml`
declares an optional extra, `pmprov`, documented but unused by any shipped
code:

```toml
[project.optional-dependencies]
pmprov = ["pmprov @ git+https://github.com/<org>/pmprov.git@vX.Y.Z"]
```

The README explains that once a `PmprovAdapter` exists, installing with
`pip install "marimo-pmprov[pmprov]"` pulls in that pinned pmprov version.

## Target-artifact selection (picker)

Two-part mechanism, replacing a plain "recent selections" dropdown:

1. **Enrichment (`provenance_widget/display.py`)** — thin wrapper functions
   `pw.show_table(state, artifact_name=...)` / `pw.show_chart(state, ...)`
   that render via `mo.ui.table` / a chart element *and* stamp the rendered
   container with `data-pw-artifact-id`, `data-pw-artifact-name`,
   `data-pw-granularity` attributes, keeping a live link to the underlying
   `mo.ui` element's `.value` for row/column/cell/brush selection. This is
   the only manual step an analyst takes — use `pw.show_table(...)` instead
   of `mo.ui.table(...)` directly.
2. **Picking** — the sidebar composer's target field has a crosshair
   "Pick from notebook" button. Clicking arms a picker: the widget's JS
   attaches a one-shot document-level hover/click listener (ordinary
   browser JS, sees the whole notebook DOM, not just the sidebar),
   highlights any element carrying `data-pw-*` attributes on hover, and on
   click reads the nearest tagged ancestor's metadata + current selection
   value back into the composer's target field. A secondary "recent
   selections" list in the same dropdown covers picks made moments ago
   without re-arming the picker.

Gutter "+" hover affordances (git-blame style) are the passive counterpart:
any `pw.show_*`-rendered element shows a "+" on hover that starts a new
annotation pre-targeted at that artifact/selection.

## Widget / traitlet sync

`ProvenancePanel(source: ProvenanceSource, mode="student")` is the Python
façade. It builds one `anywidget.AnyWidget` instance with traitlets:

| Traitlet | Direction | Purpose |
|---|---|---|
| `tree` | Py→JS | Serialized `ProvenanceTree` (nodes, edges, artifacts) |
| `mode` | Py↔JS | `"student"` \| `"reviewer"` |
| `active_tab` | Py↔JS | `"curated"` \| `"tree"` \| `"inspect"` |
| `selection` | JS→Py | Current picker/dropdown target (artifact id + granularity + value) |
| `commits` | Py↔JS | Append-only list of `Annotation` — new entries push in from JS composer, render in Python-side history |
| `restore_request` / `restore_ack` | JS→Py / Py→JS | Reviewer "Restore to @tag" round-trip (simulated in mock mode) |

`ProvenancePanel.sidebar()` returns an object ready for `mo.sidebar(...)`
(Curated/Tree-summary/Inspect segmented control + composer).
`ProvenancePanel.tree_surface()` returns the full-width Tree tab element
for when the user wants it as the primary surface instead of embedded in
the sidebar, per the spec's "one full-width surface for the tree view".

## Frontend (vanilla TS + esbuild)

```
frontend/src/
  main.ts            # anywidget render() entrypoint, mounts app shell
  state.ts             # local view-state store synced from traitlets
  picker.ts             # document-level hover/click picker logic
  views/
    curated.ts           # commit rail + composer
    tree.ts                 # Miller columns + artifact legend + cross-highlight
    inspect.ts                # diff view
  components/
    node-card.ts, tag-chip.ts, artifact-badge.ts, segmented-control.ts
  theme.css                     # light/dark via prefers-color-scheme + marimo theme class
```

Bundled to `provenance_widget/static/widget.js` + `widget.css` via esbuild
at build/publish time; Node is a dev-time-only dependency, not required to
`pip install` the package.

## Mock data (`mock_source.py`)

A single branching example over a synthetic event log, using pmprov's
`StepCategory` mapping and operation names from `operations.py`:

`IMPORT (load_event_log)` → `FILTER (duration > 120h)` → `ENRICHMENT
(resource cost)` → branches into `RULE_INDUCTION` (Branch A) and
`CONFORMANCE` (Branch B). Every node carries realistic `Delta`
(columns added/removed, row count before/after), an `Agent`, and 1–2
`Annotation`s with `Tag`s (`#cleaning`, `#cost`, `#v1.1`, etc.) and
artifact references at varying granularity (whole dataset / named column /
row subset / chart brush).

## Scope confirmed with user

- Functional (not static-mockup) plugin: real anywidget, real tab
  switching, real Miller-columns drill-down, real composer that appends to
  `commits`, real artifact-legend dimming, real hover cross-highlight.
- Mock data only, but shaped exactly like pmprov's real model — no
  invented field structure.
- Frontend: vanilla JS/TS + esbuild, no framework.
- Target picker: hybrid of enrichment wrapper functions + a document-level
  "pick from notebook" cursor mode + a recent-selections fallback in the
  dropdown.
