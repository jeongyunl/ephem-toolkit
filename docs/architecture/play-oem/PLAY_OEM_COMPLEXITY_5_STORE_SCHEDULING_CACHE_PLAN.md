# play-oem — Store Scheduling and Cache Lifecycle Complexity Reduction Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Baseline and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context: [PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Load-lifecycle findings:
[PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md).
Current dataflow: [PLAY_OEM_DATAFLOW.md](./PLAY_OEM_DATAFLOW.md).

## Goal

Make derived-work scheduling, query readiness, cache validity, and eviction
easier to understand and verify by mapping their existing ownership and
concurrency contract, then evaluating one bounded improvement only if the
evidence supports it. Preserve store-owned raw data, snapshot semantics,
partial coverage, cancellation, pinned views, bounded derived-memory behavior,
and query performance. A cohesive description or test may be the right result;
moving methods or splitting `oem_data_store.py` is not an outcome by itself.

Follow the complexity strategy: establish the as-built contract, distinguish
inherent coordination from avoidable policy duplication, and then evaluate a
small hypothesis against the same tests and measurements. Assess local
reasoning, overall coupling, and code volume separately.

## Current implementation and initial evidence

`OemDataStore` owns raw rows and lazily allocated derived buffers. Query methods
accept a `StoreSnapshot` and range; nonblocking queries can return available
partial results and schedule missing work, while scheduler workers call the
same query methods in waiting mode. `ChunkMemo` shares in-flight chunk
computations and stamps results by epoch and policy revision. Views consume
read-only slices that retain leases on their backing chunks.

The following is an initial static orientation, not a completed lock, memory,
or query-invariant audit. Verify it against all relevant call sites and tests
before drawing conclusions.

| Trigger / surface | Observed behavior | Points to verify |
| --- | --- | --- |
| `prefetch(snapshot, request)` | Normalizes and validates a `QueryRequest`; rejects stale snapshots; deduplicates by epoch, revision, tier-specific policy revision, and request; returns a shared future. | Exact identity semantics for each tier; behavior when requests are canceled, stale, or resubmitted while running. |
| Range hint or tier subscription changes | Advances range generation, updates queue priorities, and may cancel stale requests; dragging makes only small plot-priority work eligible. | Active versus queued cancellation, generation updates, subscription races, and starvation/fairness under changing hints. |
| Scheduler drain | A single-worker executor selects the minimum-priority eligible request and runs it through the public query API in waiting mode. | Lock ordering, worker shutdown, exceptions, and whether active work can publish after range/reset changes. |
| Nonblocking query | Returns currently ready slices and coverage while requesting missing chunks. | Coverage consistency across tiers and whether a query can return stale or internally mixed readiness. |
| Waiting query / prefetch | Computes requested chunks, deduplicates via `ChunkMemo`, and publishes tier notices as chunks become ready. | Cancellation points, notice ordering, temporary/tentative chunks, and cross-tier dependencies. |
| View slice lifetime | `ColumnGroupView` pins chunks through a lease; derived NumPy views can retain the lease. | All slicing/view conversions that must preserve ownership and cleanup when the store is collected. |
| Eviction | Computes candidate bytes for complete/tentative series, Earth-fixed, and station-profile chunks plus ground-track result entries; evicts least-recently-used entries, skipping pinned and range-active chunks. | Meaning of the budget versus RSS/mapped pages; uncounted bounded caches; behavior when all chunks are pinned/active or memory advice is unavailable. |
| Epoch reset / store close | Reset clears memos and tiers, advances epoch, and cancels scheduled work; close cancels work and shuts down the one-worker executor with a wait. | Lock order, in-flight computation invalidation, retained snapshots/views, and shutdown latency under active computation. |

Static inspection finds three principal locks: store state (`_lock`), derived
computation/eviction (`_derived_compute_lock`), and scheduling/subscribers
(`_scheduler_lock`). The store's default derived budget is 256 MiB and the
derived chunk size is 4096 rows. Ground-track results also have a four-entry
limit; footprint results have a 32-entry limit; station interval results have
a 128-entry limit. These limits and the budget count different things and must
not be summarized as a single verified process-memory ceiling.

The scheduler has one worker. Range priorities distinguish plot, near-plot /
current-time, playback, and other work. `series` and Earth-fixed computations
do not key chunks on interpolation-policy revision; station profiles do.
Ground-track results are built from Earth-fixed results and are cached
separately. These are starting facts for the query matrix, not a claim that the
tiers share identical validity rules.

## Relevant assessment findings

The authoritative assessment ranks **store scheduling and cache lifecycle**
second, after load lifecycle. It identifies `prefetch`,
`_drain_scheduler_queue`, `_run_prefetch`, and `_evict_derived_buffers` as
coexisting with raw storage and query methods in a 3,545-line module at its
original baseline. The assessment did not prove that this boundary causes
defects or that moving methods would reduce coupling.

Current targeted sizes at preparation are 3,545 physical lines in
`oem_data_store.py`; `prefetch` is 90 lines, `_priority_for_request` 33,
`_drain_scheduler_queue` 42, `_run_prefetch` 43, `series` 159,
`earth_fixed_positions` 152, `ground_track` 186, `station_access` 244, and
`_evict_derived_buffers` 162. These are code-volume context, not reduction
targets. The module also owns raw loading and point queries, so dependencies
outside scheduling must be mapped before extracting a component.

Existing separation worth preserving includes `ChunkMemo`, `QueryRequest`,
`StoreQuery`/coverage, `ColumnGroupView` leases, and the shared priority queue.
The query tiers retain different policies (especially station-specific
sampling, Earth-fixed conversion, and ground-track result caching). No common
query or cache helper should be introduced solely because methods have similar
shapes.

## Interactions with other subsystems

- **Raw storage and snapshots:** epochs, revisions, reservations, and reset
  state are protected by store ownership. Derived work must not publish into a
  replacement epoch or treat an older snapshot as current.
- **Chunk memo:** `ChunkMemo` has `ABSENT`, `COMPUTING`, `COMPLETE`, and
  `TENTATIVE` states; it shares in-flight work, propagates errors/cancellation,
  and prevents invalidated work from publishing. The store's ready masks and
  buffers must agree with memo state.
- **Views and pinned data:** `ColumnGroupView` / pair slices can outlive a
  query result. Eviction must not invalidate memory currently exposed to a view,
  and view cleanup must release pins.
- **Range and playback hints:** plot range, playback range, current time, and
  dragging state influence priority and eviction protection. Preserve this
  prioritization without making the store depend on wx or controller objects.
- **Tier-specific queries:** series groups, Earth-fixed positions, ground
  track, and station access differ in interpolation dependencies, segment
  support, margin expansion, completeness, and caching. Footprints and station
  interval caches have separate bounded policies.
- **Platform and memory mapping:** chunk release uses `mmap` memory advice where
  available. Verify behavior on supported platforms and do not equate logical
  eviction with immediate RSS reduction.

## Required behavior and constraints

- Keep the store as the sole owner of raw and derived orbit data; retain
  zero-copy ingestion and snapshot-bound read-only views.
- Preserve epoch, revision, and policy-revision validity exactly where each
  tier depends on them. Do not make all tiers depend on policy revision or
  remove a dependency based on one tier's behavior.
- Preserve nonblocking partial results and precise coverage distinctions:
  ready, pending, empty, outside requested coverage, and unavailable.
- Preserve in-flight deduplication, cancellation, range priority, drag
  eligibility, notice publication, and error propagation.
- Preserve chunk pin counts, active-range protection, cache limits, and memory
  budget behavior, including the actual platform-specific release semantics.
- Keep expensive calculations off the wx thread and avoid introducing lock
  inversions, blocking callbacks, or shutdown deadlocks.
- Preserve numerical output, segment boundaries/gaps, interpolation support,
  station-specific limitations, and bounded display/query ranges.
- Do not split the module or add a new scheduling abstraction unless a bounded
  experiment demonstrates lower total reasoning cost and equivalent behavior.

## Implementation checklist

Work in dependency order. This plan is preparatory; the initial observations
are not a complete specification. Keep the assessment authoritative for
priorities and put verified details, commands, results, and decisions here.

- **Status:** Investigation complete; shared request-range policy implemented.
- **Progress:** 8/8 checklist items.
- [x] Trace representative scheduling paths from view query to `prefetch`,
      queue selection, `_run_prefetch`, chunk computation, notice publication,
      query result, and eviction. Include both nonblocking and waiting callers
      and each supported tier. Record thread, lock, epoch/revision, and future
      ownership at each boundary.
- [x] Produce an as-built state/transition table for request normalization,
      deduplication, queueing, priority changes, tier-interest changes,
      dragging, queued and active cancellation, query completion/failure,
      reset, and close. Trace tentative-tail promotion and invalidation during
      in-flight computation.
- [x] Build a responsibility matrix for `OemDataStore`, `ChunkMemo`,
      scheduler/futures, each derived tier, `ColumnGroupView` leases, and
      callers/views. Inventory lock order, validity stamps, readiness masks,
      cache ownership, memory accounting, and caller obligations. Identify
      repeated policy separately from tier-specific behavior.
- [x] Map existing tests to the contract and run focused scheduler, cache,
      range, and query tests. Add meaningful missing coverage for any
      demonstrated invariant gaps, including cancellation during active work,
      reset/close with work in flight, pinned-view lifetime, and memory
      pressure where the test environment can verify it. Record platform and
      native-memory limitations.
- [x] Record a before baseline at a specific commit and working-tree state:
      relevant traces, locks, tier responsibilities, code volume, tests, and
      measurable memory/responsiveness behavior where applicable. State
      commands, Python/tool versions, platform, fixtures, and exclusions. Do
      not claim RSS or performance improvement from logical cache counters
      alone.
- [x] Rank observed issues by change frequency where evidence exists,
      reasoning/testing difficulty, and consequence of mistakes. State
      uncertainty. Select one bounded hypothesis with affected interfaces,
      invariants, alternatives, expected benefit, and rejection criteria.
      Candidate: centralize repeated request-range expansion used by priority
      and drag eligibility, but only if tier semantics match after tracing.
- [x] Evaluate the hypothesis with a sketch or testable prototype. If
      justified, implement only the smallest change and compare the same
      transition map, responsibility matrix, call sites, tests, code volume,
      and relevant performance/memory evidence. Retain no change that merely
      moves policy or weakens a tier-specific contract.
- [x] Update the assessment with findings and revised priorities; update
      dataflow or store design only if behavior or architecture changes.
      Record validation, known limitations, the final decision, and a
      recommendation for the next subsystem.

## Execution record — 2026-11-10

### Verified scheduling and query trace

`StoreViewContext` binds a stable `StoreSnapshot`, resolved plot range, and
coverage. Its series, Earth-fixed, Ground Track, and station-access methods
delegate to the store with `wait=False` by default. A store query returns
currently ready data and coverage; when work is missing, it submits a
`QueryRequest` to `prefetch`. Explicit waiting queries and the single scheduler
worker call the same tier methods with `wait=True`.

`prefetch` normalizes supported requests and validates the snapshot epoch. The
deduplication key is `(epoch, revision, policy_revision, request)`, with
policy revision included only for station access. An identical outstanding
request returns the same future. Otherwise the request gets a sequence number,
priority, range generation, and a cancellable future and enters the heap.

Range-hint and tier-interest updates hold `_scheduler_lock`, update the current
generation/priority, cancel stale work, and reheap queued work. During dragging,
the drain considers only priority-1 work whose estimated requested rows do not
exceed `DERIVED_CHUNK_SIZE` (4096). One executor worker drains eligible items
in priority/sequence order. It releases the scheduler lock before dispatching
to the tier query. The future's cancellation event is passed through waiting
queries to chunk computations. Result, exception, or cancellation is recorded
on the future; completion removes the scheduled-work entry. Subscriber
callbacks are copied under the scheduler lock and invoked after releasing it.

`ChunkMemo` shares in-flight work and stamps chunks by epoch/policy. It releases
its memo lock while the compute callback runs, then verifies that its entry is
still current before publishing. Partial loading can produce tentative series
tail chunks, which are recomputed on the next request. Queries track ready
rows separately and calculate coverage from ready spans, rather than treating
an enqueued request as complete data.

The main lock sequence verified in the inspected paths is:

- Query snapshots validate under `_lock`; `prefetch` then acquires
  `_scheduler_lock`. Reset is initiated under `_lock` and cancels work under
  `_scheduler_lock`.
- Scheduling and range-hint methods use `_scheduler_lock`; the worker releases
  it before calling query methods.
- Derived computations and eviction use `_derived_compute_lock`; code that
  reads or mutates store-owned arrays then uses `_lock`. Eviction calls
  `ChunkMemo.evict`, whose release callback invalidates the ready mask before
  removing the memo entry.
- `_publish_notice` releases `_scheduler_lock` before callbacks.

These are the observed lock relationships, not a proof over every method or
future callback. No lock inversion was found in the traced path. `close` marks
the scheduler closed, cancels scheduled futures, then waits for executor
shutdown. Reset invalidates memo entries and advances the epoch; retained
snapshots/views can still hold their backing references but cannot make stale
work current again.

### Query/cache responsibility matrix

| Tier / owner | Validity and work model | Cache, coverage, and eviction behavior |
| --- | --- | --- |
| Series groups | One buffer/memo per group; chunk validity uses epoch and policy revision `0`. Unrequested groups are not computed. A partial tail is tentative. | Nonblocking queries return ready spans; multi-group coverage uses common ready spans. Chunks are eligible for eviction when unpinned and not protected by an active range. |
| Earth-fixed positions | One lazy buffer/memo; chunk validity uses epoch and policy revision `0`. Requested bounds expand by the supplied margin for support. | Read-only slices retain chunk leases; reported coverage is limited to the caller's requested bounds. |
| Ground Track | Depends on Earth-fixed positions and applies WGS-84 conversion/seam splitting. Its result key includes epoch, revision, bounds, margin, and center longitude; interpolation policy does not alter the geometry. | Only complete results no larger than the configured budget are cached; LRU cache is also limited to four entries. Nonblocking calls enqueue work and report incomplete coverage until ready. |
| Station access | A station profile tier is keyed by epoch, revision, policy revision, and station identity/location. It samples each segment separately and uses point-state queries; access windows expand by a minimum/fractional margin. | Partial profiles produce partial coverage. Station interval results include bounds and elevation threshold and are limited to 128 entries. Profile chunks use the shared pin/range-aware eviction path. |
| Footprints | Point-query cache keyed by its query inputs and cleared on epoch reset. | LRU entry count is capped at 32; this cache is not included in `_evict_derived_buffers`' byte total. |
| `ColumnGroupView` / slices | A lease pins all backing chunks spanned by the view; array-derived views retain the lease when they share memory. | Finalization decrements pin counts; eviction skips pinned chunks. The store can be collected independently because the finalizer holds a weak reference. |
| `OemDataStore` eviction | Default derived budget is 256 MiB. Candidate byte totals include complete/tentative series, Earth-fixed, and station-profile chunks plus Ground Track result arrays. | Ground Track LRU entries are removed first, then chunk candidates by touch order. Pinned and range-active chunks are skipped. Chunk page release depends on `mmap` memory-advice support. |

The budget is therefore a policy over selected derived buffers, not a process
RSS ceiling: metadata, Python objects, the bounded footprint and interval
caches, raw buffers, active/pinned chunks, and allocator/OS page behavior are
not all represented by the same byte count. If memory advice is unavailable,
the implementation returns without evicting mapped chunks. This is recorded as
a platform/memory limitation to verify, not as a demonstrated defect.

### Bounded hypothesis and result

The scheduler independently expanded tier support ranges in both
`_priority_for_request` and `_request_rows`. The same three rules appeared in
both places: explicit margins for Earth-fixed/Ground Track, duration-derived
margins for station access, and no expansion for series. A mismatch could make
the scheduler prioritize one range while drag eligibility estimates another.
Change frequency is unknown; the risk is policy drift, not an observed defect.

The shared `_expanded_request_bounds` helper now owns those rules and is used by
both methods. It does not merge query implementations or change any
tier-specific computation. Added parameterized coverage for all four tiers and
an integration check that the expanded range controls both priority and
drag-size estimation. Added tests proving that reset cancels active prefetch
without publishing into a new epoch and that close signals active work and waits
for it to stop.

Before/after source baseline: commit `68d679fa28d31bff81a0a67502f89f8a9b827510`.
At task start the only existing worktree changes were documentation from the
preceding lifecycle-plan task; the source file was unchanged. Environment:
macOS, Python 3.9.6, pytest 8.4.2.

| Measure | Before | After |
| --- | ---: | ---: |
| `oem_data_store.py` physical lines | 3,545 | 3,536 |
| Function/method definitions in the module | 114 | 115 |
| `_priority_for_request` | 33 lines | 21 lines |
| `_request_rows` | 42 lines | 31 lines |
| Shared `_expanded_request_bounds` | — | 12 lines |

Together, the two callers shrink by 23 lines while the shared helper adds 12,
for 11 fewer lines across those functions; module volume falls by 9 lines.
There is one additional named helper, but less duplicate policy to compare.
This modestly improves local reasoning and lowers overall drift risk without
changing scheduler interfaces or ownership. No memory, numerical, or algorithm
path changed, so no benchmark or RSS claim is made.

Validation command:

```sh
pytest -q tests/ephem_toolkit/play_oem/test_oem_data_store.py \
  tests/ephem_toolkit/play_oem/test_chunk_memo.py \
  tests/ephem_toolkit/play_oem/test_play_oem_app.py
```

Result: 163 passed; 14 existing Matplotlib/Pyparsing deprecation warnings.
Specific new tests are
`test_request_bounds_include_each_tiers_support_margin`,
`test_scheduler_priority_and_drag_size_use_expanded_request_bounds`,
`test_clear_cancels_active_prefetch_without_publishing_old_epoch`, and
`test_close_cancels_active_prefetch_and_waits_for_worker`. Logical eviction
behavior is covered by existing tests, but no RSS or cross-platform memory
advice experiment was run. Native GUI performance and change/defect history
remain unmeasured.

The final decision is to retain the shared range-expansion helper and tests.
No scheduler extraction or generalized query helper is justified by this
investigation. The next assessment priority is **derived store queries**:
compare their range/coverage/invalidation rules, especially station-specific
sampling versus shared series/Earth-fixed chunk handling.

**Done when:** scheduler, query, and eviction ownership and validity rules are
checked against implementation and tests; memory and platform limits are stated
accurately; a bounded candidate is evaluated or rejected with evidence; and
any accepted change preserves the contract. The conclusion must distinguish
local reasoning, overall coupling, code volume, and actual memory/performance
evidence. If no production change is justified, record that decision without
claiming a complexity reduction.

**Depends on:** [PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md)
and the existing complexity strategy and assessment. This plan does not
supersede the main release-readiness plan.
