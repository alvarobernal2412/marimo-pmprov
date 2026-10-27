"""Print the cell-by-cell outcomes of one scenario from out/results.json.

Usage: python show_result.py S02
"""
import json
import sys
from pathlib import Path

data = json.loads((Path(__file__).parent / "out" / "results.json").read_text(encoding="utf-8"))
prefix = sys.argv[1]
for scenario in data:
    if not scenario["id"].startswith(prefix):
        continue
    print(f"{scenario['id']}: {scenario['title']}  ({scenario['seconds']}s)")
    if scenario["skipped"] or scenario["crashed"]:
        print("  ", scenario["skipped"] or scenario["crashed"])
    for cell in scenario["cells"]:
        print(f"  [{cell['steps']} step(s)] {cell['src'].splitlines()[0][:100]}")
        for check, outcome in cell["checks"].items():
            mark = "ok " if outcome["status"] in ("PASS", "NA") else outcome["status"]
            print(f"      {check:<22} {mark:<5} {outcome['why'][:170]}")
    for check, outcome in scenario["summary"].items():
        if check in ("immutable_after", "persist_after_restart"):
            print(f"  scenario: {check:<22} {outcome['status']:<5} {outcome['why'][:170]}")
