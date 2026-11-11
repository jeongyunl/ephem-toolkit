# play-oem complexity: subsystem research

This research examines behavior that is difficult to reason about because of
interacting states, ordering, concurrency, or numerical boundaries. It is based
on static inspection of the source and named tests at commit `cf93496`; the tests
were not run for this research. The [complexity assessment](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md)
contains the separate size and decision-count baseline. Rankings below are
qualitative judgments about reasoning and consequences, not defect findings.

## Investigation overview

| Order | Subsystem | Main source of logical complexity | Recommended investigation |
| --- | --- | --- | --- |
| 1 | Incremental load and replacement | Concurrent generation, store epoch, partial installation, and failure state | Model transitions and ownership across worker and UI. |
| 2 | Derived-data scheduling and cache lifetime | In-flight work, invalidation, tentative results, pinned views, eviction | Map validity keys, locks, and ownership for each tier. |
| 3 | Station access and pass boundaries | Discontinuous samples, refined crossings, clipped intervals, extrema | Specify the interval state machine and boundary cases. |
| 4 | Playback and time ranges | Independent coverage, playback bounds, moving plot rules, ongoing loading | Trace range resolution and changes under append and seek. |
| 5 | Snapshot-based point interpolation | Segment gaps, policy revisions, support points, exact versus interpolated state | Document snapshot and interpolation contracts across consumers. |
| 6 | Panel construction and teardown | Partial resource acquisition, rollback, replacement, native GUI lifetime | Map ownership and failure paths. |

This order reflects the focus of the subsystem research. The assessment owns
the overall work-item priorities. They do not imply that
domain rules, asynchronous loading, or caching should be removed. In particular,
some complexity is inherent in the required behavior; potential reduction lies
in clarifying and containing it.

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

**Next:** construct an event/transition table showing the current and pending
store, generation, epoch, installed prefix, and thread at each transition.
Cross-reference each transition with tests, including close and cancellation
under backpressure. Investigate grouping lifecycle state only after establishing
which combinations are valid. A reduction must retain partial loading and the
old-data/valid-prefix behavior.

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

**Next:** document, per tier, its key, input revisions, work cancellation,
publication condition, and pin/eviction lifetime. Draw the lock and ownership
boundaries, then examine whether the caller protocol or shared policy can be
simplified without sacrificing range-limited computation or memory behavior.
Measure peak memory and relevant load/query performance for any experiment.

## 3. Station access and pass boundaries

**Where:** [`station_access._intervals_for_segment`](../../../src/ephem_toolkit/play_oem/station_access.py),
the store's `station_access` query, and station views.

The interval computation tracks whether access is active, refines entry and
exit crossings, records peak elevation and minimum range, and handles missing
metrics, coverage edges, and segment gaps. A store query additionally deals with
range-limited profiles and partial results. The local interval function has a
decision score of 42 in the assessment, but the key issue is the relationship
among these states and boundaries, rather than the score itself.

**Reasoning challenge:** a pass beginning at coverage is different from a
refined entry within valid data; missing metrics interrupt continuity; a
segment gap must not be mistaken for a continuous interval. Clipping and
extrema must remain consistent with the actual interval. Existing station
analysis tests cover partial coverage and multi-segment profiles, while store
tests cover station profiles and interpolation-dependent support margins.

**Next:** enumerate entry, exit, missing-data, gap, and coverage-edge cases in
a small transition table, including extrema initialization and reset. Map each
case to the lower-level access tests as well as store/view tests; identify
uncovered combinations before considering a cohesive active-pass state object
or other simplification. Preserve crossing refinement and clipping semantics.

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

**Next:** trace one fixed/follow combination and one moving-offset combination
through seek, append, and a range drag, including UI refresh. Identify which
layer owns rules versus resolved bounds and whether there is repeated
coordination. Preserve the distinction between empty plot range and unloaded or
partial coverage; do not collapse playback and plot bounds for convenience.

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

**Next:** map which consumers use each cursor, their status and unit contracts,
and how changes to raw samples or policy affect a result. Compare behavior at
exact samples, near segment edges, and during incremental append. Simplify only
where the same numerical and compatibility guarantees can be demonstrated.

## 6. Panel lifecycle and GUI resources

**Where:** [`PanelManagementMixin._open_view`](../../../src/ephem_toolkit/play_oem/app/panel_management.py)
and view-specific `close` methods.

Opening a panel acquires a host, view, content, callbacks, and possibly a
Matplotlib canvas or native backend resources. Replacement must keep or restore
the old panel if construction fails. Different resources become available at
different points, so rollback depends on how far construction progressed.

Application startup has a separate rollback boundary: if `PlayerApp` GUI
construction fails, it releases the clock observer, timer, completed
workspace, and frame acquired so far, while preserving the process-level
`wx.App`. The failure-injection evidence and native-wx limitation are recorded
in [plan 14](./PLAY_OEM_COMPLEXITY_14_PARTIAL_GUI_STARTUP_CLEANUP_PLAN.md).

The panel/view resource-acquisition and cleanup paths are mapped in
[plan 12](./PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md), and
application partial-startup cleanup is covered in
[plan 14](./PLAY_OEM_COMPLEXITY_14_PARTIAL_GUI_STARTUP_CLEANUP_PLAN.md).
The [plan 15 result-state comparison](./PLAY_OEM_COMPLEXITY_15_STORE_VIEW_RESULT_STATE_PLAN.md)
found distinct view-specific query and presentation rules; no shared result
classifier or resource-ownership change was justified. Native wx partial
startup cleanup was verified on macOS Cocoa in
[plan 16](./PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md); other
wx backends and versions remain unverified. Plan 17 completed a runner
feasibility review: this environment has no Linux/GTK or Windows/MSW runner,
local container runtime, or repository workflow configuration, so cross-platform
execution is blocked. The macOS result must not be generalized; continuing
requires access to GTK/Linux and MSW/Windows runners. Evidence and limitations
are recorded in
[plan 17](./PLAY_OEM_COMPLEXITY_17_CROSS_PLATFORM_WX_CLEANUP_PLAN.md).
The next step is the separately scoped runner-enablement investigation in
[plan 18](./PLAY_OEM_COMPLEXITY_18_WX_CI_RUNNER_ENABLEMENT_PLAN.md), which first
proves hosted wxGTK/Xvfb and wxMSW desktop feasibility before proposing minimal
CI jobs. Self-hosted infrastructure and broader compatibility matrices remain
out of scope.
Plan 18 found zero configured GitHub Actions workflows and no way in this
session to validate hosted policy or actual non-macOS execution. It added no
workflow; GTK/MSW remain blocked until hosted workflow execution is authorized
or platform runners are provided.
Plan 19's hosted runner pilot is deferred: the available environment is
macOS-only and Ubuntu/Windows access is unavailable. No workflow was added or
triggered. Resume the pilot only when non-macOS runner access is available:
[plan 19](./PLAY_OEM_COMPLEXITY_19_HOSTED_WX_TEST_PILOT_PLAN.md).
The next local investigation is active incremental-load shutdown on macOS,
checking cancellation, timer/observer cleanup, and rejection of late events
without changing cross-platform status:
[plan 20](./PLAY_OEM_COMPLEXITY_20_ACTIVE_LOAD_SHUTDOWN_PLAN.md).
Plan 20 confirmed the existing blocked-parser close test covers cancellation,
store closure, and absence of post-close appends; the focused loader/app tests
passed (11 passed) on macOS, with no production change.
Plan 21 is the next macOS-only validation: combine that active-load shutdown
case with real wx resources and deterministic parser blocking, while keeping
the GTK/MSW runner work deferred:
[plan 21](./PLAY_OEM_COMPLEXITY_21_NATIVE_WX_ACTIVE_LOAD_SHUTDOWN_PLAN.md).
Plan 21 passed on macOS Cocoa (wxPython 4.2.4 / wxWidgets 3.2.8); the full
app lifecycle suite passed (98 passed). Real wx shutdown during blocked OEM
parsing cancelled the loader, stopped the timer, closed workspace/store,
preserved `wx.App`, and prevented a late append. GTK/MSW remain unverified.
The next step is to re-rank remaining candidates against the complexity
strategy and either select one evidence-backed investigation or pause the
sequence:
[plan 22](./PLAY_OEM_COMPLEXITY_22_CANDIDATE_RERANKING_PLAN.md).
Plan 22 found no remaining candidate meeting the evidence, complexity-benefit,
and validation criteria. The current sequence is paused; reopen it only when
new evidence or non-macOS runner access becomes available.
On closer source comparison, `_install_store_snapshot` has the same pending
playback-bounds decision in its first-append and later-append paths, with a
distinct later-only follow-coverage case. Plan 23 evaluates a narrow
deduplication as an actual complexity-reduction experiment:
[plan 23](./PLAY_OEM_COMPLEXITY_23_SNAPSHOT_INSTALLATION_DEDUPLICATION_PLAN.md).
The duplicated pending-bounds decision was consolidated in
`_apply_pending_playback_bounds`; first-append anchoring and later-append
follow-coverage logic remain distinct. The focused app, clock, and time-range
suites passed (162 passed) on macOS.

## Scope and follow-up

This review identifies the main logical interactions visible in the inspected
paths; it is not an exhaustive proof of all states or test coverage. The first
deliverable should be the load transition table, followed by the cache validity
and lifetime matrix. Use concrete traces and existing tests to refine the
ranking; treat any proposed reduction as an experiment with explicit invariants
and before/after evidence.
