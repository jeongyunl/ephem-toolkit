# `play-oem` — Implementation Plan

Requirements: [PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md). Software design:
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md). GUI development:
[PLAY_OEM_GUI_DESIGN.md](./old/PLAY_OEM_GUI_DESIGN.md). Completed selected-layout record:
[PLAY_OEM_GUI_WX_MIGRATION.md](./old/PLAY_OEM_GUI_WX_MIGRATION.md).

Ground Stations is implemented. See its
[completion report](./old/PLAY_OEM_GROUND_STATIONS_IMPLEMENTATION_REPORT.md) and
[user guide](../../tools/PLAY_OEM_GROUND_STATIONS.md). The original software/GUI designs and
mockups are archived in [old/](./old/).

## Current runtime behavior

The completed steps below are an implementation history and may record behavior that has since
changed. Current `play-oem` loads the full OEM file and selects the time-axis unit from its span
(minutes below one hour, hours otherwise). Playback speed, direction, seeking, and render rate are
controlled in the GUI. The Settings pane FPS slider ranges from 1 to 30 FPS (default 30). Its timer
advances the clock across all complete elapsed frame periods, redraws once, and drops intermediate
frames when rendering overruns.

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

For a numbered step with substeps, keep completed substeps under the active parent until every
substep is done. Then move the entire parent entry, including all substep statuses and evidence,
to `Completed steps` as one unit.

If implementation cannot progress in the documented order, stop and reevaluate the plan before
starting work out of sequence. Update the step order, dependencies, completion criteria and
status/progress fields here so the plan reflects the actual dependency order, then continue from
the revised sequence. Do not bypass a blocked or incomplete prerequisite without documenting
and resolving the change in sequence.

If the implementation approach changes in a way that affects the architecture, interfaces,
backends, CLI behavior or other design decisions, update
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md) as needed before proceeding with dependent steps.
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

## Current directive — complete migration to wxPython

The original Tk implementation in completed steps 6–14 is historical work, not completion of
the current GUI requirement. Migrate the entire existing `play-oem` GUI to wxPython before
adding the remaining views and dashboard features. Keep the playback clock, cursor lookup,
OEM loading, computed series, CLI semantics, and view data contract toolkit-independent where
possible. The finished application must have one wx event loop and no runtime Tk dependency,
Tk-specific fallback, or Tk-only GUI path. Use Matplotlib's wx canvas for plots; retain VTK as
an optional 3D backend only if its wx integration is validated.

Migration guardrails:

- Target GUI stack: `wx.App`, `wx.Frame`, `wx.Timer`, Matplotlib `FigureCanvasWxAgg`, and
  wx-native controls (`Slider`, `TextCtrl`, `Button`, `Panel`, `Menu`) instead of Tk widgets.
- Preserve all playback/data semantics in the model layer; only the UI and event plumbing move
  to wxPython.
- Keep the core CLI and data-processing code runnable in headless environments. Backend-neutral
  Matplotlib tests use `MPLBACKEND=Agg`; tests that create `wx.App` use wx under a virtual display
  on Linux (`xvfb-run`).
- The migration is not complete until the proof gate passes: no `tkinter` imports remain in the
  active `play-oem` implementation, no `TkAgg` or `PhotoImage`/PPM fallback code remains in the
  supported path, and the runtime installed via the documented GUI extra launches in a real wx
  session.
- Installation: GUI dependencies are declared as a `playback` extra in `pyproject.toml`
  (`pip install "ephem-toolkit[playback]"`). Step 15 resolves the extra with Poetry for
  development. This repository ignores `poetry.lock`, so clean installs use the declared
  dependency constraints rather than a committed lock. The base install must not require
  wxPython. VTK remains a separate optional extra only if step 20 records `VTK-KEEP`.

Steps 15–23 document the wxPython migration and its acceptance. The remaining dashboard and
plot-set work follows in the active steps below. Update
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md) in step 15 so the architecture agrees
with this directive. Use [PLAY_OEM_GUI_DESIGN.md](./old/PLAY_OEM_GUI_DESIGN.md) for
GUI-focused implementation and improvement guidance. The first Tk playback demo in step 10
remains a historical milestone; a wxPython demo must pass the migration acceptance criteria in
step 23.

## Milestone L — Release readiness

### 28. Cross-platform polish and publish documentation

Run the application and test suite on supported platforms. Resolve lifecycle, error-message,
dependency, and window-management issues without introducing silent fallbacks. Publish
`docs/tools/PLAY_OEM.md`, update README tool listings and [TODO.md](../../development/TODO.md),
and keep `plot-oem` as the separate static-plot command.

- **Status:** Not started.
- **Progress:** 0/8 checklist items.
- [ ] Verify clear errors for missing wxPython/Matplotlib and explicit-but-unavailable VTK.
- [ ] Verify `--help`, invalid arguments, SIGINT, and clean wx window shutdown.
- [ ] Smoke-test macOS, Linux, and Windows; record backend-specific limitations.
- [ ] Run focused tests and the performance benchmark.
- [ ] Document wxPython installation, CLI, controls, views, backends, and limitations.
- [ ] Update README and TODO references and document `plot-oem` versus `play-oem`.
- [ ] Review all cross-links and command examples against tested behavior.
- [ ] Resolve all failures found in release checks or record an explicit accepted limitation.

**Done when:** supported workflows pass on target platforms or documented limitations are
explicit and accepted, and user-facing documentation matches tested wxPython behavior.
**Depends on:** Step 27.

## Completed steps

Steps 6–14 record the Tk implementation. They keep their original status for auditability and
are superseded by the wxPython migration in steps 15–23.

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

**Superseded by steps 15–23 (wxPython migration).** The notes below describe the Tk implementation.

**Implementation notes:** Use classic Tk buttons rather than themed widgets for the elapsed and
UTC readouts. Keep each value on its own flat, single-line button with explicit colors; this
keeps the readout visible on the legacy macOS Tk 8.5 runtime.

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

**Superseded by steps 15–23 (wxPython migration).** The notes below describe the Tk implementation.

**Implementation notes:** Detect the Tcl/Tk patch level when opening the view. Tk 8.6+ uses the
Matplotlib `TkAgg` canvas. The verified macOS Tk 8.5.9 runtime leaves `TkAgg` canvases and native
Canvas drawings blank, but renders raster images in classic Tk buttons. Its fallback therefore
uses Matplotlib Agg to rasterize the complete speed/altitude figure to one PPM image, preserving
its standard axes, ticks, labels and styling. Keep plot clicks mapped through the rendered axes
bounds, and flush Tk layout before the initial Matplotlib draw.

### 8. Animate the time-series cursor

Implement `speed_altitude.update(t_s)` and connect it to the shared playback clock. Keep the
full series fixed while the cursor follows the clock. Ensure seeking updates the figure even
when playback is paused.

- **Status:** Done.
- **Progress:** 3/3 checklist items.
- [x] Move the cursor on clock ticks.
- [x] Move the cursor immediately after a seek while paused.
- [x] Test cursor positions at the start, an interior time and the end.

**Done when:** the time-series view stays synchronized with the clock under playback and
random seeks.
**Depends on:** Step 7.

**Superseded by steps 15–23 (wxPython migration).** The notes below describe the Tk implementation.

**Implementation notes:** Clock notifications update the Matplotlib cursor and call
`draw_idle()` on Tk 8.6+, or move synchronized red cursor columns on the legacy-Tk Matplotlib
raster image.
Unsubscribe the view when its window closes.

### 9. Add basic play, pause, seek and speed controls

Add the play/pause button, `Space` shortcut, timeline slider, UTC/elapsed readouts and basic
speed selection (at least `1x` and `10x`). Slider interaction should seek; clock updates should
update the slider without causing a feedback seek.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Wire play/pause button and `Space` to the clock.
- [x] Wire slider drag/click to seek.
- [x] Synchronize the slider from the clock without feeding changes back into `seek()`.
- [x] Wire basic speed selection and display the selected rate.
- [x] Test control callbacks and verify the UI remains responsive during playback.

**Done when:** a user can play, pause, seek and change between at least two speeds in the GUI.
**Depends on:** Step 8.

**Superseded by steps 15–23 (wxPython migration).** The notes below describe the Tk implementation.

**Implementation notes:** Use a `PhotoImage` timeline graphic displayed in a classic Tk button
because the native Scale is not visible on the verified macOS Tk 8.5.9 runtime. The draggable
slider tracks a normalized timeline fraction and maps it to the clock bounds; disable seeking
for a zero-duration timeline. Clock updates redraw the image without invoking the pointer seek
handler.

### 10. Add the Matplotlib 3D orbit and deliver the first demo

Implement `views/trajectory3d/mpl_backend.py` from the existing `plot-oem` state-vector plotting
code. Draw the orbit once; update the satellite marker from `CursorState`. Open this view and
the speed/altitude view as the default `overview`.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Draw the 3D orbit path with labeled axes and frame context.
- [x] Move the satellite marker from the shared cursor state.
- [x] Open trajectory and speed/altitude views together as `overview`.
- [x] Verify play, pause, seeking and basic speed changes keep both views synchronized.
- [x] Run a manual demo with a repository test OEM and confirm normal close/SIGINT behavior.

**First demo / done when:** `play-oem tests/data/ISS_2026-05-20.OEM` opens the control window,
3D orbit and speed/altitude plot; play, pause, seek and speed changes visibly work.
**Depends on:** Step 9.

### 11. Add full speed range, reverse and playback CLI options

Expand the speed control to 1x–1000x with presets; add direction toggle and `R`; implement
`--speed`, `--reverse`, `--start`, `--autoplay`, `--loop` and `--fps`. Reverse without an
explicit start begins at the timeline end.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Add log-scale speed selection and presets through 1000x.
- [x] Add direction toggle and signed-rate readout; reverse without moving the cursor.
- [x] Implement and validate the listed CLI options.
- [x] Test forward/reverse boundary pause and loop behavior in the GUI and CLI.
- [x] Test invalid speed, start time and FPS values produce clear errors.

**Done when:** the full playback range and reverse direction work from controls and CLI.
**Depends on:** Step 10.

### 12. Add direct time entry and seek shortcuts

Support elapsed-duration and UTC input, sample/time stepping, start/end shortcuts and click-to-seek.
Plot clicks must not intercept Matplotlib pan/zoom interactions.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Parse elapsed durations and UTC epochs; show invalid input without changing the clock.
- [x] Add sample stepping, minute stepping and start/end keyboard shortcuts.
- [x] Add click-to-seek when the plot toolbar is not in pan/zoom mode.
- [x] Test seeks while playing, paused and reversed.
- [x] Verify all open views follow each seek.

**Done when:** each documented random-seek interaction reaches the requested timeline time
without altering speed or direction.
**Depends on:** Step 11.

**Superseded by steps 15–23 (wxPython migration).** The notes below describe the Tk implementation.

**Implementation notes:** Native Entry widgets were mapped but visually blended into the dark
macOS Tk 8.5.9 control window. The visible input surface uses a PhotoImage-backed classic button
that focuses an Entry text buffer and mirrors typed text; Return and Seek submit that same buffer.

### 13. Add the view registry, groups and toolbar

Implement one registry for individual views and groups. Add toolbar actions to open/raise a view
without duplication, and connect `--plots` to the same registry. Preserve `overview` as the
default launch selection.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Register `overview`, `state`, `motion` and `all` groups.
- [x] Add individual-view toolbar buttons and open/raise behavior.
- [x] Implement comma-separated `--plots` names/groups and validate unknown names.
- [x] Test group expansion and duplicate-open behavior.

**Done when:** toolbar and CLI launch selections use the same tested registry.
**Depends on:** Step 12.

**Implementation notes:** [registry.py](../../../src/ephem_toolkit/play_oem/views/registry.py)
defines canonical view names and group expansion for both the toolbar and CLI. The toolbar enables
only groups whose views are implemented; the CLI reports unavailable views instead of opening
partial groups. Step 14 enables the State group; Step 15 will enable Motion and All.

### 14. Add the state-components view

Split the X/Y/Z and VX/VY/VZ histories from the original state-vector plot into a dedicated
Matplotlib view. Add it to the State group and preserve the `state-vectors` compatibility alias
for opening both state components and the 3D trajectory.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Build the position and velocity component plots with units and frame labels.
- [x] Add synchronized cursor artists and click-to-seek behavior.
- [x] Add view and alias names to the registry.
- [x] Test group and alias behavior.

**Done when:** the State group and compatibility alias open the expected views.
**Depends on:** Step 13.

**Superseded by steps 15–23 (wxPython migration).** The notes below describe the Tk implementation.

**Implementation notes:** The six position and velocity component traces use one shared time
axis and synchronized cursor lines. The legacy Tk path displays a Matplotlib-rendered PPM and
retains click-to-seek and cursor updates without requiring Tcl/Tk 8.6.

### 15. Define the wxPython target architecture, capture the Tk baseline and add the GUI dependency

Record the wxPython decision and target event/window ownership model in
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md). Inventory every Tk-dependent file and helper, capture
the current Tk behavior as a baseline before any code is replaced, and add the wxPython
dependency so steps 16–21 can run the GUI. Do not add new Tk functionality or begin feature work
during this migration.

- **Status:** Done.
- **Progress:** 8/8 checklist items.
- [x] Update the design document to make wxPython the sole GUI framework and document the
      wx application, frame, timer, plot-window, and shutdown ownership model.
- [x] Inventory Tk-dependent production code: `control_window.py`, `app.py`, and
      `views/state_components.py` import `tkinter`; `views/raster.py`,
      `views/speed_altitude.py`, and `views/trajectory3d/mpl_backend.py` hold PPM/PhotoImage
      raster helpers; `tests/ephem_toolkit/play_oem/test_play_oem_app.py` uses Tk fakes and mocks
      `FigureCanvasTkAgg`. A repository search found no additional Tk-dependent production or test
      files. Remaining design/plan references are historical alternatives or superseded Tk steps.
- [x] Capture the Tk baseline before replacing code: for `tests/data/ISS_2026-05-20.OEM`, record
      speed, altitude, position/velocity components, 3D orbit extents, axis labels, units and
      frame labels at start, an interior time, end, and one reverse-seek time. Values are in
      `tests/data/play_oem_tk_baseline.json`; four checkpoints for three views are also saved as
      PNGs outside the repository in the session files area.
- [x] Record the decisions the design depends on: SIGINT is forwarded with `wx.CallAfter`; the
      timeline slider has 10,000 integer steps mapped to clock bounds; and Matplotlib uses
      `FigureCanvasWxAgg` with wx-hosted toolbars.
- [x] Add a `playback` optional extra in `pyproject.toml` containing `wxPython>=4.2.4` and
      `matplotlib>=3.7`, regenerate `poetry.lock`, and record the minimum wxPython version chosen.
- [x] Verify wxPython wheel or install availability for each supported Python version (3.9–3.13)
      on macOS, Linux, and Windows. For Linux, record whether a wheel or a source build is needed.
- [x] Specify headless CI: pure-Python tests run without a display; tests that create a `wx.App`
      run under `xvfb-run` on Linux; backend-neutral Matplotlib tests set `MPLBACKEND=Agg`.
- [x] Define the proof gate: no `tkinter` imports, no `TkAgg` usage, and no PhotoImage/PPM
      fallback in the supported runtime path, checked by a repeatable search recorded in the
      step notes.

**Done when:** the design and inventory are internally consistent, the baseline fixture is
committed, the `playback` extra resolves from the lock, and `import wx` succeeds on the
development platform. No architecture decision remains open that would change steps 16–21.

**Step 15 evidence and decisions:** wxPython 4.2.4 is the minimum: its PyPI release has wheels for
macOS x86_64/arm64 and Windows (win32/win_amd64) on each supported Python version 3.9–3.13. PyPI
publishes no Linux wheels for this release, so Linux installs build from source and require wxGTK
build dependencies. The newer 4.3.2 release requires Python 3.10+, so the 4.2.4 floor preserves
the existing Python 3.9 support. The regenerated lock resolves wxPython 4.2.4 on Python 3.9–3.10
and 4.3.2 on Python 3.11–3.13. Development platform: macOS 26.7.1 arm64, Python 3.9.6; the
matching 4.2.4 macOS arm64 wheel is available. `poetry install --extras playback` succeeded and
`import wx` reports wxPython 4.2.4. The repeatable post-migration proof-gate search is
`rg -n -i 'tkinter|TkAgg|PhotoImage|PPM' src/ephem_toolkit/play_oem`; it must return no matches.
Run the same search over `tests/ephem_toolkit/play_oem` to identify Tk-only tests for removal.

**Depends on:** Step 14.

### 16. Replace the Tk app shell and window lifecycle with wxPython

Rebuild `app.py` around one `wx.App` and a primary `wx.Frame`. Replace Tk `after()` scheduling
with `wx.Timer`, driven from monotonic elapsed time and the existing `PlaybackClock`. Migrate
window ownership, close handling, observer cleanup, and SIGINT behavior without moving playback
logic into widgets or starting a second event loop. To preserve `--plots` through this boundary,
bring forward the minimal wx plot-frame and `FigureCanvasWxAgg` lifecycle for the three existing
views; the dashboard controls remain in step 17 and toolbar/click refinements remain in step 18.

- **Status:** Done.
- **Progress:** 7/7 checklist items.
- [x] Create the wx application and primary frame through the existing `play-oem` launch path.
- [x] Drive clock ticks with a wx timer using monotonic time and preserve configured FPS behavior.
- [x] Preserve startup time, autoplay, loop, reverse, speed, and CLI-selected plot behavior.
- [x] Open the existing speed/altitude, state-components, and 3D views in wx child frames and
      update their cursors from clock notifications.
- [x] Define frame/view close behavior, including stopping timers and unsubscribing observers.
- [x] Handle normal close and SIGINT using the mechanism recorded in step 15, without a lingering
      process or duplicate wx app instance.
- [x] Add lifecycle tests with wx-safe test fixtures or mocks that do not require a display.

**Done when:** `play-oem` launches a minimal wx window, opens the requested existing plots in wx
frames, updates the playback time and view cursors, and shuts down cleanly while clock and CLI
tests continue to pass.
**Depends on:** Step 15.

**Step 16 evidence:** to keep the dependency order while preserving `--plots`, the initial
`FigureCanvasWxAgg` and per-view frame lifecycle moved forward from step 18; dashboard controls
remain in step 17, and toolbar/click-to-seek plus removal of PPM raster methods remain in step 18.
Lifecycle tests use mocked wx windows/canvases without requiring a display. The focused wx app,
clock and CLI tests passed (58 total), and a real macOS wx smoke test opened a plot frame, ticked
playback and shut down cleanly.

### 17. Rebuild the playback control dashboard with native wx widgets

Replace `control_window.py` and Tk image-backed controls with native wx controls. Preserve
play/pause, keyboard shortcuts, timeline seeking, direct time entry, speed and direction
controls, readouts, toolbar actions, and the no-feedback rule for programmatic slider updates.

- **Status:** Done.
- **Progress:** 7/7 checklist items.
- [x] Implement native play/pause, speed, direction, elapsed/UTC readouts, and timeline controls.
- [x] Implement elapsed-duration and UTC entry with validation that leaves the clock unchanged
      on invalid input.
- [x] Preserve sample/time stepping, start/end shortcuts, reverse, and keyboard bindings.
- [x] Map the integer `wx.Slider` range to clock bounds using the resolution recorded in step 15,
      and synchronize slider updates from the clock without triggering recursive seek callbacks.
- [x] Preserve zero-duration timeline behavior and disable seeking when no interval exists.
- [x] Add wx-native layout, sizing, keyboard focus order, labeled controls, and close behavior
      for the dashboard.
- [x] Port control tests to assert behavior and state transitions rather than Tk widget internals.

**Done when:** every existing playback and seek interaction works through wx controls with
equivalent validation and clock behavior.
**Depends on:** Step 16.

**Step 17 evidence:** implemented the wx-native playback dashboard, including play/pause, reverse,
speed presets and logarithmic slider, elapsed/UTC readouts, direct duration/UTC seek, sample and
time stepping, start/end navigation, timeline seek, view/group actions, and focus-aware keyboard
accelerators. Programmatic slider synchronization is guarded against feedback, and the timeline is
disabled for zero-duration data. Behavior tests cover valid and invalid duration/UTC inputs,
control and accelerator actions, focus behavior, speed/timeline mappings, and zero-span seeking.
All 88 playback tests passed; a real macOS wx smoke test exercised the dashboard, time entry,
direction control, plot opening, and clean close.

### 18. Migrate Matplotlib views to wx canvases

Complete the minimal canvas integration introduced in step 16. Remove TkAgg and raster-image
display paths from the supported view runtime. Preserve plotted data, cursor synchronization,
labels, toolbar interactions, and click-to-seek. Keep numerical view construction independent of
wx where practical so it remains testable with a non-interactive Matplotlib backend.

- **Status:** Done.
- **Progress:** 7/7 checklist items.
- [x] Add wx-native Matplotlib navigation toolbars and complete canvas lifecycle handling.
- [x] Remove the remaining raster fallback methods from speed/altitude and state-component views.
- [x] Remove the raster fallback methods from the Matplotlib 3D trajectory view.
- [x] Preserve plot click-to-seek while respecting active pan/zoom toolbar modes.
- [x] Preserve one-window-per-view behavior, raise-existing behavior, and clean close/unsubscribe.
- [x] Compare each migrated view's data, labels, units, and cursor locations with the step 15
      baseline fixture using deterministic tests.
- [x] Test wx canvas rendering and cursor updates under the display-backed GUI test setup.

**Done when:** all currently implemented plots render and update in wx windows without using a
Tk canvas, Tk widget, or raster-image workaround.
**Depends on:** Step 17.

**Step 18 evidence:** added `NavigationToolbar2WxAgg` to every plot frame, connected left-clicks
on time-series axes to the shared playback clock, and ignored plot clicks while pan/zoom is active
or when the event has no seekable 2D time coordinate. Plot close disconnects the Matplotlib event
callback and clock observer. Removed the speed/altitude, state-component, and 3D raster/PPM
fallbacks and their obsolete tests. Deterministic tests compare the three view datasets, labels,
units, 3D extents, and cursor positions with the Tk-era baseline fixture. All 89 playback tests
passed; a real macOS wx smoke test opened all three canvases with toolbars, verified synchronized
cursor updates and click-to-seek/pan behavior, and closed cleanly. A search of the active playback
source and tests found no `tkinter`, `TkAgg`, `PhotoImage`, PPM, or raster references.

### 19. Port view registry, plot selection, and cross-window synchronization

Connect the existing view registry and `--plots` behavior to wx frame creation and activation.
Ensure all open plot windows consume the same cursor state and remain synchronized for playback
and every seek interaction.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Preserve canonical view names, aliases, groups, and unknown/unavailable selection errors.
- [x] Wire dashboard actions and `--plots` to the same registry and view-opening code.
- [x] Prevent duplicate windows and correctly raise/focus an existing view.
- [x] Verify simultaneous cursor updates and click-to-seek across every currently implemented
      view.
- [x] Test closing/reopening views during playback and after seeks.

**Done when:** toolbar/dashboard and CLI selections produce the same wx views, with no duplicate
windows or stale subscriptions.
**Depends on:** Step 18.

**Step 19 evidence:** added integration and lifecycle tests covering CLI alias expansion,
dashboard group and direct-view actions, unavailable selections, duplicate-window focus,
synchronized updates across all three implemented views, click-to-seek from both time-series
views, and close/reopen during playback after a seek. The complete `play-oem` test suite passed:
92 tests, with 14 Matplotlib dependency deprecation warnings.

### 20. Prototype VTK integration with the wx event loop

Before implementing or retaining a VTK scene, prove that VTK can be embedded and driven safely
from the wx application on supported platforms. Do not introduce a competing GUI event loop.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Open and close a minimal VTK render window hosted by a wx frame.
- [x] Drive VTK event processing and rendering without blocking wx timers or playback controls.
- [x] Verify resize, close, and interaction behavior on macOS, Linux, and Windows where available.
- [x] Record one outcome in the design document, `VTK-KEEP` or `VTK-DROP`, with platform
      limitations. Step 21 implements only the recorded outcome.
- [x] Specify explicit-backend errors and `auto` selection/fallback behavior before adding CLI
      or dependency changes.

**Done when:** the outcome is recorded in the design. For `VTK-KEEP`, wx/VTK lifecycle and event
handling are demonstrated on supported targets; for `VTK-DROP`, the removal is documented.
**Depends on:** Step 19.

**Step 20 evidence:** on macOS, wxPython 4.2.4 and VTK 9.6.2 successfully rendered a VTK scene
inside `wxVTKRenderWindowInteractor` under the single wx main loop. Eight wx timer callbacks
completed while rendering; resizing updated the VTK render-window dimensions; simulated
trackball mouse input changed the camera; and closing the wx frame ended the loop cleanly.
Linux and Windows were unavailable and remain unverified. The design records `VTK-KEEP`, the
embedded event-loop approach, platform limitations, and backend error/fallback behavior.

### 21. Complete the VTK backend migration and backend selection

Follow the outcome recorded in step 20. For `VTK-KEEP`, migrate the trajectory scene to wx
embedding behind the same view contract as Matplotlib. For `VTK-DROP`, remove VTK from product
scope, document Matplotlib as the sole 3D backend, and leave no unmaintained Tk/VTK path.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] For `VTK-KEEP`, implement the wx-hosted VTK orbit, WGS84 Earth, satellite marker,
      direction-aware tail, and trackball camera. For `VTK-DROP`, remove VTK code and references.
- [x] Keep marker/tail state driven by the shared cursor and playback controls.
- [x] Implement and validate `--3d-backend {auto,vtk,matplotlib}` only if VTK is retained.
- [x] Test explicit VTK selection errors and `auto` behavior when VTK/rendering is unavailable.
- [x] Add/document an optional VTK dependency extra only if the backend is retained.

**Done when:** the supported 3D backend set is fully wx-compatible, consistently selected, and
covered by backend-specific tests and documentation.
**Depends on:** Step 20.

**Step 21 evidence:** implemented the embedded VTK view and backend CLI selection. A captured
visual smoke test exposed an unregistered VTK OpenGL render-window factory: the widget reported
an initial render but displayed no scene. Importing VTK's OpenGL render-window implementation
fixed the blank output, and startup now rejects a non-OpenGL render-window class. The optional
VTK extra is bounded to `vtk>=9.2,<9.7`; its lock resolves to VTK 9.6.2 with CPython 3.9
wheels for macOS, Linux and Windows. `poetry check --lock` and a dry-run install with both
`playback` and `vtk` extras passed. The actual wx app rendered the VTK trajectory alongside a
Matplotlib plot. After the visual fix, the full `play-oem` suite passed 104 tests with 14
Matplotlib dependency deprecation warnings. The factory fix is shared code, not a portability
guarantee: only macOS/Cocoa rendering has been visually verified; Linux/GTK and Windows need
their own smoke captures before support is claimed.

### 22. Remove Tk-only code and verify the dependency split

Delete obsolete Tk-specific runtime code, raster helpers and tests after steps 16–21 have ported
their behavior. Confirm that the `playback` extra added in step 15 installs from the lock and that
the base install works without wxPython. Keep static plotting dependency behavior separate unless
the design requires a documented adjustment.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Remove Tk imports, `after()` timers, TkAgg canvas usage, Tk-specific UI paths, and Tk-only
      test fixtures from the active implementation.
- [x] Remove the PPM/PhotoImage raster helpers in `raster.py`, `speed_altitude.py`,
      `mpl_backend.py`, and `state_components.py` after confirming no supported caller remains.
- [x] Verify playback-extra resolution from the local lock on the available platform; record
      platform wheel/build availability and unverified target platforms in the design document.
- [x] Confirm the base install imports and runs `plot-oem` and other CLI tools without wxPython.
- [x] Run the proof gate search from step 15; classify any remaining match as migration-history
      documentation only.

**Done when:** the shipped `play-oem` runtime has no Tk dependency or fallback, the GUI installs
through the locked `playback` extra, and the base install does not require wxPython.
**Depends on:** Step 21.

**Step 22 evidence:** steps 16–18 had already removed the Tk runtime paths and raster helpers;
searches found no Tk/PPM/raster references in active source or tests and no raster helper files.
The remaining matches are migration-history/decision text in the architecture documents.
`poetry check --lock` and `poetry install --dry-run --extras playback` passed on macOS arm64,
Python 3.9; the previous macOS install is recorded under step 15. wxPython has macOS and Windows
wheels, while Linux requires a source build with wxGTK dependencies; Windows and Linux installs
were not run here. A test import hook blocked wxPython while `plot-oem`, `diff_oem`, and
`slice_oem` each ran `--help` successfully. The repository ignores `poetry.lock`, so the local
lock used for validation is not committed; clean installs resolve from `pyproject.toml`.

### 23. Accept the wxPython migration

Run the complete focused playback test suite and a live wx startup/shutdown smoke test. Verify
interaction behavior with the control/application tests when desktop input automation is
unavailable. Treat the Tk implementation as superseded; do not mark the migration complete based
only on unit tests or a successful import.

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Verify a repository OEM opens the wx control frame and default overview plots, with values
      matching the step 15 baseline fixture.
- [x] Verify play, pause, seek, direct time entry, stepping, reverse, speed, loop, and autoplay.
- [x] Verify plot synchronization, click-to-seek, view close/reopen, and normal shutdown/SIGINT.
- [x] Verify `--help`, invalid arguments, missing GUI dependencies, and backend-selection errors.
- [x] Run focused tests on the available macOS/Python target; record unavailable Python versions,
      platforms and accepted limitations.
- [x] Confirm all failures found in migration testing are resolved or explicitly documented.

**Done when:** the existing `play-oem` feature set runs on wxPython end to end, focused tests pass,
and the supported platform/dependency behavior is documented.
**Depends on:** Step 22.

**Step 23 evidence:** `poetry run pytest -q tests/ephem_toolkit/play_oem` passed **105 tests**
on macOS arm64/Python 3.9 (14 Matplotlib dependency deprecation warnings). The repository
baseline comparison test verified plotted data, labels, cursor positions and extents against the
Step 15 fixture. A live `play-oem tests/data/ISS_2026-05-20.OEM` run loaded 5,402 states and
prepared the default overview; sending SIGINT exited cleanly with status 0. The controls, clock,
plot synchronization, click-to-seek, close/reopen and backend-selection behaviors passed their
focused tests. `--help` returned 0, invalid arguments returned 2, and a subprocess with wxPython
blocked returned 1 with an install hint for the `playback` extra. That check exposed and fixed a
raw import error in `__main__.py`. Only macOS/Python 3.9 was exercised; desktop input automation
was unavailable, and other Python versions plus Linux/Windows installs and GUI rendering remain
unverified as documented in `PLAY_OEM_SOFTWARE_DESIGN.md`.

### 24. Add remaining motion and geometry diagnostics

Refactor the original RTN deltas, angular velocity, direction change, and geocentric distance
figures into individual views using the migrated wx/Matplotlib view lifecycle. Preserve the
existing calculations, units, labels, and plot behavior; add each view to the registry and Motion
diagnostics group.

#### 24-1. Inventory the existing diagnostic plots

Record each plot's source data, calculation, units, labels, axes, and edge-case behavior to
preserve.

- **Status:** Done.
- **Progress:** 1/1 checklist items.
- [x] Compare the original `plot-oem` implementations and document the four plots' behavior.

**Done when:** the required source data, formulas, labels, units, axes, and edge cases are recorded.
**Depends on:** Step 23.

**Inventory:** `compute_orbit_series` in `plot_oem/plot_oem.py` supplies the derived arrays to
the plot helpers; the CLI passes the selected elapsed-time unit to each helper.

- **RTN deltas:** For each sample after the first, call `core.misc.transform_to_rtn(current,
  previous)` and convert the six-component relative state to km and km/s. Plot only position
  components R/T/N against the current sample's elapsed time. Use three stacked axes titled
  “Radial/Transverse/Normal Position Delta vs Time,” with labels in km. There are N-1 points;
  with no deltas, show “Not enough samples.”
- **Angular velocity:** Express each velocity direction in the local RTN basis and normalize it.
  For each adjacent pair, compute `acos(clip(dot, -1, 1))`; divide by positive sample interval
  for rates in deg/s and rad/s. The first sample and non-positive intervals remain zero. Plot two
  stacked panels with separate deg/s and rad/s labels/titles; zero rates are filtered from the
  lines. If there is not more than one sample, show “Not enough samples.”
- **Direction change:** Convert the RTN velocity-direction components to Euler-style angles:
  roll is zero, pitch is `atan2(radial, transverse)`, and yaw is
  `atan2(normal, hypot(radial, transverse))`, in degrees. Euler-angle rates are adjacent raw
  angle differences divided by positive sample intervals; the first rate is zero. Plot roll,
  pitch, and yaw in the upper panel and their rates in the lower panel, in degrees and deg/s.
  Empty inputs display “Not enough samples.” Preserve the current raw-difference behavior,
  including angle wrap discontinuities.
- **Geocentric distance:** Compute the position-vector norm in km. Plot distance and sample-to-
  sample `np.diff(distance)` in km (not a rate), with the delta plotted at `elapsed_time[1:]`.
  Use two stacked panels with distance/delta titles and km labels. With one sample, retain the
  distance plot and show “Not enough samples” in the delta panel.

#### 24-2. Define the wx view contracts

Specify each view's name, data inputs, cursor-update behavior, and Motion-group placement. Reuse
existing series or shared calculations where they provide the required data.

- **Status:** Done.
- **Progress:** 1/1 checklist items.
- [x] Record the inputs, update contract, labels, and registry names for all four views.

**Done when:** each view has a clear data and lifecycle contract before implementation begins.
**Depends on:** Step 24-1.

**View contracts:** use the existing registry names and labels: `rtn` / “RTN Deltas”,
`angular-velocity` / “Angular Velocity”, `direction-change` / “Direction Change”, and `distance` /
“Geocentric Distance”. All four are already members of the `motion` group.

Each view follows the existing `SpeedAltitudeView`/`StateComponentsView` lifecycle:
`build(orbit_series, time_unit) -> Figure`, `update(time_s)` with absolute TT seconds, and
`close()`. `build` plots static history data and creates a cursor line on every time-series axis;
`update` only moves those cursor artists. Use `time_unit.get_axis_label()` on the bottom axis,
preserving app-level plot-click-to-seek behavior by keeping elapsed time on the x-axis.

- `rtn`: `rtn_elapsed_time` and `rtn_delta_km[:, 0:3]`; three stacked R/T/N axes, km units.
- `angular-velocity`: `elapsed_time`, `angular_velocity_deg_s`, and
  `angular_velocity_rad_s`; two stacked axes, respectively deg/s and rad/s.
- `direction-change`: `elapsed_time`, `euler_angles_deg`, and `euler_angle_rates_deg_s`;
  upper axis plots roll/pitch/yaw in degrees, lower axis their rates in deg/s.
- `distance`: `elapsed_time` and `geocentric_distance_km`; upper axis plots distance in km,
  lower axis plots `np.diff(geocentric_distance_km)` against `elapsed_time[1:]` in km.

#### 24-3. Implement the RTN-delta view

- **Status:** Done.
- **Progress:** 1/1 checklist items.
- [x] Implement the RTN-delta plot and compare its plotted values, units, and labels with
      `plot-oem`.

**Done when:** the RTN-delta view matches the reference calculation and presentation.
**Depends on:** Step 24-2.

**Evidence:** Added `RtnDeltaView` with three stacked R/T/N position-delta axes, km labels,
time-unit-aware x-axis, per-axis playback cursors, object legend, and the “Not enough samples”
state for a one-state OEM. The app now opens it via the existing `rtn` registry name. Tests compare
the plotted arrays against `plot-oem`'s `OrbitSeries`, verify labels/cursor movement and empty
input, and exercise app selection. The full focused playback suite passes: 109 tests, 14 existing
Matplotlib dependency deprecation warnings.

#### 24-4. Implement the angular-velocity view

- **Status:** Done.
- **Progress:** 1/1 checklist items.
- [x] Implement the angular-velocity plot and compare its plotted values, units, and labels with
      `plot-oem`.

**Done when:** the angular-velocity view matches the reference calculation and presentation.
**Depends on:** Step 24-2.

**Evidence:** Added `AngularVelocityView` with deg/s and rad/s panels, reference labels and
titles, zero-rate filtering, per-axis playback cursors, and the single-state “Not enough samples”
message. The app opens it via `angular-velocity`. Tests compare both plotted series with
`plot-oem`, verify labels and cursor movement, cover a one-state OEM, and exercise app selection.
The full focused playback suite passes: 112 tests, 14 existing Matplotlib dependency deprecation
warnings.

#### 24-5. Implement the direction-change view

- **Status:** Done.
- **Progress:** 1/1 checklist items.
- [x] Implement the direction-change plot and compare its plotted values, units, and labels with
      `plot-oem`.

**Done when:** the direction-change view matches the reference calculation and presentation.
**Depends on:** Step 24-2.

**Evidence:** Added `DirectionChangeView` with Euler-angle and Euler-angle-rate panels, matching
the reference labels, raw-angle rates, object legends, playback cursors, and single-state empty
handling. Tests compare both data arrays with `plot-oem`, verify labels and cursor movement, cover
a one-state OEM, and exercise app selection.

#### 24-6. Implement the geocentric-distance view

- **Status:** Done.
- **Progress:** 1/1 checklist items.
- [x] Implement the geocentric-distance plot and compare its plotted values, units, and labels
      with `plot-oem`.

**Done when:** the geocentric-distance view matches the reference calculation and presentation.
**Depends on:** Step 24-2.

**Evidence:** Added `GeocentricDistanceView` with distance and sample-to-sample delta panels,
km units, object legends, playback cursors, and one-state empty-delta handling. Tests compare
distance and delta data with `plot-oem`, verify labels and cursor movement, cover a one-state
OEM, and exercise app selection.

#### 24-7. Register the diagnostic views

- **Status:** Done.
- **Progress:** 1/1 checklist items.
- [x] Register all four views for individual opening and in the Motion diagnostics group; verify
      opening and closing each view does not disturb other open views.

**Done when:** every new view opens independently and the group opens all four.
**Depends on:** Steps 24-3, 24-4, 24-5, and 24-6.

**Evidence:** All four names are registered with `PlayerApp`; the Motion group test opens
exactly the four diagnostics, each individual view has an app-selection test, and parametrized
close tests verify that closing one diagnostic leaves the other three open.

#### 24-8. Validate synchronization and regressions

- **Status:** Done.
- **Progress:** 1/1 checklist items.
- [x] Verify playback updates, cursor synchronization, click-to-seek, and seek behavior across
      all four views; run focused tests and resolve regressions.

**Done when:** all four views remain synchronized and the focused tests pass.
**Depends on:** Step 24-7.

**Evidence:** Extended the shared-view seek/click test to include all four diagnostics and tested
Motion-group opening plus independent view closure. A live wx smoke test opened the Motion group
from a repository OEM with 721 states and exited cleanly on SIGINT. The full focused suite passed:
122 tests, with 14 existing Matplotlib dependency deprecation warnings.

**Step 24 complete when:** substeps 24-1 through 24-8 are done.

### 25. Add current-state readouts and OEM data context

Populate the wx control dashboard from `CursorState` and OEM metadata. Keep common values
visible and put less-used metadata in a collapsible details panel.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Display position, velocity, speed, and altitude with units and validity checks.
- [x] Display object, frame, center, time span, and sample count.
- [x] Display whether cursor values are sampled or interpolated.
- [x] Add a details panel for less-used metadata and test missing-metadata behavior.

**Evidence:** The wx dashboard now updates Cartesian position and velocity, speed,
altitude, and sampled/interpolated/unavailable status from `CursorState`. It shows the
object, frame, center, selected time span, and post-filter sample count, with remaining
OEM metadata in a wx collapsible pane. Missing numerical state and metadata display as
unavailable rather than stale values. Focused dashboard/app/CLI validation passed:
`poetry run pytest -q tests/ephem_toolkit/play_oem/test_play_oem_control_window.py
tests/ephem_toolkit/play_oem/test_play_oem_app.py
tests/ephem_toolkit/play_oem/test_play_oem_cli.py` (71 passed).

**Done when:** the wx dashboard presents key state and source context without relying on plot
windows.
**Depends on:** Step 24-8.

### 26. Implement segment and data-gap handling

Ensure the loader/series preserve OEM segment boundaries; plot each segment separately and
never interpolate or draw a continuous line across a gap. Keep the timeline seekable through a
gap while indicating that no state is available there.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Identify and preserve segment boundaries during loading and filtering.
- [x] Render each segment separately and mark boundaries in applicable views.
- [x] Return gap status from cursor lookup without carrying forward prior values.
- [x] Show unavailable state readouts and gap status while seeking through gaps.
- [x] Test interpolation and plotting on a multi-segment OEM.

**Evidence:** The OEM parser records per-state segment IDs while keeping the existing
five-item `_read_oem_impl` return shape for callers; duration filtering retains the matching
prefix of IDs. Series calculations omit cross-segment deltas/rates, cursor lookup returns a
gap status (and uses segment-local interpolators), and 2D/3D renderers draw segment runs
separately. The control dashboard clears state values during gaps. Multi-segment parser,
cursor, derived-series, and rendering tests pass. Validation:
`poetry run pytest -q tests/ephem_toolkit/play_oem` (127 passed), and the OEM parser +
cursor/data subset passed (95 passed).

**Done when:** no view or readout implies continuous or interpolated data across an OEM gap.
**Depends on:** Step 25.

### 27. Optimize rendering and validate playback performance

Add responsive 2D rendering and display decimation, per-view throttling for Matplotlib 3D, and
frame dropping as needed. Profile before changing algorithms; keep full-resolution data for
cursor lookup.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Use full WxAgg redraws for cursor updates after partial blitting caused plot corruption
      during click-to-seek.
- [x] Add display-only decimation for large histories.
- [x] Throttle Matplotlib 3D updates without slowing the playback clock.
- [x] Benchmark all views open at 1000x with an OEM of at least 100k samples.

**Evidence and accepted deviation:** 2D playback cursors use `draw_idle()` full redraws;
partial WxAgg bitmap blitting produced duplicated and mispositioned plot content after
click-to-seek in the reported macOS UI. The step-27 performance measurements below predate
this correctness fix and should not be treated as measurements of the current redraw path.
2D histories are min/max decimated to 2,000 points per segment; Matplotlib 3D display paths
are limited to 500 points per segment and VTK paths to 2,000 points per segment.
Full-resolution series and cursor data remain unchanged. 3D rendering is throttled
independently of the playback clock. Automated redraw, decimation, throttle, and
cursor-correctness tests pass.

Native wx measurements on this macOS environment used all seven views, 100,000 synthetic
orbit samples, 1000x playback, and a five-second run: automatic VTK measured about 6.7
playback updates/s; Matplotlib measured about 11.4 updates/s with the 10 Hz 3D cap. A
Matplotlib run with a 5 Hz 3D cap reached about 14.4 updates/s. All native results are below
the N1 target of 15 updates/s. A cached Agg render-loop benchmark reached about 538 view
updates/s, but Agg is CPU software rendering and is not a substitute for native UI
responsiveness. The user explicitly accepted the current measured performance and requested
deferring further optimization. This is an accepted deviation, not a claim that N1 was met.

See the “Performance findings and deferred work” section in
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md) for the benchmark method, platform/backend
caveats, unverified hypotheses, and follow-up profiling candidates. N1 retains its 15 fps
target for future consideration.

**Done when:** the N1 target is met, or a below-target benchmark is documented and explicitly
accepted, with cursor values remaining correct.
**Depends on:** Step 26.
