# play-oem — Station Interval State Complexity Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and candidate priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior boundary and performance investigation:
[PLAY_OEM_COMPLEXITY_9_DOMAIN_PERFORMANCE_HOTSPOTS_PLAN.md](./PLAY_OEM_COMPLEXITY_9_DOMAIN_PERFORMANCE_HOTSPOTS_PLAN.md).
Station access implementation:
[`station_access.py`](../../../src/ephem_toolkit/play_oem/station_access.py).

## Goal

Evaluate whether `_intervals_for_segment` can represent one in-progress
access interval with a cohesive state value instead of coordinating many
parallel optional locals. Reduce the number of invariants a maintainer must
remember while preserving interval boundaries, crossing refinement, extrema,
and coverage/gap flags.

This reopens the station interval candidate as a complexity-reduction
experiment, not as a bug fix. Plan 9 found no incorrect result and added
boundary tests; correctness alone is not a reason to rewrite this domain logic.

## Evidence and hypothesis

The function currently tracks active start time and metrics, peak time and
metrics, minimum-range time and metrics, last access metrics, prior sample
time/access state, and coverage/gap facts as separate locals. A missing metric
and an access exit each clear a similar group of active-interval fields. The
completion and missing-metric paths each check that several optionals are
present before constructing an `AccessInterval`.

**Hypothesis:** an internal active-interval state object or similarly cohesive
representation could keep start/extrema/end metrics together, simplify reset
and completion checks, and make invalid partial combinations harder to
represent. Reject it if it only relocates the same optional-field checks,
introduces many tiny methods, obscures transition order, or increases concepts
more than it reduces coordinated local state.

## Procedure

1. Revisit plan 9's transition table and tests. Enumerate which fields exist
   only while a pass is active and which facts belong to the segment iteration.
2. Sketch the smallest candidate state representation and its transitions for
   entering access, continuing access, leaving access, missing metrics, and
   end-of-segment completion. Keep crossing refinement and output construction
   outside it unless a clear ownership boundary requires otherwise.
3. Compare current and proposed representations by the number of independently
   coordinated fields, presence guards, reset sites, methods, and caller
   obligations. Explicitly account for added type/method indirection.
4. If the state object makes the interval invariant materially clearer, make
   the narrow implementation change. Keep calculations and tolerances
   unchanged; do not redesign the station-access algorithm.
5. Add or adapt focused tests only where the representation changes the
   observable contract. Retain tests for access entry/exit, missing metric
   split/reset, active interval at coverage end, gap flags, and extrema.
6. Run station-access, store station-query, and station-analysis tests.
   Compare produced intervals across existing boundary fixtures.
7. Keep the refactor only if it reduces state coordination and the resulting
   transition loop is easier to explain. Otherwise leave production logic
   unchanged and record the reason.
8. Update the assessment and subsystem overview with the code decision and
   next candidate.

## Required behavior

- Preserve refined entry/exit times and `CROSSING_TIME_TOLERANCE_S`.
- Preserve peak elevation and minimum-range sample/time selection.
- Preserve missing-metric interval splitting and extrema reset.
- Preserve coverage-start/end and source-gap clipping flags.
- Preserve endpoint metrics and all `AccessInterval` values.
- Do not add performance-sensitive allocations per sample; allocate state only
  when an access interval begins, unless measurements show otherwise.

## Implementation checklist

- **Status:** Complete — active interval invariants are grouped.
- **Progress:** 8/8 checklist items.
- [x] Reconcile the proposed state object with plan 9's transition table and
      existing boundary evidence.
- [x] Identify active-pass fields and their valid combinations.
- [x] Compare one cohesive representation against the current parallel locals.
- [x] Implement one active interval object that owns start, extrema, and end
      metrics, with no per-sample object allocation.
- [x] Preserve numerical/domain behavior and focused tests.
- [x] Run station-access, store, and station-analysis suites.
- [x] Keep the refactor because the function now has one active-state owner and
      no parallel optional-field completeness guard.
- [x] Update the assessment and subsystem overview.

**Done when:** The in-progress interval state is materially easier to
understand and verify, or the state-object hypothesis is rejected with a
specific complexity tradeoff and no production code is changed.

## Execution record — 2026-11-11

Added `_ActiveAccessInterval` to own the active pass's start, extrema, and
endpoint metrics. It initializes all required metrics together, updates peak
and minimum range through `observe`, and constructs the final
`AccessInterval` through `finish`. `_intervals_for_segment` now owns one
optional active-state reference instead of parallel optional fields and
repeated all-fields-present guards; gap and exit transitions clear the state
with one assignment. The state object is allocated per active interval, not
per sample. Crossing refinement and coverage/gap decisions remain in the
segment loop.

The store, station-access, station-analysis, and pass-view tests passed
(113 passed, 1 display-dependent skip) on macOS with Python 3.9.6. No
numerical tolerances or interval semantics were changed.
