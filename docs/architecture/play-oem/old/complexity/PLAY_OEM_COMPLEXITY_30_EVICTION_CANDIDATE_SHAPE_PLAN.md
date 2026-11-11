# play-oem — Derived-Buffer Eviction Candidate Complexity Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and candidate priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior store scheduling/cache investigation:
[PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md](./PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md).
Eviction implementation:
[`oem_data_store.py`](../../../src/ephem_toolkit/play_oem/oem_data_store.py).

## Goal

Evaluate whether the eviction-candidate representation in
`OemDataStore._evict_derived_buffers` can be made easier to reason about. The
current candidate is a ten-element positional tuple carrying LRU order,
buffer/tier identity, chunk location, storage references, dimensions, and byte
size. The goal is to make the eviction data contract clearer without changing
candidate ordering or memory behavior.

This is a bounded local-complexity experiment, not an eviction redesign or
general cache abstraction.

## Evidence and hypothesis

The function constructs candidate tuples, uses `candidate[-1]` for byte
accounting, sorts by `item[:4]`, then unpacks all ten positions before checking
pins, active ranges, memo validity, and platform memory advice. The meaning of
each tuple position must be maintained consistently across collection,
accounting, sorting, and release.

Plan 5 mapped tier-specific validity and eviction constraints and rejected a
general scheduler/query extraction. This plan considers only whether named
candidate fields improve local reasoning while retaining one eviction loop.

**Hypothesis:** a small immutable private record with named fields will remove
positional coupling and make byte accounting, ordering, and release logic
clearer. Reject it if the added type and construction ceremony outweigh the
clarity, or if it expands into a generalized tier protocol.

## Procedure

1. Trace candidate production for series, Earth-fixed, and station-profile
   tiers. Verify the invariants represented by every tuple field and the
   current ordering key.
2. Compare candidate representations: current tuple, a private named tuple,
   or a frozen dataclass. Select the least complex form that names fields
   clearly and preserves array/memo references.
3. Keep tier-specific candidate enumeration, station-only interval-cache
   invalidation, pin/range protection, and memory advice in the existing
   function.
4. If the named representation is clearer, implement only that representation.
   Do not extract collection or eviction into a framework.
5. Run focused `test_oem_data_store.py` and chunk-memo tests. Add a test only
   if the representation change exposes an untested ordering or size invariant.
6. Compare the candidate contract and eviction path before/after. Retain the
   change only if positional knowledge is removed without introducing
   indirection or changing memory accounting.
7. Update the assessment and subsystem overview with the outcome.

## Required behavior

- Preserve byte totals and ground-track-cache-first eviction.
- Preserve LRU ordering by access order, buffer id, tier, then chunk index.
- Preserve skipping pinned and range-active chunks.
- Preserve epoch and tier-specific policy-revision validation.
- Preserve station interval-cache invalidation after station chunk eviction.
- Preserve platform memory-advice behavior and mapped-buffer readiness updates.

## Outcome

Implemented `_EvictionCandidate` as a frozen record with named fields. Candidate
byte accounting and the existing four-part eviction ordering now name their
inputs; the tier enumeration and single eviction loop remain in place. The
station-only invalidation, pin/range checks, memo validation, and release
callback behavior were not generalized or moved.

Existing store tests cover memory-budget eviction, pinned-view protection, and
chunk recomputation. Validation passed:

- `python3 -m pytest tests/ephem_toolkit/play_oem/test_oem_data_store.py tests/ephem_toolkit/play_oem/test_chunk_memo.py`
- **87 passed**
- `git diff --check`

No new test was needed for the representation-only change; the eviction sort
key remains the same four values in the same order as the former tuple slice.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 7/7 checklist items.
- [x] Map tuple fields to candidate creation, accounting, ordering, and release.
- [x] Confirm memory-budget and tier-eviction test coverage.
- [x] Select the smallest named representation or reject it.
- [x] Keep eviction ordering and tier-specific behavior unchanged.
- [x] Run store and chunk-memo tests.
- [x] Compare the local reasoning required before and after.
- [x] Update the assessment and subsystem overview.

**Done when:** Eviction candidates have a clearer named contract without
changing memory behavior, or a named type is rejected as needless ceremony.
