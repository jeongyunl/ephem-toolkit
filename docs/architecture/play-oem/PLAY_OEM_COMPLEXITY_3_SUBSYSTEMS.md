# play-oem complexity: subsystem research

This research records the original static findings and the later targeted
investigations of difficult state, concurrency, and domain behavior. The initial
inspection used commit `cf93496`; current decisions and less-evaluated areas are
summarized in the [complexity assessment](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Rankings are qualitative judgments, not defect findings.

## Scope boundary

This research supports reducing implementation complexity, not algorithmic
efficiency. Reducing asymptotic time complexity or space complexity (Big-O
runtime or memory) is out of scope. Runtime and memory observations may define
constraints or check that maintainability changes preserve behavior, but lower
latency or RSS is not a target; separate performance or memory optimization
work should be tracked independently.

## Current priority map

The subsystem sections below preserve verified behavior and design constraints;
their order reflects investigation history, not the next-work sequence. The
[assessment](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md) owns the ranked tasks and
decision criteria.

| Priority | Evidence task | Relevant subsystem findings | Timing and boundary |
| --- | --- | --- | --- |
| 1 — complete | [Map internal dependencies and responsibility ownership](./PLAY_OEM_COMPLEXITY_33_INTERNAL_DEPENDENCY_RESPONSIBILITY_MAP_PLAN.md). | All six subsystem sections, especially load/controller, store/cache, view, and backend interactions. | The first-pass map found no eager import cycle or avoidable boundary cost. Retain current boundaries; revisit explicit coordination points only if future changes demonstrate repeated cost. |
| 2 — complete | [Retire `OemCursor`](./PLAY_OEM_COMPLEXITY_36_OEM_CURSOR_RETIREMENT_FEASIBILITY_PLAN.md). | [Snapshot-based interpolation and cursors](#5-snapshot-based-point-interpolation), app startup, and incremental loading. | `StoreCursor.empty()` provides pre-load startup without store lifecycle costs; trajectory updates use committed store samples. Focused migration suites passed (266 tests). |
| 3 — complete | [Review saved-state validation structure](./PLAY_OEM_COMPLEXITY_37_SAVED_STATE_VALIDATION_BOUNDARY_PLAN.md). | Saved-state loading, schema validation, and compatibility fallback. | Retained the inline checks: their section-specific order and error handling outweigh the duplicated mechanics. Focused saved-state, CLI, and config tests passed (71). |
| 4 — complete | [Review panel-open preflight](./PLAY_OEM_COMPLEXITY_38_PANEL_OPEN_PREFLIGHT_PLAN.md). | [Panel/native lifecycle](#6-panel-lifecycle-and-gui-resources). | Retained the inline preflight; fixed failed forced replacement dropping the restored default-view lookup. Focused lifecycle/panel/cleanup suites passed (157). |
| 5 — complete | [Review terminal load cleanup](./PLAY_OEM_COMPLEXITY_39_TERMINAL_LOAD_CLEANUP_PLAN.md). | [Load/replacement](#1-incremental-load-and-replacement) and [playback/ranges](#4-playback-coverage-and-time-ranges). | Shared only the identical `COMPLETE`/`FAILED` drag reset after their distinct transitions; retained Plan 26's single event loop. App/loader suites passed (113). |
| 6 — complete | [Review capacity scanner simplification](./PLAY_OEM_COMPLEXITY_40_CAPACITY_SCANNER_SIMPLIFICATION_PLAN.md). | [Load/replacement](#1-incremental-load-and-replacement) and store allocation. | Replaced the two scanner paths with one bounded strict-UTF-8 scanner; 88 focused tests passed and the synthetic medians met Plan 40's guardrails. Plan 32 remains deferred. |
| 7 — complete | [Review pass endpoint look-angle policy](./PLAY_OEM_COMPLEXITY_41_PASS_ENDPOINT_LOOK_ANGLE_POLICY_PLAN.md). | [Playback/ranges](#4-playback-coverage-and-time-ranges) and Ground Station Passes rendering. | Shared endpoint normalization locally; the two methods plus helper decreased from 124 to 115 lines and score 42 to 36. Focused suite passed (27, 1 skipped); no view split. |
| 8 — complete | [Review sky-plot empty-state rendering](./PLAY_OEM_COMPLEXITY_42_SKY_PLOT_EMPTY_STATE_RENDERING_PLAN.md). | Ground Station Passes rendering. | Reused shared centered text options; `_draw_sky_plot` decreased from 172 to 157 lines with decision score unchanged at 27. Focused suite passed (28, 1 skipped); state precedence remains inline. |
| 9 — complete | [Review sky-plot layout padding](./PLAY_OEM_COMPLEXITY_43_SKY_PLOT_LAYOUT_PADDING_PLAN.md). | Ground Station Passes rendering. | Shared one subplot adjustment; `_draw_sky_plot` decreased from 157 to 152 lines with score unchanged at 27. Focused suite passed (29, 1 skipped); exact margins and legend ordering preserved. |
| 10 — complete | [Review access-graph interval annotation](./PLAY_OEM_COMPLEXITY_44_ACCESS_GRAPH_INTERVAL_ANNOTATION_PLAN.md). | Ground Station Access rendering. | Selected label and hatch together; `_draw_elevation_graph` decreased from 122 to 119 lines and score from 26 to 24. Focused suite passed (5); gap precedence and legend de-duplication preserved. |
| 11 — complete | [Review access-plot empty-state rendering](./PLAY_OEM_COMPLEXITY_45_ACCESS_GRAPH_EMPTY_STATE_RENDERING_PLAN.md). | Ground Station Access rendering. | Reused local centered text options; `_draw_elevation_plot` decreased from 82 to 77 lines with score unchanged at 15. Focused suite passed (5); message precedence and axes-on/off behavior preserved. |
| 12 — deferred indefinitely | [Hosted wx test pilot](./PLAY_OEM_COMPLEXITY_19_HOSTED_WX_TEST_PILOT_PLAN.md). | [Load shutdown](#1-incremental-load-and-replacement) and [panel/native lifecycle](#6-panel-lifecycle-and-gui-resources). | GTK/MSW and native VTK behavior remains unverified. Do not resume without explicit reprioritization. |
| 13 — deferred indefinitely | [Measure representative load, derived-query, and range-change behavior](./PLAY_OEM_COMPLEXITY_32_REPRESENTATIVE_LOAD_MEASUREMENT_PLAN.md). | [Load/replacement](#1-incremental-load-and-replacement), [derived cache](#2-derived-data-scheduling-and-cache-lifetime), and [playback/ranges](#4-playback-coverage-and-time-ranges). | No execution is scheduled. Resume only after explicit reprioritization; measurements remain operating constraints, not optimization targets. |
| 14 — deferred | Reassess maintenance trends. | See the [assessment](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md) for history findings. | Available source history spans only 27 days; revisit after several months of ordinary maintenance. |

These are evidence-collection priorities, not proposals to remove domain rules,
asynchronous loading, caching, or backend variants. Potential simplification
must come from clarifying necessary behavior and containing its interactions.

## Dependency and responsibility map (Plan 33)

The completed [Plan 33 execution record](./PLAY_OEM_COMPLEXITY_33_INTERNAL_DEPENDENCY_RESPONSIBILITY_MAP_PLAN.md)
maps 63 package modules and 238 direct eager internal import edges; the
first-pass graph had no eager cycles. Type-only and local imports account for
apparent cycles in a broader scan, including the intentional lazy VTK path.
This static result is not a complete runtime call graph.

The main ownership boundaries are explicit: the incremental session and loader
own worker/generation state, the store owns raw and derived data plus query
scheduling, view bindings own tier-interest subscriptions, and the app
coordinates snapshot installation and refresh. Range actions dispatch
snapshot-bound state to views, while the workspace owns panel placement and
redraw scheduling. The app is the composition root; callbacks and dynamic
registration cross module boundaries without creating an eager import cycle.

Adding a view or derived-tier consumer requires coordinated edits to distinct
registry, factory, panel-dispatch, subscription, and refresh-routing contracts.
Those are the clearest maintenance hotspots, but the inspected paths and tests
did not establish duplicated policy or recurring failures that justify
consolidation. No production refactor is proposed. Plan 32 is deferred
indefinitely and will not be resumed without explicit reprioritization.

## 1. Incremental load and replacement

**Where:** [`incremental_loader.py`](../../../src/ephem_toolkit/play_oem/incremental_loader.py),
[`streaming_oem.py`](../../../src/ephem_toolkit/play_oem/streaming_oem.py),
`OemDataStore` lifecycle methods, and
[`PlayerApp._poll_incremental_load`](../../../src/ephem_toolkit/play_oem/app/controller.py).

The worker scans capacity when necessary, streams rows into an epoch-scoped
store, and publishes generation-tagged events. The wx-thread controller drains
five event kinds, validates append notices against snapshots, and installs the
first usable data before the load completes. A replacement can start while old
data or work still exists. Generation identifies the load session; epoch
protects store operations. They are related but not interchangeable.

**Reasoning challenge:** a failure before the first batch and a failure after
the first batch have different visible outcomes. For example, a failed
replacement can retain the previously installed OEM before first append, while
a later failure can leave a valid prefix of the new one. A late event must not
install data from an obsolete generation. Cancellation, queue backpressure,
store invalidation, and GUI shutdown add ordering constraints. Tests named
`test_incremental_replacement_keeps_old_oem_until_first_batch`,
`test_failed_incremental_replacement_leaves_current_oem_installed`, and
`test_controller_ignores_stale_incremental_events` cover parts of this behavior;
loader tests cover cancellation and stale appends.

**Current status and remaining evidence:** Plan 4 records the transition table
and bounded event-drain change; Plans 20–21 verify close during blocked parsing,
including real wx resources on macOS Cocoa. Plan 33 maps the session/loader,
store, and controller ownership and finds no boundary change to make. Plan 32's
combined measurement is deferred indefinitely and is not scheduled. GTK/MSW
behavior is a separate conditional check when runners are available. Do not
reopen event-policy work without a concrete platform or responsiveness
finding.

## 2. Derived-data scheduling and cache lifetime

**Where:** [`oem_data_store.py`](../../../src/ephem_toolkit/play_oem/oem_data_store.py),
[`chunk_memo.py`](../../../src/ephem_toolkit/play_oem/chunk_memo.py), and
[`views/base.py`](../../../src/ephem_toolkit/play_oem/views/base.py).

Queries can return partial coverage while missing data is computed. The store
schedules and prioritizes work, memoizes derived chunks, and may evict them;
views can hold references to data backed by those chunks. `ChunkMemo` shares an
in-flight computation among callers and checks epoch and policy revision. It
distinguishes absent, computing, tentative, and complete entries; a tentative
entry is recomputed on the next request.

**Reasoning challenge:** a computation can finish after a range, epoch, policy,
or subscription changes, and invalidated work must not publish as current.
Memory reclamation must also respect active views. These rules interact with
which derived tier actually depends on interpolation policy; one global
invalidation rule could recompute unnecessarily or reuse invalid data. Existing
tests cover in-flight deduplication and invalidation in `test_chunk_memo.py`,
and policy-dependent prefetch keys, partial coverage, and pinned views in
`test_oem_data_store.py`.

**Current status and remaining evidence:** Plans 5–6 mapped tier validity and
shared query rules; Plan 30 clarified the eviction-candidate representation.
Plan 33 confirms the store owns scheduler/cache policy while view bindings own
tier-interest subscriptions. Broader scheduler/query extraction was rejected.
Plan 32's representative peak RSS and query/load latency study is deferred
indefinitely and will not be resumed without explicit reprioritization.
Reducing runtime or memory complexity is out of scope.

## 3. Station access and pass boundaries

**Where:** [`station_access._intervals_for_segment`](../../../src/ephem_toolkit/play_oem/station_access.py),
the store's `station_access` query, and station views.

The interval computation tracks whether access is active, refines entry and
exit crossings, records peak elevation and minimum range, and handles missing
metrics, coverage edges, and segment gaps. A store query additionally deals with
range-limited profiles and partial results. The function's score of 42 was from
the initial assessment baseline; the key issue is the relationship among these
states and boundaries, rather than the score itself.

**Reasoning challenge:** a pass beginning at coverage is different from a
refined entry within valid data; missing metrics interrupt continuity; a
segment gap must not be mistaken for a continuous interval. Clipping and
extrema must remain consistent with the actual interval. Existing station
analysis tests cover partial coverage and multi-segment profiles, while store
tests cover station profiles and interpolation-dependent support margins.

**Current status and remaining evidence:** Plan 27 grouped active interval
metrics in `_ActiveAccessInterval`; Plan 29 rejected phase extraction because
the query phases share state and cache/lock ordering. Existing numerical tests
cover boundary and gap behavior. Runtime cost on large, discontinuous,
multi-segment real inputs remains unmeasured. No benchmark is scheduled under
Plan 32, which is deferred indefinitely; do not reopen it without explicit
reprioritization. Avoid changing numerical logic without a concrete
correctness finding.

## 4. Playback, coverage, and time ranges

**Where:** [`clock.py`](../../../src/ephem_toolkit/play_oem/clock.py),
[`time_range.py`](../../../src/ephem_toolkit/play_oem/time_range.py), and
[`app/time_range_actions.py`](../../../src/ephem_toolkit/play_oem/app/time_range_actions.py).

The clock tracks current time, signed rate, play/loop state, coverage, and
independent playback bounds. Plot endpoints can independently follow playback
bounds, use an offset from current time, or be fixed. Resolution clips to OEM
coverage; crossed or disjoint endpoints yield an empty effective range. During
incremental loading coverage can grow while explicit playback bounds or saved
range choices remain meaningful.

**Reasoning challenge:** a seek can change a relative plot range without
changing the plot rule; an append can extend coverage without moving the cursor
or resuming playback. Reverse and loop behavior add endpoint cases. Existing
clock tests cover both directions, looping, and coverage extension; time-range
tests cover endpoint combinations, clipping, and empty ranges.

**Current status and remaining evidence:** Plans 7 and 23–26 mapped refresh and
snapshot-installation behavior, retaining separate playback and plot-bound
rules. Plan 32 describes an end-to-end range-drag scenario while derived work
is pending during incremental append, but that measurement is deferred
indefinitely and is not scheduled.

## 5. Snapshot-based point interpolation

**Where:** `OemDataStore.state_at` in
[`oem_data_store.py`](../../../src/ephem_toolkit/play_oem/oem_data_store.py)
and [`cursor.py`](../../../src/ephem_toolkit/play_oem/cursor.py).

A point query checks the store epoch and interpolation policy revision, then
distinguishes empty data, out-of-range time, exact samples, segment gaps, and
interpolated samples. Interpolation needs support samples and must not bridge a
gap. The result also includes derived values. Querying at the same time after
forward playback, reverse playback, or seek should not depend on traversal
history.

**Reasoning challenge:** a snapshot and an interpolation policy jointly define
validity, while partial loads may change available support at a boundary. The
compatibility and store-backed cursor paths must be compared before assuming
they can share or discard behavior. Tests cover snapshot policy changes and
point-query behavior in `test_oem_data_store.py`, and stateless samples, edges,
and gaps in `test_stateless_interpolation.py`.

**Current status and remaining evidence:** Plan 10 compared both cursor paths
across exact, interpolated, gap, and out-of-range results; Plan 28 retained the
two metadata phases because their validation contracts differ. Plan 35 first
clarified the app's switched cursor typing. Plan 36 subsequently retired
`OemCursor`: the app and views now use `StoreCursor`, whose inert empty state
covers pre-load startup and whose bound state queries the active store
snapshot. The trajectory view's append/update test commits to the store and
refreshes the cursor. The migration's focused suites passed (266 tests).
External compatibility is not a gate by maintainer direction.

## 6. Panel lifecycle and GUI resources

**Where:** [`PanelManagementMixin._open_view`](../../../src/ephem_toolkit/play_oem/app/panel_management.py)
and view-specific `close` methods.

Opening a panel acquires a host, view, content, callbacks, and possibly a
Matplotlib canvas or native backend resources. Replacement must keep or restore
the old panel if construction fails. Resources become available at different
stages, so rollback remains stage-specific.

**Verified:** Plan 12 centralized low-level resource release; Plan 14 established
partial-startup rollback while keeping transaction cleanup explicit. Plan 15
rejected a shared result classifier because views have distinct partial/empty
presentation rules. Plans 16 and 20–21 verified native startup and active-load
cleanup on macOS Cocoa.
Plans 17–19 found no available GTK/MSW runner and added no speculative CI.
Detailed evidence and tests remain in the individual plan documents linked
from the [assessment](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).

**Remaining evaluation:** GTK/MSW teardown and native VTK widget lifecycle are
unverified. Fake-widget tests do not establish native event or resource
behavior. Plan 19 is deferred indefinitely and will not resume without explicit
reprioritization. Plan 32's workload study is also deferred indefinitely.

## Cross-cutting evidence gaps

The internal dependency and responsibility map is complete; its coverage and
limits are recorded in Plan 33. The project maintainer has said that there are
not yet external users and compatibility is not a concern, so Plan 34 is closed
without execution. The representative runtime and memory measurement is
deferred indefinitely. Plan 35 completed a minimal typing clarification; Plan
36 superseded its two-cursor model by retiring `OemCursor`. `StoreCursor` is now
the only playback cursor, with an inert empty state for startup and a
snapshot-backed state for loaded data.

Plan 37 completed without a code change: the proposed helper would not reduce
validation rules or caller obligations. Plan 38 retained its inline preflight
and fixed failed forced replacement losing the old default-view lookup; the
focused lifecycle/panel/cleanup suites passed (157). Plan 39 shared terminal
drag cleanup without extracting event handlers; the app and incremental-loader
suites passed (113). Plan 40 removed the separate ASCII capacity scanner after
the single bounded path passed behavior tests and synthetic timing guardrails.
Plan 41 completed a local endpoint-normalization review in the Ground Station
Passes view; its shared helper retained the distinct coverage and interpolation
rules and reduced the combined decision score. Plan 42 reused centered
status-text options without moving its message-selection branches or changing
precedence; it did not split the view. Plan 43 shared subplot-padding setup
while preserving the two margins and legend ordering. Plan 44 paired access
interval labels and hatches without changing gap precedence or legend
de-duplication. No further production refactor is selected. Plan 19's platform
validation, Plan 32's workload study, and longer-term maintenance review
remain deferred indefinitely as ranked in the assessment.
Promote a follow-on code change only when evidence identifies a specific
repeated rule or costly ownership interaction and a bounded change can be
validated without weakening behavior.
