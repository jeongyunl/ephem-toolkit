# play-oem — Native wx Active-Load Shutdown Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Python-level active-load shutdown result:
[PLAY_OEM_COMPLEXITY_20_ACTIVE_LOAD_SHUTDOWN_PLAN.md](./PLAY_OEM_COMPLEXITY_20_ACTIVE_LOAD_SHUTDOWN_PLAN.md).
Native wx startup cleanup evidence:
[PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md](./PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md).
Deferred cross-platform runner pilot:
[PLAY_OEM_COMPLEXITY_19_HOSTED_WX_TEST_PILOT_PLAN.md](./PLAY_OEM_COMPLEXITY_19_HOSTED_WX_TEST_PILOT_PLAN.md).

## Goal

Determine whether active-load shutdown preserves the verified cleanup
invariants when exercised with real wx frame, workspace, controls, and timer
resources on macOS Cocoa. Plan 20 established Python-level behavior using the
app test doubles; plan 16 established real-wx behavior for partial
initialization failure. This plan checks their intersection without implying
GTK/Linux or MSW/Windows coverage.

## Why this step

The current macOS environment can test native wx resources, while non-macOS
runner access is deferred. The real-wx test from plan 16 does not close an app
with a load in flight, and the blocked-parser test from plan 20 uses
`make_app`-provided test doubles. A native integration test can close that
specific evidence gap while remaining deterministic and backend-scoped.

## Investigation procedure

1. Inspect the existing display-gated native startup test and the
   blocked-parser shutdown regression. Reuse their real-resource setup and
   event synchronization where practical; do not duplicate setup abstractions
   without a clear need.
2. Verify the current wx backend and display availability. If native display
   support is unavailable, record a skip/block and do not claim native
   shutdown coverage.
3. If feasible, add a focused display-gated test that starts a real
   `PlayerApp`, blocks the loader at a deterministic parser boundary, then
   closes the primary frame while the worker is active.
4. Assert the real app's timer is stopped, the session is cancelled without
   blocking close, the workspace and acquired native frame are destroyed,
   process-level `wx.App` is preserved, and releasing the parser produces no
   late store append or UI mutation.
5. Always release the parser in `finally` and wait for worker completion;
   avoid timing sleeps and ensure failed assertions cannot leak a worker or
   wx resource.
6. Make a production change only if the real-wx run reproduces a cleanup
   defect not covered by the Python-level test. Otherwise retain the current
   implementation.
7. Run the new native test and focused app lifecycle suite on macOS. Record
   wxPython/wxWidgets versions and distinguish skip from pass.
8. Update this plan, the assessment, and subsystem overview. Keep GTK/MSW
   explicitly deferred.

## Required behavior and constraints

- Keep parser work on the loader thread and all wx operations on the wx thread.
- Preserve cancellation, no-wait close behavior, store epoch invalidation,
  and rejection of late app events.
- Preserve existing app/frame ownership and partial-startup cleanup behavior.
- Use deterministic event synchronization; do not rely on arbitrary sleeps.
- Gate native UI execution on actual display availability.
- Claim results only for the tested macOS Cocoa and wxPython/wxWidgets versions.

## Implementation checklist

- **Status:** Complete — native macOS active-load shutdown verified.
- **Progress:** 8/8 checklist items.
- [x] Inspect and reuse the native startup and Python-level shutdown test
      patterns.
- [x] Verify native backend/display availability.
- [x] Add a real-wx active-load shutdown regression only after confirming the
      setup is safe and
      deterministic.
- [x] Assert timer, session, store, workspace, app, frame, and late-event
      outcomes.
- [x] Make no production change because no defect was reproduced.
- [x] Run the native integration test and full app lifecycle suite on macOS.
- [x] Record exact versions and pass/skip/block status; retain GTK/MSW deferral.
- [x] Update the assessment, subsystem overview, and this plan.

**Done when:** Native active-load shutdown is verified with deterministic
real-wx resources on the available macOS backend, or an exact display/runtime
blocker is documented. No other backend is implied.

## Execution record — 2026-11-11

The native test blocks OEM parsing on the loader thread, closes the real app,
and verifies that close returns with the session cancelled, wx timer stopped,
store cancelled and scheduler closed, workspace closed, process-level
`wx.App` preserved, and no queued loader events available to the closed app.
After releasing the parser it waits for worker completion and verifies that no
sample was appended and the real frame is gone from wx's top-level windows.
Cleanup releases the parser and destroys any remaining test-owned frame even
when an assertion fails.

The display-gated native integration test passed, and the complete app
lifecycle suite passed (**98 passed**). Environment: macOS Cocoa, wxPython
4.2.4, wxWidgets 3.2.8. No production fix was indicated. GTK/Linux and
MSW/Windows remain deferred and unverified.
