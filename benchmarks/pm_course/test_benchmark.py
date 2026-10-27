"""Regression guard for the benchmark: results may improve, never get worse.

Each (scenario, check) is compared with baseline.json, the results recorded when
the benchmark was written. A gap that gets fixed shows up as a warning
("improved"); a check that used to pass and no longer does fails the test.

    pytest benchmarks/pm_course/test_benchmark.py -q
    python benchmarks/pm_course/run_benchmark.py --update-baseline   # after a fix lands

The tests need pmprov importable; they are skipped otherwise.
"""
import json
import warnings
from pathlib import Path

import pytest

pytest.importorskip("tracker", reason="pmprov not installed")
from tracker.storage import DuckDBSQLiteBackend  # noqa: E402

if not hasattr(DuckDBSQLiteBackend, "load_state_bindings"):
    pytest.skip("the baseline was recorded with pmprov >= 0.8.0", allow_module_level=True)

from harness import run_scenario  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402

BASELINE = json.loads((Path(__file__).parent / "baseline.json").read_text(encoding="utf-8"))
RANK = {"FAIL": 0, "ERROR": 0, "NA": 1, "PASS": 2}


@pytest.fixture(scope="module")
def results():
    return {}


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_scenario_does_not_regress(scenario, results):
    result = run_scenario(scenario)
    if result.skipped:
        pytest.skip(result.skipped)
    assert not result.crashed, f"the harness crashed: {result.crashed}"

    baseline = BASELINE.get(scenario.id)
    assert baseline is not None, f"{scenario.id} has no baseline; run run_benchmark.py --update-baseline"
    regressions, improvements = [], []
    for check, outcome in result.summary().items():
        before = baseline.get(check, "NA")
        if RANK[outcome.status] < RANK[before]:
            regressions.append(f"{check}: {before} -> {outcome.status} ({outcome.why[:120]})")
        elif RANK[outcome.status] > RANK[before] and before != "NA":
            improvements.append(f"{check}: {before} -> {outcome.status}")
    if improvements:
        warnings.warn(f"{scenario.id} improved ({'; '.join(improvements)}); update the baseline", stacklevel=1)
    assert not regressions, f"{scenario.id} regressed: " + "; ".join(regressions)
