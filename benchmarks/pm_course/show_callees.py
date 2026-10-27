"""List the distinct operations (callees) of tracked-form statements, by library.

Usage: python show_callees.py
"""
import collections
import json
from pathlib import Path

NOISE_ROOTS = {"display", "print", "fig", "plotly", "px", "len", "mo", "marimo", "sys", "random", "app", "html", "dcc", "go"}

data = json.loads((Path(__file__).parent / "out" / "survey.json").read_text(encoding="utf-8"))
groups = collections.defaultdict(collections.Counter)
examples = {}
for f in data["files"]:
    name = Path(f["file"]).name
    if name.endswith(("with_solutions.ipynb", "_BPME.ipynb")) or (name == "event_enricher.py" and not f["file"].startswith("utils")):
        continue
    for s in f["statements"]:
        if s["form"] not in {"assign_call", "expr_call", "assign_unpack_call"} or "callee" not in s and s["form"] != "assign_unpack_call":
            continue
        callee = s.get("callee")
        if callee is None:
            continue
        root = s.get("root", "").split(".")[0]
        head = callee.split(".")[0].split("(")[0].split("[")[0]
        if head in NOISE_ROOTS or root in NOISE_ROOTS:
            continue
        key = root if root in {"pm4py", "pandas", "sklearn", "numpy", "event_enricher", "rulelearn", "helpers", "viz", "itertools"} else "<variable method>"
        groups[key][callee] += 1
        examples.setdefault(callee, s["src"])

for lib, counter in sorted(groups.items()):
    print(f"\n## {lib}  ({sum(counter.values())} calls, {len(counter)} distinct)")
    for callee, n in counter.most_common(60):
        print(f"  x{n:<3} {callee:<46} e.g. {examples[callee][:100]}")
