# play-oem — Terminal Load-Event Cleanup Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior event-routing decision:
[PLAY_OEM_COMPLEXITY_26_INCREMENTAL_EVENT_ROUTING_PLAN.md](./PLAY_OEM_COMPLEXITY_26_INCREMENTAL_EVENT_ROUTING_PLAN.md).
Load transition contract:
[PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md).

## Goal

Evaluate one narrow repeated action in `PlayerApp._poll_incremental_load`:
both `COMPLETE` and `FAILED` events stop an active range drag. Determine whether
that terminal-event cleanup can be expressed once without extracting event
handlers or changing event ordering.

Plan 26 rejected per-event handler extraction because it would add outcome
plumbing and obscure FIFO transitions. This plan does not reopen that
conclusion.

## Baseline and hypothesis

At source revision `c422b94c7ec3b938ff104e16fe5e35d8672e863d`,
`_poll_incremental_load` is 128 lines with a decision score of 32 under the
assessment's AST indicator. It already preserves the bounded queue drain,
generation filtering, per-kind transitions, and coalesced post-drain refresh.

**Hypothesis:** moving only the identical range-drag reset to a shared
terminal-event point may remove duplicated cleanup while keeping event-specific
state transitions visible. Reject it if a shared condition obscures which
events are terminal or changes the exact point at which drag state is cleared.

## Scope and constraints

- Limit consideration to range-drag cleanup for `COMPLETE` and `FAILED`.
- Preserve FIFO processing, generation checks, the per-tick drain bound,
  valid-prefix behavior, and post-drain dashboard/view refresh.
- Preserve completion and failure status messages, store closure, playback
  pause, metadata handling, and refresh behavior.
- Do not extract event handlers, add a dispatcher/result type, or alter other
  event branches.

## Procedure

1. Trace both terminal branches and confirm that the drag reset has identical
   preconditions, timing, and effects.
2. Verify or add focused coverage that active range dragging is cleared on
   both completion and failure, while nonterminal events leave it unchanged.
3. Compare the minimal common-cleanup expression with the existing two
   branches; reject it if it introduces a new flag or less-visible control
   flow.
4. If the change is clearer, implement only this deduplication.
5. Run the focused app lifecycle and incremental-loader suites, including
   bounded draining, stale-generation, completion, failure, and range-drag
   cases.
6. Update the assessment and subsystem record with the decision and results.

## Done when

Terminal drag cleanup is either expressed once with unchanged observable
timing and behavior, or retained in both branches because the shared form
would make event handling less clear. No broader event-routing refactor is
included.

**Status:** Complete; terminal cleanup deduplicated.

## Outcome

The `STARTED`, `SEGMENT_METADATA`, and `RAW_APPEND` branches continue before
reaching the terminal-event cleanup. `COMPLETE` and `FAILED` each perform
their distinct state transitions first, then apply the same conditional drag
reset. The shared condition now names both terminal kinds and clears dragging
at the same point as before:

```python
if (
    event.kind in (LoadEventKind.COMPLETE, LoadEventKind.FAILED)
    and self._range_dragging
):
    self._set_range_dragging(False)
```

No event handlers, result flags, or other event policy were extracted. Added
parameterized coverage confirms `STARTED` leaves dragging active while both
`COMPLETE` and `FAILED` clear it. Existing tests continue to cover stale
generations, bounded draining, append and completion behavior, failure, and
deferred refresh.

Validation:

```sh
python3 -m pytest \
  tests/ephem_toolkit/play_oem/test_play_oem_app.py \
  tests/ephem_toolkit/play_oem/test_incremental_loader.py
```

Result: 113 passed, no platform-dependent skips, and 14 third-party
Matplotlib/Pyparsing deprecation warnings. The common reset preserves the
event-specific ordering and post-drain refresh behavior.
