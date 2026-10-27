"""Print distinct source examples per statement form from out/survey.json.

Usage: python show_forms.py [form ...]   (default: the forms pmprov does not track)
"""
import collections
import json
import sys
from pathlib import Path

data = json.loads((Path(__file__).parent / "out" / "survey.json").read_text(encoding="utf-8"))
by = collections.defaultdict(list)
for f in data["files"]:
    name = Path(f["file"]).name
    # the *_with_solutions / _BPME notebooks repeat their base notebooks
    if name.endswith(("with_solutions.ipynb", "_BPME.ipynb")):
        continue
    for s in f["statements"]:
        by[s["form"]].append((name[:24], s["src"]))

forms = sys.argv[1:] or [
    "assign_subscript", "assign_subscript_read", "assign_unpack_call", "assign_attribute",
    "assign_other", "assign_expression", "assign_comprehension", "expr_value", "for", "if",
]
for form in forms:
    print(f"\n== {form} ({len(by[form])})")
    seen = set()
    for fname, src in by[form]:
        key = src[:60]
        if key in seen:
            continue
        seen.add(key)
        print(f"  [{fname}] {src}")
        if len(seen) >= 14:
            break
