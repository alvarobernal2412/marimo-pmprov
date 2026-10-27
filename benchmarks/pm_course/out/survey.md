# Course code survey

20 files, 317 code units, 1089 top-level statements, 2 magic lines, 0 unparsable units.

## Statement forms (what pmprov's rewriter sees)

| form | count | share |
|---|---:|---:|
| expr_call | 333 | 30.6% |
| assign_call | 263 | 24.2% |
| assign_literal | 101 | 9.3% |
| import | 97 | 8.9% |
| def | 78 | 7.2% |
| assign_subscript_read | 62 | 5.7% |
| assign_subscript | 51 | 4.7% |
| return | 36 | 3.3% |
| for | 31 | 2.8% |
| assign_comprehension | 11 | 1.0% |
| expr_value | 8 | 0.7% |
| assign_alias | 6 | 0.6% |
| assign_unpack_call | 3 | 0.3% |
| assign_other | 3 | 0.3% |
| assign_attribute | 2 | 0.2% |
| pass | 2 | 0.2% |
| assign_expression | 1 | 0.1% |
| if | 1 | 0.1% |

Statements using `inplace=`: 0; chained callee (`a.b().c()`): 5; with a lambda: 51.

## Libraries imported (files)

- pandas: 18
- event_enricher: 18
- pm4py: 15
- plotly: 10
- dash: 10
- sklearn: 10
- sys: 6
- ipywidgets: 4
- random: 3
- helpers: 2
- re: 2
- rulelearn: 2
- itertools: 1
- matplotlib: 1
- viz: 1
- marimo: 1

## Callee roots

- display: 163
- event_log: 69
- fig: 63
- print: 51
- plotly: 39
- case_log: 32
- event_enricher: 31
- len: 26
- pm4py: 22
- marimo: 18
- cases: 15
- sklearn: 11
- pandas: 9
- grouping: 9
- filtered_event_log: 7

## Most frequent tracked-form callees

- `display` x163
- `print` x51
- `fig.show` x43
- `len` x26
- `px.histogram` x20
- `fig.update_layout` x19
- `track_variables` x19
- `case_log.apply` x19
- `mo.md` x18
- `event_log.groupby` x16
- `pm4py.read_xes` x13
- `precision_score` x10
- `cases.agg` x9
- `px.scatter` x7
- `px.ecdf` x6
- `event_log.groupby()[].apply` x6
- `sys.path.append` x6
- `cases[].last` x6
- `event_log[].apply` x5
- `random.choice` x5
- `case_log[].apply` x5
- `short_event_log.groupby` x4
- `event_log.groupby()[].count` x4
- `event_log.drop` x4
- `event_log[].value_counts` x4
- `create_case_log` x4
- `pr_gram` x4
- `grouping.agg` x3
- `event_log.groupby()[].first` x3
- `event_log.groupby().agg` x3
- `pd.DataFrame.from_records` x3
- `df.rename` x3
- `event_log.apply` x3
- `case_add_activity_incidence` x3
- `event_log.groupby()[].last` x3
- `x_train.apply` x3
- `filtered_event_log[].unique().tolist` x2
- `pd.read_csv` x2
- `grouping[].max` x2
- `result_df.reset_index` x2

## Per file

| file | cells | statements | assign_call | expr_call | assign_subscript | containers |
|---|---:|---:|---:|---:|---:|---:|
| 01 Intro\assignment1.ipynb | 8 | 23 | 6 | 9 | 0 | 0 |
| 01 Intro\purchase_example_start.ipynb | 12 | 14 | 1 | 8 | 0 | 0 |
| 02 Exploratory\event_enricher.py | 1 | 20 | 0 | 0 | 0 | 19 |
| 02 Exploratory\grouping_tutorial_sepsis.ipynb | 19 | 41 | 13 | 15 | 1 | 2 |
| 02 Exploratory\grouping_tutorial_sepsis_with_solutions.ipynb | 19 | 55 | 17 | 21 | 4 | 3 |
| 02 Exploratory\interactive_histogram.ipynb | 4 | 26 | 6 | 3 | 0 | 4 |
| 02 Exploratory\pandas-intro-sepsis.ipynb | 19 | 40 | 2 | 25 | 2 | 0 |
| 02 Exploratory\sepsis_v1.ipynb | 39 | 118 | 37 | 42 | 6 | 4 |
| 02 Exploratory\sepsis_v1_BPME.ipynb | 44 | 115 | 29 | 39 | 5 | 6 |
| 02 Exploratory\sepsis_v1_with_solutions.ipynb | 39 | 130 | 40 | 46 | 8 | 5 |
| 03_KPIs\sepsis_v2.ipynb | 16 | 81 | 17 | 23 | 11 | 5 |
| 06_Conformance\sepsis_v4.ipynb | 20 | 83 | 20 | 22 | 6 | 5 |
| 07_DD\event_enricher.py | 1 | 20 | 0 | 0 | 0 | 19 |
| 07_DD\helpers.py | 1 | 1 | 0 | 0 | 0 | 1 |
| 07_DD\rule_induction_sepsis.ipynb | 21 | 102 | 34 | 29 | 4 | 7 |
| 07_DD\sepsis_v5.ipynb | 15 | 65 | 22 | 20 | 2 | 0 |
| 07_DD\viz.py | 1 | 4 | 0 | 0 | 0 | 1 |
| main.py | 1 | 2 | 0 | 0 | 0 | 2 |
| rule_induction_sepsis_marimo.py | 36 | 129 | 19 | 31 | 2 | 8 |
| utils\event_enricher.py | 1 | 20 | 0 | 0 | 0 | 19 |
