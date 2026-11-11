# play-oem — View Refresh Coordination Complexity Reduction Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Baseline and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context: [PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Load lifecycle findings:
[PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md).
Store scheduling and cache findings:
[PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md](./PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md).
Derived query findings:
[PLAY_OEM_COMPLEXITY_6_DERIVED_STORE_QUERIES_PLAN.md](./PLAY_OEM_COMPLEXITY_6_DERIVED_STORE_QUERIES_PLAN.md).
Current dataflow: [PLAY_OEM_DATAFLOW.md](./PLAY_OEM_DATAFLOW.md).

## Goal

Execute authoritative assessment priority 4, **Reduce repeated view protocol
where equivalent**, using store-driven refresh coordination as the bounded
slice. Trace how store/load/range events become panel updates; compare the
controller's refresh routing with the ten `StoreViewBinding` users and their
view-specific update methods. Identify any genuinely common caller obligation
that can be made easier to follow or test.

Preserve targeted refresh, coalescing, stable snapshot and range behavior,
partial-coverage display, drag deferral, hidden-panel state, wx-thread
ownership, and each view's rendering and resource rules. An evidence-based
decision not to add a helper is acceptable. Do not simplify by moving methods,
replacing tier-specific rendering with a generic callback, or counting source
lines as a proxy for reduced protocol complexity.

This plan is specifically about notification-to-view refresh and its interaction
with store bindings. Do not take on panel construction/rollback (priority 2),
full view lifecycle design (candidate priority 6), or large-view decomposition
(priority 7) except where required to trace refresh behavior.

## Current implementation and initial evidence

`PlayerApp._subscribe_store_notices` subscribes a callback that places
`(store, notice)` pairs on a `SimpleQueue`; it does not call views from the
producer callback. The wx timer invokes `_poll_incremental_load` and then
`_drain_store_notices`. The drain filters notices from replaced stores and
stale epochs, coalesces append/reset into a refresh of all open panels, and maps
tier notices to affected view names. It drains until the queue is empty, with no
per-tick limit observed in this path.

`_refresh_store_views` defers during an incremental-load drag, refreshes its
bound snapshot if epoch/revision/policy changed, then consumes pending panel
IDs. For each panel it may rebuild, call `update_from_store`, apply the range,
update the current time, and request a redraw. Failures are reported in the
status bar. The pending-ID set is cleared before panel updates; trace whether
failed or skipped updates are reliably retried before proposing a change.

`_refresh_incremental_views` serves both the store-backed path and a legacy
non-store path. In the store path it queues all panels and delegates to
`_refresh_store_views`; the legacy path rate-limits rebuilds to
`INCREMENTAL_VIEW_REFRESH_INTERVAL_S` (5 seconds) unless forced. Drag release
can force a pending refresh. Separately, `_dispatch_time_range` updates visible
panels immediately and records range/time state for hidden panels. These paths
may overlap in responsibilities, but their behavior is not presumed
interchangeable.

`StoreViewBinding` owns tier-interest subscriptions and a view's current
`StoreViewContext`. `bind` changes subscriptions when the store identity
changes and always updates the context; `with_range` updates the bound context;
`close` unsubscribes and clears it. The controller's notice-to-view map is a
separate refresh policy. It is not necessarily safe to derive one map from the
other: for example, station-status views bind with no tier interest but are
still included in station-access notice routing because their point metrics
change with the store.

The current ten binding consumers group as follows:

| Consumer | Bound tier interest | Initial refresh-specific distinction |
| --- | --- | --- |
| `SpeedAltitudeView` | series | History series view; controller also owns common range, cursor, and redraw orchestration. |
| `GeocentricDistanceView` | series | Receives both kinematics and distance-delta notice routing. |
| `RtnDeltaView` | series | RTN-only query and rendering behavior. |
| `AngularVelocityView` | series | Direction-rate group. |
| `DirectionChangeView` | series | Shares the direction-rate group but renders a different value. |
| `GroundTrackView` | ground-track, earth-fixed, footprints | Store update refreshes track artists and may request a draw itself. |
| `GroundStationPassesView` | station-access | Parent lifecycle supports pass-list and sky-view presentations. |
| `GroundStationAccessView` | station-access | Access result/profile rendering and station selection. |
| `GroundStationAnalysisView` | station-access, or none for station-status mode | Queries station profiles/metrics; station-status deliberately has no tier subscription. |
| `GroundStationPassTrackView` | ground-track, earth-fixed | Selected-pass rendering with its own range/context updates. |

This list is an orientation inventory. Verify each consumer's build/update/close
sequence, hidden-panel behavior, and whether a context update triggers a query,
artist mutation, layout, or redraw. The Matplotlib and VTK trajectory backends
implement store-view methods but do not appear in the ten binding users; treat
them as comparison cases, not as evidence that they share the binding protocol.

One observable candidate is repeated redraw orchestration: at least
`GroundTrackView.update_from_store` requests `draw_idle`, while the controller
then calls `set_time_range`, `update`, and another draw request. wx/Matplotlib
may coalesce draw requests, so this is not yet a demonstrated duplicate paint
or performance problem. Another candidate is unbounded notice draining on the
timer thread; a continuously replenished queue could delay the next tick, but
no latency or backlog measurement has established that it does.

At planning time, the clean worktree is at commit
`1e52e6bf5440c45c3401f8f75ba1fb28a92449e7`. The inspected baseline files have
1,925 lines in `app/controller.py`, 691 in `views/base.py`, and 2,639 in
`test_play_oem_app.py`. These counts locate the protocol; they are not a
complexity score or a target.

## Initial trigger-to-view map

| Trigger | Initial route | Important policy to verify |
| --- | --- | --- |
| Store append/reset notice | Queue callback -> timer drain -> queue all open panels -> store refresh | Store/epoch filtering, coalescing, pending IDs, and refresh after store replacement. |
| Series tier notice | Series group maps to history view names; distance-delta also targets distance | Targeting accuracy, missing/extra view IDs, and whether update interests match query dependencies. |
| Earth-fixed/Ground Track/footprint notice | Targets Ground Track and pass Ground Track | Point-footprint refresh and range-bound track refresh may have distinct prerequisites. |
| Station-access notice | Targets station-status, pass-strip, profile views, pass-list, sky-view, and pass-ground-track | Some consumers share a panel or have no station-access tier subscription; do not treat view IDs as one-to-one with bindings. |
| Incremental parser progress/completion | `_poll_incremental_load` installs data, updates clock/context, and schedules `_refresh_incremental_views` | Bounded parser-event drain is already in place; preserve final refresh, valid prefixes, stale-generation rejection, and wx-thread installation. |
| Plot-range change/drag | `_dispatch_time_range` updates visible panels or stores pending range for hidden panels; refresh can be deferred during loading drag | Preserve immediate range semantics, hidden-panel catch-up, throttling/defer conditions, and forced refresh at drag end. |
| Panel opened before a store is installed | Store refresh rebuilds panels marked `requires_store_rebuild` | Preserve panel identity, stack, and build-path transition; panel rollback itself is outside this plan. |

The reverse mapping from a tier notice to controller view names and the forward
mapping from each view binding to scheduler tier interest encode related but
different responsibilities. Establish their complete correspondence and
exceptions before considering a registry or shared routing helper.

## Existing tests and evidence to extend

Initial relevant tests include:

- `test_store_view_context_refresh_and_binding_lifecycle` in
  `test_store_series_views.py`: immutable contexts, context refresh, binding
  store-switch behavior, tier-interest unsubscribe, and close.
- `test_incremental_store_appends_extend_clock_and_complete_full_history`,
  `test_incremental_panel_data_update_reuses_view_and_canvas`,
  `test_store_refresh_rebuilds_panels_opened_before_the_store`, and
  `test_incremental_timeline_uses_declared_domain_and_defers_drag_redraws` in
  `test_play_oem_app.py`: notice routing, in-place update, pre-store rebuild,
  timeline state, and drag deferral.
- `test_ground_station_updates_refresh_open_station_views` and
  `test_replacement_refreshes_cancelled_active_store_context`: station view
  refresh and replacement context behavior.
- `test_failed_view_change_restores_the_original_panel`: relevant only as a
  regression guard if a refresh change touches replacement/cleanup.
- Store-view tests for partial series coverage, Ground Track updates, and
  station/pass coverage: preserve view-specific interpretation rather than
  asserting only that an update callback ran.

Map every existing refresh and binding test to a behavior; add tests only for
demonstrated gaps. Likely cases to assess include:

- Multiple same-tick notices coalesce to one affected-panel refresh; stale
  store/epoch notices do not update a replacement.
- Tier routing updates exactly the dependent panels, including station-status
  without a station-access subscription, and avoids unrelated panels.
- A notice storm does not monopolize the timer thread, if measurement confirms
  the unbounded drain is a responsiveness risk.
- Drag deferral and release produce one current-snapshot/current-range update;
  hidden panels receive the latest range when shown.
- A view update failure is surfaced, and its retry/recovery behavior is
  documented; add automatic retry only if a safe bounded policy is established.
- Store replacement and close unsubscribe old listeners and do not deliver
  callbacks into disposed views.

## Interactions and constraints

- **Store notice producer and scheduler:** notices can be emitted from
  background derived computations. Keep producer callbacks thread-safe and
  lightweight; do not invoke wx or view methods from scheduler threads.
- **Incremental loader:** parser events are separately polled and already have
  a per-tick bound. Distinguish that queue from store notices. Preserve
  generation/epoch filtering, batch installation, completion handling, and
  valid-prefix visibility.
- **Time range and playback:** visible views receive range/time changes through
  `_dispatch_time_range`; hidden views retain pending values. Refresh
  coalescing must not drop a seek or change playback/cursor state.
- **Store snapshots and query coverage:** each refresh uses one stable
  `StoreViewContext`; refresh on changed epoch/revision/policy while retaining
  partial data and view-specific incomplete-coverage messaging.
- **`StoreViewBinding`:** subscriptions express tier interest for scheduler
  behavior and must be released on store switch/close. Keep them distinct from
  controller refresh routing unless a shared representation proves both
  contracts without introducing panel-name coupling into views or stores.
- **Rendering/backends:** a `draw_idle` request is not necessarily a completed
  paint. Count requests and measure elapsed timer work separately; retain
  Ground Track, station/table, history, Matplotlib, and VTK update semantics.
- **Panel lifecycle:** `_open_view` rollback, resource ownership, and
  backend-native cleanup are already separate assessment candidates. Preserve
  those guarantees but do not refactor panel creation as a proxy for refresh
  simplification.

## Required behavior and constraints

- Keep all store and view refresh mutations on the wx thread; store callbacks
  only enqueue notices.
- Preserve store identity and epoch filtering, tier-specific routing, notice
  coalescing, and targeted versus full refresh behavior.
- Preserve stable snapshot capture, current resolved plot range, coverage,
  current-time update, and hidden-panel pending state.
- Preserve incremental-load refresh rate/defer behavior and the forced final or
  post-drag refresh.
- Preserve store-binding interest changes on store switch, and unsubscribe on
  close or replacement.
- Preserve partial coverage, view-specific rendering, and backend-specific
  resource cleanup.
- Do not add a generic refresh framework, registry, queue cap, or redraw
  suppression until the traced ownership and measured benefit justify it.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 8/8 checklist items.
- [x] Trace one append, one tier notice for each tier family, one replacement,
      one load completion, and one range/drag event from producer through timer
      dispatch to visible/hidden panel behavior. Record thread, store/epoch and
      snapshot revision, coalescing, pending IDs, current range/time, view
      callback order, and redraw requests.
- [x] Build an event-to-view matrix for append/reset, series groups,
      Earth-fixed/Ground Track/footprints, station access, incremental parser
      progress/completion, range changes, and store replacement. Mark all
      affected view names, non-refresh cases, unknown notices, and stale queue
      rejection.
- [x] Inventory all ten `StoreViewBinding` users by tier interest and build,
      update, range/query, redraw, close, and replacement obligations. Compare
      them with the controller routing map and document intentional
      mismatches, including station-status and panel subviews.
- [x] Map existing tests to the matrix and run the focused controller,
      binding, range, history, Ground Track, and station-view suites. Add only
      deterministic tests for a demonstrated routing, lost-update, stale
      notice, deferral, failure-recovery, or responsiveness gap.
- [x] Record a before baseline at a specific commit and working-tree state:
      affected methods/callers, refresh and redraw request counts for
      representative triggers, queue depth/drain time under a reproducible
      notice burst if relevant, and test coverage. State commands, setup,
      counts, and limitations; do not equate `draw_idle` calls with actual
      paints or infer change frequency.
- [x] Rank identified issues by evidence, frequency, consequence, and
      reasoning/testing cost. Select one bounded candidate, with expected
      benefit, affected consumers, alternatives, preserved invariants, and
      rejection criteria. Candidate evidence includes repeated controller/view
      update steps, mismatch between binding interest and refresh routing, and
      the uncapped timer-thread notice drain; none is a pre-approved fix.
- [x] Evaluate one small experiment and compare behavior, callers, tests,
      update/redraw counts, timer responsiveness, local reasoning, overall
      coupling, and code volume. Keep the change only if the total protocol is
      simpler without losing targeted updates, recovery, or view-specific
      behavior.
- [x] Update the assessment with verified findings and revised priorities.
      Update dataflow or view/store design only if behavior or ownership
      changes. Record validation, remaining uncertainty, the decision, and the
      next work item.

## Execution record — 2026-11-10

### Verified refresh flow and view contracts

The store's subscriber callback only queues `(store, notice)`; it does not call
wx or views. `_on_timer` runs `_poll_incremental_load` and then drains notices.
The load poll is wx-thread-owned and already caps parser events at 64 per tick.
The notice drain filters by store identity and the current snapshot epoch,
coalesces append/reset to all open panels, and unions the view IDs from
`_views_for_tier_notice`. It then refreshes against a single current
`StoreViewContext` snapshot. The binding tests confirm that same-store context
updates do not duplicate tier interest and changing stores unsubscribes the old
store.

The controller mapping was verified for every tier family:

| Notice | Refreshed view IDs |
| --- | --- |
| series / kinematics | speed-altitude, distance |
| series / rtn | rtn |
| series / direction-rates | angular-velocity, direction-change |
| series / distance-delta | distance |
| earth-fixed, ground-track, or footprints | ground-track, pass-ground-track |
| station-access | station-status, pass-strip, elevation-profile, azimuth-profile, range-profile, pass-list, sky-view, pass-ground-track |

The ten bindings and their tier sets are enumerated in the initial inventory.
They are not a duplicate copy of the view routing map: bindings register
scheduler tier interest, while the controller map expresses which visible
panels become stale. Station-status is intentionally refreshed by
station-access notices although its `StoreViewBinding` has no tier interest.
Deriving the refresh map from binding subscriptions would miss that point-query
consumer.

Range changes use a separate path. `_dispatch_time_range` updates visible
panels and stores the latest range/time for hidden panels; `_refresh_store_views`
also applies range, current time, and redraw after `update_from_store`. At least
`GroundTrackView.update_from_store` itself requests `draw_idle`, so the
controller can issue more than one redraw request. Actual paints may coalesce;
no view-paint count or user-visible rendering cost was demonstrated. Keep the
view-specific update methods and do not remove generic controller updates
without evidence for all ten consumers.

The failure path is explicit but not automatic: `_refresh_store_views` reports
an exception in the status bar, but it has already cleared the pending-ID batch
and does not retry that panel on the next timer tick. A later notice can trigger
another attempt. No update failure was reproduced. Automatic per-tick retry
could hot-loop on a persistent view error, so the retry policy remains a
product/behavior question rather than an assumed fix.

### Notice-drain experiment and decision

Baseline commit was
`1e52e6bf5440c45c3401f8f75ba1fb28a92449e7`; the worktree was clean before
this task. Source counts were 1,925 lines in `app/controller.py` and 691 in
`views/base.py`. The execution test selection covered
`test_play_oem_app.py`, `test_store_series_views.py`, the time-range action and
slider tests, Ground Track, station access/analysis/passes, the history view
tests, and `test_graph_panel.py`.

The notice drain was measured with a `SimpleQueue` containing identical valid
series `TierNotice` objects and an active store, but no open panels. Queue
construction was outside the timed interval; five trials per size measured the
real drain/filter/mapping loop while excluding view updates and rendering:

| Notices drained | Median drain time | Trial range |
| ---: | ---: | ---: |
| 10,000 | 11.51 ms | 11.46-11.55 ms |
| 100,000 | 114.63 ms | 114.38-114.86 ms |

The experiment confirms linear timer-thread work for a large backlog, but it
does not establish that production creates such a backlog. Parser-driven append
notices are constrained by the existing 64-event poll; derived notices are
produced by background work, and their real queue depth/rate was not measured.
A naive per-tick cap would either refresh each partial batch (undoing existing
coalescing and potentially causing repeated rendering) or defer refresh until
the queue empties (which can starve under a continuously replenished queue).
Without representative producer-rate evidence and an explicit coalescing
policy, no queue cap is justified.

No shared registry/helper was justified either: tier interest and stale-view
routing are different policies, and station-status demonstrates a real
mismatch. No source production files changed. Added an eight-case
`test_tier_notices_target_only_dependent_views` matrix for all tier/group
targets, and extended the incremental-store integration test with duplicate
and stale-epoch notices to verify one coalesced update and stale rejection.

The focused command ran the app controller, binding/context, range, history,
Ground Track, station, and graph-panel test files. Result: 217 passed, 3
skipped, 18 existing Matplotlib/Pyparsing and pyproj deprecation warnings. The
test-only change does not establish a performance improvement. The synthetic
drain timing is a stress bound, not a production workload benchmark.

**Decision:** retain the current refresh and binding architecture. The tier
map is explicit and now directly tested; rendering remains view-specific; and
the measured drain cost is concerning only at synthetic backlog sizes whose
production likelihood is unknown. Revisit notice batching if real queue-depth
or timer-latency instrumentation shows sustained backlog. Keep the visible
error message and the lack of automatic retry documented; reconsider recovery
only with a bounded policy and a reproducing failure case.

The assessment records this result. No dataflow or store design change is
warranted. The next authoritative work item is priority 5, saved-state parsing
and validation.

**Done when:** trigger-to-view behavior and all ten binding contracts are
verified; refresh, binding, and rendering responsibilities are distinguished;
a concrete candidate is accepted or rejected using tests and measurements; and
no update, range, thread, subscription, or cleanup guarantee is weakened.
Report local complexity, overall coupling, code volume, and runtime/rendering
effects separately. Do not claim a reduction if the investigation concludes
the current protocol is intentionally tier- or view-specific.

**Depends on:** [PLAY_OEM_COMPLEXITY_6_DERIVED_STORE_QUERIES_PLAN.md](./PLAY_OEM_COMPLEXITY_6_DERIVED_STORE_QUERIES_PLAN.md)
and assessment priority 4. This plan does not supersede the main
release-readiness plan.
