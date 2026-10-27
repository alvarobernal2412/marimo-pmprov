"""Runs notebook-style cells under real pmprov tracking and checks every step.

Mirrors what a marimo kernel does: each cell's source is parsed, rewritten by
pmprov's `ProvTrackTransformer` (the same transformer marimo's patched compile
uses), compiled and executed in one shared namespace, with a real
`RuntimeTracker` behind it. After each cell the harness compares what pmprov
recorded with ground truth taken from the live namespace:

  recorded            a step/state was recorded for an analysis cell (and none for noise)
  output_restorable   pmprov's restore_state() returns the step's own output exactly   [pmprov]
  snapshot_exact      the reviewer's snapshot of the state holds every analysis
                      variable exactly as it was                                     [marimo-pmprov]
  params_ok           the call's arguments were recorded and serialised              [pmprov]
  tree_delta_ok       the tree node exists and its column delta matches reality      [marimo-pmprov]
  resume_exact        resuming from a past state (restore into the namespace + checkout)
                      puts back exactly the variables that state held                 [pmprov]
  final_namespace     the latest state's snapshot holds every analysis variable the
                      notebook ended with (catches untracked variables)               [marimo-pmprov]
  immutable_after     earlier snapshots are unchanged by later cells
  persist_after_restart  a resumed session reproduces the last snapshot
  annotations_roundtrip  an annotation added to the last state is stored, edited, survives a
                      restart exactly once, and is gone after being deleted           [both]
"""
from __future__ import annotations

import ast
import contextlib
import copy
import io
import logging
import tempfile
import traceback
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

CHECKS = [
    "recorded",
    "output_restorable",
    "snapshot_exact",
    "params_ok",
    "tree_delta_ok",
    "resume_exact",
    "final_namespace",
    "immutable_after",
    "persist_after_restart",
    "annotations_roundtrip",
]


@dataclass
class Cell:
    """One notebook cell (usually one statement) of a scenario."""

    src: str
    analysis: bool | None = True  # should produce a tracked step/state; None = a policy question, either is fine
    min_steps: int = 1  # a loop may legitimately record one step per iteration
    note: str = ""
    resume_from: int | None = None  # before running: resume the analysis from the state after cell N


@dataclass
class Scenario:
    id: str
    title: str
    evidence: str  # where the pattern occurs in the course code
    cells: list[Cell]
    namespace: Callable[[], dict] = dict  # builds the initial namespace (helpers, data)
    requires: tuple[str, ...] = ()  # optional modules; scenario is skipped without them
    expect_gap: str = ""  # a gap already understood (documentation only; results decide)


@dataclass
class Outcome:
    status: str  # PASS | FAIL | NA | ERROR | SKIP
    why: str = ""


@dataclass
class CellResult:
    src: str
    checks: dict[str, Outcome] = field(default_factory=dict)
    steps: int = 0


@dataclass
class ScenarioResult:
    id: str
    title: str
    evidence: str
    cells: list[CellResult] = field(default_factory=list)
    scenario_checks: dict[str, Outcome] = field(default_factory=dict)
    skipped: str = ""
    crashed: str = ""

    def summary(self) -> dict[str, Outcome]:
        """Worst outcome of every check across the scenario's cells."""
        out: dict[str, Outcome] = {}
        for check in CHECKS:
            collected = [c.checks[check] for c in self.cells if check in c.checks]
            collected += [self.scenario_checks[check]] if check in self.scenario_checks else []
            fails = [o for o in collected if o.status in ("FAIL", "ERROR")]
            if fails:
                out[check] = fails[0]
            elif any(o.status == "PASS" for o in collected):
                out[check] = Outcome("PASS")
            else:
                out[check] = Outcome("NA")
        return out


# ---------------------------------------------------------------- equality

def clone(value: Any) -> Any:
    if isinstance(value, (pd.DataFrame, pd.Series)):
        return value.copy(deep=True)
    try:
        return copy.deepcopy(value)
    except Exception:
        return _Opaque(repr(value))


@dataclass
class _Opaque:
    text: str


def is_analysis_value(value: Any) -> bool:
    """Values pmprov could be expected to persist/replay: frames, series, figures."""
    if isinstance(value, (pd.DataFrame, pd.Series)):
        return True
    return type(value).__module__.startswith(("plotly", "matplotlib")) and hasattr(value, "to_dict" if "plotly" in type(value).__module__ else "savefig")


_NO_FINGERPRINT = object()


def _plain_repr(value: Any) -> str:
    """repr without memory addresses, so two equal objects compare equal."""
    import re

    return re.sub(r" at 0x[0-9A-Fa-f]+", "", repr(value))


def fingerprint(value: Any) -> Any:
    """A comparable summary of objects whose identity or repr is not comparable.

    Covers what the course produces besides frames: pandas GroupBy objects,
    matplotlib figures/axes/bar containers and plotly figures. Anything else
    returns _NO_FINGERPRINT and is compared normally.
    """
    kind = type(value).__module__ + "." + type(value).__name__
    if "GroupBy" in kind:
        return ("groupby", value.ngroups, value.size().to_dict())
    if kind.startswith("matplotlib.figure"):
        return ("figure", tuple(np.round(value.get_size_inches(), 2)), [fingerprint(ax) for ax in value.axes])
    if kind.startswith("matplotlib.axes"):
        return ("axes", value.get_title(), len(value.patches), len(value.lines),
                [round(float(p.get_height()), 6) for p in value.patches])
    if kind.startswith("matplotlib.container"):
        return ("container", len(value), [round(float(p.get_height()), 6) for p in value])
    if kind.endswith("petri_net.obj.PetriNet"):
        return ("petri_net", sorted(p.name for p in value.places), sorted(t.name for t in value.transitions),
                sorted((a.source.name, a.target.name) for a in value.arcs))
    if kind.endswith("petri_net.obj.Marking"):
        return ("marking", sorted((place.name, count) for place, count in value.items()))
    if kind.startswith("plotly.graph_objs"):
        return ("plotly", repr(value.to_plotly_json()))
    return _NO_FINGERPRINT


def same(truth: Any, got: Any) -> tuple[bool, str]:
    if got is None:
        return False, "variable missing from the snapshot"
    if isinstance(truth, pd.DataFrame):
        if not isinstance(got, pd.DataFrame):
            return False, f"expected a DataFrame, got {type(got).__name__}"
        try:
            pd.testing.assert_frame_equal(got, truth, check_like=False)
            return True, ""
        except AssertionError as exc:
            return False, "DataFrame differs: " + str(exc).splitlines()[0][:140]
    if isinstance(truth, pd.Series):
        if isinstance(got, pd.DataFrame) and got.shape[1] == 1:
            got = got.iloc[:, 0]
        if not isinstance(got, pd.Series):
            return False, f"expected a Series, got {type(got).__name__}"
        try:
            pd.testing.assert_series_equal(got, truth, check_names=False)
            return True, ""
        except AssertionError as exc:
            return False, "Series differs: " + str(exc).splitlines()[0][:140]
    a, b = fingerprint(truth), fingerprint(got)
    if a is not _NO_FINGERPRINT and b is not _NO_FINGERPRINT:
        return (a == b, "" if a == b else f"{a!r:.90} != {b!r:.90}")
    try:
        eq = got == truth
        return (bool(np.all(eq)), "" if np.all(eq) else f"{got!r:.60} != {truth!r:.60}")
    except Exception:
        left, right = _plain_repr(truth), _plain_repr(got)
        return (left == right, "" if left == right else "repr differs")


# ------------------------------------------------------------ AST helpers

def bound_names(tree: ast.AST) -> list[str]:
    """Variable names a cell binds or mutates (assignment targets, roots of subscripts)."""
    names: list[str] = []

    def root(node: ast.AST) -> str | None:
        while isinstance(node, (ast.Subscript, ast.Attribute)):
            node = node.value
        return node.id if isinstance(node, ast.Name) else None

    for node in ast.walk(tree):
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        for t in targets:
            for sub in ast.walk(t):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    names.append(sub.id)
                elif isinstance(sub, (ast.Subscript, ast.Attribute)) and isinstance(sub.ctx, ast.Store):
                    r = root(sub)
                    if r:
                        names.append(r)
    seen, ordered = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered


def primary_target(tree: ast.Module) -> str | None:
    """The single Name a cell assigns from a call, if that is what it does."""
    if len(tree.body) == 1 and isinstance(tree.body[0], ast.Assign):
        stmt = tree.body[0]
        if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name) and isinstance(stmt.value, ast.Call):
            return stmt.targets[0].id
    return None


def input_frame_name(tree: ast.Module) -> str | None:
    """The frame a call operates on: its receiver (`df.drop(...)`) or first argument (`f(df)`)."""
    if not (len(tree.body) == 1 and isinstance(tree.body[0], (ast.Assign, ast.Expr))):
        return None
    value = tree.body[0].value
    if not isinstance(value, ast.Call):
        return None
    func = value.func
    while isinstance(func, ast.Attribute) and isinstance(func.value, ast.Call):
        func = func.value.func  # walk down a method chain to its first receiver
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id
    if value.args and isinstance(value.args[0], ast.Name):
        return value.args[0].id
    return None


def call_arg_count(tree: ast.Module) -> int:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            return len(node.args) + len(node.keywords)
    return 0


# ----------------------------------------------------------- the session

class _LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record.getMessage())


class Session:
    """One tracked notebook session over a throwaway database."""

    def __init__(self, workdir: Path, history_name: str = "benchmark") -> None:
        import builtins

        import tracker.kernel_hooks as hooks
        from tracker import init_marimo

        self.workdir = workdir
        self.history_name = history_name
        builtins._provtrack_runtime = hooks._NoOpRuntime()
        hooks.patch_marimo_ast_compile()
        self._transformer = hooks._TRANSFORMER
        self.rt = self._open(init_marimo)
        self.ns: dict[str, Any] = {}
        self._seen_steps: set[str] = set()

    def _open(self, init_marimo):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return init_marimo(
                history_name=self.history_name,
                db_path=str(self.workdir / "prov.db"),
                artifact_dir=str(self.workdir / "artifacts"),
            )

    def reopen(self):
        """Simulate a restart: a new tracker resumed from the same database."""
        from tracker import init_marimo

        self.rt.storage._executor.submit(lambda: None).result()
        self.rt = self._open(init_marimo)
        return self.rt

    def settle(self) -> None:
        self.rt.storage._executor.submit(lambda: None).result()

    def graph(self) -> dict:
        self.settle()
        return self.rt.storage.load_graph(self.rt._history.history_id)

    def run(self, src: str) -> tuple[list[dict], list[str], str]:
        """Execute a cell; return (new steps, pmprov warnings, error text)."""
        tree = ast.parse(src)
        self._transformer.visit(tree)
        ast.fix_missing_locations(tree)
        code = compile(tree, "<cell>", "exec")
        capture = _LogCapture()
        logger = logging.getLogger("pmprov")
        logger.addHandler(capture)
        error = ""
        try:
            with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
                warnings.simplefilter("ignore")
                exec(code, self.ns)
        except Exception:
            error = traceback.format_exc(limit=3).strip().splitlines()[-1]
        finally:
            logger.removeHandler(capture)
        steps = [s for s in self.graph()["steps"] if s["step_id"] not in self._seen_steps]
        steps.sort(key=lambda s: s["timestamp"])
        self._seen_steps.update(s["step_id"] for s in steps)
        return steps, capture.records, error

    def adapter_and_panel(self, mode: str = "reviewer"):
        from provenance_widget.pmprov_adapter import PmprovAdapter
        from provenance_widget.serialize import tree_to_json
        from provenance_widget.widget import ProvenancePanel

        adapter = PmprovAdapter(self.rt)
        panel = ProvenancePanel(source=adapter, mode=mode, auto_refresh=False)
        panel.widget.tree = tree_to_json(adapter.get_tree())
        return adapter, panel


# ------------------------------------------------------------ the runner

def run_scenario(scenario: Scenario, workdir: Path | None = None) -> ScenarioResult:
    import importlib

    result = ScenarioResult(scenario.id, scenario.title, scenario.evidence)
    for module in scenario.requires:
        try:
            importlib.import_module(module)
        except Exception:
            result.skipped = f"needs {module}"
            return result

    tmp = None
    if workdir is None:
        tmp = tempfile.TemporaryDirectory(prefix="pmbench_")
        workdir = Path(tmp.name)
    try:
        return _run(scenario, workdir, result)
    except Exception:
        result.crashed = traceback.format_exc(limit=4).strip().splitlines()[-1]
        return result
    finally:
        if tmp is not None:
            with contextlib.suppress(Exception):
                tmp.cleanup()


def _run(scenario: Scenario, workdir: Path, result: ScenarioResult) -> ScenarioResult:
    session = Session(workdir, history_name=scenario.id)
    session.ns.update(scenario.namespace())
    history: list[tuple[str, dict[str, Any], str | None, int]] = []  # (state_id, truth, primary, cell index)
    previous_columns: dict[str, list[str]] = {}

    for index, cell in enumerate(scenario.cells):
        resume_outcome = None
        if cell.resume_from is not None:
            resume_outcome = _resume(session, history, cell.resume_from)
        tree = ast.parse(cell.src)
        names = bound_names(tree)
        primary = primary_target(tree)
        input_name = input_frame_name(tree)
        previous_columns_before = dict(previous_columns)  # frames as they were before this cell
        n_args = call_arg_count(tree)
        steps, warnings_seen, error = session.run(cell.src)
        cr = CellResult(src=cell.src, steps=len(steps))
        if resume_outcome is not None:
            cr.checks["resume_exact"] = resume_outcome
        result.cells.append(cr)
        if error:
            cr.checks["recorded"] = Outcome("ERROR", f"cell raised: {error[:120]}")
            continue

        # ---- recorded
        if cell.analysis is True:
            if len(steps) >= cell.min_steps:
                cr.checks["recorded"] = Outcome("PASS")
            else:
                cr.checks["recorded"] = Outcome("FAIL", f"{len(steps)} step(s) recorded, expected {cell.min_steps}+")
        elif cell.analysis is None:
            cr.checks["recorded"] = Outcome("PASS", f"policy: {len(steps)} step(s) recorded")
        else:
            cr.checks["recorded"] = (
                Outcome("PASS") if not steps else Outcome("FAIL", f"{len(steps)} step(s) recorded for a non-analysis cell")
            )

        truth = {n: clone(v) for n, v in session.ns.items() if not n.startswith("_") and is_analysis_value(v)}
        for n in names:
            if n in session.ns and n not in truth:
                truth[n] = clone(session.ns[n])
        if not steps or not cell.analysis:
            previous_columns = {n: list(v.columns) for n, v in truth.items() if isinstance(v, pd.DataFrame)}
            continue

        state_id = steps[-1]["output_state_id"]
        history.append((state_id, truth, primary, index))
        adapter, panel = session.adapter_and_panel()

        # ---- output_restorable (pmprov layer)
        if primary and primary in truth:
            try:
                result_state = session.rt.restore_state(state_id)
                ok, why = same(truth[primary], result_state.variables.get(primary))
                if not ok and primary not in result_state.variables:
                    arts = session.rt.storage.load_state_artifacts(state_id)
                    skipped = "; ".join(f"{x['name']}: {x['reason']}" for x in result_state.skipped) or "none"
                    logged = (warnings_seen or ["none"])[0][:90]
                    why = f"not restored ({type(truth[primary]).__name__}); artifacts on state: {len(arts)}; skipped: {skipped}; pmprov log: {logged}"
                cr.checks["output_restorable"] = Outcome("PASS" if ok else "FAIL", why)
            except Exception as exc:
                cr.checks["output_restorable"] = Outcome("ERROR", f"{type(exc).__name__}: {exc}"[:140])
        else:
            cr.checks["output_restorable"] = Outcome("NA")

        # ---- snapshot_exact (marimo-pmprov layer, whole notebook)
        cr.checks["snapshot_exact"] = _snapshot_outcome(panel, state_id, truth)

        # ---- params_ok (pmprov layer)
        failed = [w for w in warnings_seen if "serialis" in w.lower() or "serializ" in w.lower()]
        if failed:
            cr.checks["params_ok"] = Outcome("FAIL", failed[0][:140])
        elif n_args:
            try:
                records = session.rt.storage.load_state_detail(state_id).get("params", [])
                cr.checks["params_ok"] = (
                    Outcome("PASS") if len(records) >= n_args else Outcome("FAIL", f"{len(records)} param records for {n_args} arguments")
                )
            except Exception as exc:
                cr.checks["params_ok"] = Outcome("ERROR", str(exc)[:120])
        else:
            cr.checks["params_ok"] = Outcome("NA")

        # ---- tree_delta_ok (marimo-pmprov layer)
        node = adapter.get_tree().nodes.get(state_id)
        if node is None:
            cr.checks["tree_delta_ok"] = Outcome("FAIL", "no node for the state in the tree")
        elif primary and isinstance(truth.get(primary), pd.DataFrame) and input_name in previous_columns_before:
            added = set(truth[primary].columns) - set(previous_columns_before[input_name])
            shown = {c.name for c in node.delta.columns_added}
            cr.checks["tree_delta_ok"] = (
                Outcome("PASS") if added == shown else Outcome("FAIL", f"delta shows +{sorted(shown)}, columns actually added {sorted(added)}")
            )
        else:
            cr.checks["tree_delta_ok"] = Outcome("PASS")
        previous_columns = {n: list(v.columns) for n, v in truth.items() if isinstance(v, pd.DataFrame)}

    # ---- final_namespace: does the latest state describe the notebook as it ended?
    analysis_names: set[str] = set()
    for cell in scenario.cells:
        if cell.analysis is True:
            analysis_names.update(bound_names(ast.parse(cell.src)))
    final_truth = {
        n: clone(v) for n, v in session.ns.items()
        if not n.startswith("_") and (is_analysis_value(v) or n in analysis_names)
        and n not in scenario.namespace()
    }
    if history:
        adapter, panel = session.adapter_and_panel()
        result.scenario_checks["final_namespace"] = _snapshot_outcome(panel, history[-1][0], final_truth)
    else:
        result.scenario_checks["final_namespace"] = Outcome("FAIL", "no state was recorded at all")

    # ---- immutable_after: every earlier snapshot still holds
    if history:
        adapter, panel = session.adapter_and_panel()
        bad = []
        for state_id, truth, _, index in history[:-1]:
            outcome = _snapshot_outcome(panel, state_id, truth)
            if outcome.status != "PASS":
                bad.append(f"cell {index}: {outcome.why}")
        result.scenario_checks["immutable_after"] = (
            Outcome("PASS") if not bad else Outcome("FAIL", "; ".join(bad)[:200])
        ) if len(history) > 1 else Outcome("NA")

        # ---- persist_after_restart
        try:
            session.reopen()
            adapter, panel = session.adapter_and_panel()
            state_id, truth, _, _ = history[-1]
            result.scenario_checks["persist_after_restart"] = _snapshot_outcome(panel, state_id, truth)
        except Exception as exc:
            result.scenario_checks["persist_after_restart"] = Outcome("ERROR", f"{type(exc).__name__}: {exc}"[:140])
    if history:
        result.scenario_checks["annotations_roundtrip"] = _annotations_roundtrip(session, history[-1][0])
    return result


def _annotation_texts(session: Session, state_id: str) -> list[tuple[str, str, list[str]]]:
    """(id, note, tag names) of every annotation the tree shows on a state."""
    session.settle()
    adapter, _ = session.adapter_and_panel()
    node = adapter.get_tree().nodes.get(state_id)
    return [(a.annotation_id, a.note, sorted(t.name for t in a.tags)) for a in (node.annotations if node else [])]


def _annotations_roundtrip(session: Session, state_id: str) -> Outcome:
    """Add, edit (text and tags), restart, delete, restart: the lifecycle an analyst and a reviewer rely on."""
    try:
        _, panel = session.adapter_and_panel(mode="analyst")
        note = {
            "annotationId": "bench-1", "title": "first note", "note": "first note",
            "tags": [{"name": "bench", "color": "#64748B"}], "artifacts": [],
            "author": {"agent_id": "bench", "agent_type": "human", "display_name": "B"},
            "timestamp": "2026-01-01T00:00:00",
        }
        panel.commit_annotation(note, state_id=state_id)
        shown = _annotation_texts(session, state_id)
        if [(n, t) for _, n, t in shown] != [("first note", ["bench"])]:
            return Outcome("FAIL", f"after add the state shows {shown}")

        panel.update_annotation(
            "bench-1",
            {**note, "title": "edited note", "note": "edited note", "tags": [{"name": "bench2", "color": "#64748B"}]},
        )
        shown = _annotation_texts(session, state_id)
        if [(n, t) for _, n, t in shown] != [("edited note", ["bench2"])]:
            return Outcome("FAIL", f"after edit the state shows {shown} (expected the edited note with tag bench2)")

        session.reopen()
        shown = _annotation_texts(session, state_id)
        if [(n, t) for _, n, t in shown] != [("edited note", ["bench2"])]:
            return Outcome("FAIL", f"after a restart the state shows {shown} (expected the edited note once, with bench2)")

        stored_id = shown[0][0]
        _, fresh_panel = session.adapter_and_panel(mode="analyst")
        fresh_panel.remove_annotation(stored_id)
        if _annotation_texts(session, state_id):
            return Outcome("FAIL", "the annotation is still shown after being deleted")
        if session.rt.storage.load_tags("analysis_state", state_id):
            return Outcome("FAIL", "the deleted annotation's tags are still on the state")
        session.reopen()
        if _annotation_texts(session, state_id):
            return Outcome("FAIL", "the deleted annotation came back after a restart")
        return Outcome("PASS")
    except Exception as exc:
        return Outcome("ERROR", f"{type(exc).__name__}: {exc}"[:160])


def _resume(session: Session, history: list, cell_index: int) -> Outcome:
    """Resume from the state after cell `cell_index`, as an analyst "continue from here"."""
    entry = next((h for h in history if h[3] == cell_index), None)
    if entry is None:
        return Outcome("ERROR", f"no recorded state after cell {cell_index} to resume from")
    state_id, truth = entry[0], entry[1]
    try:
        for name in list(truth):
            session.ns.pop(name, None)  # a fresh kernel: nothing but what restore brings back
        session.rt.restore_state(state_id, into=session.ns, checkout=True)
    except Exception as exc:
        return Outcome("ERROR", f"{type(exc).__name__}: {exc}"[:140])
    problems = []
    for name, expected in truth.items():
        ok, why = same(expected, session.ns.get(name))
        if not ok:
            problems.append(f"{name}: {why}")
    return Outcome("PASS") if not problems else Outcome("FAIL", "; ".join(problems)[:240])


def _snapshot_outcome(panel, state_id: str, truth: dict[str, Any]) -> Outcome:
    try:
        snap = panel.snapshot(state_id)
    except Exception as exc:
        return Outcome("ERROR", f"{type(exc).__name__}: {exc}"[:140])
    problems = []
    for name, expected in truth.items():
        ok, why = same(expected, snap.variables.get(name))
        if not ok:
            problems.append(f"{name}: {why}")
    return Outcome("PASS") if not problems else Outcome("FAIL", "; ".join(problems)[:240])
