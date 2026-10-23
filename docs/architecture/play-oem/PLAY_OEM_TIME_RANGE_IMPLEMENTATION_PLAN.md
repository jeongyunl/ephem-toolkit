# `play-oem` — Shared Time Range Implementation Plan

> Status: **proposed**. All implementation steps and validation are pending.

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

Add `play_oem/time_range.py` with independent playback bounds, immutable plot endpoints,
applied rule, and optional resolved range types with pure validation/resolution operations.
Keep all epochs in absolute TT seconds and all
offsets in seconds. This layer must import without GUI or rendering dependencies.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Implement the model and signatures specified in the software design, including separate
      playback bounds, disabled filtering returning OEM coverage, and fixed plot defaults.
- [ ] Validate independent playback bounds against OEM coverage and intersect all four plot
      endpoint combinations with OEM coverage, independently of playback bounds; allow either offset sign on either endpoint.
- [ ] Prove independent coverage containment with narrowed playback bounds, plots extending
      beyond either end or disjoint from playback, inclusive/singleton selections,
      future-only/past-only windows, wholly outside requests, and mixed endpoint crossings.
      Validate always-reversed same-mode pairs; accept empty resolved intersections.
- [ ] Test deterministic resolution for forward, backward, and randomly ordered playback
      times, including validation of playback times passed to the resolver.
- [ ] Verify imports remain toolkit-independent and record focused test evidence.

**Done when:** pure tests establish the equations and failure behavior without a display,
and immutable coverage is distinct from playback bounds and the effective plot range.
**Depends on:** None.

## 2. Add playback limits and integrate every navigation path

Extend `clock.py` with independent playback bounds while preserving dataset `t_start` and
`t_end`. Add application range ownership and actions in `app/time_range_actions.py`, and
update controller/state contracts and existing playback actions. GUI controls follow later.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Add playback-bound properties/setter, atomic clamp/notification, and compensation reset;
      preserve current rate/direction and dataset limits.
- [ ] Apply bounds to tick, seek, sample/second stepping, both directions, singleton bounds,
      and existing optional loop behavior.
- [ ] Route seek fractions, typed times, plot clicks, start/end buttons, and shortcuts through
      the same limits; keep full-coverage slider mapping and dataset-relative time parsing.
- [ ] Implement independent playback/plot actions, pause-on-edit and timer baseline reset;
      plot edits dispatch refreshes without calling seek or the clock bounds setter. Keep
      separate Full OEM/All OEM data resets, enable retention, and dataset replacement reset.
- [ ] Test playback-only clamping, plot-edit time/bounds preservation, invalid-edit atomicity,
      failed-load retention, single-notification ordering, and stable time origin/speed.
      Verify playback can traverse plot boundaries and empty plots without stopping. Changing
      playback bounds preserves fixed plots; relative plots change only if clock time changes.
- [ ] Run focused clock/application tests and record evidence for every navigation route.

**Done when:** every movement respects the model's playback bounds, All OEM data
selects all OEM history independently of playback bounds, plot edits cannot change clock time/bounds,
and edits cannot expose an intermediate rule/time combination.
**Depends on:** Step 1.

## 3. Propagate the range and filter time-series data

Extend `views/base.py` and all time-series implementations, the plotting helpers, application
panel lifecycle, and `_OpenView` bookkeeping. Establish one controller-owned clock dispatch
for consistent range and cursor updates. Spatial views receive the protocol method here;
their rendering behavior is completed in step 4 before any editor is exposed.

- **Status:** Not started.
- **Progress:** 0/7 checklist items.
- [ ] Add the optional-empty `set_time_range` contract with OEM coverage for axis fallback,
      including the empty graph and temporary spatial-view adapters;
      initialize a newly built view with the applied range before its first visible draw.
- [ ] Replace individual view subscriptions with one controller dispatch, resolve bounds once,
      update range before cursor state, and preserve cleanup on panel close/replacement.
- [ ] Select samples inclusively by each series' timestamps, preserve contiguous valid OEM
      runs, and decimate after filtering; retain full-resolution source computations.
- [ ] Handle RTN's separate sample axis/segment IDs and verify all scalar/component histories.
- [ ] Implement effective X limits, full-data Y baselines, vertical-only navigation while
      filtering, Home behavior, singleton points, and distinct empty-overlap/no-sample states.
      Hide plot cursor lines outside the effective range while keeping global readouts live.
- [ ] Bound selection caches and coalesce redraws through existing panel/workspace scheduling;
      retain only the latest pending state for hidden panels.
- [ ] Run headless renderer/integration tests, including narrow-window extrema, gaps,
      sample-free intervals, optional empty results, in/out-of-range cursor interpolation,
      playback-bound independence, and changed-range/unchanged-time updates.

**Done when:** all time-series data artists contain only eligible samples, all panels observe
the same resolved state, axes follow the design, and closing views leaves no stale callbacks.
**Depends on:** Step 2.

## 4. Integrate both 3D renderers and ground-track filtering

Complete range handling in `views/trajectory3d/mpl_backend.py`, `vtk_backend.py`, and
`views/ground_track.py`, reusing full source positions and cached Earth-fixed coordinates.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Filter 3D paths by timestamp before decimation in both backends, preserve contiguous
      OEM topology, and intersect existing direction-aware tails with the range.
- [ ] Filter ground-track samples before map-seam splitting and decimation without repeating
      full-file frame conversion.
- [ ] Preserve camera/spatial bounds, map projection/center/extent, and backgrounds. Gate
      plot markers/footprints/current tail endpoints by effective-range membership as well
      as existing interpolation/gap validity; keep global current-state readouts live.
- [ ] Support empty intersections, no-sample/singleton paths, and transitions to All OEM data;
      never leave stale paths or bridge gaps/seams.
- [ ] Add backend and coordinate-selection tests for inclusive membership, tails in both
      directions, seam crossings, in-range interpolated overlays without source samples, and
      hidden plot overlays during playback outside plots.
- [ ] Run available backend checks, record optional VTK skips explicitly, and verify native
      resource cleanup with repeated panel replacement and closure.

**Done when:** all view types honor the same filter with no spatial-navigation reset;
both backend paths have automated coverage, with unavailable live checks carried to step 6.
**Depends on:** Step 3.

## 5. Build the shared editor and combined playback/range slider

Add a focused wx editor module, `workspace/time_range.py`, and compose it into the current
workspace with independent fixed UTC playback-bound fields and plot fields above transport,
and four same-height range handles above a standard wx.Slider track. Use separate Full OEM and All OEM data actions.
Adapt `workspace/timeline.py` and slider consumers to one shared control, preserving existing
seek callbacks, full-coverage mapping, tooltip behavior, and programmatic synchronization.
Wire it to the application actions without duplicating the model's validation or adding an
independent playback loop.

- **Status:** Not started.
- **Progress:** 0/8 checklist items.
- [ ] Build playback-bound fields/Full OEM and plot Enabled/All OEM data with independent
      mode/value fields, effective plot UTC, OEM-clipping labels, and validation feedback.
      Use compact From/To inputs followed on the right by Fixed time checkboxes: checked
      means fixed UTC, unchecked means playback offset. Remove separate mode buttons;
      retain accessible endpoint-specific checkbox names, fitted fields, and inline helpers. Respect
      native font/theme minimum heights and preserve full editable timestamp precision.
- [ ] Add fixed-UTC and signed-duration parsing, requested-instant-preserving checkbox toggles,
      Enter/focus-loss submission, Escape restoration, and invalid-draft protection.
- [ ] Implement `TimeRangeSlider(wx.Slider)` with its native current-time thumb and four
      draggable range handles at one height immediately above the standard track: solid
      rounded playback grips and outlined diamond plot grips. No persistent text on/near
      handles; hover/focus tooltips provide names, values, and fixed/offset mode. Validate
      native track alignment and painting, horizontal collision fan-out, and all five targets.
- [ ] Implement live pointer dragging, pointer capture termination, keyboard adjustment,
      plot-grip clamping only to OEM coverage, playback-grip ordering/clamping, and pause-on-edit
      without automatic resume. Route each gesture exclusively to its correct action.
- [ ] Synchronize fields/slider/readouts without recursive events or overwriting drafts;
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

None. This proposal does not record implementation or runtime-validation completion.
