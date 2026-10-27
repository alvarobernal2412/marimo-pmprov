"""Benchmark scenarios: one per operation pattern found in the course code.

Each scenario is a short notebook-style program in the exact statement form the
course uses (see out/survey.md for the counts). "evidence" cites where.
Library-specific patterns use stand-ins that return the same kinds of objects
(a Petri net tuple, a list of alignment dicts, a fitted estimator) so the suite
runs without pm4py/scikit-learn; real-library variants run when installed.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from harness import Cell, Scenario

CASE_ID = "case:concept:name"
ACTIVITY = "concept:name"
TS = "time:timestamp"
COURSE_DIR = Path(os.environ.get("PM_COURSE_DIR", r"C:\Users\ABernalCaunedo\PhD_Code\PM_Course"))


# ------------------------------------------------------------------ data

def make_event_log(n_cases: int = 40, seed: int = 0) -> pd.DataFrame:
    """A small sepsis-like event log: tz-aware timestamps, NaNs, mixed columns."""
    rng = np.random.default_rng(seed)
    activities = ["ER Registration", "ER Triage", "ER Sepsis Triage", "Leucocytes", "CRP", "Admission NC", "Release A"]
    start = pd.Timestamp("2014-10-22", tz="UTC")
    rows = []
    for case in range(n_cases):
        t = start + pd.Timedelta(days=int(rng.integers(0, 400)))
        age = float(rng.integers(20, 90))
        group = [None, "A", "B", "C"][int(rng.integers(0, 4))]
        for k in range(int(rng.integers(3, 8))):
            t = t + pd.Timedelta(hours=int(rng.integers(1, 30)))
            rows.append({
                CASE_ID: f"C{case}",
                ACTIVITY: activities[k % len(activities)],
                TS: t,
                "lifecycle:transition": "complete",
                "org:group": group,
                "Age": age if k % 2 == 0 else np.nan,
            })
    return pd.DataFrame(rows)


def make_dtype_frame(name: str) -> pd.DataFrame:
    """A two-row frame holding one column of the given course-relevant dtype."""
    import datetime

    columns = {
        "tz_datetime": pd.to_datetime(["2014-01-01", None], utc=True),
        "naive_datetime": pd.to_datetime(["2014-01-01", "2014-01-02"]),
        "timedelta": pd.to_timedelta([1, None], unit="h"),
        "categorical": pd.Categorical(["a", "b"]),
        "bool": [True, False],
        "nullable_int": pd.array([1, None], dtype="Int64"),
        "list_values": [["A", "B"], ["A"]],  # concept:name::append in the course
        "dict_values": [{"k": 1}, None],
        "mixed_object": [1, "x"],
        "python_date": [datetime.date(2014, 1, 1), datetime.date(2014, 1, 2)],  # df[ts].dt.date
        "string_with_none": ["p", None],
        "float_nan": [1.5, float("nan")],
    }
    return pd.DataFrame({"value": columns[name]})


DTYPE_CASES = [
    "tz_datetime", "naive_datetime", "timedelta", "categorical", "bool", "nullable_int", "list_values",
    "dict_values", "mixed_object", "python_date", "string_with_none", "float_nan",
]


def make_rich_frame() -> pd.DataFrame:
    """Every dtype the course frames carry: lists, timedeltas, categoricals, nullable, NA."""
    return pd.DataFrame({
        "ts": pd.to_datetime(["2014-01-01", "2014-01-02", None], utc=True),
        "delta": pd.to_timedelta([1, 2, None], unit="h"),
        "cat": pd.Categorical(["a", "b", "a"]),
        "flag": [True, False, True],
        "count": pd.array([1, None, 3], dtype="Int64"),
        "variant": [["A", "B"], ["A"], ["A", "C", "B"]],  # concept:name::append in the course
        "mixed": [1, "x", None],
        "payload": [{"k": 1}, {"k": 2}, None],
        "text": ["p", None, "r"],
    })


# ------------------------------------------------------- namespaces/stubs

def _course_functions() -> dict:
    path = COURSE_DIR / "utils" / "event_enricher.py"
    if not path.exists():
        return {}
    spec = importlib.util.spec_from_file_location("course_event_enricher", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["course_event_enricher"] = module
    spec.loader.exec_module(module)
    return {n: getattr(module, n) for n in (
        "create_case_log", "event_add_relative_case_time", "case_add_activity_incidence",
        "event_add_order_classifier", "event_add_relative_log_time",
    )}


class PetriNetStub:
    def __init__(self, places: int) -> None:
        self.places = places

    def __repr__(self) -> str:
        return f"PetriNet(places={self.places})"

    def __eq__(self, other) -> bool:
        return isinstance(other, PetriNetStub) and other.places == self.places


class Explainer:
    """Stand-in for rulelearn.RipperExplainer: stateful, fitted in place."""

    def __init__(self) -> None:
        self.rules: list[str] = []

    def fit(self, frame, target) -> None:
        self.rules = [f"{c} > 0" for c in frame.columns[:2]]

    def explain(self) -> list[str]:
        return list(self.rules)

    def __eq__(self, other) -> bool:
        return isinstance(other, Explainer) and other.rules == self.rules


def discover_model(log):
    """pm4py.discover_petri_net_inductive-shaped: (net, initial marking, final marking)."""
    return PetriNetStub(log[ACTIVITY].nunique()), {"start": 1}, {"end": 1}


def alignments_stub(log):
    """pm4py.conformance_diagnostics_alignments-shaped: a list of dicts."""
    return [{"fitness": 1.0, "alignment": [("a", "a")]}, {"fitness": 0.5, "alignment": [("a", ">>")]}]


def precision_score_stub(truth, predicted) -> float:
    return float((truth == predicted).mean())


def keep_since(log, year):
    return log[log[TS].dt.year >= year].copy()


def base_ns(**extra) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ns = {
        "pd": pd, "np": np, "plt": plt,
        "CASE_ID": CASE_ID, "ACTIVITY": ACTIVITY, "TS": TS,
        "STANDARD_COLUMNS": [CASE_ID, ACTIVITY, TS],
        "make_event_log": make_event_log, "make_rich_frame": make_rich_frame, "make_dtype_frame": make_dtype_frame,
        "keep_since": keep_since, "display": lambda *a, **k: None,
    }
    ns.update(extra)
    return ns


def course_ns(**extra) -> dict:
    ns = base_ns(**extra)
    ns.update(_course_functions())
    return ns


EV = Cell("event_log = make_event_log()")  # the tracked load that starts most scenarios


# ------------------------------------------------------------- scenarios

SCENARIOS: list[Scenario] = [
    Scenario(
        "S01_library_function", "Course library function: x = f(df)",
        "create_case_log x4 (sepsis_v1, rule_induction); the baseline tracked form",
        [EV, Cell("case_log = create_case_log(event_log)")], course_ns),

    Scenario(
        "S02_enricher_mutates_argument", "Enricher mutates its argument in place and returns it",
        "event_add_relative_case_time x2, case_add_activity_incidence x3: `df['c'] = ...; return df`",
        [EV,
         Cell("event_log = event_add_relative_case_time(event_log)"),
         Cell("case_log = create_case_log(event_log)"),
         Cell("case_log = case_add_activity_incidence(case_log, event_log)")], course_ns),

    Scenario(
        "S03_method_rebinding", "Method call that rebinds the same name",
        "event_log = event_log.drop/sort_values (sepsis_v1), case_log.dropna x2, df.rename x3",
        [EV,
         Cell("event_log = event_log.drop(columns=['lifecycle:transition'])"),
         Cell("event_log = event_log.sort_values(by=[TS, CASE_ID])"),
         Cell("event_log = event_log.rename(columns={'Age': 'age'})"),
         Cell("event_log = event_log.reset_index(drop=True)")], base_ns),

    Scenario(
        "S04_groupby_chain", "groupby().agg() chains, GroupBy objects and Series results",
        "event_log.groupby x16, cases.agg x9, groupby()[].first/apply (sepsis_v1, grouping_tutorial)",
        [EV,
         Cell("cases = event_log.groupby(CASE_ID)", note="a lazy GroupBy object, not data"),
         Cell("case_log = cases.agg(start=(TS, 'first'), n=(ACTIVITY, 'count'))"),
         Cell("last_seen = event_log.groupby(CASE_ID, as_index=False)[TS].max()"),
         Cell("ages = event_log.groupby(CASE_ID)['Age'].first()", note="a Series result")], base_ns),

    Scenario(
        "S05_boolean_mask_filter", "Boolean-mask row filter: x = df[cond]",
        "assignment1, purchase_example, pandas-intro-sepsis: event_log[event_log['concept:name'] == ...]",
        [EV,
         Cell("filtered = event_log[event_log[ACTIVITY] == 'CRP']"),
         Cell("adults = event_log[(event_log['Age'] > 40) & event_log['org:group'].notna()]")], base_ns),

    Scenario(
        "S06_projection_and_slice", "Column projection, slice and row/column reads",
        "projected_event_log = event_log[STANDARD_COLUMNS]; short = projected[:61]; event_log.loc[0]",
        [EV,
         Cell("projected = event_log[STANDARD_COLUMNS]"),
         Cell("short = projected[:20]"),
         Cell("row = event_log.loc[0]", note="a Series (one row)"),
         Cell("column = event_log[ACTIVITY]", note="a Series (one column)")], base_ns),

    Scenario(
        "S07_query_and_loc_filters", "query() and .loc row filters",
        "filtered_event_log.query('1 <= amount <= 25') (assignment1), event_log.loc[...]",
        [EV,
         Cell("older = event_log.query('Age >= 40')"),
         Cell("loc_filtered = event_log.loc[event_log['Age'] > 50]")], base_ns),

    Scenario(
        "S08_column_assign_in_place", "New column by subscript assignment: df['c'] = expr",
        "34 uses: event_log['weekday'], ['young'], ['date'], ['admission_time'] (sepsis_v1, pandas-intro)",
        [EV,
         Cell("event_log['weekday'] = event_log[TS].apply(lambda x: x.weekday())"),
         Cell("event_log['young'] = event_log['Age'] < 35"),
         Cell("event_log['date'] = event_log[TS].dt.date"),
         Cell("case_log = event_log.groupby(CASE_ID).agg(n=(ACTIVITY, 'count'))")], base_ns),

    Scenario(
        "S09_column_assign_transform", "Column from groupby().transform(lambda)",
        "event_log['relative_case_time'] = event_log.groupby(...).transform(lambda x: x - x.min())",
        [EV, Cell("event_log['rel'] = event_log.groupby(CASE_ID)[TS].transform(lambda x: x - x.min())")], base_ns),

    Scenario(
        "S10_column_assign_in_loop", "Columns assigned inside a for loop",
        "for outcome in outcomes: case_log[outcome] = case_log[outcome + '::count'] > 0 (rule_induction)",
        [EV,
         Cell("case_log = event_log.groupby(CASE_ID).agg(n=(ACTIVITY, 'count'))"),
         Cell("for outcome in ['A', 'B']:\n    case_log[outcome] = case_log['n'] > 3", min_steps=1)], base_ns),

    Scenario(
        "S11_dtype_conversion_loop", "dtype conversion loop on a training frame",
        "for column in x_train.select_dtypes(include=['bool']).columns: x_train[column] = ...astype(...)",
        [EV,
         Cell("case_log = event_log.groupby(CASE_ID).agg(n=(ACTIVITY, 'count'))"),
         Cell("case_log['big'] = case_log['n'] > 3"),
         Cell("x_train = case_log.copy()"),
         Cell("for column in x_train.select_dtypes(include=['bool']).columns:\n    x_train[column] = x_train[column].astype('object')")], base_ns),

    Scenario(
        "S12_tuple_unpack_model", "Tuple-unpacked non-DataFrame outputs (a process model)",
        "pn, im, fm = pm4py.discover_petri_net_inductive(...) (sepsis_v4); net, im, fm = bpmn_converter.apply(...)",
        [EV, Cell("pn, im, fm = discover_model(event_log)")],
        lambda: base_ns(discover_model=discover_model)),

    Scenario(
        "S13a_plotly_figures", "Plotly figures built and mutated in place",
        "fig = px.histogram(...); fig.update_layout(...) x19; fig.show() x43 (sepsis_v1, v2)",
        [EV,
         Cell("hist = px.histogram(event_log, x='Age')"),
         Cell("hist.update_layout(title='Age')", note="in-place mutation of a tracked plotly figure"),
         Cell("hist.show()", analysis=False)],
        lambda: base_ns(px=__import__("plotly.express", fromlist=["express"])), requires=("plotly",)),

    Scenario(
        "S13b_matplotlib_axes_mutation", "A matplotlib figure changed through its axes",
        "fig, ax = plt.subplots(); ax.bar(...); ax.set_title(...) (sepsis_v2)",
        [EV,
         Cell("fig, ax = plt.subplots()"),
         Cell("bars = ax.bar([1, 2, 3], [3, 1, 2])", note="mutates fig through ax"),
         Cell("ax.set_title('Release Combinations')", note="mutates fig through ax; returns a Text")],
        base_ns),

    Scenario(
        "S14_lambda_argument", "Callable argument and Series[bool] result",
        "case_log.apply(lambda case: case['Admission_IC::count'] == 0, axis=1) x15 (rule_induction)",
        [EV,
         Cell("case_log = event_log.groupby(CASE_ID).agg(n=(ACTIVITY, 'count'))"),
         Cell("explanation = case_log.apply(lambda case: case['n'] > 4, axis=1)"),
         Cell("outcome = case_log['n'] > 4")], base_ns),

    Scenario(
        "S15_scalar_results", "Scalar results used later",
        "precision = precision_score(outcome, explanation) x10; n = len(df); min_timestamp = df[c].min()",
        [EV,
         Cell("min_timestamp = event_log[TS].min()"),
         Cell("precision = precision_score_stub(event_log['Age'] > 0, event_log['Age'] > 50)")],
        lambda: base_ns(precision_score_stub=precision_score_stub)),

    Scenario(
        "S16_list_dict_results", "list / dict results",
        "activities = list(activity_stats.index); combo_counts = dict(...); diagnostics = alignments(...)",
        [EV,
         Cell("activities = list(event_log[ACTIVITY].unique())"),
         Cell("counts = dict(event_log[ACTIVITY].value_counts())"),
         Cell("diagnostics = alignments_stub(event_log)")],
        lambda: base_ns(alignments_stub=alignments_stub)),

    Scenario(
        "S17_stateful_estimator", "Stateful object fitted in place (rule learner)",
        "estimator = RipperExplainer(); estimator.fit(x_train, target); rule_set = estimator.explain()",
        [EV,
         Cell("case_log = event_log.groupby(CASE_ID).agg(n=(ACTIVITY, 'count'))"),
         Cell("estimator = Explainer()"),
         Cell("estimator.fit(case_log, case_log['n'] > 3)", note="mutates the estimator; returns None"),
         Cell("rule_set = estimator.explain()")],
        lambda: base_ns(Explainer=Explainer)),

    Scenario(
        "S18_display_noise", "Display / inspection calls must not create states",
        "display x163, print x51, fig.show x43, event_log.head(2), event_log.info(), bare names",
        [EV,
         Cell("display(event_log)", analysis=False),
         Cell("print(event_log.shape)", analysis=False),
         Cell("event_log.head(2)", analysis=False, note="returns a DataFrame but is a view"),
         Cell("event_log.info()", analysis=False),
         Cell("event_log", analysis=False),
         Cell("pd.set_option('display.max_columns', None)", analysis=False)], base_ns),

    Scenario(
        "S19_write_side_effects", "Writing results out (sinks)",
        "filtered_event_log.to_csv('registration_events.csv'); pm4py.write_xes(...)",
        [EV,
         Cell("event_log.to_csv(OUT, index=False)", analysis=None, note="a sink: no new data; recording it is a policy choice")],
        lambda: base_ns(OUT=str(Path(os.environ.get("TEMP", ".")) / "pmbench_out.csv"))),

    Scenario(
        "S20_read_csv_variants", "Reading data with dict/list parameters",
        "pd.read_csv(path, parse_dates=[...], dtype={...}) (purchase_example, assignment1)",
        [Cell("event_log = pd.read_csv(CSV, parse_dates=[TS], dtype={'org:group': str})")],
        lambda: _csv_ns()),

    Scenario(
        "S21_rerun_with_changed_parameter", "Cell re-run after a control changes (marimo style)",
        "interactive_histogram / marimo notebooks: the same step re-executed with new parameter values",
        [EV,
         Cell("year = 2014", analysis=False),
         Cell("since = keep_since(event_log, year)"),
         Cell("year = 2015", analysis=False),
         Cell("since = keep_since(event_log, year)"),
         Cell("case_log = create_case_log(since)"),
         Cell("year = 2014", analysis=False),
         Cell("since = keep_since(event_log, year)")], course_ns),

    Scenario(
        "S22_alias_and_copy", "Aliases and copies of tracked frames",
        "x_train = filtered_case_log.copy(); df = event_log; short_event_log = projected[:61]",
        [EV,
         Cell("case_log = event_log.groupby(CASE_ID).agg(n=(ACTIVITY, 'count'))"),
         Cell("x_train = case_log.copy()"),
         Cell("x_train['extra'] = 1"),
         Cell("df = event_log", note="an alias: a step bound to the existing version, no new data")], base_ns),

    Scenario(
        "S24_function_body_operations", "A user function that performs several operations inside",
        "def duration(group) + grouping.pipe(duration); dash/ipywidgets callbacks (10 notebooks)",
        [EV,
         Cell("def derive(log):\n    kept = log[log['Age'].notna()]\n    return kept.groupby(CASE_ID).agg(n=(ACTIVITY, 'count'))", analysis=False),
         Cell("case_log = derive(event_log)")], base_ns),

    Scenario(
        "S25_inplace_methods", "In-place methods that return None",
        "df.drop(..., inplace=True), sort_values(inplace=True), fillna(inplace=True): not in the course, common in pandas",
        [EV,
         Cell("event_log.drop(columns=['lifecycle:transition'], inplace=True)"),
         Cell("event_log.sort_values(by=TS, inplace=True)")], base_ns),

    Scenario(
        "S26_train_test_split", "Multi-output split of a frame (sklearn)",
        "scikit-learn imported by 10 notebooks; x_train / target built from filtered_case_log",
        [EV,
         Cell("case_log = event_log.groupby(CASE_ID).agg(n=(ACTIVITY, 'count'))"),
         Cell("train, test = train_test_split(case_log, test_size=0.3, random_state=0)")],
        lambda: base_ns(train_test_split=__import__("sklearn.model_selection", fromlist=["x"]).train_test_split),
        requires=("sklearn",)),

    Scenario(
        "S27_real_pm4py", "Real pm4py discovery, alignments and DECLARE",
        "pm4py.discover_petri_net_inductive, conformance_diagnostics_alignments, discover_declare (sepsis_v4)",
        [EV,
         Cell("event_log = pm4py.format_dataframe(event_log, case_id=CASE_ID, activity_key=ACTIVITY, timestamp_key=TS)"),
         Cell("pn, im, fm = pm4py.discover_petri_net_inductive(event_log)"),
         Cell("diagnostics = pm4py.conformance_diagnostics_alignments(event_log, pn, im, fm)"),
         Cell("declare_model = pm4py.discover_declare(event_log)")],
        lambda: base_ns(pm4py=__import__("pm4py")), requires=("pm4py",)),
]


SCENARIOS.append(Scenario(
    "S28_resume_and_branch", "Analyst resumes from a past state and continues (branch)",
    "marimo notebooks re-run from an earlier point; 'resume' / 'navigate back to a past state' (pmprov checkout)",
    [EV,
     Cell("case_log = create_case_log(event_log)"),
     Cell("event_log = event_log.sort_values(by=[TS, CASE_ID])"),
     Cell("event_log = event_log.drop(columns=['Age'])"),
     Cell("pass", analysis=False, resume_from=1, note="resume from the state right after create_case_log"),
     Cell("event_log = event_log.rename(columns={'org:group': 'group'})", note="a new branch from the resumed state"),
     Cell("case_log = create_case_log(event_log)")],
    course_ns))


SCENARIOS.append(Scenario(
    "S29_receiver_vs_argument_delta", "Same operation as a method (receiver) and as a function (argument)",
    "pandas style in the course is almost always the method form: event_log.groupby().agg(), df.rename(), df.merge()",
    [EV,
     Cell("case_log = event_log.groupby(CASE_ID).agg(n=(ACTIVITY, 'count'))"),
     Cell("method_merged = event_log.merge(case_log, left_on=CASE_ID, right_index=True)"),
     Cell("function_merged = pd.merge(event_log, case_log, left_on=CASE_ID, right_index=True)"),
     Cell("method_assigned = event_log.assign(flag=1)"),
     Cell("function_assigned = assign_flag(event_log)")],
    lambda: base_ns(assign_flag=lambda df: df.assign(flag=1))))


def _csv_ns() -> dict:
    path = Path(os.environ.get("TEMP", ".")) / "pmbench_log.csv"
    make_event_log().to_csv(path, index=False)
    return base_ns(CSV=str(path))


# One scenario per dtype so a failure names the dtype that does not survive storage.
SCENARIOS += [
    Scenario(
        f"S23_dtype_{name}", f"Storage round trip of a {name} column",
        "dtypes carried by course frames (lists from ::append, dates from .dt.date, tz-aware timestamps, NA)",
        [Cell(f"frame = make_dtype_frame({name!r})")], base_ns)
    for name in DTYPE_CASES
]


def _ns_with_dtype_frames() -> dict:  # kept for the namespace of S23 scenarios
    return base_ns(make_dtype_frame=make_dtype_frame)
