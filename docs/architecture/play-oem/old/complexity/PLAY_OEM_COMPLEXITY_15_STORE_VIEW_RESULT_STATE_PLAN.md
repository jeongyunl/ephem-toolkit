# play-oem — Store-Backed View Result-State Investigation Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior query and refresh investigations:
[PLAY_OEM_COMPLEXITY_6_DERIVED_STORE_QUERIES_PLAN.md](./PLAY_OEM_COMPLEXITY_6_DERIVED_STORE_QUERIES_PLAN.md),
[PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md](./PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md).
Prior view lifecycle and partial-startup investigations:
[PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md),
[PLAY_OEM_COMPLEXITY_14_PARTIAL_GUI_STARTUP_CLEANUP_PLAN.md](./PLAY_OEM_COMPLEXITY_14_PARTIAL_GUI_STARTUP_CLEANUP_PLAN.md).

## Goal

Compare how representative store-backed views interpret query coverage,
available committed-prefix data, and load state when choosing what to render
and what status to present. Establish whether repeated caller-side policy is
present and whether it can be made clearer without conflating distinct states
or changing view-specific messages and behavior.

This investigation concerns query-result interpretation, not store query
algorithms, refresh routing, or resource ownership. Plans 6, 7, and 12 already
cover those adjacent responsibilities. The current evidence identifies
different status-selection branches, not a confirmed inconsistency or a reason
to introduce a shared abstraction.

## Remaining-candidate ranking

| Candidate | Current evidence | Relative decision |
| --- | --- | --- |
| Store-backed result and status interpretation | `StoreViewContext` binds queries to a snapshot and range; Ground Track and station views separately combine range overlap, query coverage, returned data, and load status. The station views share a failed/cancelled-load helper, while other views retain different display behavior. | Investigate next: these states affect whether partial data is shown as loading, partial, empty, unavailable, or terminally failed. Compare policy before proposing any shared classification. |
| Raw ingestion reservation protocol | `_StoreRowSink` has one production streaming caller. The load-lifecycle investigation already mapped its reservation, commit, and close role, and tests cover store reservation invariants, capacity, and cancellation. | Defer: revisit only if a concrete uncovered failure or a second independent production protocol appears. |
| Load event consumption | The controller handles multiple generation-tagged event kinds, but its per-tick drain is bounded and the lifecycle investigation mapped stale-event and replacement behavior. | Defer: no duplicate consumer or new transition mismatch has been established. |
| Native wx startup cleanup | Plan 14 adds Python-level rollback and failure-injection tests; those tests do not establish native wx destruction behavior. | Defer until a display-capable integration environment can exercise a concrete native failure path. |

This ranking is a bounded research choice, not a defect finding. It favors
unresolved caller-side result semantics over repeating already-mapped store,
refresh, panel-lifecycle, or startup-cleanup work.

## Planning baseline and initial evidence

`StoreViewContext` captures a stable `StoreSnapshot`, holds the effective plot
range and coverage, and supplies range-limited queries. With no plot range, its
empty-query path returns an empty value and complete coverage with no requested
interval. Therefore `coverage.complete` alone does not distinguish an
empty-effective-range result from complete data coverage.

`store_load_status_message()` centralizes failed and cancelled store status
messages, including the possibility of showing available data after
cancellation. Other interpretation remains in the view callers:

- `GroundTrackView` distinguishes no effective range, absent query, empty
  incomplete result, empty complete result, partial result, and complete
  result when updating track status.
- `GroundStationPassesView` combines station selection, whether OEM data is
  loaded, terminal load status, query limitation, per-station query coverage,
  interval presence, and visible-range overlap.
- `GroundStationAnalysisView` shares the terminal load-status helper but also
  applies panel-type-specific range, interval, and profile rules.
- `SpeedAltitudeView` renders available series groups and retains partial
  query coverage; its current empty/partial behavior is not the same status
  policy as the station views.

Existing focused tests cover some of these cases: Ground Station Passes tests
exercise failed/cancelled loads, no-access results, and non-overlapping ranges;
Speed/Altitude tests exercise empty and partial coverage; Ground Track tests
exercise store-backed queries and range changes. The test inventory must
establish which exact user-visible state transitions are asserted before
adding coverage.

## State and caller matrix to verify

| State dimension | Cases to distinguish | Caller question |
| --- | --- | --- |
| Context and selection | No store context, unloaded OEM, no selected station, removed station | Which caller owns the primary unavailable/selection message? |
| Effective range | No range request, range outside coverage, valid range | Does each view distinguish no query interval from an empty complete result? |
| Query result | No result yet, complete empty value, complete non-empty value | Is “loading” distinct from “no samples/no intervals” for each query type? |
| Coverage | Incomplete with no usable values, incomplete with a committed prefix, complete | Is partial data kept visible and labeled accurately? |
| Load state | Loading, failed, cancelled, complete | Can terminal load state coexist with a valid prefix, and which message takes precedence? |
| Domain result | Limitation, no qualifying access, data outside visible range | Which results are domain-specific and must not be generalized? |

Treat range coverage, returned values, and store load status as separate inputs;
do not infer one from another. Preserve caller-specific station selection,
domain limitations, and plot-range messaging unless evidence shows a shared
invariant.

## Investigation procedure

1. Trace `StoreViewContext` snapshot, range, empty-query, and refresh behavior.
   Record what query coverage and values mean for no range, incomplete data,
   and complete data.
2. Trace the status/result path in Ground Track, Ground Station Passes, Ground
   Station Analysis, and Speed/Altitude. Record the order of conditions and
   which state wins when dimensions coexist.
3. Inventory existing tests by state and asserted output/visible data. Include
   failed and cancelled loads with committed prefixes, not only complete
   snapshots.
4. Build a compact state matrix for the represented query kinds. Mark
   inapplicable combinations rather than forcing identical behavior across
   unrelated domain results.
5. Identify missing tests only where behavior is ambiguous or a concrete
   inconsistency is plausible. Prefer headless query/status tests; report any
   display-gated cases separately.
6. Compare repeated policy with the existing
   `store_load_status_message()` helper. Consider a shared state classifier
   only if it represents a genuinely common invariant while leaving final
   presentation and domain-specific messages with their views.
7. If a change is justified, add the regression first, make one narrow change,
   and compare caller obligations and helper complexity before and after. If
   no change is justified, record why the separate rules correspond to
   different result semantics.
8. Run the focused Ground Track, Ground Station Passes/Analysis, Speed/
   Altitude, and shared store-view tests. Update the assessment with findings,
   validation, limitations, and the next-ranked candidate. Update subsystem
   documentation only if the result-state contract or ownership changes.

## Required behavior and constraints

- Preserve the snapshot and range binding supplied by `StoreViewContext`.
- Preserve partial committed-prefix rendering where the current view supports
  it; do not make incomplete coverage appear complete.
- Keep no effective range, empty complete result, incomplete empty result,
  and terminal load status distinguishable where the view currently needs
  those distinctions.
- Preserve station selection, limitation messages, access interval semantics,
  and per-view range behavior.
- Do not centralize UI strings or add a generic result framework solely to
  reduce local branches.
- Preserve refresh throttling, wx-thread ownership, query bounds, and
  backend-specific rendering.
- Keep fake/headless test evidence separate from native GUI presentation.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 8/8 checklist items.
- [x] Map `StoreViewContext` snapshot, range, and empty-query semantics.
- [x] Trace result/status precedence in the selected store-backed views.
- [x] Inventory current tests against query values, coverage, and load states.
- [x] Build a cross-view state matrix and mark view-specific states.
- [x] Add only missing tests needed to resolve a concrete ambiguity.
- [x] Select a narrow shared-policy change if justified, or record a no-change
      decision.
- [x] Run focused view/store validation and record display limitations.
- [x] Update the assessment with results, validation, limitations, and the
      next-ranked candidate; update subsystem documentation only if its
      contract changes.

**Done when:** query coverage, returned data, and load-state precedence are
mapped against representative callers and tests; and any shared policy is
evidence-backed or explicitly deferred.

## Execution record — 2026-11-11

### State precedence and caller comparison

`StoreViewContext` keeps snapshot, range, and query results together. Its
no-range query path returns a complete empty result with no requested
interval, so completeness alone does not mean that samples cover a requested
range. The existing `store_load_status_message()` helper is a genuine shared
policy for failed and cancelled store snapshots; it does not try to classify
query values or domain results.

The callers apply different precedence for different user tasks.
GroundStation Passes and GroundStation Analysis first handle station or
unloaded-context states, then prefer the terminal store status over query and
domain-specific messages. Their remaining messages distinguish incomplete
coverage, results/limitations, and plot-range visibility. Ground Track instead
reports local plot-range and track-query states (loading, empty, partial, or
complete); load failure is reported by the application load path. Speed/
Altitude has no comparable status chain: it draws available series groups and
shows empty artists when there are no samples. These policies do not share a
single status precedence without hiding meaningful view-specific distinctions.

The terminal-state station-analysis tests use a loading store with three
committed raw rows, then mark the snapshot failed or cancelled. The view keeps
that three-row snapshot and reports the terminal status while query coverage
remains incomplete. In this setup station-derived profiles are not available
before the final frame metadata is published; the test does not claim that
every committed prefix can already produce every derived view.

Ground Track previously had no assertions for its status text. A headless
regression now distinguishes an incomplete empty query ("loading"), a complete
empty query ("no samples"), and a missing effective range ("no overlap").
Existing tests cover Speed/Altitude empty and partial series, and station-view
loading, terminal, no-access, limitation, and no-overlap states. No
cross-view state classifier or production change is justified; retain the
existing terminal-load helper and view-owned result/presentation rules.

### Validation and limitations

The focused Ground Track, Ground Station Passes, Station Analysis, Speed/
Altitude, and shared series-view suites passed: **80 passed, 3 skipped**.
The skips require a wx display. The new Ground Track assertions use the
Matplotlib Agg canvas, and no native GUI presentation was exercised. The run
emitted existing Matplotlib/Pyparsing and pyproj deprecation warnings.

No query contract, dataflow ownership, or subsystem behavior changed. The
subsystem overview now points to this completed comparison. Raw ingestion and
load-event consumption remain deferred absent a concrete protocol gap or
transition mismatch; native wx teardown still requires a display-capable
integration environment. No next implementation candidate is selected;
re-rank remaining candidates before another plan.
