# `play-oem` — Implementation Plan

Requirements: [PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md). Architecture:
[PLAY_OEM_DESIGN.md](./PLAY_OEM_DESIGN.md).

## How to use this plan

Work **one pending numbered step at a time, in order**. Do not begin a later pending step until
the current step's checklist and completion criteria pass. Keep pending steps in chronological
dependency order; each dependency field identifies its prerequisite, including prerequisites
that have been moved to the completed section at the end of this document. Step 1 has no
dependency.

When a step is complete, move its full entry to the `Completed steps` section at the end of this
document. Preserve its original number, status, progress, checklist, completion criteria and
dependency so the completion record remains auditable. The active work sequence stays at the
beginning in dependency order.

If implementation cannot progress in the documented order, stop and reevaluate the plan before
starting work out of sequence. Update the step order, dependencies, completion criteria and
status/progress fields here so the plan reflects the actual dependency order, then continue from
the revised sequence. Do not bypass a blocked or incomplete prerequisite without documenting
and resolving the change in sequence.

If the implementation approach changes in a way that affects the architecture, interfaces,
backends, CLI behavior or other design decisions, update
[PLAY_OEM_DESIGN.md](./PLAY_OEM_DESIGN.md) as needed before proceeding with dependent steps.
If the change alters user-facing requirements or behavior, update
[PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md) as well. Keep the implementation plan and design
consistent with the implementation.

For every step, keep the status and progress fields current:

- `Not started` — no work begun.
- `In progress` — implementation or its checks are underway.
- `Blocked` — cannot proceed; record the blocker.
- `Done` — all checklist items and completion criteria pass.

Progress is the number of checklist items completed. Update the step's status and count as work
advances; do not mark a step done based only on code being written.

The first full playback demo is **step 10**. It should be possible to open a sample OEM, play,
pause and seek it, and see a synchronized 3D orbit and time-series plot before implementing
the remaining views, advanced controls or VTK.

## Milestone B — Playback core

## Milestone C — First runnable GUI and demo

### 8. Animate the time-series cursor

Implement `speed_altitude.update(t_s)` and connect it to the shared playback clock. Keep the
full series fixed while the cursor follows the clock. Ensure seeking updates the figure even
when playback is paused.

- **Status:** Not started.
- **Progress:** 0/3 checklist items.
- [ ] Move the cursor on clock ticks.
- [ ] Move the cursor immediately after a seek while paused.
- [ ] Test cursor positions at the start, an interior time and the end.

**Done when:** the time-series view stays synchronized with the clock under playback and
random seeks.
**Depends on:** Step 7.

### 9. Add basic play, pause, seek and speed controls

Add the play/pause button, `Space` shortcut, timeline slider, UTC/elapsed readouts and basic
speed selection (at least `1x` and `10x`). Slider interaction should seek; clock updates should
update the slider without causing a feedback seek.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Wire play/pause button and `Space` to the clock.
- [ ] Wire slider drag/click to seek.
- [ ] Synchronize the slider from the clock using a feedback guard.
- [ ] Wire basic speed selection and display the selected rate.
- [ ] Test control callbacks and verify the UI remains responsive during playback.

**Done when:** a user can play, pause, seek and change between at least two speeds in the GUI.
**Depends on:** Step 8.

### 10. Add the Matplotlib 3D orbit and deliver the first demo

Implement `views/trajectory3d/mpl_backend.py` from the existing `plot-oem` state-vector plotting
code. Draw the orbit once; update the satellite marker from `CursorState`. Open this view and
the speed/altitude view as the default `overview`.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Draw the 3D orbit path with labeled axes and frame context.
- [ ] Move the satellite marker from the shared cursor state.
- [ ] Open trajectory and speed/altitude views together as `overview`.
- [ ] Verify play, pause, seeking and basic speed changes keep both views synchronized.
- [ ] Run a manual demo with a repository test OEM and confirm normal close/SIGINT behavior.

**First demo / done when:** `play-oem tests/data/ISS_2026-05-20.OEM` opens the control window,
3D orbit and speed/altitude plot; play, pause, seek and speed changes visibly work.
**Depends on:** Step 9.

## Milestone D — Complete playback and seeking

### 11. Add full speed range, reverse and playback CLI options

Expand the speed control to 1x–1000x with presets; add direction toggle and `R`; implement
`--speed`, `--reverse`, `--start`, `--autoplay`, `--loop` and `--fps`. Reverse without an
explicit start begins at the timeline end.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Add log-scale speed selection and presets through 1000x.
- [ ] Add direction toggle and signed-rate readout; reverse without moving the cursor.
- [ ] Implement and validate the listed CLI options.
- [ ] Test forward/reverse boundary pause and loop behavior in the GUI and CLI.
- [ ] Test invalid speed, start time and FPS values produce clear errors.

**Done when:** the full playback range and reverse direction work from controls and CLI.
**Depends on:** Step 10.

### 12. Add direct time entry and seek shortcuts

Support elapsed-duration and UTC input, sample/time stepping, start/end shortcuts and click-to-seek.
Plot clicks must not intercept Matplotlib pan/zoom interactions.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Parse elapsed durations and UTC epochs; show invalid input without changing the clock.
- [ ] Add sample stepping, minute stepping and start/end keyboard shortcuts.
- [ ] Add click-to-seek when the plot toolbar is not in pan/zoom mode.
- [ ] Test seeks while playing, paused and reversed.
- [ ] Verify all open views follow each seek.

**Done when:** each documented random-seek interaction reaches the requested timeline time
without altering speed or direction.
**Depends on:** Step 11.

## Milestone E — Full dashboard and plot set

### 13. Add the view registry, groups and toolbar

Implement one registry for individual views and groups. Add toolbar actions to open/raise a view
without duplication, and connect `--plots` to the same registry. Preserve `overview` as the
default launch selection.

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Register `overview`, `state`, `motion` and `all` groups.
- [ ] Add individual-view toolbar buttons and open/raise behavior.
- [ ] Implement comma-separated `--plots` names/groups and validate unknown names.
- [ ] Test group expansion and duplicate-open behavior.

**Done when:** toolbar and CLI launch selections use the same tested registry.
**Depends on:** Step 12.

### 14. Add the state-components view

Split the X/Y/Z and VX/VY/VZ histories from the original state-vector plot into a dedicated
Matplotlib view. Add it to the State group and preserve the `state-vectors` compatibility alias
for opening both state components and the 3D trajectory.

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Build the position and velocity component plots with units and frame labels.
- [ ] Add synchronized cursor artists and click-to-seek behavior.
- [ ] Add view and alias names to the registry.
- [ ] Test group and alias behavior.

**Done when:** the State group and compatibility alias open the expected views.
**Depends on:** Step 13.

### 15. Add remaining motion and geometry diagnostics

Refactor the original RTN deltas, angular velocity, direction change and geocentric distance
figures into individual `build`/`update` views. Add each to the registry and Motion diagnostics
group.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Add RTN delta view.
- [ ] Add angular velocity and direction-change views.
- [ ] Add geocentric distance view.
- [ ] Synchronize cursor and click-to-seek behavior across the new views.
- [ ] Compare plotted data and labels with the corresponding `plot-oem` figures.

**Done when:** every planned view is independently openable and synchronized.
**Depends on:** Step 14.

### 16. Add current-state readouts and OEM data context

Populate the control dashboard from `CursorState` and OEM metadata. Keep common values visible
and put less-used metadata in a collapsed details panel.

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Display position, velocity, speed and altitude with units and validity checks.
- [ ] Display object, frame, center, time span and sample count.
- [ ] Display whether cursor values are sampled or interpolated.
- [ ] Add a details panel for less-used metadata and test missing metadata behavior.

**Done when:** the dashboard presents key state and source context without relying on plot
windows.
**Depends on:** Step 15.

### 17. Implement segment and data-gap handling

Ensure the loader/series preserve OEM segment boundaries; plot each segment separately and
never interpolate or draw a continuous line across a gap. Keep the timeline seekable through a
gap while indicating that no state is available there.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Identify and preserve segment boundaries during loading and filtering.
- [ ] Render each segment separately and mark boundaries in applicable views.
- [ ] Return gap status from cursor lookup without carrying forward prior values.
- [ ] Show unavailable state readouts and gap status while seeking through gaps.
- [ ] Test interpolation and plotting on a multi-segment OEM.

**Done when:** no view or readout implies continuous or interpolated data across an OEM gap.
**Depends on:** Step 16.

## Milestone F — Performance

### 18. Optimize rendering and validate playback performance

Add blitting and display decimation for 2D views, per-view throttling for Matplotlib 3D and frame
dropping. Profile before changing algorithms; keep full-resolution data for cursor lookup.

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Add and test blitting with correct invalidation on resize/redraw.
- [ ] Add display-only decimation for large histories.
- [ ] Throttle Matplotlib 3D updates without slowing the playback clock.
- [ ] Benchmark all views open at 1000x with an OEM of at least 100k samples.

**Done when:** the UI remains interactive at the performance target in N1 and cursor values
remain correct.
**Depends on:** Step 17.

## Milestone G — Optional VTK 3D backend

### 19. Prototype VTK/Tk integration and add backend selection

Before implementing the full VTK scene, create a minimal VTK render window driven by the Tk
timer. After validating event handling on the development platform, add `Trajectory3DView`
backend selection, `--3d-backend {auto,vtk,matplotlib}` and the optional `vtk` dependency.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Open and close a minimal VTK window alongside the Tk control window.
- [ ] Pump VTK events and rendering from the Tk timer; verify interaction remains responsive.
- [ ] Verify behavior on macOS; record any platform limitation before proceeding.
- [ ] Add backend selection and clear behavior for auto, explicit VTK and Matplotlib.
- [ ] Add/document the optional VTK install extra without making it a base dependency.

**Done when:** the minimal integration is stable enough to proceed, and backend selection
works with and without VTK installed.
**Depends on:** Step 18.

### 20. Implement the VTK trajectory scene

Implement the complete VTK backend behind the same view contract: orbit polyline, WGS84 Earth,
satellite marker, direction-aware tail and trackball camera.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Build the static orbit, Earth and camera scene.
- [ ] Update marker and tail from the same cursor state as Matplotlib.
- [ ] Verify rotate/zoom interaction while playing and seeking.
- [ ] Add backend contract tests, using a test-safe VTK rendering setup where supported.
- [ ] Test explicit VTK errors and `auto` fallback when VTK/rendering is unavailable.

**Done when:** VTK and Matplotlib views produce equivalent cursor state and both honor the
same playback controls.
**Depends on:** Step 19.

## Milestone H — Release readiness

### 21. Cross-platform polish and smoke tests

Run the application and test suite on supported platforms. Resolve lifecycle, error-message and
window-management issues without introducing silent fallbacks.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Verify clear errors for missing Tk and explicit-but-unavailable VTK.
- [ ] Verify `--help`, invalid arguments, SIGINT and clean window shutdown.
- [ ] Smoke-test macOS, Linux and Windows; record any backend-specific limitations.
- [ ] Run focused tests and performance benchmark.
- [ ] Resolve all failures found in these checks.

**Done when:** supported workflows pass on target platforms or documented limitations are
explicit and accepted.
**Depends on:** Step 20.

### 22. Publish finished-tool documentation and confirm command separation

Write the user-facing `docs/tools/PLAY_OEM.md`, update README tool listings and
[TODO.md](../development/TODO.md). Keep `plot-oem` as the separate static-plot command and
`play-oem` as the interactive playback command. Share numerical/data-processing code only when
compatibility with both commands is verified.

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Document installation, CLI, controls, views, backends and limitations.
- [ ] Update README and TODO references.
- [ ] Document the separate responsibilities of `plot-oem` and `play-oem`.
- [ ] Review all cross-links and examples.

**Done when:** user-facing documentation matches tested behavior and the migration decision is
documented.
**Depends on:** Step 21.

## Completed steps

### 1. Scaffold the package and command

Create `src/ephem_toolkit/play_oem/` with `__init__.py`, `__main__.py` and `play_oem_cli.py`.
Add the `play-oem` console entry point in `pyproject.toml`. Implement argument parsing for the
input path and `--help`; do not add GUI or playback behavior yet.

- **Status:** Done.
- **Progress:** 3/3 checklist items.
- [x] `play-oem --help` exits successfully and shows the command synopsis.
- [x] `play-oem` without an input reports a normal argparse usage error.
- [x] Add focused CLI/entry-point tests and run them.

**Done when:** the installed project exposes `play-oem` and its minimal CLI tests pass.
**Depends on:** None.

### 2. Copy and verify OEM loading and series computation

Copy the relevant code from `plot_oem` into the new package: `time_unit.py`, `data.py` (OEM
reading and duration filtering), and `series.py` (including `OrbitSeries` and computed
diagnostics). Keep this step as close to the existing implementation as possible; change only
imports, package references or structure required to make the copy work.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Read an existing test OEM through the new loader.
- [x] Verify duration filtering produces the same timestamps as `plot-oem`.
- [x] Compare computed series values with `plot-oem` for a representative OEM.
- [x] Add or adapt focused data/series tests and run them.

**Done when:** the new package loads and computes the same baseline series as `plot-oem`.
**Depends on:** Step 1.

### 3. Wire the CLI to load and prepare OEM data

Add `--duration` and `--time-unit` with the same accepted values and behavior as `plot-oem`.
Wire `play-oem` to parse the duration, load states with the new package modules, filter them,
compute the series and print a concise processing summary. The command will become interactive
when the GUI is implemented in step 6.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Add `--duration` and `--time-unit` options with the same accepted values as `plot-oem`.
- [x] Wire CLI execution to parse options, read/filter OEM states and compute the orbit series.
- [x] Confirm a valid OEM prints the loaded/selected state counts and processes the selected time unit.
- [x] Add focused CLI workflow/error tests and run them.

**Done when:** `play-oem` loads a valid OEM, applies duration and time-unit options, computes its
series and reports success without rendering figures or opening a window.
**Depends on:** Step 2.

### 4. Implement and test `PlaybackClock`

Add pure-Python `clock.py` with timeline bounds, current time, signed playback rate, playing
state and loop behavior. Implement `tick`, `seek`, play/pause/toggle, speed/direction changes,
reverse, sample/time stepping and observer notification.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Implement monotonic-time advancement and clamping at both timeline ends.
- [x] Implement loop wrap in forward and reverse directions.
- [x] Implement seek, step, speed changes and reverse without changing the current time.
- [x] Cover paused, playing, boundary and loop behavior with unit tests.
- [x] Verify observers receive updates after ticks and seeks.

**Done when:** all clock tests pass without importing Tk or Matplotlib.
**Depends on:** Step 3.

### 5. Implement direction-independent cursor lookup

Add `cursor.py` to resolve the OEM state and derived values at a requested timeline time.
Use a fresh `searchsorted` lookup and the existing interpolation machinery; represent exact
sample, interpolated, and out-of-range/gap status explicitly. Segment-aware gap behavior is
completed in step 17; do not silently carry a previous sample forward.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Implement lookup for exact samples and times between samples.
- [x] Return explicit status and a clear unavailable state where no valid value can be resolved.
- [x] Check representative position/velocity values against `core/interpolator`.
- [x] Test identical state values when a time is reached forward, backward and by random seek.

**Done when:** cursor lookup is deterministic, direction-independent and unit-tested without
opening a display.
**Depends on:** Step 4.

### 6. Create the Tk app shell and lifecycle

Add `app.py` and the initial `control_window.py`. Create one Tk root, a minimal control window,
an `after()` timer driven by `time.monotonic()`, and reliable close/SIGINT handling. Start with
the timer updating a visible elapsed-time label; do not open plot windows yet.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Launch a Tk root from the `play-oem <input_oem>` CLI path.
- [x] Tick the clock from the Tk timer and display current elapsed/UTC time.
- [x] Stop the timer and destroy cleanly when the window closes.
- [x] Handle SIGINT without leaving the application process running.

**Done when:** the command opens and closes a minimal functioning control window on the
development platform.
**Depends on:** Step 5.

### 7. Define the view lifecycle and build the first static time-series view

Add the toolkit-neutral `View` protocol and a Matplotlib `speed_altitude` view. Implement
`build` to draw the static speed and altitude histories, including axis labels, units and a
cursor artist. Connect the view window lifecycle to the app.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Define a view interface with build, update and close behavior.
- [x] Build the speed/altitude figure from the computed series.
- [x] Add a cursor artist at the initial time.
- [x] Test building and closing the view with a non-interactive Matplotlib backend.

**Done when:** the app can open and close one static time-series view from an OEM.
**Depends on:** Step 6.
