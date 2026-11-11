# play-oem — Incremental Event Routing Complexity Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and candidate priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Load lifecycle contract and prior decision:
[PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md).
Recent snapshot-installation reductions:
[PLAY_OEM_COMPLEXITY_23_SNAPSHOT_INSTALLATION_DEDUPLICATION_PLAN.md](./PLAY_OEM_COMPLEXITY_23_SNAPSHOT_INSTALLATION_DEDUPLICATION_PLAN.md),
[PLAY_OEM_COMPLEXITY_25_SNAPSHOT_INSTALLATION_PHASES_PLAN.md](./PLAY_OEM_COMPLEXITY_25_SNAPSHOT_INSTALLATION_PHASES_PLAN.md).

## Goal

Evaluate whether `PlayerApp._poll_incremental_load` can be made easier to
understand by separating event-specific transitions from work shared across a
poll tick. Preserve generation filtering, the bounded queue drain, event
ordering, and coalesced post-drain refresh behavior.

The purpose is implementation complexity reduction, not creating one handler
per event or adding a general event-policy framework. Keep a code change only
if it reduces the rules a maintainer must follow without adding result
plumbing or obscuring state transitions.

## Evidence and hypothesis

`_poll_incremental_load` drains at most
`MAX_INCREMENTAL_LOAD_EVENTS_PER_TICK`, rejects stale generations, and
processes five event kinds: `STARTED`, `SEGMENT_METADATA`, `RAW_APPEND`,
`COMPLETE`, and `FAILED`. Event-specific state changes are followed by shared
per-tick dashboard/time-display and incremental-view refresh work. The drain
bound is already a tested responsiveness invariant.

Plan 4 found one event consumer and no duplicated event policy, and rejected a
shared lifecycle-state abstraction. This plan does not reopen that decision.
The narrower hypothesis is that the current event branch logic and shared
post-drain aggregation may admit one clear responsibility boundary. It may
also be that the explicit loop is easier to understand than helper calls that
must communicate `data_changed` and `load_completed`; that result should reject
the refactor.

## Procedure

1. Trace each event branch's reads, writes, exception policy, and control flow.
   Identify which outcomes drive the two post-drain flags and which updates
   must remain coalesced once per tick.
2. Verify tests for stale generations, bounded draining, first/later append,
   completion, failure before/after the first append, and deferred refresh.
3. Sketch one alternative boundary without editing. Compare its call path and
   outcome communication with the current loop. Reject blanket per-kind
   handlers, result tuples/dataclasses, or state mutation hidden behind broad
   callback interfaces unless they demonstrably reduce reasoning.
4. If one cohesive boundary remains, make the smallest refactor. Keep
   generation filtering, the bounded drain, event order, and once-per-tick
   post-processing in the controller.
5. Run the focused app lifecycle and incremental-loader suites. Add tests only
   for a behavior gap the refactor could change.
6. Compare the behavior trace and responsibility map before/after. Retain the
   change only if the resulting code makes event transitions and shared
   post-processing easier to understand, not merely shorter.
7. Update the assessment and subsystem overview with the code decision and
   next candidate.

## Required behavior

- Process only current-generation events and preserve FIFO order.
- Drain no more than `MAX_INCREMENTAL_LOAD_EVENTS_PER_TICK` per timer tick.
- Preserve per-kind behavior for metadata, raw append, completion, and failure.
- Preserve coalesced dashboard/time display and view refresh after draining.
- Preserve cancellation, valid-prefix, and stale-event semantics.
- Do not add a new lifecycle-state owner or event abstraction by default.

## Implementation checklist

- **Status:** Complete — event-handler extraction rejected.
- **Progress:** 7/7 checklist items.
- [x] Map branch-local transitions and shared post-drain behavior.
- [x] Confirm focused test coverage for all behavior affected by a refactor.
- [x] Evaluate one boundary and reject unnecessary result plumbing before
      editing.
- [x] Make no code change because the available boundary would add result
      plumbing or hidden mutation without reducing the state transitions.
- [x] Run app lifecycle and incremental-loader tests.
- [x] Reject per-event extraction because the current single loop keeps event
      order and once-per-tick aggregation visible together.
- [x] Update the assessment and subsystem overview.

**Done when:** Event-specific transitions and shared per-tick behavior are
clearer in the implementation, or the refactor is rejected with a concrete
complexity tradeoff and no production code is changed.

## Execution record — 2026-11-11

The existing loop presents generation filtering, FIFO event order, each
event-specific transition, and the `data_changed` / `load_completed` outcomes
that drive one shared post-drain update. Extracting event handlers would need
to return and combine those outcomes or mutate controller fields through
hidden side effects. A dispatcher would add indirection without removing
duplicated policy or state; the current method is one consumer and the branches
already follow the event protocol in order. Therefore no extraction or
production change was justified.

The existing tests cover stale-generation rejection, the 64-event per-tick
bound, replacement, first and later appends, completion, failure, and refresh
behavior. Validation on macOS with Python 3.9.6: the app and incremental-loader
suites passed (**109 passed**). The bounded drain remains unchanged.
