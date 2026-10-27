"""Run every scenario and write out/results.json and out/report.md.

Usage:  python run_benchmark.py [--update-baseline] [scenario-id-prefix ...]
Needs pmprov and marimo-pmprov importable (e.g. the marimo-pmprov venv).
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from harness import CHECKS, run_scenario  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402

ICON = {"PASS": "pass", "FAIL": "FAIL", "ERROR": "ERROR", "NA": "-", "SKIP": "skip"}
LAYER = {
    "recorded": "pmprov", "output_restorable": "pmprov", "params_ok": "pmprov",
    "snapshot_exact": "marimo-pmprov", "tree_delta_ok": "marimo-pmprov", "resume_exact": "pmprov", "final_namespace": "marimo-pmprov",
    "immutable_after": "both", "persist_after_restart": "both", "annotations_roundtrip": "both",
}


def run(prefixes: list[str]) -> list:
    results = []
    for scenario in SCENARIOS:
        if prefixes and not any(scenario.id.startswith(p) for p in prefixes):
            continue
        started = time.time()
        result = run_scenario(scenario)
        result.seconds = round(time.time() - started, 1)  # type: ignore[attr-defined]
        results.append(result)
        flag = result.skipped or result.crashed or ", ".join(
            f"{c}={o.status}" for c, o in result.summary().items() if o.status in ("FAIL", "ERROR")
        ) or "all pass"
        print(f"{scenario.id:<38} {result.seconds:>5}s  {flag[:110]}", flush=True)
    return results


def to_json(results: list) -> list[dict]:
    out = []
    for r in results:
        out.append({
            "id": r.id, "title": r.title, "evidence": r.evidence, "skipped": r.skipped, "crashed": r.crashed,
            "seconds": getattr(r, "seconds", None),
            "summary": {c: asdict(o) for c, o in r.summary().items()},
            "cells": [{"src": c.src, "steps": c.steps, "checks": {k: asdict(v) for k, v in c.checks.items()}} for c in r.cells],
        })
    return out


def to_markdown(results: list) -> str:
    lines = ["# Benchmark report: course operations vs pmprov / marimo-pmprov", ""]
    lines += ["Each scenario is a pattern found in the course code (see `survey.md`). Checks:", ""]
    for check in CHECKS:
        lines.append(f"- `{check}` ({LAYER[check]})")
    lines += ["", "## Matrix", "", "| scenario | " + " | ".join(CHECKS) + " |", "|---|" + "---|" * len(CHECKS)]
    totals = {c: [0, 0] for c in CHECKS}  # pass, applicable
    for r in results:
        if r.skipped:
            lines.append(f"| {r.id} | " + " | ".join(["skip"] * len(CHECKS)) + " |")
            continue
        if r.crashed:
            lines.append(f"| {r.id} | " + " | ".join(["CRASH"] * len(CHECKS)) + " |")
            continue
        row = []
        for check, outcome in r.summary().items():
            row.append(ICON[outcome.status])
            if outcome.status in ("PASS", "FAIL", "ERROR"):
                totals[check][1] += 1
                totals[check][0] += outcome.status == "PASS"
        lines.append(f"| {r.id} | " + " | ".join(row) + " |")
    lines += ["| **pass rate** | " + " | ".join(f"{p}/{n}" for p, n in totals.values()) + " |", ""]

    lines += ["## Findings", ""]
    for r in results:
        if r.skipped:
            lines += [f"### {r.id}: skipped ({r.skipped})", ""]
            continue
        if r.crashed:
            lines += [f"### {r.id}: harness crashed", "", f"`{r.crashed}`", ""]
            continue
        failing = []
        for cell in r.cells:
            for check, outcome in cell.checks.items():
                if outcome.status in ("FAIL", "ERROR"):
                    failing.append((cell.src.splitlines()[0][:90], check, outcome))
        for check, outcome in r.scenario_checks.items():
            if outcome.status in ("FAIL", "ERROR"):
                failing.append(("(whole scenario)", check, outcome))
        if not failing:
            continue
        lines += [f"### {r.id}: {r.title}", "", f"Course evidence: {r.evidence}", ""]
        for src, check, outcome in failing:
            lines.append(f"- `{src}` -> **{check}** {outcome.status}: {outcome.why}")
        lines.append("")
    return "\n".join(lines)


def baseline_of(results: list) -> dict:
    return {r.id: {c: o.status for c, o in r.summary().items()} for r in results if not r.skipped and not r.crashed}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    update = "--update-baseline" in sys.argv
    results = run(args)
    out = HERE / "out"
    out.mkdir(exist_ok=True)
    (out / "results.json").write_text(json.dumps(to_json(results), indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text(to_markdown(results), encoding="utf-8")
    print(f"\nwrote {out / 'report.md'}")
    if update:
        (HERE / "baseline.json").write_text(json.dumps(baseline_of(results), indent=1, sort_keys=True), encoding="utf-8")
        print(f"wrote {HERE / 'baseline.json'}")
