# play-oem — Snapshot Installation Complexity Reduction Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and candidate priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Load lifecycle contract:
[PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md).
Latest shutdown evidence:
[PLAY_OEM_COMPLEXITY_21_NATIVE_WX_ACTIVE_LOAD_SHUTDOWN_PLAN.md](./PLAY_OEM_COMPLEXITY_21_NATIVE_WX_ACTIVE_LOAD_SHUTDOWN_PLAN.md).

## Goal

Reduce local reasoning and maintenance cost in
`PlayerApp._install_store_snapshot` by evaluating the repeated pending
playback-bounds decision made during first and subsequent snapshot
installations. Preserve existing behavior for replacement loads, partial
coverage, fixed/follow-coverage bounds, cursor anchoring, and playback state.

This plan is explicitly directed at implementation complexity reduction.
Tests and documentation support the code experiment; they are not the outcome.

## Evidence and hypothesis

Static inspection of `controller.py` shows the same two-way decision over
`_pending_playback_bounds` in both the first-append and later-append branches:

- If the requested bounds are now fully covered, clear the pending bounds,
  update `_playback_handle_bounds`, clear the loading cursor anchor, and install
  the bounds while `_installing_incremental_batch` is true.
- Otherwise, if the requested start is covered and differs from the current
  time, seek to it under the same batch-install guard and clear the anchor.

The later-append branch has one additional behavior when no bounds are pending
and playback bounds are not fixed during loading. That behavior is not part of
the duplicated decision and must remain distinct.

**Hypothesis:** extracting only the identical pending-bounds operation into a
small private helper will remove duplicated policy and make first/later
snapshot handling easier to compare, without adding a lifecycle abstraction or
changing ownership. Reject the extraction if the helper needs flags or
callbacks to represent materially different behavior, or if it merely relocates
the same branching and makes the call path harder to follow.

## Procedure

1. Recheck the two branches in `_install_store_snapshot` and list the exact
   state read/written by each, including `_pending_playback_bounds`,
   `_playback_handle_bounds`, `_loading_cursor_anchor_s`, clock time, and
   `_installing_incremental_batch`.
2. Locate tests for initial append, later append, saved/fixed playback bounds,
   and range extension. Add focused tests only for any missing behavior that
   the refactor could alter.
3. Extract the common pending-bounds decision only if it can be expressed
   without a mode flag, callback protocol, or broader state owner. Keep the
   later-only follow-coverage update separate.
4. Compare the before/after code and call path. The result should have one
   source for pending-bounds policy and fewer repeated decision branches, not
   simply move them into a new module.
5. Run the app lifecycle and relevant clock/range tests. Record exact results.
6. Revert the extraction if it increases indirection or obscures the first
   append versus later append distinction. Keep only a change that measurably
   improves local reasoning while preserving the full behavior contract.
7. Update the assessment and subsystem overview with the code decision and
   next candidate.

## Required behavior

- Preserve deferred application of saved playback bounds until coverage
  contains them.
- Preserve seek-to-start behavior when only the requested start is covered.
- Preserve `_installing_incremental_batch` cleanup via `finally`.
- Preserve loading cursor anchoring for out-of-coverage saved starts.
- Preserve later-append follow-coverage updates when no pending bounds exist.
- Do not alter replacement, cursor refresh, or store ownership semantics.

## Implementation checklist

- **Status:** Complete — repeated pending-bounds policy consolidated.
- **Progress:** 7/7 checklist items.
- [x] Map reads, writes, and behavior in both pending-bounds branches.
- [x] Confirm focused test coverage for initial and later appends and playback
      bound modes.
- [x] Extract the duplicate policy without a mode flag or callback.
- [x] Preserve the later-only follow-coverage branch.
- [x] Run focused app lifecycle and clock/range validation.
- [x] Keep the change because one implementation now owns the shared decision;
      the initial-only cursor anchor and later-only follow-coverage behavior
      remain visible at their call sites.
- [x] Update the assessment and subsystem overview with the outcome.

**Done when:** There is one clear implementation of pending playback-bounds
application, or the extraction is rejected with a concrete reason showing that
the apparent duplication encodes different behavior.

## Execution record — 2026-11-11

The identical covered-bounds and covered-start decisions are now handled by
`_apply_pending_playback_bounds`. The first-append path still establishes the
loading cursor anchor before applying the pending bounds, and the later-append
path still owns its separate no-pending/follow-coverage update. The helper has
no mode argument or callback protocol; it centralizes the duplicated
decision without merging the distinct first/later append responsibilities.

Existing app tests cover pending saved ranges through initial and later
appends, including delayed coverage and eventual application of the playback
range. No additional test was needed. Validation on macOS with Python 3.9.6:
the app, clock, and time-range suites passed (**162 passed**). The bounded
change removes duplicate decision logic while retaining a named call at each
append boundary; no platform or performance claim is made.
