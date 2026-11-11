# play-oem — Large GUI View Responsibilities Investigation Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
View refresh findings:
[PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md](./PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md).
Current dataflow: [PLAY_OEM_DATAFLOW.md](./PLAY_OEM_DATAFLOW.md).

## Goal

Investigate the remaining assessment candidate, **Large GUI view
responsibilities**. Map the responsibilities, state ownership, and tested
contracts of `GroundTrackView` and `GroundStationPassesView`; identify whether
one concrete boundary would make a likely change easier to understand and
verify.

This is an investigation, not a mandate to split either class. Treat necessary
wx, Matplotlib, projection, selection, and store-binding coordination as
behavioral constraints. Do not select an extraction based on class size or
method count alone.

## Planning baseline and initial evidence

At planning time, the worktree is clean at commit
`b6245ad077791eb4e87cd0f8c5daaefaf9d23d1d`.

### Ground Track view

`GroundTrackView` is 1,355 lines at this baseline. Its constructor owns
projection/background settings, station selection and visibility, store
binding, navigation state, Matplotlib artists, wx controls, and callbacks.
`_build_panel` composes the panel and controls; `_draw_map` clears and rebuilds
axes, projection graticules, background, and station artists; store queries
drive track and playback updates.

Map navigation is a candidate boundary, not a confirmed abstraction. Panning,
limit changes, center-longitude synchronization, scrollbars, and projection
redraws exchange state across `_pan_map`, `_sync_center_from_extent`,
`_update_scrollbars`, the scroll handlers, control handlers, and `_draw_map`.
The `_syncing_limits` guard distinguishes redraw-induced limit events from
user navigation. Existing tests explicitly exercise panning across all
configured projections and backgrounds, viewport stability, pole limits,
station selection, station replacement, and resizing.

### Ground Station Passes view

`GroundStationPassesView` is 1,127 lines at this baseline and combines wx
panel/layout management, station and interval selection, access-query
preparation, a pass table, a polar sky plot, playback markers, and user
actions. `GroundStationPassListView` and `GroundStationSkyView` specialize
layout and suppress the unused presentation. `StationAnalysisContext`
already synchronizes selected station/interval state across focused views.

The existing pass-view tests cover range filtering, selection retention,
store-backed access/profile queries, shared selection, responsive layouts,
sky-plot behavior, actions, and close-time unsubscription. This is a useful
comparison for distinguishing a real mixed-responsibility boundary from a
cohesive stateful view with already-shared selection policy.

Line counts are current source measurements, not evidence that either view
needs decomposition. No tests or GUI scenarios have been run for this plan.

## Candidate comparison

| Candidate | State and responsibilities that cross | Existing evidence | Initial risk |
| --- | --- | --- | --- |
| Ground Track navigation | Projection, center longitude, axes limits, `_syncing_limits`, controls, scrollbars, and redraws | `test_ground_track_view.py` covers pan/center behavior, projection/background combinations, limits, and station interactions | High behavioral coupling; a change can alter viewport preservation or projection geometry |
| Ground Track artist lifecycle | Map/background, station, track, footprint, marker, and status artists are created and refreshed through different paths | Store-view and station tests cover selected updates; map rebuild and cleanup paths need a lifecycle trace | Risk of duplicating store/query or artist ownership policy |
| Pass table and sky view | Shared station/interval selection, visible rows, sky plot, playback marker, responsive layout, and actions | `StationAnalysisContext` and focused-view tests already cover cross-view selection and lifecycle | A split may add coordination and weaken selection consistency |

Use the first trace to select at most one bounded experiment. Prefer the
Ground Track navigation boundary only if inspection finds a cohesive,
testable state transition that can be separated without moving wx/axes
semantics into a second orchestration layer. Treat the pass-view structure as
a comparator; do not refactor both views in one work item.

## Test and evidence map

| Area | Initial evidence | Required preservation checks |
| --- | --- | --- |
| Ground Track navigation/projection | `test_ground_track_view.py` | Center normalization, projection redraw, pan/zoom behavior, viewport limits, scroll bounds, resize |
| Ground Track station controls | `test_ground_track_view.py` | Stable station identity, stale-marker removal, no playback seek on marker selection, pass-view callback |
| Ground Track store/playback | `test_ground_track_view.py`, `test_store_raw_views.py` | Bound range, segment boundaries, loading/coverage status, playback marker and footprint behavior |
| Pass table/sky coordination | `test_ground_station_passes_view.py` | Station/interval retention, range overlap, shared selection, playhead visibility, focus/seek callbacks |
| Panel and resource lifecycle | `test_play_oem_app.py`, view tests | Rebuild/update routing, stable panel identity, store binding unsubscribe, close-safe deferred callbacks |

Determine which tests use headless Matplotlib, wx fakes, or a display-gated
wx application before treating them as evidence for native GUI behavior.
Existing tests are a baseline; add only regression cases justified by the
trace or by a selected experiment.

## Investigation procedure

1. Trace construction, state initialization, store binding, update, and close
   for both views. Record ownership of data, wx widgets, Matplotlib objects,
   callbacks, selection state, and subscriptions.
2. Map each `GroundTrackView` responsibility and its state dependencies.
   Follow navigation changes through projection rebuilds and axis-limit
   callbacks; identify which invariants are state transitions versus rendering
   side effects.
3. Map `GroundStationPassesView` table, sky, and selection flows. Verify which
   behavior is already shared through `StationAnalysisContext` and which
   behavior is specialized by the pass-list and sky-view subclasses.
4. Compare the candidate boundaries against actual caller protocols and tests.
   Identify duplicated policy, missed coverage, and display-dependent
   assumptions. Do not infer a production defect from complexity alone.
5. Rank candidate changes by demonstrated consequence, change frequency if
   available, evidence strength, expected reduction in caller or maintainer
   burden, regression risk, and validation cost. Keep unknown metrics unknown.
6. Select no more than one bounded experiment, and only if a cohesive boundary
   reduces total coordination without duplicating existing store, panel, or
   selection ownership. Otherwise document why the current composition is
   preferable.
7. If an experiment is justified, define before/after behavior and focused
   regression criteria before editing. Run the relevant Ground Track/pass
   tests and app integration tests; record GUI skips and the exact environment
   limitation.
8. Update the assessment with the responsibility map, decision, test results,
   remaining uncertainty, and next candidate. Update subsystem/dataflow docs
   only if verified runtime ownership changes.

## Required behavior and constraints

- Preserve Ground Track projection math, normalized center longitude, map
  limits, pan/zoom semantics, scrollbar positions, and resize behavior.
- Preserve station identity/selection, station-layer and label controls,
  pass-view opening, and the guarantee that selecting a marker does not seek.
- Preserve store query binding, range filtering, segment boundaries,
  incremental refresh, playback markers, and close-time unsubscription.
- Preserve pass-list/sky-view shared selection, responsive layout thresholds,
  interval range semantics, table actions, and polar plot/playback behavior.
- Keep wx/Matplotlib resource creation and disposal at a clear owner; do not
  introduce duplicate lifecycle or forwarding layers.
- Separate headless/fake-widget evidence from native display and layout
  evidence. Run display-gated tests only when the environment supports them.
- Do not change behavior or extract a new abstraction solely to reduce lines,
  method counts, or class size.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 8/8 checklist items.
- [x] Trace state and resource ownership through construction, store binding,
      updates, callbacks, and close for both candidate views.
- [x] Map Ground Track navigation state transitions and their projection,
      axes-limit, control, and scrollbar dependencies.
- [x] Map pass-table/sky-view selection and layout flows, including behavior
      already centralized by `StationAnalysisContext`.
- [x] Classify existing tests by behavior and by headless, fake, or native GUI
      evidence; identify only concrete coverage gaps.
- [x] Rank the candidate boundaries using demonstrated benefit, duplication,
      risk, and validation cost; select at most one bounded experiment.
- [x] If justified, define compatibility criteria and add focused regression
      tests before changing production code; otherwise record the no-change
      decision.
- [x] Run the smallest relevant test set and any justified app integration
      tests; record pass, skip, and display-environment results.
- [x] Update the assessment with verified findings, decision, limitations,
      and the next candidate. Update other architecture documentation only if
      runtime ownership changes.

**Done when:** both candidate views have a caller/state/resource/test map; any
selected experiment is bounded by verified behavior and focused tests; and
the decision either demonstrates a cohesive improvement or explicitly
preserves the current composition with its rationale.

## Execution record — 2026-11-10

### Responsibility map and candidate decision

`GroundTrackView` coordinates panel controls, projection and background
rendering, station markers and selection, store-backed track/footprint queries,
playback updates, and navigation. Its navigation path couples projected world
extents, axes limits, center-longitude synchronization, scrollbar positions,
and wx controls. `_update_scrollbars` and the horizontal/vertical handlers
implemented inverse one-dimensional mappings independently: horizontal
positions increase from the left, while vertical positions are reversed.
Scrollbar range, thumb size, travel, overflow, and clamping were embedded in
those methods.

`GroundStationPassesView` combines table and polar-plot presentation, but its
station/interval sharing is already mediated by `StationAnalysisContext`, and
the pass-list and sky-view variants specialize layout/presentation. Existing
tests cover shared selection, responsive layout, retention, actions, and
subscription cleanup. No evidence showed that splitting this view would
reduce total coordination.

The broad view classes were not decomposed. The bounded experiment extracted
the pure scrollbar viewport-to-position and position-to-center mappings into
two private helpers in `ground_track.py`, with shared constants for scrollbar
range, thumb size, and travel. The view still owns projections, wx controls,
axes limits, and redraws. This removes the duplicated horizontal/vertical
conversion policy while keeping GUI lifecycle in its existing owner.

### Regression evidence and validation

Before the implementation, the three new scrollbar tests failed because the
mapping helpers did not exist. The tests now cover forward and reversed
mapping, round-trip viewport centers within scrollbar quantization, no
overflow for a full-world viewport, clamped endpoints, and wiring of both
scrollbars to axis limits and enabled state.

Final focused validation:

- `test_ground_track_view.py` and `test_ground_station_passes_view.py`:
  41 passed, 3 skipped.
- Selected app view lifecycle cases in `test_play_oem_app.py`:
  9 passed, 79 deselected.
- Store-backed view checks in `test_store_raw_views.py`: 3 passed.

The three skips are display-backed wx tests. Headless rendering and app fakes
passed; native wx layout behavior was not verified. Existing Matplotlib and
pyproj deprecation warnings remain outside this change. A Pylance file syntax
request timed out, but the focused test runs imported and executed the modified
module successfully.

### Decision and remaining scope

The scrollbar conversion is a small, cohesive boundary with direct behavioral
tests. No broader state object, view split, or artist manager was justified:
projection and axes interactions are still owned by `GroundTrackView`, while
pass-view selection and lifecycle already have tested shared owners. No
subsystem or dataflow ownership changed. Re-rank the remaining assessment
candidates before selecting another authoritative work item; none is
pre-ranked by this investigation.
