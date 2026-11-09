# Changelog

## 0.8.0

### Added
- The player can stand before the first step. **Step 0 (start)** is the state where nothing has been computed yet: First and Back from
  step 1 go there, and Next leaves it for step 1. Step *n* of the player is then the step whose result is on screen, and the first
  Next shows what step 1 made. A notebook that reads `panel.snapshot(...)` sees nothing computed at the start; `INITIAL_STATE` (in
  `provenance_widget.snapshot`) is the id the cursor has there.
- While the notebook catches up with a step, the player says so: a spinner and "Rebuilding the notebook for step n...". The player
  sends a ping (`replay_ping`) right behind the move and the kernel answers it (`replay_pong`) once the redraw is over. A step that
  draws no table or map of its own then says that, so a quiet step does not look like a stuck one.

## 0.7.1

### Fixed
- The PDF export draws a Plotly figure on a machine that has no Chrome browser, such as a hosted notebook. Plotly's image export
  (kaleido) needs Chrome; the export now downloads one the first time it needs it (picking an element never does) and says why when
  it cannot, instead of the misleading "install the kaleido package".

## 0.7.0

### Added
- `ProvenancePanel(empty_hint=...)`: the line the analyst's list shows while there is no annotation yet. A course can use it to say how
  to write one (what to pick, which tags). Without it the list says "None yet. Add the first one above.", as before.

### Fixed
- An annotation written while the browser was offline is sent to the notebook when the browser is back online. Before, it stayed on
  the page, never reached the notebook, and was lost on a reload.
- Replay (and stepping) opens the tab that holds the table or map an annotation points at, so that it can be outlined. Before,
  a target in a tab the reader was not on stayed out of sight.

### Changed
- A pinned table cell or column blinks until the reviewer clicks, presses Escape or replays another annotation, like a pinned node or
  link of a map. A whole table or map keeps the short outline.

## 0.6.0

### Fixed
- The PDF export draws the output of a step that returns several variables (`figure, meta = ...`). It used to say that the output
  could not be recovered, because the step does not say which of its variables an annotation is about. When exactly one of them is a
  table or a figure, that one is used; when none or several are, nothing is guessed and the report says so, as before.

### Changed
- The PDF report shows which part of a map an annotation is about. For a Plotly Sankey (such as a Linear Continuous Process Mapper
  map), the pinned node or link is drawn in colour with the rest faded, and its name and number of cases are written on the
  figure. A pin that is not found, or that matches several marks, leaves the figure as it was.
- The report words a pinned link or node plainly (`link into A_Cancelled, 6,840 cases`) instead of the recorded
  `{...} -> {...} (A_Cancelled (6840))`.
- Entries are grouped under a heading per task when they carry `task8`, `task 9`, ... tags. A map drawn for the same step and
  element is drawn once; later entries say "Same as Figure n".
- A small dict of numbers, such as the counts of a summary step, is drawn as a table, not as Python text.
- The summary says "written 06 Nov 2026, 23:25" when the first and the last annotation were written in the same minute.

## 0.5.2

### Changed
- Replay makes a pinned node or link of a map blink until the reviewer moves on. A short pulse was easy to miss on a small mark.
  The mark is filled and outlined in amber, fades in and out, and stops on a click or Escape, when another annotation is replayed,
  or after a minute. Tables, cells and whole artifacts keep the short outline.

## 0.5.1

### Fixed
- Replay finds the pinned cell, node or link of a map that has to be drawn again. Moving the stepper redraws the maps of the
  notebook, which for a large map takes longer than the first look at it, and Replay then stayed on the outline of the whole map.
  It now keeps looking, for a few seconds, until the pinned element is there.

## 0.5.0

### Added
- Replay points at what an annotation pinned, not at the whole artifact. A pinned table cell or column is outlined in the table,
  and a pinned node or link of a Plotly Sankey (such as a Linear Continuous Process Mapper map) is outlined on the map. The picker
  can now pin a Sankey node or link; a node is recorded by its label and a link as `source -> target (label)`.
- A pinned cell is recorded with its value (`row 2, column amount = 30`). On replay the recorded row is used while it still holds
  that value; if the table was sorted, filtered or paged differently, the one row that holds it is used. When the value is in
  several rows, in none, or on another page, the whole table is outlined instead of a wrong cell. A cell recorded by an earlier
  version has no value and is found by its row, as before.
- `frontend/src/locators.ts`: the lookup from a recorded pin back to its element, the counterpart of the detail resolvers.
  Pins it cannot find, and kinds without a locator, keep the outline around the whole artifact.

## 0.4.6

### Changed
- The player stays in view while you read the annotations: the sidebar no longer scrolls as a whole, only the annotation list does.
- A closed annotation reads "Step 3: first 30 characters…" (the step number is the one the player shows) so the list is an even
  column; clicking it opens the whole note, tags and artifacts, and clicking again folds it shut.

## 0.4.5

### Fixed
- The tags of a note belong to that note. pmprov keeps tags per step, so every note on a step showed the tags of all the notes
  on it (an intent and its findings, written on the same map, all showed `#intent #finding`). The adapter now keeps each note's
  own tags in `note_tags.json` next to `provenance.db`, shows them on that note alone, and keeps pmprov's tags of the step as
  their union. A note saved by an earlier version has no record and shows its step's tags, as before.

## 0.4.4

### Added
- Stepping through a recorded analysis flashes what the step produced. When a reviewer moves the stepper (not only when they press
  Replay on a note), the tables and maps the notebook shows under that step's own state id are scrolled into view and outlined, so
  it is easy to see where a step shows up. `Snapshot.produced_here(name)` says whether the step the snapshot ends at (re)bound a
  name; a notebook gives such an output the snapshot's `state_id` as its `artifact_id`, and an earlier output a different one.

## 0.4.3

### Added
- `Sync` knows when a course is closed: a save the server refuses because the course's closing time has passed gives the status
  `closed` ("This course is closed, so your work is no longer saved. What you saved before is kept.") and is not retried. Restoring
  still works, so a closed course can be read.

## 0.4.2

### Changed
- `Sync` saves sooner: a change is sent 2 seconds after the last one (it was 5), checked every second. While a change is waiting
  its status is `pending` ("Saving your latest changes… please wait a moment before closing this page."), so a student can
  tell when it is safe to close the page; it returns to `saved` once the change is on the server, or when it turned out not
  to change anything.
- `zip_provenance` leaves out stored values over 500 KB (it was 2 MB). Maps and tables are a few KB to a few tens of KB; what
  the limit removes are copies of a whole event log, which made the zip several MB for no benefit. Pass `max_artifact_bytes`
  to change it.
- `zip_provenance` makes the same zip for the same contents: the files' modification times are no longer written into it. A
  file that was only touched used to change the zip, and `Sync` saved an identical copy again.

## 0.4.1

### Fixed
- `Sync` could not save while pmprov had `provenance.db` open on Windows (the zip raised `PermissionError`), and the failure
  ended the background saver for good. It now reads the folder while holding pmprov's connection lock, so no connection has the
  file open and the copy is consistent, and a failed attempt is reported as status `busy` and tried again. The saver no longer
  stops on any one failure.

## 0.4.0

### Added
- `provenance_widget.sync.Sync`: keeps a provenance folder on a `provenance-sync` server under the student's key. `restore()`
  brings the stored work back into an empty (or older) folder when a notebook opens, `push()` saves a changed folder, and
  `start()` saves in the background a few seconds after the last change. It never raises into the notebook: what goes wrong
  (wrong key, no connection, a copy saved from another tab) becomes `status`, in words a student can act on. Another
  student's local copy is never uploaded under a key, and work that was never synced is put aside, not overwritten. The key
  is held in memory and is not written into the provenance folder.
- `PmprovAdapter.repeated_runs(min_length=4)`: sequences of steps that were run again (the same functions with the same
  arguments, one after another), and `describe_run()` for a sentence about each. Nothing is filtered or removed: it only says
  where to look, and a single step run twice is not flagged.

## 0.3.1

### Fixed
- Picking a very large Plotly Sankey (more than 1,500 nodes, such as a sequence-based process map of a whole log) no longer
  blocks the notebook for many seconds: the picture of it is not rendered for the annotation, and the exported report draws
  it from the recorded step instead.

## 0.3.0

### Added
- Pressing Replay on a note in the reviewer now points at what the note is about: the notebook scrolls to the
  targeted table or chart (found by the name it was picked under) and an outline flashes around it. It needs the
  notebook to show that element with `show_table`, `show_chart` or `show`.

### Fixed
- The stepper said "Viewing an earlier step. Notebook outputs still show the latest run." on every earlier step. It now
  says so only when the notebook's cells do not follow the replay cursor (`panel.reactive_cursor`).

### Removed
- The `↺ @tag` button on a note, its "Restoring parameters to ..." banner, `ProvenancePanel.request_restore()`,
  `acknowledge_restore()` and the `restore_request` / `restore_ack` traits. Nothing consumed the request: no parameter was
  restored and the banner never went away. The button did what Replay does, so Replay is the way to jump to a note's step.

## 0.2.5

### Fixed
- A note keeps what it was written about. The element an analyst picked (which map or table, the clicked part) was
  held only by the sidebar, and a reloaded note, such as in the reviewer, fell back to "step id - Whole dataset".
  It is now saved in `picked_elements.json` next to `provenance.db` (so it travels with the folder, and without the
  snapshot of the value) and read back with the note. Deleting a note removes its entry.

### Added
- `provenance_widget.portable`: `zip_provenance(folder)` zips a history without the stored values that are too big to
  carry (over 2 MB each, and the largest ones when the artifacts pass 25 MB in total) and says what it left out;
  `unpack_provenance(zip_bytes, folder)` unzips it refusing paths outside the folder; `relocate_artifacts(db, dir)`
  repoints the stored paths. A step whose value was left out still shows in the history, it just cannot restore it.
- Apache License 2.0 (`LICENSE`, and `license` in the package metadata).
- `guides/portable-provenance.md`: moving a stored history to another machine (for example from molab to a laptop), why the
  stored artifact paths break the restore of maps and tables, and the short fix.

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
