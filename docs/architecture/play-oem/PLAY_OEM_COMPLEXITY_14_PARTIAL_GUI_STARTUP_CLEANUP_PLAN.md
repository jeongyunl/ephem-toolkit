# play-oem — Partial GUI Startup Cleanup Investigation Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Controller initialization findings:
[PLAY_OEM_COMPLEXITY_13_CONTROLLER_INITIALIZATION_SHARED_STATE_PLAN.md](./PLAY_OEM_COMPLEXITY_13_CONTROLLER_INITIALIZATION_SHARED_STATE_PLAN.md).

## Goal

Investigate cleanup when `PlayerApp` GUI construction fails after acquiring
wx resources but before `__init__` returns. Map each acquisition to its owner
and release path, inject failures at deterministic construction boundaries,
and decide whether a narrow rollback boundary is needed.

The preceding controller investigation verified that the external clock
observer is now registered only after final workspace setup. It also left
native wx cleanup after failure during frame, workspace, or control-window
construction unverified. This plan addresses that specific gap; it does not
repeat the general panel/view lifecycle audit.

## Remaining-candidate ranking

| Candidate | Current evidence | Relative decision |
| --- | --- | --- |
| Partial GUI startup failure cleanup | `PlayerApp.__init__` acquires or reuses `wx.App`, creates a frame and workspace/control-window hierarchy, and creates a timer before it returns. Normal close and `_release_wx_resources` run only after successful construction. Plan 13 could verify the late clock-subscription failure, but not native-window cleanup. | Investigate next: a failure can occur after concrete resources exist, and deterministic constructor failure injection can establish cleanup behavior without changing normal startup. |
| Raw ingestion reservation protocol | `_StoreRowSink` has one production caller; the earlier load-lifecycle trace did not find repeated independent row-sink protocols. The store and streaming tests already cover validation, cancellation, capacity, epoch replacement, and provisional-prefix behavior. | Defer: revisit only if a concrete protocol gap or second independent caller appears. |
| Load event consumption | The earlier lifecycle trace found no duplicated event consumer, and the controller's per-tick drain is already bounded. | Defer: do not repeat the load-state investigation absent a new transition mismatch. |

This re-ranking is based on the specific unverified resource boundary and
validation cost, not on constructor size. The ranking does not establish a
production defect.

## Planning baseline and initial evidence

`PlayerApp.__init__` creates or reuses `wx.App`, creates the top-level frame,
then builds the status bar, workspace, and control window. It later creates a
timer and registers the clock observer. The clock observer is now registered
after `workspace.set_oem_loaded()` and any initial status message, so those
final calls cannot leave the external clock holding a partially initialized
app.

Normal cleanup is available only after construction completes:

- `run()` calls `start()` and enters `MainLoop()`, then calls `close()` in its
  `finally` path.
- Frame-close handling stops the timer, releases observers and view resources,
  closes stores, and closes the workspace.
- `_release_wx_resources()` drops wrapper references after the run loop has
  stopped; it is not itself a constructor rollback.

There is no encompassing constructor rollback around the frame/workspace/
control-window acquisitions. If one of those constructors raises, the caller
does not receive a `PlayerApp` on which to call `close()`. The tests' fake
frame tracks `Destroy()`, and fake workspace/control components permit
deterministic failure injection, but these fakes do not prove native wx
ownership or teardown behavior.

The resource ownership question includes whether the `wx.App` was newly
created or already existed. A rollback must not tear down an app owned by
another caller. The timer is created during initialization but starts only in
`start()`; distinguish stopping/releasing an unstarted timer from a running
timer. Preserve exception transparency if cleanup itself fails.

## Resource acquisition matrix to verify

| Acquisition stage | Resource and owner | Failure question |
| --- | --- | --- |
| wx application | Reuse `wx.GetApp()` or create `wx.App(False)` | Which instance belongs to this `PlayerApp`, and what cleanup is valid for a newly created versus reused app? |
| Frame/menu/status bar | Top-level frame and child UI objects | If a later child constructor fails, is the frame destroyed and are child wrappers released? |
| Workspace | Splitters, panels, controls, redraw/scroll timers, and callback references | Does a partially constructed workspace expose a safe close path, or must rollback destroy its owning frame? |
| Control window | Settings/state controls, event bindings, and accelerators | Which references or bindings remain if control construction or content attachment fails? |
| Playback timer | wx timer attached to the frame, initially not started | Is it stopped or detached when a subsequent initialization step fails? |
| Clock observer | Bound callback retained by caller-owned clock | Confirm it is not registered before all failure-prone setup has completed; preserve the plan 13 regression. |

## Investigation procedure

1. Trace constructor operations from `wx.GetApp()` through frame, workspace,
   control-window, timer, final workspace setup, and clock subscription. Mark
   every point where an operation may raise after a resource has been acquired.
2. Trace the normal close, run-finally, and `_release_wx_resources` paths.
   Record which resources each path actually releases and whether those paths
   can run on a partially initialized object.
3. Use deterministic fakes to inject a failure at each distinct boundary:
   after frame creation, during workspace construction, during control-window
   construction/content attachment, and during final workspace setup. Assert
   the original exception propagates, previously acquired resources are
   released exactly once, and no clock observer or running timer remains.
4. Test both a newly created wx app and an already-existing app. Establish the
   ownership contract before deciding whether rollback should destroy or
   preserve the app object.
5. Distinguish resources owned by the frame hierarchy from callbacks,
   subscriptions, timers, and Python wrapper references. Do not equate dropping
   references with destroying native windows.
6. If a failure reveals a leak, add the focused regression before changing
   code. Evaluate one narrow rollback boundary that preserves the original
   exception and does not add a generic lifecycle framework. If failure
   injection finds no actionable leak, record a no-change decision.
7. Run the focused app lifecycle/startup tests. If a display is available,
   exercise one native construction failure; otherwise report that fake-widget
   results do not establish native wx teardown.
8. Update the assessment with verified cleanup behavior, any change, tests,
   limitations, and the next-ranked candidate. Update subsystem documentation
   only if resource ownership or startup transitions change.

## Required behavior and constraints

- Preserve construction of a new wx app and reuse of an existing wx app.
- Preserve the public `PlayerApp` constructor, valid startup behavior, and
  original setup exceptions.
- Cleanup must be idempotent and must not mask the original construction
  failure with a cleanup exception.
- Do not destroy an app object owned by another caller.
- Release only resources acquired by the failed construction; do not close
  unrelated views, stores, or windows.
- Keep timer, observer, workspace, and frame ownership explicit; preserve
  wx-thread requirements.
- Do not add a broad `__del__` fallback or a general resource framework solely
  to reduce constructor length.
- Keep fake-widget evidence separate from claims about native wx teardown.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 8/8 checklist items.
- [x] Map constructor acquisition and possible failure points in execution
      order.
- [x] Compare normal close/run cleanup with resources present during partial
      construction.
- [x] Verify which resources belong to a newly created versus reused wx app.
- [x] Add failure-injection tests at the distinct frame/workspace/control
      construction boundaries.
- [x] Assert exception transparency and exact-once cleanup for acquired
      resources, timer state, and clock observers.
- [x] Select one narrow rollback change if a concrete leak is reproduced, or
      record a no-change decision.
- [x] Run focused app lifecycle/startup tests and record native-display
      limitations.
- [x] Update the assessment with findings, validation, limitations, and the
      next-ranked candidate; update architecture documentation only if
      ownership or transitions change.

**Done when:** partial construction has a verified ownership and cleanup
contract for each acquired resource; tests support each reported claim; and a
production change is narrowly justified or explicitly deferred.

## Execution record — 2026-11-11

### Failure evidence and rollback behavior

Failure injection reproduced two cleanup gaps: a frame remained undestroyed
when workspace construction failed, and an initialized workspace and frame
remained open when control-window or later workspace setup failed. The
clock-observer ordering regression from plan 13 also confirmed that failure
during final workspace setup happens before subscription.

`PlayerApp.__init__` now delegates GUI construction to
`_initialize_wx_ui()` inside a rollback boundary. If construction raises, the
rollback unsubscribes an acquired clock observer, stops an acquired timer,
closes a fully constructed workspace, and destroys the acquired frame, in that
order. It attempts each cleanup independently, logs cleanup exceptions, and
re-raises the original construction exception. It intentionally preserves
`wx.App` whether that app was created during this construction or reused from
the process; both cases are covered by failure-injection tests.

Tests inject failures during workspace construction, control-window
construction, control-content attachment, and final workspace setup. They
verify exception transparency, frame/workspace cleanup, one timer stop, no
early clock subscription, preserved new/reused wx apps, and continued frame
cleanup when workspace close itself raises. A workspace whose constructor
raises is not assigned to `PlayerApp`, so rollback relies on destroying its
owning frame rather than calling `close()` on an incomplete object.

### Validation and limitations

The app, CLI, and control-window regression suites passed: **125 passed**.
The fakes establish the Python-level cleanup calls and their order; they do not
establish native wx ownership/destruction behavior. No native desktop failure
injection was available. No dataflow or subsystem ownership changed. The
subsystem overview now records the separate partial-startup rollback boundary.

Plan 14 is complete. Native wx teardown remains a limitation rather than a
verified claim. No further implementation candidate is selected here;
re-rank the remaining assessment leads before starting another plan.
