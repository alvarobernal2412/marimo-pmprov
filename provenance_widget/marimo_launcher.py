"""Start marimo with pmprov's tracking active.

    python -m provenance_widget.marimo_launcher run notebook.py
    python -m provenance_widget.marimo_launcher edit notebook.py --omit my_helper --omit other.call

Why this exists: pmprov tracks a notebook by patching marimo's compiler so every
cell is rewritten before it runs. A notebook that applies the patch in its own
top-level code only works when marimo executes that code, and marimo (0.23)
loads a notebook by parsing it, so the patch never runs and nothing is tracked.
Applying it here, before marimo starts, fixes that for `marimo run` (cells run
in this process) and, because the patch is applied when this module is
imported, for the kernel process `marimo edit` spawns as well.

Everything after the command is passed to marimo unchanged, except
`--omit NAME` (repeatable, or comma separated): extra calls to leave out of the
provenance tree. The widget's own plumbing and common marimo UI calls are left
out by default.
"""
from __future__ import annotations

import builtins
import sys

# Calls that are widget plumbing or marimo display, never analysis steps.
DEFAULT_OMIT = (
    "PmprovAdapter", "ProvenancePanel", "show_table", "show_chart",
    "panel.snapshot", "panel.reactive_cursor", "panel.sidebar", "snap.get", "snap.missing",
    "mo.ui.table", "mo.ui.slider", "mo.ui.dropdown", "mo.ui.multiselect", "mo.ui.text",
    "mo.ui.number", "mo.ui.checkbox", "mo.ui.radio", "mo.ui.button",
    "mo.md", "mo.vstack", "mo.hstack", "mo.callout", "mo.stop", "mo.sidebar",
)


def split_omit(argv: list[str]) -> tuple[list[str], list[str]]:
    """Separate `--omit NAME[,NAME...]` options from the arguments marimo gets."""
    rest: list[str] = []
    omit: list[str] = []
    it = iter(argv)
    for arg in it:
        if arg == "--omit":
            value = next(it, "")
            omit.extend(n for n in value.split(",") if n)
        elif arg.startswith("--omit="):
            omit.extend(n for n in arg.split("=", 1)[1].split(",") if n)
        else:
            rest.append(arg)
    return rest, omit


def activate(extra_omit: list[str] | None = None) -> None:
    """Apply pmprov's compiler patch and omit list in this process."""
    from tracker import omit_functions
    from tracker.kernel_hooks import _NoOpRuntime, patch_marimo_ast_compile

    builtins._provtrack_runtime = _NoOpRuntime()  # replaced by init_marimo() in the notebook
    patch_marimo_ast_compile()
    omit_functions(*DEFAULT_OMIT, *(extra_omit or []))


# Applied at import so the kernel process marimo spawns (it re-imports this
# module under spawn, with the same arguments) is patched too.
_MARIMO_ARGS, _OMIT = split_omit(sys.argv[1:])
if __name__ in ("__main__", "__mp_main__"):
    activate(_OMIT)


def main() -> None:
    from marimo._cli.cli import main as marimo_main

    marimo_main(_MARIMO_ARGS)


if __name__ == "__main__":
    main()
