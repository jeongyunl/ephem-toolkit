# `play-oem` — Shared Time Range Implementation Plan

> Status: **in progress**. Steps 1–4 are implemented and verified. Step 5 is partially
> implemented; step 6 remains pending.

Software design:
[PLAY_OEM_TIME_RANGE_SOFTWARE_DESIGN.md](./PLAY_OEM_TIME_RANGE_SOFTWARE_DESIGN.md).
GUI design and five alternatives:
[PLAY_OEM_TIME_RANGE_GUI_DESIGN.md](./PLAY_OEM_TIME_RANGE_GUI_DESIGN.md).
Existing application architecture:
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md).
This plan follows the workflow convention in
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md).

## Outcome and agreed defaults

Implement one shared interval with independently fixed UTC or playback-relative endpoints.
Filter every time-series, 3D orbit, and ground-track view. Maintain
`effective plot range ⊆ OEM coverage` and `playback range ⊆ OEM coverage`.
Neither range constrains the other; plots may extend beyond or be disjoint from playback. Playback bounds are independent fixed
UTC values; plot edits never change them or seek the clock. Apply valid edits live while
paused, follow effective plot bounds on time axes, and retain stable Y scales. Preserve the OEM time origin, full-resolution cursor data, gaps, spatial navigation,
and current rendering cadence. Both settings last only for the loaded dataset session.
Playback defaults to Full OEM; plot filtering defaults to All OEM data. Allow playback
outside plots and represent empty intersections explicitly.

This document is an execution design, not an implementation report. The initial documentation
delivery does not complete any checklist below. No CLI extension, dependencies, persistent
range settings, per-view overrides, or disjoint intervals are planned.

## How to use this plan

Work one pending numbered step at a time in dependency order. Do not start a later step until
the current checklist and completion criteria pass. If dependencies or the architecture change,
update this plan and the linked designs before proceeding with dependent work.

Maintain **Status** (`Not started`, `In progress`, `Blocked`, or `Done`) and **Progress** as
completed checklist items out of the total. Record checks, commands, results, and unresolved
limitations with the step. Writing code alone does not make a step complete. When done, move
the full step entry to **Completed steps**, retaining its number, dependency, checklist, and
evidence. Do not claim a live GUI check from a headless test result.

## 1. Implement the toolkit-independent range model

**Completed steps:** This implementation was completed and verified as recorded below.

## 2. Add playback limits and integrate every navigation path

**Completed steps:** Implementation and verification are recorded below.

## 3. Propagate the range and filter time-series data

**Completed steps:** Shared propagation and time-series filtering are implemented; spatial
views received the protocol adapter and are completed in step 4.

## 4. Integrate both 3D renderers and ground-track filtering

**Completed steps:** Spatial path filtering and automated coverage are recorded below. Live
VTK context validation remains an acceptance item for step 6.

## 5. Build the shared editor and combined playback/range slider

Add a focused wx editor module, `workspace/time_range.py`, and compose it into the current
workspace with independent fixed UTC playback-bound fields and plot fields above transport,
and four same-height range handles above a standard wx.Slider track. Use separate Full OEM and All OEM data actions.
Adapt `workspace/timeline.py` and slider consumers to one shared control, preserving existing
seek callbacks, full-coverage mapping, tooltip behavior, and programmatic synchronization.
Wire it to the application actions without duplicating the model's validation or adding an
independent playback loop.

- **Status:** In progress.
- **Progress:** 3/8 checklist items.
- [x] Build playback-bound fields/Full OEM and plot Enabled/All OEM data with independent
      mode/value fields and validation feedback. Use compact same-row From/To inputs with
      Fixed time checkboxes immediately after each: checked means fixed UTC, unchecked means
      playback offset. Remove separate mode buttons;
      retain accessible endpoint-specific checkbox names, fitted fields, and inline helpers. Respect
      native font/theme minimum heights and preserve full editable timestamp precision.
- [x] Add fixed-UTC and signed-duration parsing, requested-instant-preserving checkbox toggles,
      Enter/focus-loss submission, Escape restoration, and invalid-draft protection.
- [ ] Implement `TimeRangeSlider(wx.Slider)` with its native current-time thumb and four
      draggable range handles at one height immediately above the standard track: solid
      rounded playback grips and outlined diamond plot grips. No persistent text on/near
      handles; hover/focus tooltips provide names, values, and fixed/offset mode. Validate
      native track alignment and painting, horizontal collision fan-out, and all five targets.
- [ ] Implement live pointer dragging, pointer capture termination, keyboard adjustment,
      plot-grip clamping only to OEM coverage, playback-grip ordering/clamping, and pause-on-edit
      without automatic resume. Route each gesture exclusively to its correct action.
- [x] Synchronize fields/slider/readouts without recursive events or overwriting drafts;
      retain existing transport controls and full-coverage seek mapping.
- [ ] Add keyboard names/focus, status feedback, no-file/singleton states, responsive layout,
      theme-aware styles, and equivalent exact-field access to all handle operations.
- [ ] Add meaningful editor integration tests for event routing, accepted/invalid values,
      live updates, reset/re-enable, keyboard interaction, and playback shortcut isolation;
      verify plot drags never emit seeks/change playback bounds, thumb/rail seeks never edit
      endpoints, playback drags update bounds/clamp only when needed, both reset actions remain
      independent, and all five targets remain usable
      at coincident/clipped timestamps, including empty plot ranges.
- [ ] Run a live wx editor smoke check and record environment and any remaining visual checks
      for final acceptance; do not mark unexercised interactions verified.
- **Implemented so far:** workspace/time_range.py provides fixed UTC and signed offset
  fields, one-row plot controls, fixed-mode checkboxes, validation feedback, Escape
  restoration, and independent reset actions. The persistent effective UTC row was removed;
  endpoint tooltips retain resolved UTC details.
  workspace/time_range_slider.py subclasses wx.Slider, retains native thumb seeking, and
  adds four same-height, named range grips with mode/value tooltips, drag capture, collision
  fan-out, and keyboard nudging. Controller actions preserve plot/playback independence.
- **Evidence so far:** Parser and action tests are included in the focused run below. The
  broad workspace test module fails before the new editor is constructed because its existing
  FakeSplitter lacks GetDefaultSashSize used by graph_stack.py. xvfb-run cannot start Xvfb
  in this environment because /tmp/.X11-unix has unsuitable ownership and permissions; wx
  reports no display. Native slider alignment, actual paint behavior, pointer capture, and
  focus traversal therefore remain unverified.
- **Startup crash correction:** The user-provided faulthandler trace located the segfault in
  wx.Control initialization for a grip whose native parent was wx.Slider. Grips are now
  sibling controls overlaid in the slider parent; drag and keyboard events route to the
  TimeRangeSlider instance. This removes the crashing native-slider parent relationship.
  The reported paint assertion is addressed by setting wx.BG_STYLE_PAINT before binding the
  custom paint handler; the handler clears the background with AutoBufferedPaintDC. The launch
  cannot be confirmed in this headless environment, so an on-screen rerun remains required.
- **Checks:** PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src pytest -q over
  test_time_range.py, test_time_range_actions.py, test_time_range_plotting.py,
  test_time_range_editor.py, test_play_oem_clock.py, test_rtn_view.py,
  test_ground_track_view.py, test_trajectory3d.py, and test_vtk_trajectory3d.py —
  88 passed, 7 skipped. python -m compileall -q src/ephem_toolkit/play_oem and
  git diff --check passed.

**Done when:** the selected design works end to end with every graph and navigation route,
and no hidden draft, duplicate event, or drag action can install an invalid applied rule.
**Depends on:** Step 4.

## 6. Verify lifecycle, performance, GUI behavior, and documentation

Complete acceptance using the actual application, representative large OEM data, and focused
regression checks. Update feature and application documentation to describe only implemented
behavior and measured evidence.

- **Status:** Not started.
- **Progress:** 0/8 checklist items.
- [ ] Verify new/duplicated/replaced graphs inherit both settings, hidden panels catch up, closed
      panels release work, failed OEM opens preserve state, and successful loads reset both.
- [ ] Exercise fixed/fixed, relative/relative, and both mixed combinations during paused seeks,
      forward/reverse playback, narrowed playback bounds, future-only/past-only windows, crossed
      mixed endpoints, and empty/singleton ranges. Only playback-bound edits may clamp the clock;
      assert independent OEM containment, unchanged fixed plots on playback edits, and
      plot-edit preservation of clock time/playback bounds.
- [ ] Manually verify focus, keyboard access, pointer capture, minimum size, high DPI, themes,
      OEM clipping, plot grips outside playback, overlapping handles, independent resets, playback outside plots,
      stable Y scales, hidden out-of-range overlays, and preserved map/camera navigation.
- [ ] Benchmark at least 100,000 samples with all views, fixed/moving windows, 1000x playback,
      high-speed 9000x operation, both directions, and repeated range dragging; record platform,
      backends, FPS, achieved update rate, and input latency against existing performance targets.
- [ ] Exercise supported desktop platforms and both 3D backends where available; record actual
      coverage and obtain explicit acceptance for any deferred acceptance gap or target miss.
- [ ] Run focused playback tests, appropriate broader regressions, and whitespace checks;
      record commands/results separately from live GUI evidence.
- [ ] Update the existing concepts/software design and end-user playback guide for optional
      filtering, independent playback limits, independent-coverage/empty-range semantics, session lifetime,
      and selected UI; check all cross-links.
- [ ] Reconcile these three documents with the final implementation, retaining five design
      alternatives and the selected design; publish implementation/validation status accurately.

**Done when:** behavior matches the linked designs, checks and measured limitations are
documented, and all acceptance gaps are resolved or explicitly accepted. Do not mark complete
solely because code or documentation exists.
**Depends on:** Step 5.

## Completed steps

### 1. Implement the toolkit-independent range model

Add `play_oem/time_range.py` with independent playback bounds, immutable plot endpoints,
applied rule, and optional resolved range types with pure validation/resolution operations.
Keep all epochs in absolute TT seconds and all offsets in seconds. This layer imports without
GUI or rendering dependencies.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Implemented `PlaybackTimeRange`, `TimeRangeEndpoint`, `PlotTimeRange`, and
      `ResolvedTimeRange` with pure validation and resolution functions.
- [x] Validated independent playback bounds and all four endpoint mode combinations, with
      plot resolution clipped only to OEM coverage.
- [x] Verified out-of-playback/disjoint plot windows, inclusive singleton selections,
      clipping, mixed endpoint crossings, and valid empty intersections.
- [x] Verified deterministic offset resolution across ordered and randomly ordered times,
      and rejection of invalid playback times and always-reversed same-mode pairs.
- [x] Verified isolated model import does not load wx, Matplotlib, or VTK.
- **Evidence:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src pytest -q
  tests/ephem_toolkit/play_oem/test_time_range.py` — 23 passed. Lazy package exports preserve
  `play_oem.cli` and `play_oem.main` while keeping model imports independent.
- **Depends on:** None.
- **Done when:** Pure tests establish the equations and failure behavior without a display,
  and immutable coverage is distinct from playback bounds and the effective plot range.

### 2. Add playback limits and integrate every navigation path

Extend `clock.py` with independent playback bounds while preserving dataset `t_start` and
`t_end`. Add application range ownership and actions in `app/time_range_actions.py`, and
update controller/state contracts and existing playback actions. GUI controls follow later.

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Added read-only playback limits and an atomic setter; dataset limits remain immutable,
      current time clamps once, tick compensation clears, and rate/direction are retained.
- [x] Applied limits to tick, seek, second/sample stepping, both directions, singleton bounds,
      and optional loop wraparound.
- [x] Kept slider and tooltip mapping across OEM coverage; seek, typed time, plot-click,
      start/end, transport steps, and existing keyboard callbacks route through bounded clock
      behavior. Typed OEM timestamps outside playback clamp and report status.
- [x] Added independent application range state/actions, pause and timer-baseline reset,
      distinct Full OEM/All OEM data resets, endpoint retention, and successful-load reset.
      Plot edits call neither `seek` nor the playback-bound setter.
- [x] Verified invalid edits are atomic, failed opens retain both ranges, and successful
      replacement resets both. Fixed plot bounds survive playback edits; relative rules resolve
      against the resulting clock time. Playback changes do not use plot bounds.
- [x] Ran focused clock, range-action, application, and control tests.
- **Evidence:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src pytest -q
  tests/ephem_toolkit/play_oem/test_play_oem_clock.py tests/ephem_toolkit/play_oem/test_time_range.py
  tests/ephem_toolkit/play_oem/test_time_range_actions.py tests/ephem_toolkit/play_oem/test_play_oem_app.py
  tests/ephem_toolkit/play_oem/test_play_oem_control_window.py` — 123 passed.
- **Depends on:** Step 1.
- **Done when:** Every movement respects playback bounds; All OEM selects all history
  independently; plot edits preserve clock time and bounds; edit application is atomic.

### 3. Propagate the range and filter time-series data

Extend `views/base.py` and all time-series implementations, the plotting helpers, application
panel lifecycle, and `_OpenView` bookkeeping. Establish one controller-owned clock dispatch
for consistent range and cursor updates. Spatial views receive the protocol method here;
their rendering behavior is completed in step 4 before any editor is exposed.

- **Status:** Done.
- **Progress:** 7/7 checklist items.
- [x] Added the optional-empty `set_time_range` contract and OEM coverage fallback. Empty
      graph and spatial adapters implement the contract; new views receive it before drawing.
- [x] Replaced per-view clock subscriptions with one controller dispatch that resolves once,
      applies range before cursor updates, and releases cleanly on close/replacement.
- [x] Added reusable segmented history artists that select inclusive samples first and
      decimate afterward while retaining full source arrays and segment gaps.
- [x] Applied the helper to every scalar/component history. RTN uses its own elapsed-time
      axis and segment IDs; derived source computations remain full resolution.
- [x] Set shared X limits, preserve full-history Y baselines and user vertical zoom, lock X
      navigation during active filtering, support singleton samples and distinct empty states,
      and hide cursors outside the effective plot interval.
- [x] Reused the workspace redraw queue and deferred only the latest time/range for hidden
      panels, applying current state when each panel is shown. No per-range selection cache is
      retained; source arrays and line artists are bounded by the loaded dataset.
- [x] Added headless tests for narrow-window extrema, inclusive selection, segment gaps,
      sample-free and empty intervals, singleton histories, RTN timestamps, cursor visibility,
      axis/Y behavior, and shared dispatch lifecycle.
- **Evidence:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src pytest -q
  tests/ephem_toolkit/play_oem/test_play_oem_clock.py tests/ephem_toolkit/play_oem/test_time_range.py
  tests/ephem_toolkit/play_oem/test_time_range_actions.py tests/ephem_toolkit/play_oem/test_time_range_plotting.py
  tests/ephem_toolkit/play_oem/test_play_oem_app.py tests/ephem_toolkit/play_oem/test_play_oem_speed_altitude.py
  tests/ephem_toolkit/play_oem/test_state_components.py tests/ephem_toolkit/play_oem/test_rtn_view.py
  tests/ephem_toolkit/play_oem/test_angular_velocity_view.py tests/ephem_toolkit/play_oem/test_direction_change_view.py
  tests/ephem_toolkit/play_oem/test_distance_view.py` — 129 passed.
- **Depends on:** Step 2.
- **Done when:** All time-series data artists contain only eligible samples, all panels observe
  the same resolved state, axes follow the design, and closing views leaves no stale callbacks.

### 4. Integrate both 3D renderers and ground-track filtering

Complete range handling in `views/trajectory3d/mpl_backend.py`, `vtk_backend.py`, and
`views/ground_track.py`, reusing full source positions and cached Earth-fixed coordinates.

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Filtered both 3D paths by timestamp before decimation, preserved segment topology and
      singleton points, and intersected VTK direction-aware tails with the selected interval.
- [x] Filtered cached ground coordinates before seam splitting and decimation, without
      repeating Earth-frame conversion.
- [x] Preserved full spatial bounds, camera, map projection/center/extent, and backgrounds.
      Cursor markers, ground footprints, and VTK tails are gated by effective-range membership.
- [x] Added explicit empty/no-sample states and replaced stale paths on range changes.
- [x] Added inclusive path/overlay tests, forward/reverse tail coverage in the existing VTK
      tests, seam-crossing tests, and empty/singleton selector tests.
- [x] Ran spatial and existing OEM segment checks. VTK context/resource tests are present but
      the current environment skips their wx/VTK display-dependent cases.
- **Evidence:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src pytest -q
  tests/ephem_toolkit/play_oem/test_trajectory3d.py tests/ephem_toolkit/play_oem/test_vtk_trajectory3d.py
  tests/ephem_toolkit/play_oem/test_ground_track_view.py tests/ephem_toolkit/play_oem/test_play_oem_data.py`
  — 27 passed, 7 skipped (display/backend-dependent).
- **Depends on:** Step 3.
- **Done when:** All view types honor the same filter with no spatial-navigation reset;
  both backend paths have automated coverage, with unavailable live checks carried to step 6.
