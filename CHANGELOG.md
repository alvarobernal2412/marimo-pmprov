# Changelog

## 0.2.1

### Fixed
- A note typed in the sidebar before the first analysis step was recorded (or while the sidebar's tree was
  still empty) carried the "composer" placeholder and was silently dropped, so it vanished after a restart.
  It now attaches to the latest state the source has recorded, and is kept and saved as soon as the first step
  appears.
- Failures to save, edit or remove an annotation are logged as warnings instead of being swallowed.

## 0.2.0

### Added
- Reviewer replay: step through recorded states (first, back, next, latest) with a
  debugger-like stepper, branch choice and redo memory. Each state re-renders the
  whole notebook as its immutable pmprov snapshot (view only).
- Replay button on every annotation.
- Edit and delete annotations, with timestamps ordered by time.
- Annotations can target the whole analysis (the latest state) by clearing the target.
- `ProvenancePanel(mode=...)` fixes the persona when the panel is created.
- `show_tree` option (construction time, off by default) to show the Tree tab.
- `panel.snapshot(state_id)` and `panel.reactive_cursor(mo.state)` for notebooks that
  render a replayed state.
- `python -m provenance_widget.marimo_launcher run|edit notebook.py` to track
  notebooks started with `marimo run` or `marimo edit`.
- `examples/annotate_notebook.py` (filters, two charts, annotations) and a course-operations benchmark in `benchmarks/pm_course/`.
- Export PDF (analyst): the annotation history as a report in Source Sans (bundled, SIL OFL), in time order, with
  tags, step number and each targeted output drawn as the analysis showed it (marimo-style tables,
  matplotlib, Altair and Plotly figures). Also `panel.export_pdf(path)`. Needs the `pdf` extra.
- `pmprov` optional extra (`pmprov>=0.9`, Python 3.13+).

### Changed
- The `student` persona is now `analyst`. `"student"` still works as a deprecated alias.
- Compact annotation list with icon-only actions and a Pick button in the form.
- The Config tab is removed.
- pmprov 0.9.0 is recommended. Older versions replay through a slower fallback.

### Fixed
- The annotation text box no longer clears while typing.
- Deleting or editing an annotation keeps pmprov tags in sync, also after a restart.
