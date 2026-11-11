# play-oem — Active Incremental Load Shutdown Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Incremental loading implementation:
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md).
Deferred cross-platform wx pilot:
[PLAY_OEM_COMPLEXITY_19_HOSTED_WX_TEST_PILOT_PLAN.md](./PLAY_OEM_COMPLEXITY_19_HOSTED_WX_TEST_PILOT_PLAN.md).

## Goal

Use the available macOS environment to verify the app shutdown boundary while
an incremental OEM load is active. Trace how `PlayerApp` closes the loader,
stops timers, releases observers and views, and handles any already-queued
events. Determine whether existing tests establish that shutdown is
deterministic and that late loader activity cannot mutate a closed app.

This is a bounded behavioral audit, not a loader redesign. Add a regression
test or production fix only if an observable gap is found.

## Why this step

Plans 17–19 leave native GTK/Linux and MSW/Windows verification deferred because
the current environment is macOS-only. Rather than repeat that blocked
investigation, this plan returns to a locally testable Play-OEM lifecycle
invariant. The assessment identifies shutdown as a required invariant of the
load lifecycle, but prior summaries do not establish whether the interaction
between active loading and app teardown has a focused end-to-end assertion.

## Investigation procedure

1. Trace the app close path, incremental loader cancellation/close behavior,
   timer stop, observer cleanup, and queued-event handling. Identify the
   owning thread for each operation.
2. Search existing tests for closing the app during an active load, loader
   completion/cancellation races, and events delivered after shutdown. Reuse
   established fakes and deterministic synchronization; do not add sleeps.
3. If current tests cover the invariant, record the exact evidence and do not
   add duplicate tests.
4. If coverage is missing, add the narrowest regression test proving that
   closing during a load cancels or closes the loader, stops polling, releases
   app-owned observers/resources, and does not apply late events to closed UI.
5. If the test exposes a production defect, correct the lifecycle owner while
   preserving valid-prefix handling, generation rejection, and the original
   close behavior.
6. Run focused incremental-loader and app lifecycle tests on macOS. Report
   platform and test results explicitly; this does not change GTK/MSW status.
7. Update this plan, assessment, and subsystem overview with findings and the
   next candidate.

## Required behavior and constraints

- Keep loader work off the wx thread and wx-owned cleanup on the wx thread.
- Preserve cancellation, generation isolation, and ignored late events.
- Preserve process-level `wx.App` ownership and existing window cleanup.
- Use deterministic synchronization and narrow failure/race injection.
- Make no claims about GTK/Linux or MSW/Windows.

## Implementation checklist

- **Status:** Complete — existing deterministic coverage is sufficient.
- **Progress:** 7/7 checklist items.
- [x] Trace active-load shutdown across app, loader, timers, observers, and
      queued events.
- [x] Identify existing test coverage; no uncovered invariant was found.
- [x] Reuse the existing regression rather than add duplicate coverage.
- [x] Make no production change because no defect was reproduced.
- [x] Run the incremental-loader suite and focused app shutdown regression on
      macOS: 11 passed.
- [x] Preserve the deferred GTK/MSW status in all reporting.
- [x] Update the assessment, subsystem overview, and this plan.

**Done when:** Existing coverage is evidenced or a concrete missing invariant
is covered by a deterministic passing test; any production change is justified
by a reproduced defect.

## Execution record — 2026-11-11

The existing
`test_closing_while_oem_parse_is_blocked_cancels_without_waiting` deterministically
blocks the parser, closes the app, and verifies that the load session is
cancelled, the store is marked cancelled and its scheduler closed, and no
sample is appended after the parser is released. The close handler also
cancels the loader, stops the wx timer, unsubscribes app observers, closes
stores, and drops view/store contexts. Existing coverage was sufficient, so no
test or production code change was warranted.

Validation on macOS with Python 3.9.6: `test_incremental_loader.py` plus the
focused app shutdown test passed (**11 passed**). GTK/Linux and MSW/Windows
remain deferred and unverified.
