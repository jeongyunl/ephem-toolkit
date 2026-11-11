# play-oem — Derived Store Query Complexity Reduction Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Baseline and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context: [PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Scheduling and cache findings:
[PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md](./PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md).
Current dataflow: [PLAY_OEM_DATAFLOW.md](./PLAY_OEM_DATAFLOW.md).

## Goal

Compare the store's `series`, `earth_fixed_positions`, `ground_track`, and
`station_access` query contracts to determine which range, readiness,
coverage, cancellation, and invalidation rules are genuinely shared. Evaluate
one bounded internal improvement only if the evidence shows duplicated policy
that can be centralized without obscuring tier-specific behavior.

Preserve lazy range-limited computation, snapshot-bound read-only views,
progressive coverage, segment boundaries, interpolation support, station
limitations, and all cache/epoch semantics. A clarified contract or tests may
be the best result. Do not equate similar method shapes with equivalent
behavior or treat moving code as a reduction in complexity.

Apply the established complexity strategy: verify representative behavior
vertically, map responsibilities horizontally, then evaluate local reasoning,
overall coupling, code volume, and relevant performance separately.

## Current implementation and initial evidence

`StoreViewContext` captures one `StoreSnapshot` and binds it to a plot range and
coverage. Its query methods delegate to `OemDataStore`; defaults are
nonblocking. Store queries return a `StoreQuery` containing a value and
`TimeCoverage`. `wait=False` can return currently ready data while queuing
missing work; `wait=True` computes the requested portion and is used by the
store scheduler.

The following is an initial static comparison, not a completed behavioral
contract. Verify exact boundaries, errors, old-snapshot behavior, and tier
validity against the implementation and tests.

| Tier | Initial behavior | Points to verify |
| --- | --- | --- |
| Series groups | Computes only selected groups over intersecting raw rows. Results are chunked and memoized; `max_samples` strides returned views. Coverage uses the intersection of ready spans across selected groups. | Inclusive range edges, gaps and segment boundaries, multi-group coverage, stride/extrema expectations, and a loading tail's tentative-to-complete transition. |
| Earth-fixed positions | Requires Earth-centered frame metadata, computes the requested range plus an optional support margin, and returns ready read-only slices over the expanded range. Reported coverage remains clipped to the requested bounds. | Missing/invalid metadata behavior for loading versus complete snapshots, margin-only support rows, segment runs, and coverage when raw bounds do not fully cover the request. |
| Ground Track | In waiting mode, obtains Earth-fixed positions, converts to WGS-84, splits map seams, and can cache complete results. Nonblocking mode queues work and returns an empty incomplete result. | Cache identity across policy changes, Earth-fixed coverage propagation, empty versus pending results, seam/segment boundaries, and conversion failures. |
| Station access | Builds per-station, per-segment regular profile samples, evaluates point states and station metrics, then derives elevation intervals. It expands support bounds and can return explicit limitations for unsuitable source spacing or sample counts. | Policy-revision dependence, segment gaps, interval boundaries and duration claims, station-specific cache keys, partial profiles, and limitation behavior. |

`series` and Earth-fixed chunks use epoch stamps rather than interpolation
policy revision; station profiles depend on both snapshot revision and
interpolation-policy revision. Ground Track composes Earth-fixed output and
uses its own result cache. Station access computes station-specific samples and
intervals; it is not merely another raw-row chunk query. These differences are
starting evidence, not a decision against shared code.

At preparation, `oem_data_store.py` contains 3,536 physical lines. The query
methods measure approximately 159 lines for `series`, 152 for
`earth_fixed_positions`, 186 for `ground_track`, and 244 for `station_access`.
These sizes locate review effort; they are not targets or proof of unnecessary
complexity.

## Relevant assessment findings

The assessment's candidate inventory calls out derived store queries as a
separate investigation after store scheduling and cache lifecycle. It asks for
a comparison of coverage, chunk, and invalidation handling, especially between
`series` and `station_access`, and permits a shared internal operation only
where invariants truly match.

The completed [scheduling/cache investigation](./PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md)
found a single store owner, existing `ChunkMemo` separation, and different
per-tier cache/validity rules. It centralized only the identical request-range
expansion used by scheduler priority and drag eligibility. This query plan
should build on that result without reopening scheduler or eviction design
unless the query trace establishes a direct dependency.

## Interactions with other subsystems

- **Snapshot and loading lifecycle:** snapshots identify an epoch and a
  committed prefix. A query may use an older revision within the same epoch;
  appends must not make it read uncommitted rows or report unseen coverage.
  Stale epochs and policy-dependent point queries have different rejection
  rules.
- **Derived scheduler and `ChunkMemo`:** nonblocking queries submit
  `QueryRequest`s. Waiting computations share chunk work, propagate
  cancellation/errors, and publish tier notices. Preserve the scheduler
  behavior documented in
  [PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md](./PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md).
- **Views and display policy:** history, Ground Track, and station views
  interpret partial coverage differently. `StoreViewContext` handles bound
  snapshots and empty ranges, while views decide what partial output to render.
  Keep those responsibilities distinct unless repeated policy is demonstrated.
- **Interpolation and point queries:** station profile sampling uses
  `state_at`, which depends on interpolation policy and must not cross segment
  gaps. Ordinary series and Earth-fixed transforms may not share that policy
  dependency.
- **Range and timeline:** requested plot bounds, raw coverage, support margins,
  and station interval horizons are distinct. Do not treat a support margin as
  visible coverage or a partial interval as a known complete pass.
- **Numerics and coordinate transforms:** Earth-fixed conversion, WGS-84
  geodetic conversion, map seam splitting, orbital series, and station metrics
  have different numerical inputs and boundary conditions. Preserve reference
  calculations and segment-aware output.

## Required behavior and constraints

- Keep all raw and derived orbit data store-owned; do not introduce per-view
  full-history copies or a second cache owner.
- Preserve `StoreQuery` stamps, epoch/revision/policy validity, and stable
  snapshot behavior.
- Preserve nonblocking partial results and the exact distinction among empty
  ranges, pending work, incomplete coverage, unsupported inputs, and complete
  coverage.
- Preserve each tier's cache identity, chunk readiness, cancellation, notices,
  and eviction/pinning behavior.
- Preserve numerical output, inclusive/exclusive boundaries, segment gaps,
  interpolation support, and zero-copy read-only views.
- Preserve station-specific source-spacing/sample-count limitations and
  access-interval boundary semantics.
- Keep expensive calculations off the wx thread and preserve view-specific
  interpretation and rendering.
- Do not create a common query framework or split the store module unless a
  bounded experiment proves lower overall reasoning cost and equivalent
  behavior.

## Implementation checklist

Work in dependency order. Treat the initial table as orientation, not as the
specification. Keep the assessment authoritative for priorities and record
verified evidence and decisions here.

- **Status:** Complete.
- **Progress:** 8/8 checklist items.
- [x] Trace one representative successful and partial query for each tier from
      `StoreViewContext`/view caller through store query, scheduler or waiting
      computation, chunk/cache lookup, and returned value/coverage. Record the
      input snapshot revision, epoch, policy revision, range/support bounds,
      thread, notices, and view interpretation.
- [x] Produce a tier contract table for empty data, partial loading, complete
      data, out-of-range queries, unsupported metadata/source spacing,
      cancellation, stale epoch/revision/policy, and segment gaps. State exact
      coverage and value shapes, cache keys, chunk stamps, support margins,
      dependencies, and errors/limitations.
- [x] Build a responsibility matrix for `StoreViewContext`, each store query,
      shared chunk machinery, tier-specific derivation/caches, and representative
      history, Ground Track, and station views. Inventory repeated validation,
      ready-span, coverage, notice, and cleanup policy; distinguish common
      invariants from similar-looking but different domain logic.
- [x] Map existing store and view tests to the contract, run the focused query,
      interpolation, range, and view suites, and add meaningful missing cases
      for any demonstrated gaps. Include partial coverage, multi-segment gaps,
      policy changes, old snapshots after append, cache hits/recomputation, and
      error/limitation paths where applicable.
- [x] Record a before baseline at a specific commit and working-tree state:
      tier call sites, contracts, relevant code volume, test scenarios, and
      numerical/performance measures where applicable. State commands, tools,
      inputs, and exclusions. Do not claim a numerical or performance benefit
      from structural similarity or line movement.
- [x] Rank observed issues by evidence of change frequency, reasoning/testing
      difficulty, and consequence of mistakes; state uncertainty. Select one
      bounded hypothesis with affected interfaces, invariants, alternatives,
      expected benefit, and rejection criteria. Candidate: a shared helper for
      a ready-span/coverage operation only if its semantics are identical for
      at least two tiers after clipping and gap handling are accounted for.
- [x] Evaluate the hypothesis with a small sketch or prototype. If justified,
      make the narrowest change and compare the same query contracts, call
      sites, tests, local reasoning, overall interactions, code volume, and
      relevant performance. Retain no abstraction that hides station or
      coordinate-specific rules or weakens partial-coverage behavior.
- [x] Update the assessment with evidence and revised priorities; update
      dataflow or store design only if behavior or architecture changes. Record
      validation, known limitations, the final decision, and a recommendation
      for the next work item.

## Execution record — 2026-11-10

### Verified query contracts and responsibility boundaries

All range queries return a `StoreQuery` stamped with the input snapshot's
epoch, revision, and policy revision. `TimeCoverage` carries requested bounds,
covered spans, and a completion flag; the flag does not erase segment gaps.
The store validates the epoch, while `state_at` additionally rejects a
snapshot from a stale interpolation-policy revision. Same-epoch older
snapshots remain usable as committed-prefix snapshots.

| Tier | Value and coverage | Work identity and notable behavior |
| --- | --- | --- |
| Series | An immutable group mapping to read-only `ColumnGroupView` spans. Coverage is the intersection of ready rows across selected groups, converted to segment-aware covered time. `max_samples` strides displayed views, not coverage. | One buffer and memo per group; chunk stamps use epoch and policy revision `0`. Loading-tail chunks are tentative and recomputed after append. Empty group selection returns base raw coverage. |
| Earth-fixed | A tuple of read-only `ColumnGroupView` spans over the ready expanded request, including support-margin rows. Reported coverage is intersected with the original requested row range. | One lazy buffer/memo; chunk stamps use epoch and policy revision `0`. The optional caller margin expands computation but not reported coverage. |
| Ground Track | A tuple of seam-split, segment-separated coordinate groups. Waiting queries compose Earth-fixed positions and return its coverage. Nonblocking queries enqueue work and return an empty value with incomplete coverage. | Cache key is `(epoch, revision, bounds, margin, center_longitude)`; interpolation policy is not part of the key, and a hit is retagged to the current policy revision. Only complete results within the memory budget are cached, with a four-entry cap. |
| Station access | `StationAccessView` contains a station, regular per-segment profiles, access intervals, and an optional limitation. Coverage comes from ready profile samples clipped to requested bounds and is complete only when base coverage and requested profile rows are complete. | Profile tier key includes epoch, snapshot revision, policy revision, and station identity/location. Interval key adds requested bounds and elevation threshold. Profiles use `state_at`, the duration-derived support margin, and segment-specific sample grids. A source-spacing/sample-count limitation is reported in the value rather than computed as an interval. |

Empty-data short-circuits are tier-specific: series, Ground Track, and station
access return their empty value using base coverage; Earth-fixed metadata is
validated before its empty-data return. Incomplete snapshots with missing
metadata return each operation's established unavailable value, while
nonempty complete snapshots missing metadata raise
`GroundTrackPreparationError`. A non-Earth center always raises. Point
station-metric and footprint queries return `None` for incomplete metadata and
share the same validation, but retain their point-result contract. Empty plot
ranges are handled by `StoreViewContext._empty_query` as an empty, complete
query with no requested bounds.

All range queries reject a stale epoch with `RuntimeError`; an older revision
in the current epoch remains a valid prefix snapshot. `state_at` additionally
rejects a stale interpolation-policy revision. For a complete snapshot,
out-of-range requests can have empty `covered_s` while `coverage.complete` is
true: completion describes the known source, not a guarantee that every
requested time had a sample. Point state returns `CursorStatus.OUT_OF_RANGE`;
station metric/footprint point queries return `None` without a valid state.
Station access may likewise have no profile or interval rows for a range while
base coverage is complete. Query cancellation raises `CancelledError` before
or during chunk computation.

`StoreViewContext` defaults to nonblocking query calls. Those enqueue work
through the store scheduler; the worker invokes the same tier operation in
waiting mode. Series and Earth-fixed computations publish chunk-span notices,
station profile work publishes station notices, and completed Ground Track
work publishes its tier notice. Direct `wait=True` calls compute on their
caller. View tests exercise the snapshot-bound query methods and the
store/view tests exercise partial coverage; GUI thread ownership is unchanged.

| Owner | Responsibility |
| --- | --- |
| `StoreViewContext` | Captures one snapshot and binds view range/coverage; delegates nonblocking queries and handles no-range empty results. |
| `OemDataStore.series` / `earth_fixed_positions` | Select raw row ranges, queue missing work or wait, read per-tier readiness, create leased views, and assemble tier-specific coverage. |
| `OemDataStore.ground_track` | Validates geometry inputs, delegates Earth-fixed computation, transforms/splits coordinates, and owns its complete-result cache. |
| `OemDataStore.station_access` | Owns station profile layout, profile readiness, interval derivation, profile/interval caches, and limitation reporting. |
| `ChunkMemo` and shared row helpers | Share in-flight chunk computation; `_row_spans`, `_intersect_row_spans`, and `_coverage_for_rows` handle generic span operations already common to series and Earth-fixed queries. |
| Views | Render values and decide how to respond to tier-specific partial coverage. History-series views, Ground Track, station analysis, pass tables, and access views consume distinct query shapes; none owns an orbit-sized derived copy. |

The potential ready-span/coverage extraction was rejected: the shared
`_coverage_for_rows` implementation already exists for series and
Earth-fixed positions, while each caller must still define different span
selection (group intersection versus clipping expanded rows). Ground Track
delegates that coverage, and station access derives coverage from station
sample times and completeness rather than raw-row spans. A common query
framework would move complexity rather than remove it.

### Tests, caller mapping, and baseline

The focused store suite covers lazy series computation and reference values
(`test_series_groups_are_lazy_chunked_views_matching_reference_computations`),
nonblocking series and tentative-tail append behavior
(`test_nonblocking_series_query_does_not_report_uncomputed_data_complete`,
`test_loading_append_recomputes_only_the_tentative_series_tail`), Earth-fixed
read-only/lazy/range-limited behavior
(`test_earth_fixed_positions_are_lazy_memoized_read_only_views`,
`test_earth_fixed_computes_only_rows_inside_requested_range`), Ground Track
seam handling, prefetch, and policy-independent cache behavior, and station
profile sharing, policy-dependent margins, and pending coverage. A direct
deterministic Earth-fixed pending-coverage test was added because the existing
pending Ground Track test did not directly assert the Earth-fixed query result.
Store/view tests also cover multi-segment station runs, gap-limited intervals,
and partial series rendering.

The before/after store/view selection was:

```sh
tests/ephem_toolkit/play_oem/test_oem_data_store.py
tests/ephem_toolkit/play_oem/test_station_analysis.py
tests/ephem_toolkit/play_oem/test_ground_station_passes_view.py
tests/ephem_toolkit/play_oem/test_ground_track_view.py
tests/ephem_toolkit/play_oem/test_play_oem_speed_altitude.py
tests/ephem_toolkit/play_oem/test_store_series_views.py
tests/ephem_toolkit/play_oem/test_ground_station_access_view.py
```

They were run as `pytest -q` at baseline and
`python3 -m pytest -q` after the change. The nine-test
`python3 -m pytest -q tests/ephem_toolkit/play_oem/test_chunk_memo.py` run was
additional cancellation/memo validation.

The baseline was commit
`b98484e654b197d68139f5881b353d32df961d4f`; the initial worktree contained
only the just-created plan and assessment edits. The source module had 3,536
lines. Its five repeated Earth-centered metadata checks were identical apart
from caller-specific error text and the caller's distinct incomplete result.
The seven-file focused store/view baseline command (`pytest -q` with the test
files listed above) passed 151 tests with 3 skipped. The same selection under
`python3 -m pytest -q` passed 155 tests with 3 skipped after the change. Four
new tests cover incomplete metadata for all five entry points, complete
missing/invalid metadata error wording for all five, and the directly pending
Earth-fixed query. Existing Matplotlib/Pyparsing and pyproj deprecation
warnings remain. The separate `test_chunk_memo.py` cancellation tests were
also run.

### Bounded change and evaluation

Extracted `_earth_centered_frame_name(snapshot, purpose)` and used it from
Earth-fixed positions, Ground Track, station access, station metrics, and
footprints. It centralizes string-presence checks, complete-versus-loading
handling, and Earth-center validation while retaining each exact error message
and each caller's own missing-metadata result. No query signatures, value
shapes, coverage logic, interpolation policy, cache keys, chunk stamps,
scheduler behavior, or numerical calculations changed.

The evidence-ranked candidate was repeated metadata validation: its change
frequency is unknown, but inconsistent acceptance could route an Earth-fixed
transform through the wrong center/frame, while missing metadata has a distinct
loading-versus-complete contract. The expected benefit is fewer places where
that policy can drift, with a negligible call-site cost. Leaving five copies
was the alternative; a broader shared query framework was rejected because
coverage and result contracts do not match. No defect history or observed
metadata-policy drift was found.

Source volume moved from 3,536 to 3,505 physical lines (31 fewer; 60 deleted,
29 added). This is a local reduction in duplicated validation and a single
point for metadata policy, not evidence that the store's overall complexity
or coupling has been reduced. The calls remain explicit at five consumers so
their missing-data behavior is visible. No runtime/performance benchmark was
run: the helper only replaces repeated validation and does not change derived
computation. Change frequency and defect history are unknown. Pylance
cross-reference requests timed out, so caller mapping used targeted source and
test searches plus direct inspection of `StoreViewContext`; no signatures were
changed.

The assessment now records this result. The next authoritative work item is
priority 4, view refresh coordination. No dataflow or store-design document
change is warranted because runtime architecture and behavior are unchanged.

**Done when:** the four query contracts and their caller responsibilities are
verified against implementation and tests; shared and tier-specific rules are
explicit; a bounded candidate is evaluated or rejected with evidence; and any
accepted change preserves numerical, snapshot, coverage, segment, and cache
behavior. Explain effects on local reasoning, overall coupling, code volume,
and measured performance separately. If no production change is justified,
record that outcome without claiming complexity was reduced.

**Status:** Complete; 8/8 checklist items.

**Depends on:** [PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md](./PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md)
and the existing complexity strategy and assessment. This plan does not
supersede the main release-readiness plan.
