# Benchmark report: course operations vs pmprov / marimo-pmprov

Each scenario is a pattern found in the course code (see `survey.md`). Checks:

- `recorded` (pmprov)
- `output_restorable` (pmprov)
- `snapshot_exact` (marimo-pmprov)
- `params_ok` (pmprov)
- `tree_delta_ok` (marimo-pmprov)
- `resume_exact` (pmprov)
- `final_namespace` (marimo-pmprov)
- `immutable_after` (both)
- `persist_after_restart` (both)
- `annotations_roundtrip` (both)

## Matrix

| scenario | recorded | output_restorable | snapshot_exact | params_ok | tree_delta_ok | resume_exact | final_namespace | immutable_after | persist_after_restart | annotations_roundtrip |
|---|---|---|---|---|---|---|---|---|---|---|
| S01_library_function | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S02_enricher_mutates_argument | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S03_method_rebinding | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S04_groupby_chain | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S05_boolean_mask_filter | pass | pass | pass | - | pass | - | pass | pass | pass | pass |
| S06_projection_and_slice | pass | pass | pass | - | pass | - | pass | pass | pass | pass |
| S07_query_and_loc_filters | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S08_column_assign_in_place | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S09_column_assign_transform | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S10_column_assign_in_loop | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S11_dtype_conversion_loop | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S12_tuple_unpack_model | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S13a_plotly_figures | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S13b_matplotlib_axes_mutation | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S14_lambda_argument | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S15_scalar_results | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S16_list_dict_results | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S17_stateful_estimator | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S18_display_noise | pass | pass | pass | - | pass | - | pass | - | pass | pass |
| S19_write_side_effects | pass | pass | pass | - | pass | - | pass | - | pass | pass |
| S20_read_csv_variants | pass | pass | pass | pass | pass | - | pass | - | pass | pass |
| S21_rerun_with_changed_parameter | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S22_alias_and_copy | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S24_function_body_operations | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S25_inplace_methods | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S26_train_test_split | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S27_real_pm4py | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S28_resume_and_branch | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass |
| S29_receiver_vs_argument_delta | pass | pass | pass | pass | pass | - | pass | pass | pass | pass |
| S23_dtype_tz_datetime | pass | pass | pass | pass | pass | - | pass | - | pass | pass |
| S23_dtype_naive_datetime | pass | pass | pass | pass | pass | - | pass | - | pass | pass |
| S23_dtype_timedelta | pass | pass | pass | pass | pass | - | pass | - | pass | pass |
| S23_dtype_categorical | pass | pass | pass | pass | pass | - | pass | - | pass | pass |
| S23_dtype_bool | pass | pass | pass | pass | pass | - | pass | - | pass | pass |
| S23_dtype_nullable_int | pass | pass | pass | pass | pass | - | pass | - | pass | pass |
| S23_dtype_list_values | pass | pass | pass | pass | pass | - | pass | - | pass | pass |
| S23_dtype_dict_values | pass | pass | pass | pass | pass | - | pass | - | pass | pass |
| S23_dtype_mixed_object | pass | pass | pass | pass | pass | - | pass | - | pass | pass |
| S23_dtype_python_date | pass | pass | pass | pass | pass | - | pass | - | pass | pass |
| S23_dtype_string_with_none | pass | pass | pass | pass | pass | - | pass | - | pass | pass |
| S23_dtype_float_nan | pass | pass | pass | pass | pass | - | pass | - | pass | pass |
| **pass rate** | 41/41 | 41/41 | 41/41 | 37/37 | 41/41 | 1/1 | 41/41 | 26/26 | 41/41 | 41/41 |

## Findings
