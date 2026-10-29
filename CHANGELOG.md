# Changelog

## 0.2.4

### Fixed
- The exported PDF draws what the analyst picked. A target now carries a snapshot of the element it was picked on,
  and the report draws that snapshot instead of looking a variable up at the recorded step, which returned an
  unrelated table for tables built inside a display cell.
- "Export PDF" with a live source no longer waits for the source's storage queue. It builds the report from what
  the sidebar holds, on its own thread, so it finishes in seconds while a long history is still being written.
- The target of a picked table cell or column names the column ("column Attribute") instead of running the column's
  name into its type and distinct count.

### Added
- `show(element, artifact_id, artifact_name, value=...)` makes any element pickable. Snapshots have a `kind`:
  a table (its head, as shown), text, or an image (matplotlib, Altair, Plotly and PIL figures). `show_chart` takes
  the underlying `figure` so a picked chart is drawn as an image.
- `export_pdf(include_authors=False, include_settings=False)`: the report no longer lists the author or the
  step's settings unless asked to, and prints only short scalar settings of the step itself.

### Changed
- Step labels in the report read as words and are cut at the first bracket or parenthesis and at 40 characters
  (a chained call used to print whole).

## 0.2.3

### Fixed
- A long analysis history no longer slows the notebook down. The panel's background refresh re-read every
  recorded state from the database every 0.75 s (one connection each), which kept a core busy once a history held a
  few hundred states and starved the notebook. A recorded state never changes, so `PmprovAdapter` now builds each
  node once and reloads only the annotations of states they changed on, and the panel pushes the tree to the browser
  only when it changed.
- With a live source, the first tree is built by the refresh thread instead of while the panel is constructed, so
  opening a notebook on a large history no longer waits for it.
- "Export PDF" with a live source runs on the same background worker as annotation writes, after the writes already
  queued, instead of on marimo's kernel thread, where it froze every other UI element while pmprov's storage queue drained.

## 0.2.2

### Fixed
- Saving, editing or removing an annotation in the sidebar no longer freezes the notebook. With a live pmprov
  history the save waited, on marimo's kernel thread, for pmprov's storage queue (which can hold minutes of
  artifact writes), so every other UI element (dropdowns, sliders, the PDF export) stopped responding until it
  drained. These writes now run, in order, on a background worker for live sources. Fixed sources are unchanged.

### Added
- `ProvenancePanel.wait_for_persistence(timeout=None)` blocks until the queued annotation writes have reached the
  source, for scripts and tests.

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
