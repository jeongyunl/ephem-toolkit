# play-oem — Station-Access Query Phase Complexity Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and candidate priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Derived-query comparison:
[PLAY_OEM_COMPLEXITY_6_DERIVED_STORE_QUERIES_PLAN.md](./PLAY_OEM_COMPLEXITY_6_DERIVED_STORE_QUERIES_PLAN.md).
Station interval-state reduction:
[PLAY_OEM_COMPLEXITY_27_STATION_INTERVAL_STATE_PLAN.md](./PLAY_OEM_COMPLEXITY_27_STATION_INTERVAL_STATE_PLAN.md).

## Goal

Evaluate whether `OemDataStore.station_access` can be made easier to
understand and change by clarifying the boundary among station-query
preparation, ready-profile/interval assembly, and coverage/cache finalization.
Reduce the number of responsibilities and state transitions a maintainer must
hold in mind without hiding station-specific behavior behind generic
query machinery.

This is a code-complexity experiment, not a request to split
`oem_data_store.py` or force station access into the other range-query paths.

## Evidence and hypothesis

`station_access` currently performs input validation and empty/unsupported
early returns, selects station-profile storage and expanded row ranges,
schedules or computes missing work, touches chunks, consults an interval
cache, assembles ready profile views and intervals, computes coverage
completeness, creates limitation messages, caches completed intervals, and
evicts derived buffers.

Plan 6 found that station access has distinct sample-grid coverage and
station-specific behavior, so a shared generic query abstraction was not
justified. The candidate here is local phase ownership, not policy sharing.

**Hypothesis:** one or more natural phase boundaries may reduce local
reasoning if each phase has a cohesive contract and a small input/output
surface. Reject extraction if it requires a broad context object, returns
several loosely related values, or merely relocates the current sequence.

## Procedure

1. Trace the function in execution order and inventory state passed among
   validation, storage/range preparation, work scheduling, profile assembly,
   interval computation, coverage, cache publication, and eviction.
2. Map existing tests for empty and unsupported snapshots, partial coverage,
   ready/pending station rows, wait/cancel behavior, interval-cache hits, and
   segment-gap limitations.
3. Identify at most one candidate phase boundary. Sketch its signature and
   caller before editing; keep snapshot, tier, cache, and lock ownership
   explicit.
4. Reject extraction if the caller must carry multiple parallel accumulators
   or the helper needs the same store internals as the parent. Do not introduce
   a general result-builder or query framework.
5. If a cohesive boundary survives, implement it with narrow inputs and
   outputs. Keep derived-buffer locks, cache publication, and eviction ordering
   unchanged unless the trace proves they belong within the same phase.
6. Run station-access, store, station-analysis, and pass-view tests. Add a
   focused test only if the refactor changes a previously unverified behavior.
7. Compare local responsibilities, state passed across the boundary, and
   caller reasoning before and after. Keep the change only if the phase is
   clearer without shifting equivalent complexity.
8. Update the assessment and subsystem overview with the code decision and
   next candidate.

## Required behavior

- Preserve validation order and early-return values for empty/unsupported data.
- Preserve station-specific range expansion, partial coverage, and gap rules.
- Preserve wait/cancellation semantics and priority scheduling.
- Preserve lock boundaries and consistent ready-buffer snapshots.
- Preserve interval-cache key, publication conditions, and eviction behavior.
- Do not add allocations or material performance overhead to row processing.

## Implementation checklist

- **Status:** Complete — phase extraction rejected.
- **Progress:** 8/8 checklist items.
- [x] Map phases, state ownership, lock boundaries, and order dependencies.
- [x] Map existing tests to each phase and behavior.
- [x] Evaluate candidate boundaries and their inputs/outputs.
- [x] Reject broad-context or accumulator-forwarding abstractions.
- [x] Make no implementation change because no phase met the complexity
      reduction criterion.
- [x] Run station, store, analysis, and pass-view suites.
- [x] Compare the current pipeline and candidate helper boundaries.
- [x] Update the assessment and subsystem overview.

**Done when:** `station_access` has a demonstrably clearer responsibility
boundary with preserved query behavior, or the extraction is rejected with a
specific complexity tradeoff and no production code is changed.

## Execution record — 2026-11-11

The method has visible sequential phases, but candidate helpers did not have
small independent contracts. Profile/interval assembly would need to exchange
`layout_ranges`, `tier`, cached intervals, profile views, access intervals,
coverage spans, and ready-row information; moving this into a helper would
replace local state with a multi-value protocol. Preparation, computation,
ready-buffer reads, cache publication, and eviction also share snapshot/tier
state and ordering constraints. Extracting those phases would split lock and
cache ownership across method boundaries without reducing the rules required
to understand the query.

No source or test change was made. The station-access, store,
station-analysis, and pass-view suites passed (**113 passed, 1
display-dependent skip**) on macOS with Python 3.9.6. Station-specific behavior
remains local to `station_access`; a generic query or result-builder
abstraction is not justified.
