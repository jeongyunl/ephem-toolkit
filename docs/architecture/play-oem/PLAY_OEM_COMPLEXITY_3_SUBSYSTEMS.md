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
| 2 — deferred indefinitely | [Measure representative load, derived-query, and range-change behavior](./PLAY_OEM_COMPLEXITY_32_REPRESENTATIVE_LOAD_MEASUREMENT_PLAN.md). | [Load/replacement](#1-incremental-load-and-replacement), [derived cache](#2-derived-data-scheduling-and-cache-lifetime), and [playback/ranges](#4-playback-coverage-and-time-ranges). | No execution is scheduled. Resume only after explicit reprioritization. If reinstated, use measurements as operating constraints, not optimization targets; time/space complexity optimization remains out of scope. |
| 3 — conditional | Verify native cross-platform GUI behavior. | [Load shutdown](#1-incremental-load-and-replacement) and [panel/native lifecycle](#6-panel-lifecycle-and-gui-resources). | GTK/MSW and native VTK evidence requires suitable runners; do not infer native behavior from fake widgets or add speculative CI. |
| 4 — conditional | Establish external compatibility use. | [Point interpolation and cursors](#5-snapshot-based-point-interpolation). | Seek package/release or consumer evidence before changing cursor, store, or saved-state compatibility paths. |
| 5 — deferred | Reassess maintenance trends. | See the [assessment](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md) for history findings. | Available source history spans only 27 days; revisit after several months of ordinary maintenance. |

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
multi-segment real inputs remains unmeasured. This is not a separate priority-1
benchmark unless representative files or observed behavior implicate station
queries; avoid changing numerical logic without a concrete correctness or
performance problem.

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
rules. The highest-priority end-to-end scenario is a range drag while derived
work is pending during incremental append. Measure it with representative OEM
data, collecting the shared workload metrics in the priority map before
proposing more coordination.

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
two metadata phases because their validation contracts differ. External
consumers remain unknown. Treat consumer discovery as the conditional
compatibility priority; examine partial-load behavior under live derived work
as part of the representative workload only if it exercises these cursor
boundaries. Do not consolidate compatibility paths without consumer and
behavior evidence.

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
behavior. This is conditional on suitable runners or a concrete lifecycle
failure; it is not a reason to block the representative workload study.

## Cross-cutting evidence gaps

The internal dependency and responsibility map is complete; its coverage and
limits are recorded in Plan 33. The representative runtime and memory
measurement is deferred indefinitely and is not an active task. Neither phase
presumes a refactor.

Platform availability, external compatibility evidence, and longer-term
maintenance trends remain conditional or deferred as ranked in the assessment.
Promote a code change only when these observations identify a specific
repeated rule or costly ownership interaction and a bounded change can be
validated without weakening behavior.
