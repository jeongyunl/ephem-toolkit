# `play-oem` — Unified OEM Data Store Implementation Plan

Requirements: [PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md). Target architecture:
[PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md](./PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md). Current
dataflow: [PLAY_OEM_DATAFLOW.md](./PLAY_OEM_DATAFLOW.md) and
[PLAY_OEM_DATAFLOW.mmd](./PLAY_OEM_DATAFLOW.mmd).

## Goal and scope

Replace the fragmented OEM samples and their analysis/plotting products with one authoritative
in-memory `OemDataStore`. The store owns raw samples and lazily materializes only requested
derived quantities. Consumers read read-only views; they must not retain orbit-sized copies.
Backwards compatibility with current play-oem internal modules and constructors is not required.

This plan executes the delivery sequence in the unified-store design. It does not replace the
play-oem GUI implementation plan. Store-specific performance policy, historical evidence, and
loader measurements are consolidated in the design and this plan.

**Non-negotiable requirements:**

- Raw rows are parsed into final store-owned buffers; do not stage or copy the orbit dataset.
- Derived data is computed on demand, for requested ranges, and written once to its final
  store-owned buffer. Views return slices, not gathered or concatenated arrays.
- Keep application and view call sites on a snapshot-bound read context with typed results;
  centralize tier subscriptions and lifecycle handling instead of repeating low-level store
  interactions in each consumer.
- Preserve numerical output, interpolation behavior, segments/gaps, cancellation, incremental
  coverage, and existing playback semantics.
- Keep expensive derivation off the loader and wx event-loop paths. `state_at` must not trigger
  chunk computation.
- Run all further benchmarks headlessly. Do not launch wx, create canvases, or use
  `--gui-stall-probe`; headless results do not prove GUI responsiveness.

## Current implementation

An experimental raw tier, direct parser-to-store ingestion, and opt-in
`IncrementalLoadSession` store mode exist. The store supports fixed-capacity raw reservations,
committed-prefix snapshots, epoch/revision checks, segment bounds, lifecycle states, and
generation-tagged append events. Automatic capacity sizing runs on the loader worker, excludes
covariance-block lines, and is cancellable. Step 3 adds point-state queries, lazy series groups,
and memoized Earth-fixed position queries. Step 4 adds prioritized cancellable range prefetch,
partial-coverage results, chunk notices, live playback timestamps, station-access profiles, and
per-chunk derived-data eviction. The active player's default incremental load path now creates one
`OemDataStore` per load generation, consumes committed `RAW_APPEND` snapshots, and drives playback
through the store's live sample-time view and `StoreCursor`. It retains the current file until the
replacement has committed usable rows, then releases the old store after replacing its views.

Stateless mode on the existing core interpolators and zero-copy plotting primitives are
implemented and validated. Every registered data view has a store-backed builder, and panel
creation dispatches through `StoreViewContext` when that builder is available. Step 7 now wires
the active player to direct parser-to-store loading, live sample-time playback, snapshot-bound
view contexts, range hints, queued store notices, and store-backed station prefetch. Replacement,
failure, cancellation, metadata finalization, and stale-notice handling are coordinated on that
path. Compatibility state and the legacy prepared-batch path remain for the separately scoped
Step 8 cleanup. Step 7 is still in progress because the JPSS-1 automatic-capacity first-append
gate failed; the application's end-to-end no-copy and responsiveness acceptance gates are not yet
complete.

Historical automatic-sizing measurements counted physical lines and reserved 172,833 rows for
21,601 JPSS-1 states because covariance rows contributed to the bound. Current sizing excludes
covariance blocks; the macOS allocation probe and remaining cross-platform limitations are
recorded in the
[store design](./PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md).

## Graph-to-tier reuse

The current graph inventory is defined in
[`views/registry.py`](../../../src/ephem_toolkit/play_oem/views/registry.py). Migrate graph
families to shared store-owned intermediates; do not make a separate orbit-sized result for each
view.

**Diagram roles:** `PLAY_OEM_DATAFLOW.md` and `.mmd` describe the verified current implementation
until Step 8. The architecture diagrams in the store design describe the target `OemDataStore`
contract. Keep the graph names and shared-intermediate relationships aligned, but do not show
target tiers or APIs as shipped in the current-state diagram. Keep benchmark results in the store
design's performance section, not in the current dataflow document or diagram.

The [public query contract](./PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md#public-interface) is
normative: low-level ranged queries return `StoreQuery[T]` with an epoch/revision stamp and
explicit time coverage; `ColumnGroupView` exposes read-only tier-buffer views with column names
and segment bounds. Application and view consumers use a snapshot-bound read context that
provides typed, range-bound query methods and explicit empty/partial results. Series keys are
`kinematics`, `rtn`, `direction-rates`, and `distance-delta`; tier notices identify the affected
group or station and use tier-local row spans. Ground Track, Earth-fixed, series, and station-access
queries share that contract. Point queries such as `state_at` and `station_metrics_at` remain
non-blocking and do not materialize history tiers.

| Current graph types | Shared data or computation | Separate outputs that remain distinct |
|---|---|---|
| 3D Orbit; State Components; Speed / Altitude; RTN Deltas; Angular Velocity; Direction Change; Geocentric Distance | Raw timestamps, states, segment boundaries, and requested `Series` column groups | Each graph requests only its own fields; 3D should read raw position columns in the target design. |
| Ground Track; Pass Ground Track | Earth-fixed ITRF sample-position tier and `prepare_ground_track` algorithm | WGS-84 latitude/longitude coordinates; Pass Ground Track requests only the selected pass interval. |
| Station Status; Pass Strip; Elevation Profile; Azimuth Profile; Range Profile; Pass List; Sky View | Per-station look-angle profiles (time, azimuth, elevation, range) and access intervals, shared through one station-access tier | Profile views select different columns; pass views use interval boundaries and summary metrics. Current station status evaluates the current cursor state. |
| Ground Track and Pass Ground Track; all station views | The same raw sample identity and Earth-fixed positions; use one ITRF conversion/cache path | Ground Track produces geodetic coordinates; station analysis produces station-relative ENU metrics (azimuth, elevation, range). Do not treat these as the same derived result. |

Footprints are a Ground Track-specific small result from the current Earth-fixed position and
elevation mask. Reuse shared raw/ITRF data, but do not make station graphs depend on footprint
results. The detailed mapping and current-implementation caveats are in the
[store design](./PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md#shared-data-across-current-graph-types).

## Performance policy and acceptance

All future benchmarks are headless. Do not launch wx, create windows/canvases, or use
`--gui-stall-probe`. Headless measurements can compare parsing, preparation, storage, scheduling,
and process RSS; they cannot establish GUI responsiveness, time to visible plot, or interactive
application memory.

Use `scripts/bench_play_oem.py` with the ISS and JPSS-1 fixtures, covariance-free and
covariance-heavy data, multi-segment inputs, and 100,000- and 1,000,000-state scale cases where
practical. Measure first append/prepared batch separately from validated completion; completion
requires EOF and context validation. Include replacement and synchronized cancellation phases.
Use fresh processes for comparable process-RSS high-water measurements, warm the inputs, alternate
baseline/candidate order, run at least five unprofiled measurements, and report environment,
fixture characteristics, settings, samples, median, and range. Keep profiling separate from timing
runs and do not add overlapping stage times.

Provisional headless loader gates are at least 10% lower median JPSS-1 validated-completion time
for combined changes, no more than 5% regression in median first-batch time on either primary
fixture, and no more than 5% regression in comparable process peak RSS. These are not end-to-end
or UI acceptance criteria.

The historical latest seven-run parser/session comparison met those provisional gates for ISS
and JPSS-1 completion only: median completion improved 2.6% and 16.5%, respectively. The original
report described first-batch and RSS medians as within their provisional limits, but later
comparisons found first-batch timing variable and inconsistent. Treat the result as historical
evidence for those fixtures, not a general or interactive-UI gate pass. The candidate
substituted the OEM parser and ODM line validator while keeping the current time conversion,
session, preparer, and benchmark settings. This does not establish a general result or a gain
from the final store integration. At 100,000 and 1,000,000 states, parser/session comparisons
showed overlapping ranges and no material completion improvement; these checks are not evidence
that a future lazy store meets its targets.

The original user-set GUI target of a maximum 500 ms loading timer gap remains unresolved. Earlier
one-off probes observed maximum gaps of 710 ms and about 547 ms; their first-install/draw and RSS
measurements are historical only. Do not repeat GUI benchmarks or treat headless results as
passing the GUI gate. No absolute worker-cancellation limit has been agreed; report synchronized
cancellation observations without inventing one.

## How to use this plan

Work one pending numbered step at a time and in dependency order unless the user explicitly
authorizes out-of-order work. If authorized, record the unresolved prerequisite and do not mark it
complete. Keep each status and progress count current. When a step is complete, move its full entry
to `Completed steps`, preserving its original number, checklist, criteria, dependencies, and
evidence.

If work reveals a dependency or design decision that changes the sequence, update this plan and
the [store design](./PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md) before proceeding out of order.
Keep this plan and the store design synchronized for measurements, performance gates, and
loader-specific changes. Do not mark a step done solely because code has been written; its tests
and completion criteria must pass.

Status meanings: `Not started` — no work begun; `In progress` — implementation or checks are
underway; `Blocked` — a documented dependency prevents progress; `Done` — checklist and completion
criteria pass. Progress is the number of completed checklist items.

## Active implementation sequence

Steps 4, 5, and 6 are complete. **Step 7 remains open:** direct `RAW_APPEND` ingestion, controller
context and lifecycle wiring, range hints, and notice-driven store-view refresh are implemented,
but its automatic-capacity first-append gate has not passed. Per explicit user direction, Step 8
may proceed while Step 7's performance acceptance is deferred and unresolved. This exception does
not mark Step 7 complete or change its scope.

### 7. Migrate loading and controller state to `OemDataStore`

Wire direct store loading only after all views consume the store contract. Preserve early playback,
ordered coverage, user ranges, metadata, errors, cancellation, and replacement semantics.

- **Status:** In progress (active store-path and lifecycle wiring are implemented; the
  automatic-capacity first-append performance gate failed and is explicitly deferred while Step 8
  proceeds).
- **Progress:** 6/7 checklist items.
- [x] Create and own one store per playback epoch; route initial and incremental OEM loading
      through the loader's direct-store mode and raw-append notices without parser-batch-to-playback
      staging or delaying the first usable raw samples. Keep reservation, commit, and abort calls
      inside the loader sink, not in the controller or views. First bind the store to the selected
      file generation, then install its committed snapshots into the clock/cursor and refresh
      store-backed views; preserve the active file until the replacement publishes usable data.
- [x] Replace `PlaybackData`'s derived-data fields and controller references to `series`,
      `time_unit`, `cursor`, `_incremental_store`, and `_ground_track_source` with store-backed
      reader contexts on the active path where appropriate; extend `PlaybackClock` from committed
      timestamps.
- [x] Capture or refresh one snapshot-bound reader context per append, tier, range, or policy
      update and share it with affected views. Route point-state queries through this context
      instead of exposing store/snapshot pairs at each call site.
- [x] Publish range hints on plot-range, playback-range, seek, drag, and view-open/close changes;
      apply tier/append notices to the affected views without blocking wx event handling.
- [x] Replace the station warm-up thread and polling refresh work with store prefetch and notices
      on the active store path; keep wx event handling limited to applying notices and updating
      views.
- [x] Coordinate metadata finalization, failed/cancelled prefixes, replacement epochs, stale
      notices, saved ranges, interpolation policy, and clock coverage through one lifecycle.
- [ ] Pass direct initial/incremental loading, early playback, replacement, failure, cancellation,
      and scheduling tests; meet headless performance gates in
      [Performance policy and acceptance](#performance-policy-and-acceptance).

**Done when:** the active player loads and consumes one authoritative store, preserves current
behavior, and has no orbit-sized staging or parallel controller copies.
**Depends on:** Step 6.

**Evidence for the first work item:** `python3 -m pytest tests/ephem_toolkit/play_oem -q`
passed (628 passed, 4 skipped). App tests cover direct loading, store-backed cursor/context state,
replacement retention and cleanup, load failure, and saved ranges. `compileall` and
`git diff --check` passed. This does not certify the remaining scheduling or GUI responsiveness
gates.

**Current Step 7 evidence:** `python3 -m pytest tests/ephem_toolkit/play_oem
tests/ephem_toolkit/core/interpolator -q` passed (687 passed, 4 skipped); `compileall` and
`git diff --check` passed. The new controller regression verifies that replacing an in-progress
load refreshes the retained store context to `CANCELLED`. A five-pair, fresh-process alternating
JPSS-1 comparison with macOS Low Power Mode off previously failed the first-append gate:
direct-store median was 52.199 ms versus 13.736 ms for the prepared-batch baseline (+280.0%,
against a maximum 5% regression); completion and peak RSS improved 30.0% and 9.0%. Subsequent
instrumented and Low-Power-Mode-on diagnostics also failed the first-append gate. The capacity
scanner was optimized while retaining covariance exclusion, line-length validation,
universal-newline handling, and bounded cancellation checks; the first scan optimization reduced
its focused median from 76.318 to 50.617 ms. An ASCII read-only-mapping fast path avoids per-line
string materialization and measured 48.711 ms versus 51.698 ms for the strict text path (5.8%
faster) in an alternating 11-run scan microbenchmark.

The latest five-pair fresh-process comparison alternated prepared-batch and mapped
automatic-capacity direct-store runs with Low Power Mode `1` before and after. First-delivery
medians were 23.967 versus 68.064 ms (+184.0%); validated completion was 1.253803 versus 0.861978
s (31.3% faster); and process peak RSS including startup and warm-up was 90.5 versus 93.9 MiB
(3.8% higher). Both variants validated 21,601 states; direct-store capacity was 21,624 with 43
append notices. Completion meets its provisional gate and RSS remains within the 5% limit, but
first delivery still fails; Low Power Mode-on results are diagnostic, not acceptance evidence.
Profiling the text path identifies reads, line splitting/validation, and marker searches as the
scan bottleneck. A one-pass mapped prototype matched randomized cases but improved scan time by
less than 1.1%, and larger chunks offered no material gain, so neither was adopted; the scanner
keeps 1 MiB cancellation-check intervals. A regex validation alternative was substantially slower
and rejected. A later Python-only experiment replaced the two literal covariance-marker searches
with compiled bytes-regex searches over bounded mmap windows: nine alternating candidate-only
runs measured 7.408 ms versus 18.973 ms for literal-prefix mmap search. ASCII validation now uses
a reduction instead of allocating a boolean mask, and newline offsets are shifted in place. The
current scanner measured 17.379 ms median (17.163–22.190) versus 50.331 ms (50.030–67.890) for
the strict text fallback in 13 alternating full-scan pairs with `lowpowermode=1`; these scan-only
results are diagnostic. It matched the reference on 300 randomized ASCII inputs across varied
chunk sizes, and the full play-oem/interpolator suites passed (688 passed, 4 skipped). A separate
five-repeat direct-session diagnostic at `lowpowermode=1` measured 40.108 ms median first append,
0.831426 s validated completion, and 93.3 MiB peak RSS; it is unpaired and does not establish the
gate. Repeat the alternating benchmark with power mode verified and stable before re-evaluating
the gates. The comparisons and limitations are in
[store design's performance evidence](./PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md#controller-integration-measurements).

### 8. Consolidate ownership, remove superseded paths, and accept the migration

After every consumer is store-backed, remove duplicate caches and obsolete preparation paths,
update architecture documentation, and run final correctness/performance gates.

- **Status:** In progress (opened by explicit user direction while Step 7's first-append gate
  remains unresolved; no Step 8 checklist items are complete yet).
- **Progress:** 0/8 checklist items.
- [ ] Remove `GroundTrackSource`, `source_prefix_matches`, controller-held Ground Track arrays,
      app-scoped `EarthFixedPositionCache`/`StationAccessCache`, and the module footprint cache.
- [ ] Ensure frame changes are represented in epoch/query identity and interpolation-policy
      changes invalidate only dependent interpolation/access products.
- [ ] Test cache retention for unaffected ranges, invalidation around support margins, safe
      eviction while views are drawing, and identical results after recomputation.
- [ ] Remove `AppendablePlaybackData`, `PreparedPlaybackBatch`, `IncrementalPlaybackPreparer`,
      `OrbitSeriesAccumulator`, and unused `load_playback_data`/`playback_data_from_batch`
      compatibility paths.
- [ ] Update `PLAY_OEM_DATAFLOW.md` and `PLAY_OEM_DATAFLOW.mmd` to describe shipped behavior;
      update the store design and this plan to distinguish the target contract from shipped
      behavior, while keeping graph names and shared-intermediate relationships aligned.
- [ ] Run numerical equivalence, laziness, segment/gap, cancellation, replacement, memory-sharing,
      allocation, and view regressions on ISS, JPSS-1, and multi-segment fixtures.
- [ ] Run headless performance and memory benchmarks against the recorded baseline; document
      remaining UI gates as unverified rather than inferring them from headless results.
- [ ] Review for residual duplicate owners, orbit-sized copies, eager derived work, stale-cache
      identity checks, and unhandled load lifecycle states.

**Done when:** the store design's validation criteria pass, superseded paths are removed, the
dataflow documentation matches the implementation, and all remaining exceptions/limitations are
explicitly documented.
**Depends on:** Steps 5–7. The Step 7 performance prerequisite is deferred by explicit user
direction; it remains an open acceptance criterion and is not considered passed.

## Deferred, separate work

### Repeat-open cache

- **Status:** Deferred.
- [ ] If repeat-open measurements justify a cache, specify source identity and modification
      detection, parser/cache versioning, atomic writes, partial/corrupt-cache handling,
      validation, invalidation, storage limits, and zero-copy-compatible mapping.
- [ ] Benchmark cold first-open and validated cache hits separately.

**Done when:** a separate design decision and measurements justify implementation; a persistent
cache is not assumed by the first-open performance gates.
**Depends on:** Step 0 and a separate approval.

## Completed steps

### 0. Establish the data and performance baseline

Capture a headless baseline and correctness references before replacing data ownership. Keep
historical GUI measurements clearly labeled and do not repeat GUI benchmarks as part of this plan.

- **Status:** Done.
- **Progress:** 3/3 checklist items.
- [x] Record parser/session baselines, relevant performance gates, and cancellation behavior.
- [x] Measure and verify the `datetime_to_tt_s` parser-speed change with matching states,
      completion metadata, and state-data digests.
- [x] Record raw direct-ingest and bounded-session candidate measurements without treating them
      as end-to-end or GUI results.

**Evidence:** The
[store design's performance evidence](./PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md#performance-evidence-and-acceptance)
records the baseline, parser comparisons, direct-store measurements, and limitations. Timestamp
conversion was measured parser-only at 53.0% lower median time on ISS (0.072736 s to 0.034165 s)
and 25.2% on JPSS-1 (0.584417 s to 0.436955 s), with matching state counts, completion metadata,
and state-data digests. Covariance retention and shared ODM line validation were optimized while
preserving validation; their results are parser/session evidence, not proof of final store
performance. The baseline work is complete; the absolute cancellation-time limit and all GUI
responsiveness gates remain unresolved/unverified.

**Done when:** reference outputs and headless measurement boundaries are recorded before the
store migration.
**Depends on:** None.

### 1. Complete the store skeleton and raw-load contract

Finish the public snapshot and notice contract and the reusable memo primitive on top of the
existing raw tier. Resolve capacity sizing and reserved-buffer behavior before controller
integration; do not trade a potentially unsafe bound for reallocating or silently truncating data.

- **Status:** Done.
- **Progress:** 8/8 checklist items.
- [x] Add fixed-capacity store-owned raw buffers, exclusive reservations, atomic committed-prefix
      snapshots, segment boundaries, gap tracking, and epoch/revision rejection.
- [x] Add direct parser row-sink ingestion without retaining parser state batches or covariance
      matrices.
- [x] Add bounded generation-tagged raw-append events, replacement epochs, and cancellation that
      cannot mutate a replacement load.
- [x] Record `LOADING`, `COMPLETE`, `FAILED`, and `CANCELLED`; expose validated metadata only
      after EOF/context validation and preserve committed prefixes on failure/cancellation.
- [x] Run automatic capacity sizing on the loader worker with cancellation checks between bounded
      reads.
- [x] Exclude covariance-block lines from automatic capacity sizing; test the conservative
      capacity bound, allocated buffer size, and explicit overflow behavior without reallocating.
- [x] Define the public `StoreSnapshot`, `StoreQuery[T]`, coverage, column-group, tier-notice,
      metadata, segment-bound, append/reset, and revision contracts from the design.
- [x] Implement and test a reusable chunk-memo primitive with absent/computing/complete/tentative
      states, in-flight request de-duplication, cancellation-safe writes, and counters.

**Done when:** one stable store contract supports generation-safe raw loading and supplies the
snapshot and memo foundations required by every derived tier; fixed-capacity behavior is safe and
its memory tradeoffs are measured or explicitly accepted.
**Depends on:** Step 0.

**Evidence:** The focused raw-store, loader, streaming, benchmark, and chunk-memo tests passed
(72 tests). The broader play-oem, CCSDS, and time-conversion regression set passed 842 tests with
4 skipped. A covariance-heavy valid OEM with 20 covariance matrices and one state allocates for
eight non-covariance lines; tests verify the bound covers parsed state rows, backing-array size,
and explicit overflow without growth. A fresh-process macOS probe reserved 64,000,000 raw/segment
array bytes for one million rows with a 32,768-byte peak-RSS delta before touching buffers; this
is not generalized to Windows or Linux, and physical-page commitment remains OS-dependent.
Historical automatic physical-line sizing measured ISS at 14.086 ms to first append and 46.389 ms
to validated completion (capacity 5,437 for 5,402 states; 70.2 MiB RSS), and JPSS-1 at 42.345 ms
and 516.716 ms (capacity 172,833 for 21,601 states; 72.5 MiB RSS). Explicit-capacity candidate
measurements were 11.821/42.137 ms on ISS and 13.106/486.874 ms on JPSS-1. These measurements
include raw validation/storage and bounded session handoff, not derived preparation or GUI
behavior; the automatic-capacity results predate the covariance-excluding bound. Full evidence is
in the [store design](./PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md#performance-evidence-and-acceptance).

### 2. Establish zero-copy interpolation and plotting primitives

Create the primitives needed to read raw rows and derived buffers without retaining point-by-point
interpolators or allocating orbit-sized display arrays.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Implement a stateless, view-based evaluator for linear, Hermite, Lagrange, and Chebyshev
      interpolation; verify outputs against the current cursor/interpolators, including
      interpolation-policy changes and segment edges.
- [x] Make the evaluator read only the required raw support rows and avoid retaining copies of
      sample points or segment-wide interpolator state.
- [x] Define reserved-buffer column groups and a `pair()` view helper for plot fields; verify
      read-only behavior and `np.shares_memory` for slices and pairs.
- [x] Validate zero-copy Matplotlib `PathPatch`/`LineCollection` paths through a draw and decide
      the documented VTK point-array exception from measured behavior.
- [x] Add allocation tests proving the evaluator and plot-view construction allocate no
      orbit-sized state or derived arrays.

**Done when:** supported interpolation results match the reference within floating-point
tolerance, and raw/plot views share their store buffers without orbit-sized copies.
**Depends on:** Step 1.

**Evidence:** The focused view-evaluator, core-interpolator, store, Agg plotting, VTK, cursor, and
3D trajectory test set passed (111 tests). A
100,000-sample allocation guard confirms a Chebyshev query uses exactly six support rows, those
rows share the input state buffer, and NumPy array conversions stay bounded to 64 elements. The
same configured interpolator is reused across multiple queries, its `interpolate_view` path does
not call the factory, and it clears support references after evaluation. Exact-sample results are
read-only views, and weakref tests confirm input arrays are not retained. Matplotlib 3.9.4 Agg
tests verify that `PathPatch` and `LineCollection` share strided pair vertices through a draw.
VTK 9.6.2 probes show that `numpy_to_vtk(deep=False)` shares packed C-contiguous `float64` data
but not strided columns; the VTK backend now retains its NumPy point buffers and avoids the
additional `deep=True` copy. Pylance syntax and diagnostics requests timed out; focused pytest
imports exercised the changed modules. `git diff --check` passed.

### 3. Add lazy interpolation and series tiers

Use the memo primitive to compute requested derived columns only. Keep display transforms outside
the store so changing a time unit or plot style does not recompute physical values.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Implement lazily requested series column groups using the existing computations as numerical
      references; write results directly to reserved final buffers rather than temporary
      full-length arrays.
- [x] Store raw-backed position and velocity as views; avoid kilometer-scaled and elapsed-time
      copies by applying units/origins in the view/artist transform.
- [x] Add Earth-fixed position chunks with memoization and stateless interpolation support using
      the zero-copy primitives from Step 2; expose one shared Earth-fixed sample-position tier for
      Ground Track, Pass Ground Track, and station-view migration.
- [x] Implement requested-range queries with segment-aware margins, covered spans, and read-only
      group views; a request must compute only intersecting absent/tentative chunks.
- [x] Test chunk boundaries, request order, partial prefixes, multi-segment inputs, append-tail
      invalidation, memo hits, and display-unit changes against one-shot reference outputs.

**Done when:** every tier remains absent until requested, repeated requests reuse complete
chunks, appends recompute only tentative tails, and results match the current implementation
without O(sample-count) temporary allocations.
**Depends on:** Steps 1–2.

**Evidence:** The focused store suite passed (37 tests), and the combined play-oem plus core
interpolator suite passed (571 passed, 4 skipped). Coverage includes point-query parity and policy
changes, lazy group selection, one-sample RTN overlap at a chunk boundary, partial loading
coverage, append-tail recomputation, request-order parity, memo hits, display-unit changes, and
Earth-fixed views. The implementation writes into per-tier reserved buffers and returns read-only
slices; it does not call the orbit-sized `compute_orbit_series` reference path. Pylance diagnostics
and syntax requests timed out; pytest imports exercised the changed modules. Range scheduling,
consumer wiring, and application-wide elimination of parallel derived-data owners remain for
Steps 5–7.

### 4. Implement range scheduling, playback-time queries, and station-access tiers

Add range-driven work and partial-coverage reporting without blocking playback or the GUI thread.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Add `RangeHint`, prioritized prefetch requests, generation cancellation, covered-span
      results, and chunk-completion notices; concurrent identical requests must share one
      computation.
- [x] Replace copied clock sample lists with `SampleTimes` over the raw timestamp column while
      preserving seek, sample-step, and coverage-extension behavior.
- [x] Implement typed anchored, chunked station look-angle profile views and derive requested
      access intervals from them; profile graphs and pass graphs must share the same per-station
      `StoreQuery[StationAccessView]`, and minimum-elevation changes must not recompute profiles.
- [x] Add range-based per-chunk eviction with active-view/in-flight-draw lifetime protection and
      deterministic recomputation; do not invalidate unaffected chunks in the same buffer.
- [x] Test that playback `state_at` performs no chunk computation, range dragging cancels stale
      work within one chunk, and partial requests never appear complete.

**Done when:** ranges and playback stay independent, prefetch is cancellable and deduplicated,
station results match the current implementation, and resident derived memory respects the
documented budget plus active ranges.
**Depends on:** Steps 2–3.

**Progress evidence:** Store, clock, and station-access tests cover request deduplication,
generation cancellation, partial coverage, station interval parity, threshold-only interval
changes, pair-view lifetime, per-chunk eviction, and deterministic recomputation. Validation:
`python3 -m pytest tests/ephem_toolkit/play_oem tests/ephem_toolkit/core/interpolator -q`
passed (636 passed, 4 skipped). Step 4 is complete; mmap advice remains platform-dependent and the
budget can be exceeded while active ranges or live views prevent eligible eviction.

### 5. Complete the store-backed view input contract

Inventory each registered view against the implemented query APIs, then close data gaps before
migrating view consumers. Preserve the zero-copy and lazy-query rules; derived view inputs must be
store-owned rather than computed or assembled by each panel.

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Inventory registered view values and interactions against store APIs, recording uncovered
      products before view migration.
- [x] Define typed view inputs for the store, stable snapshot, display unit, plot range, and
      coverage; provide tier-interest subscription and release semantics.
- [x] Implement the `speed-altitude` vertical slice using only range-limited `kinematics`;
      verify empty/partial coverage, range changes, numerical transforms, segmentation, buffer
      sharing, and tier-interest release.
- [x] Add a lazy, segment-aware `distance-delta` series group for Geocentric Distance; update the
      public query contract and test parity, range coverage, append, and segment-boundary behavior.
- [x] Add footprints and current station-metric point queries, with footprint results cached by
      the store and no per-view orbit-sized arrays.
- [x] Add store-owned range-limited Ground Track coordinates, reusing Earth-fixed positions and
      preserving segment and map-seam run boundaries without per-view full-range arrays.

**Inventory against current store queries:**

| Registered views | Existing store input | Gap to close before migration |
|---|---|---|
| State Components; 3D Orbit | Raw snapshot states, timestamps, and segment bounds | None for data inputs; handle the VTK backend's measured packed-array exception. |
| Speed / Altitude | `kinematics` | None; exercised by the vertical slice. |
| RTN Deltas | `rtn` | None. |
| Angular Velocity; Direction Change | `direction-rates` | None. |
| Geocentric Distance | `kinematics`, `distance-delta` | None; distance delta is a lazy segment-aware group. |
| Ground Track; Pass Ground Track | Earth-fixed positions, map-centered Ground Track groups, footprint point query, and station-access intervals for pass selection | None for query inputs. |
| Station Status; Pass Strip; Elevation / Azimuth / Range Profiles; Pass List; Sky View | Station profile/access query and station-metric point query | None for query inputs. |

**Done when:** every registered view's required input is available through a typed, range-aware
store query, including the distance-delta, Ground Track/footprint, and station-metric products;
no view needs to create an orbit-sized projection.
**Depends on:** Steps 1–4.

**Evidence:** The store-backed `speed-altitude` vertical slice, the first two Step 6 view groups,
the snapshot-bound consumer context and binding lifecycle, Ground Track consumers, and station
consumers validate range-limited inputs, display transforms, segment boundaries, buffer sharing,
empty states, stable limits, map seam handling, pass selection, point footprints, bounded profile
and sky display samples, backend-specific display packing, and tier-interest release. Store-backed
map paths use bounded display sampling rather than constructing an orbit-sized plotting projection.
Context tests cover snapshot refresh, no-range typed results, range replacement, and subscription
cleanup/rebinding. Ground Track queries reuse the Earth-fixed tier, return map-centered seam-split
groups, and use a bounded cache; point queries cover station metrics and footprints. Station profile
adapters share store-owned columns; station view tests cover pending-to-ready snapshot refresh,
empty-versus-loading distinction, terminal failure/cancellation messages, multi-segment separation,
bounded samples, and close cleanup. Shared binding tests cover cleanup on store replacement; legacy
station selection/range regression tests remain green. Validation:
`python3 -m pytest tests/ephem_toolkit/play_oem tests/ephem_toolkit/core/interpolator -q`
passed (681 passed, 4 skipped). `git diff --check` and `compileall` passed. Step 6 is complete;
active application loading and controller ownership are tracked separately in Step 7.

### 6. Migrate views to store snapshots and range queries

Migrate consumers only after Step 5 provides all required query outputs. Preserve plot labels,
values, segmentation, click-to-seek, empty/partial behavior, and 3D backend behavior.

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Migrate RTN Deltas, Angular Velocity, Direction Change, and Geocentric Distance to
      range-limited series-group queries; use the validated `speed-altitude` path as the pattern
      and request only fields each view uses. Store paths share derived-column buffers, apply
      display transforms, preserve segment breaks and cursor/range behavior, and release tier
      interest on close.
- [x] Migrate State Components and 3D trajectory views to raw snapshot columns. State Components
      paths and the Matplotlib 3D backend use raw-backed inputs; the VTK backend packs only its
      range-limited, decimated display path. Preserve segment, range, cursor, and camera behavior.
- [x] Promote `StoreViewContext` to a snapshot-bound consumer read facade. Add a factory and
      `refresh()` so one context binds a stable snapshot, display unit, plot range, and coverage;
      provide bound methods for series, state, Ground Track, Earth-fixed, and station queries.
      Keep query results typed and revision-stamped, expose selected groups without manual mapping
      unpacking, and represent empty/no-range results explicitly rather than returning `None`.
      Add a shared view-binding helper for tier subscriptions, context replacement, and cleanup;
      retain non-blocking behavior, read-only views, leases, and zero-copy plotting adapters.
- [x] Migrate Ground Track and Pass Ground Track to typed Earth-fixed, Ground Track, and footprint
      results through the bound read context; preserve map, seam, range, and station-selection
      behavior.
- [x] Migrate station status, pass strip, profiles, pass list, and sky view to typed
      station-profile/access and point-metric results through the bound read context; reuse shared
      store buffers. Profile adapters retain leased store columns, and profile/sky plotting bounds
      display samples per segment.
- [x] Verify empty, partial, loading, failed, cancelled, and multi-segment render states;
      confirm plotting buffer sharing, stable-snapshot refresh behavior, and resource release on
      close/replacement. Station views distinguish pending, terminal-failure, and cancelled
      snapshots; preserve separate profile runs across segments; and release station-tier interest
      on close. Shared binding tests verify subscription cleanup when replacing stores.

**Done when:** every registered view builds and updates from typed store inputs, preserves current
visual/numerical and interaction behavior, requests only needed ranges/tiers, and creates no hidden
orbit-sized `OrbitSeries` projection or downsampled copy. Callers use one snapshot-bound context per
refresh rather than passing the store, snapshot, and range to each query; tier-interest and cleanup
boilerplate is handled by the shared binding helper.
**Depends on:** Step 5.
