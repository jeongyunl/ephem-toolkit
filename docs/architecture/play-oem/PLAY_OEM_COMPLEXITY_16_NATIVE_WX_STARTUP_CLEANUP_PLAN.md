# play-oem — Native wx Startup Cleanup Verification Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Partial-startup rollback implementation and fake-widget evidence:
[PLAY_OEM_COMPLEXITY_14_PARTIAL_GUI_STARTUP_CLEANUP_PLAN.md](./PLAY_OEM_COMPLEXITY_14_PARTIAL_GUI_STARTUP_CLEANUP_PLAN.md).
Latest store-backed view result-state comparison:
[PLAY_OEM_COMPLEXITY_15_STORE_VIEW_RESULT_STATE_PLAN.md](./PLAY_OEM_COMPLEXITY_15_STORE_VIEW_RESULT_STATE_PLAN.md).

## Goal

Determine whether the constructor rollback verified with wx fakes also behaves
correctly with real wx windows and timers under a supported display server.
Establish a repeatable, bounded native integration check for one failure after
the frame, workspace, control window, and playback timer have been acquired.

This plan does not propose another rollback implementation. Change production
code only if a real wx run reveals behavior that differs from the already
tested Python-level cleanup contract. If a display-backed environment is not
available, record the exact blocker and retain the current limitation rather
than treating fake-widget tests as native proof.

## Remaining-candidate ranking

| Candidate | Current evidence | Relative decision |
| --- | --- | --- |
| Native wx partial-startup cleanup | Plan 14 added independent cleanup and failure-injection tests, but all use fakes. Existing display-dependent test fixtures skip without a usable wx display. | Investigate next: native child-window ownership and `Destroy()` behavior are the one unresolved runtime claim in the completed startup rollback work. |
| Raw ingestion reservation protocol | The load-lifecycle trace already mapped reservation, commit, observer failure, epoch replacement, cancellation, and late parse failure. `_StoreRowSink` has one production caller. | Defer: no concrete protocol gap or second independent caller has emerged. |
| Load event consumption | The load-lifecycle plan mapped event transitions and stale-generation handling; event draining is bounded per tick. | Defer: no duplicated consumer or transition mismatch is established. |
| Store-backed result-state interpretation | Plan 15 found view-specific status and rendering rules and added focused state tests; no common production classifier was justified. | Complete for the current candidate set; reopen only with a specific inconsistency. |

This order prioritizes closing an explicit validation limitation, not expanding
the startup rollback scope or claiming cross-platform native behavior from one
environment.

## Planning baseline and initial evidence

`PlayerApp.__init__` creates or reuses a process-level `wx.App`, then constructs
the frame, workspace, control window, and playback timer before final workspace
setup. On a constructor exception, `_rollback_partial_wx_initialization()`
stops an acquired timer, closes a completed workspace, destroys an acquired
frame, and preserves the original exception; it does not destroy `wx.App`.

The fake-widget tests exercise failures during workspace construction,
control-window construction, control-content attachment, and final workspace
setup. They verify cleanup calls, order, exception transparency, and app
preservation. They cannot establish how native wx handles child windows,
deferred deletion, `CallLater` timers, or frame destruction.

Existing GUI tests check `wx.App.IsDisplayAvailable()` and skip when no display
is present; their skip messages suggest `xvfb-run` for X-display tests. The
latest focused view run had three display-dependent skips. Whether this
workspace or its CI provides a usable native wx display must be confirmed
before adding a non-skipped integration test.

## Native resource and failure boundary

| Acquired resource | Rollback responsibility | Native fact to establish |
| --- | --- | --- |
| Existing or new `wx.App` | Preserve it after failed `PlayerApp` construction. | It remains the active wx application and is not destroyed or replaced. |
| Frame and child widget tree | Call `Destroy()` on the acquired frame. | Native children are disposed through the frame hierarchy without an unsafe second destruction path. |
| Completed workspace | Call `Workspace.close()` before frame destruction. | Workspace-owned deferred callbacks/timers can be stopped safely during rollback. |
| Playback timer | Stop the timer if it was acquired. | Stopping the unstarted timer is safe; no callback fires after the frame is destroyed. |
| Clock observer | Unsubscribe if acquired. | The caller-owned clock no longer retains the failed app callback when subscription has occurred. |

The preferred deterministic failure point is final workspace setup after the
real workspace, control window, and timer have been created but before clock
subscription. This exercises the broadest acquired-resource set without
deliberately corrupting a real wx widget constructor. A second failure point
during child construction is optional and should be added only if the
display-backed harness can trigger it safely and deterministically.

## Investigation procedure

1. Inspect the existing wx fixtures and test commands to determine whether a
   real display, `xvfb-run`, or a supported CI display job is available.
   Record wx version, platform/backend, and the exact command used.
2. Verify the supported native wx API for observing frame destruction and
   deferred child cleanup. Do not rely on fake-only attributes or assume that
   dropping a Python wrapper proves native destruction.
3. Add a display-gated integration test using a real `wx.App` and real frame,
   workspace, control window, and timer. Inject an exception at the selected
   final-setup boundary and assert the original exception propagates.
4. Verify the frame destruction request and native deletion state using the
   supported wx mechanism; pump only the events required by that mechanism.
   Confirm the existing `wx.App` remains usable and no post-destruction timer
   callback fires.
5. Instrument workspace close and clock subscription/unsubscription only as
   needed to establish call order; do not replace the real frame/workspace
   teardown with fakes in the native test.
6. Run the new test with a display and run its ordinary headless form to verify
   that display absence is reported as a skip, not a false pass. Keep the
   existing fake-widget tests as fast deterministic coverage.
7. Change production cleanup only if native execution reproduces a concrete
   defect. Any fix must keep cleanup independent, preserve the original error,
   and respect wx-thread requirements.
8. Update this plan, the assessment, and subsystem documentation with the
   platform-tested claim and remaining limitations. If no display-capable
   environment is available, mark the native validation blocked and do not
   report the resource boundary as verified.

## Required behavior and constraints

- Preserve the process-level `wx.App`, whether it pre-existed or was created
  for the failed constructor.
- Preserve the original construction exception and attempt remaining cleanup
  after an individual cleanup failure.
- Destroy only the frame acquired by this failed `PlayerApp`; do not tear down
  unrelated windows or stores.
- Stop timers and close completed workspace resources before destroying the
  frame, on the wx-owning thread.
- Use a deterministic failure point and avoid timing-based sleeps or
  assertions about implementation-private wx internals.
- Keep claims limited to the tested platform/backend; one native run does not
  establish behavior on all supported operating systems.
- Do not add CI display infrastructure or dependencies unless the feasibility
  review shows it is necessary and the change is separately justified.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 8/8 checklist items.
- [x] Identify a supported real-display or virtual-display execution path.
- [x] Verify the wx API used to observe native frame/child deletion.
- [x] Select a deterministic failure after native GUI resources are acquired.
- [x] Add a display-gated integration test using real wx resources.
- [x] Verify app preservation, original exception, frame cleanup, workspace
      close, and timer behavior.
- [x] Run the display-backed test; verify the headless skip guard and record
      that a display-free wx runtime was unavailable.
- [x] Make a narrow production fix only if native execution reproduces a bug.
- [x] Update the assessment and subsystem record with evidence, tested
      platform, limitations, and the next-ranked candidate.

**Done when:** one supported native wx environment verifies the partial-startup
cleanup behavior, or a specific environment blocker and unverified boundary
are recorded without overstating fake-widget evidence.

## Execution record — 2026-11-11

### Native display and deletion evidence

The workspace is macOS with wxPython **4.2.4**, wxWidgets **3.2.8**, and the
`osx-cocoa` backend. `DISPLAY` is unset and `xvfb-run` is not installed, but
`wx.App.IsDisplayAvailable()` returned `True`; a real Cocoa frame could be
created, so native validation was feasible without Xvfb.

The integration test injects a failure in `Workspace.set_oem_loaded()` after
the real frame, workspace, control window, and playback timer exist. The test
observes the real frame through `wx.GetTopLevelWindows()`, pumps wx events with
`wx.YieldIfNeeded()`, and verifies that the frame leaves the top-level window
list and its wrapper rejects further native access. This establishes native
frame deletion on this tested backend rather than inferring it from a fake's
`Destroy()` flag.

The same test confirms the original setup exception propagates, the existing
wx app remains `wx.App.Get()`, the actual timer is not running, the clock has
not yet been subscribed, and the real workspace close path ran and cleared
its pending graph timers. The test uses real wx resources; only the failure
point and resource-construction capture are instrumented. No native cleanup
failure was reproduced, so no production change was needed.

### Validation and limitations

The native integration test passed on macOS Cocoa. The complete app lifecycle
suite, including the native test, passed: **97 passed**. A display-free wx
runtime was not available, so the new test's skip branch was reviewed but not
executed in a separate headless environment. The test is display-gated like
the existing GUI tests. This run does not establish behavior on GTK, MSW, or
other wxPython versions.

Plan 16 is complete for the available platform. The macOS Cocoa rollback
boundary is now verified; cross-platform native teardown remains unverified.
Raw-ingestion reservation and load-event-consumption leads remain deferred
absent new evidence. No next implementation candidate is selected; re-rank
remaining candidates before defining another plan.
