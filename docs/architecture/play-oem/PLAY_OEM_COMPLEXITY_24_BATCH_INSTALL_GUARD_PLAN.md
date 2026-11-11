# play-oem — Incremental Batch-Install Guard Complexity Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and candidate priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Load lifecycle contract:
[PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md).
Previous snapshot-installation reduction:
[PLAY_OEM_COMPLEXITY_23_SNAPSHOT_INSTALLATION_DEDUPLICATION_PLAN.md](./PLAY_OEM_COMPLEXITY_23_SNAPSHOT_INSTALLATION_DEDUPLICATION_PLAN.md).

## Goal

Evaluate whether repeated manual toggling of
`_installing_incremental_batch` can be replaced by one scoped operation that
makes the re-entrant clock-notification suppression rule easier to understand
and harder to leave in the wrong state.

The goal is to reduce implementation complexity. A context manager or helper
is warranted only if it removes repeated lifecycle protocol without adding
more indirection than the three current call sites require.

## Evidence and hypothesis

`PlayerApp._install_store_snapshot` sets `_installing_incremental_batch` to
`True`, performs a clock/cursor operation, and resets it in `finally` at three
sites: applying pending playback bounds, extending coverage and refreshing the
cursor, and seeking to the pending start. These operations can trigger clock
observers; the flag suppresses incidental range/view refresh behavior during
the atomic snapshot-install step.

**Hypothesis:** a small scoped guard can express this repeated temporal
protocol once, restore the previous flag value even under nesting, and reduce
the number of places that must be checked for exception-safe reset. Reject the
change if a context manager obscures the operation boundary, nesting is
impossible and the helper adds more concepts than it removes, or tests cannot
show the intended notification behavior.

## Procedure

1. Trace `_on_clock_time_changed` and each guarded operation to verify exactly
   which synchronous observer callbacks depend on the flag.
2. Search other uses of `_installing_incremental_batch` and existing
   context-manager conventions before adding a new helper.
3. Confirm tests cover observer suppression during install and restoration
   after a raised clock/cursor operation. Add only missing focused coverage.
4. Prototype the smallest scoped helper, preferably saving and restoring the
   prior flag value. Keep the clock operation itself visible at each call site.
5. Compare the call paths and maintained protocol before and after. Keep the
   change only if one guard owns the set/restore invariant and the call sites
   become easier to scan without hiding behavior.
6. Run the app lifecycle and clock/range suites. Record exact outcomes.
7. Update the assessment and subsystem overview with the decision and next
   evidence-backed candidate.

## Required behavior

- Clock observers must continue to see the installing flag while the guarded
  operation can synchronously notify them.
- The previous flag state must be restored even if the operation raises.
- No extra event loop turn, timer delay, or asynchronous wrapper may be added.
- Preserve first-append versus later-append behavior and pending-bound logic.
- Avoid a generic transaction framework or a new state owner.

## Implementation checklist

- **Status:** Complete — repeated flag protocol consolidated.
- **Progress:** 7/7 checklist items.
- [x] Trace observer callbacks and all flag read/write sites.
- [x] Confirm repository context-manager conventions and test coverage.
- [x] Implement a scoped guard to own set/restore protocol.
- [x] Add targeted exception/restoration coverage.
- [x] Run app lifecycle and clock/range suites.
- [x] Keep the experiment based on reduced local reasoning, not
      abstraction novelty or line count.
- [x] Update the assessment and subsystem overview with the outcome.

**Done when:** Either one exception-safe scope owns the batch-install flag
protocol with no behavior change, or the helper is rejected with a concrete
complexity tradeoff.

## Execution record — 2026-11-11

Added `_installing_incremental_update`, a context manager that saves the
previous flag value, sets the flag for the scope, and restores the previous
value in `finally`. The three clock/cursor operations now use the same
exception-safe scope; the operations remain inline at their existing call
sites. A focused test verifies restoration after an exception and preservation
of an already-true outer state. Direct flag writes are now limited to
initialization and the context manager.

The app lifecycle, clock, and time-range suites passed (**163 passed**) on
macOS with Python 3.9.6. No GUI behavior or cross-platform claim changed. The
change removes repeated set/reset bookkeeping while retaining visible
operation boundaries.
