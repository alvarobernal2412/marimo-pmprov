# Course-operations benchmark

Goal: every analysis step and state of the process-mining course code is tracked
and can be replayed, from the analyst's and the reviewer's point of view.

This benchmark turns the operations in `PM_Course` into scenarios, runs them
under real pmprov tracking, and reports which ones are not covered.

## Run it

```bash
# from marimo-pmprov, in an environment with pmprov >= 0.9.0 importable (the project venv)
python benchmarks/pm_course/survey.py "<PM_Course dir>" benchmarks/pm_course/out   # static survey
python benchmarks/pm_course/run_benchmark.py            # writes out/report.md and out/results.json
python benchmarks/pm_course/show_result.py S08          # cell-by-cell outcomes of one scenario
pytest benchmarks/pm_course/test_benchmark.py -q        # regression guard (about 25 s)
python benchmarks/pm_course/run_benchmark.py --update-baseline   # after a gap is fixed
```

Real `pm4py` / `scikit-learn` scenarios (S26, S27) run when those packages are
importable and are skipped otherwise. To run them without installing anything,
append the course venv's `Lib/site-packages` to the **end** of `sys.path` (so the
project's own pandas wins) and call `run_benchmark.py` from there.

`PM_COURSE_DIR` overrides the course location (default
`C:\Users\ABernalCaunedo\PhD_Code\PM_Course`). The course's own
`utils/event_enricher.py` is imported and used for the library-function scenarios.

`test_benchmark.py` fails only when a check that passed in `baseline.json` stops
passing. A fixed gap shows up as a warning ("improved; update the baseline").

## How it works

`harness.py` does what a marimo kernel does: each cell is parsed, rewritten by
pmprov's own `ProvTrackTransformer`, compiled and executed in one namespace with
a real `RuntimeTracker` behind it. Ground truth is taken from the live namespace
after every cell. The checks:

| check | layer | meaning |
|---|---|---|
| `recorded` | pmprov | analysis cells produce a step/state; noise cells produce none |
| `output_restorable` | pmprov | `restore_state()` returns the step's own output exactly |
| `snapshot_exact` | marimo-pmprov | the reviewer's snapshot holds every analysis variable exactly as it was |
| `params_ok` | pmprov | the call's arguments were recorded and serialised |
| `tree_delta_ok` | marimo-pmprov | the tree node's column delta matches what the step changed |
| `resume_exact` | pmprov | resuming from a past state (restore into the namespace + checkout) is exact |
| `final_namespace` | marimo-pmprov | the latest state describes the notebook as it ended (catches untracked variables) |
| `immutable_after` | both | earlier snapshots are unchanged by later cells |
| `persist_after_restart` | both | a resumed session reproduces the last snapshot |
| `annotations_roundtrip` | both | an annotation added to the last state is stored, edited (text and tags), survives a restart exactly once, and is gone, tags included, after being deleted |

## What the course code looks like (survey.md)

20 files, 317 code units, 1089 top-level statements (the `_with_solutions` and
`_BPME` notebooks repeat their base notebooks, so counts are upper bounds).

| statement form | count | pmprov sees it as |
|---|---:|---|
| `x = f(...)` / `f(...)` | 596 | tracked (but 163 `display`, 51 `print`, 43 `fig.show` are noise) |
| `x = df[cond]`, `df[cols]`, `df[:n]`, `df.loc[...]` | 62 | **not intercepted** |
| `df['col'] = ...` | 51 | **not intercepted** (tracked by accident when the right side is a call) |
| `for ...:` with mutation or display inside | 31 | not intercepted |
| `a, b, c = f(...)` | 3 | tracked, outputs are models/figures |
| `.copy()`, aliases | 3 + 6 | `copy` is omitted |

## Results

Pass rate per check by pmprov version (the benchmark grew from 38 to 41
scenarios between 0.6 and 0.8.0: the two real-library ones now run, and the
figure scenario was split in two; `annotations_roundtrip` was added for 0.9.0):

| check | pmprov 0.6 | pmprov 0.8.0 | pmprov 0.9.0 |
|---|---:|---:|---:|
| recorded | 29/38 | 41/41 | 41/41 |
| output_restorable | 31/38 | 41/41 | 41/41 |
| snapshot_exact | 27/38 | 40/41 | 41/41 |
| params_ok | 33/34 | 37/37 | 37/37 |
| tree_delta_ok | 29/38 | 41/41 | 41/41 |
| resume_exact | 1/1 | 1/1 | 1/1 |
| final_namespace | 21/38 | 39/41 | 41/41 |
| immutable_after | 14/21 | 25/26 | 26/26 |
| persist_after_restart | 27/38 | 40/41 | 41/41 |
| annotations_roundtrip | not measured | not measured | 41/41 |

Real `pm4py` (Petri nets and markings, alignments, DECLARE) and `scikit-learn`
(`train_test_split` tuple) scenarios pass. Full matrix: `out/report.md`.

## Gaps and their status

| # | gap (found against pmprov 0.6) | status |
|---|---|---|
| G1 | statements that are not `x = call(...)` were not tracked (filters, projections, slices, `df['c'] = ...`, loops, `.copy()`, `value_counts`) | fixed in 0.8.0 (S05-S07, S10, S11, S14, S22) |
| G2 | `df['c'] = x.apply(...)` and `inplace=True` changed data without reaching any state | fixed in 0.8.0 (S08, S09, S25) |
| G3 | Series, GroupBy, scalars, lists, dicts, models could not be replayed | fixed in 0.8.0 (S04, S12, S14-S17, S26, S27) |
| G4 | plotly figures stored but not restorable | fixed in 0.8.0 (S13a) |
| G5 | a mixed-type object column lost the whole artifact silently | fixed in 0.8.0 (S23_dtype_mixed_object) |
| G6 | tree delta wrong for method-style pandas | fixed in 0.8.0 (S03, S29) |
| G7 | a `dtype=str` parameter was dropped | fixed in 0.8.0 (S20) |
| G8 | `pd.set_option` recorded as a step | fixed in 0.8.0 (S18, S19) |
| G9 | `restore_state()` returned the wrong version of most variables | fixed in 0.8.0; the 12 acceptance tests in `docs/pmprov-requests/` pass |
| G10 | an object changed through another variable was not versioned (`fig` after `ax.bar(...)` / `ax.set_title(...)`) | fixed in 0.9.0 (S13b) |
| G11 | a plain alias (`df = event_log`) was not bound at any state | fixed in 0.9.0 (S22) |

No gap is open. The benchmark says nothing about scale (below), so this is
coverage of the patterns in the course code, not a performance claim.

## Follow-ups on the marimo-pmprov side

| # | follow-up | status |
|---|---|---|
| M1 | tell "not stored" apart from "not computed yet" | done: `Snapshot.status()` / `.missing()` use the state's bindings; the example notebook uses them |
| M2 | flag a step with no stored artifact | not needed: pmprov 0.8.0 no longer loses the artifact (G5) |
| M3 | launcher that makes tracking work for `marimo run` / `marimo edit` | done: `python -m provenance_widget.marimo_launcher` (verified: 4 steps recorded in both modes; neither recorded anything without it) |
| M4 | drop the per-step restore workaround | done: `PmprovAdapter.snapshot()` uses `restore_state(names=...)`, caches by artifact version, and needs pmprov >= 0.8.0 (a clear error otherwise) |
| M5 | fallback delta when pmprov's is empty | not needed: delta is correct in 0.8.0 (G6) |

## Not covered yet

- Library-specific objects other than pm4py and scikit-learn (the `rulelearn`
  rule learner) are modelled by a stateful stand-in.
- Scale: wide case logs and the 561k-row road-traffic log are not benchmarked
  (no timing or memory checks yet).
- Interactive callbacks (dash / ipywidgets) execute inside functions, so only the
  outer call can be tracked; S24 documents the composite-step behaviour.
