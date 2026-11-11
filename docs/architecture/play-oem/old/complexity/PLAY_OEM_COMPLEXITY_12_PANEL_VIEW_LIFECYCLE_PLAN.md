# play-oem — Panel and View Lifecycle Investigation Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
View refresh findings:
[PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md](./PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md).
Recent large-view findings:
[PLAY_OEM_COMPLEXITY_11_LARGE_GUI_VIEW_RESPONSIBILITIES_PLAN.md](./PLAY_OEM_COMPLEXITY_11_LARGE_GUI_VIEW_RESPONSIBILITIES_PLAN.md).

## Goal

Execute the next selected assessment candidate, **Panel and view lifecycle**.
Trace panel/view construction, successful replacement, failure rollback,
normal disposal, store-binding cleanup, and backend-specific resource release.
Determine whether lifecycle policy is duplicated and whether a shared boundary
would reduce total coordination without hiding view-specific obligations.

The earlier view-refresh investigation explicitly deferred panel
construction/rollback and full lifecycle design. Do not repeat its
notification-routing or refresh-coalescing analysis except where it affects
whether a view is current, replaced, or disposed.

## Remaining-candidate ranking

The assessment candidates not yet completed are:

| Candidate | Current evidence | Relative decision |
| --- | --- | --- |
| Panel and view lifecycle | `_open_view` is transactional across graph-panel insertion, view construction, Matplotlib/native content setup, and rollback. Close paths release canvas callbacks, view resources, store subscriptions, and panels. Existing tests exercise failure restoration, independent duplicate instances, close, and VTK cleanup. | Investigate next: failures here can leave stale panels, callbacks, subscriptions, or native resources; the contracts and regression cases are concrete and testable. |
| Controller initialization and shared state | `PlayerApp.__init__` initializes loading, playback, config, and GUI state used by several mixins. The assessment identifies broad responsibility but no current state inconsistency or specific failing caller protocol. | Defer: broader scope and less direct behavior evidence; reconsider after lifecycle ownership is mapped. |

This re-ranking is based on consequence, evidence, and validation cost, not
source size. Do not infer a production defect from the number of cleanup
operations or their placement.

## Planning baseline and initial evidence

At planning time, the worktree is clean at commit
`18c67ab01fae515eb3656c2f98eff0c18c03559d`.

### Panel creation, replacement, and rollback

`PanelManagementMixin._open_view` chooses or creates a stable panel ID, builds
a `GraphPanelHost`, inserts or replaces the workspace panel, constructs the
view, builds legacy or store-backed content, applies range/time state, and
attaches either a Matplotlib canvas/toolbar or native wx content. It then
registers `_OpenView` state and publishes range hints. A failure during setup
disconnects an installed Matplotlib callback, unsubscribes, closes the view,
restores or removes the panel, destroys the attempted panel, and re-raises.
When replacement succeeds, the previous view's resources are released only
after the new `_OpenView` is installed.

### Normal disposal and resource owners

`_dispose_open_view` removes the panel record, calls
`_release_open_view_resources`, removes the panel from the workspace, and
destroys it in nested `finally` blocks. `_release_open_view_resources` removes
the default-view mapping, disconnects Matplotlib click callbacks, invokes the
clock-unsubscribe callback, and calls the view's required `close()` method.
The `View` protocol provides a common `close()` contract, while optional
`StoreView` behavior is separate.

`StoreViewBinding` owns tier-interest subscriptions and its current
`StoreViewContext`; `close()` unsubscribes and clears both. Views retain
additional resource duties: history views close time-range listeners and clear
figures/artists; station views unsubscribe from shared selection state as well
as closing store bindings; Ground Track clears its binding and artist/context
references; VTK finalizes its render window, disables and detaches the
interactor, removes the renderer, and clears scene references.

These are distinct resource types under a shared view-close protocol. The
failure path and normal disposal both contain callback/unsubscribe/view cleanup
operations, but their construction stage and rollback order differ. Whether
this is safe shared policy or intentional transaction-specific cleanup must be
verified before extracting a helper.

## Lifecycle matrix to verify

| Phase | Panel/controller responsibility | View/backend responsibility | Initial evidence |
| --- | --- | --- | --- |
| Create | Choose stable identity and stack; insert panel; keep old panel available during replacement | Construct and build; bind store context where available | `panel_management.py`, `test_play_oem_app.py` |
| Attach | Create Matplotlib canvas/toolbar/click callback or attach native wx content; validate VTK context | Return a supported content type and own view resources | App lifecycle tests, `test_vtk_trajectory3d.py` |
| Setup failure | Disconnect partial callbacks, close partial view, restore/remove panel, destroy attempted panel, preserve original error | Release any resources acquired before failure | `test_failed_view_change_restores_the_original_panel` |
| Replace success | Register new record before releasing old resources; preserve panel identity and user-selected height | Close old view and release backend resources | Panel replacement tests |
| Normal close | Remove registry/clock dispatch state, detach panel, destroy wx host | Unsubscribe store/selection state and release artists or native resources | Close, duplicate-instance, view and VTK tests |

Verify actual operation order and failure injection points. Do not equate
`view.close()` with full cleanup: controller-owned callbacks, canvases, toolbars,
store bindings, selection subscriptions, panels, and native render windows have
different owners.

## Investigation procedure

1. Trace `_open_view` from panel identity selection through content creation,
   `_OpenView` registration, replacement commit, and range-hint publication.
   Record which resources exist at every point where an operation can fail.
2. Trace the setup exception path and compare it with normal replacement and
   `_dispose_open_view`. Record rollback order, ownership, idempotency
   assumptions, and whether the original panel remains usable.
3. Compare one history view, Ground Track, one station view, and VTK for
   build/store-bind/close ownership. Distinguish resources released by
   `PanelManagementMixin`, `StoreViewBinding`, each view, and the native wx
   host.
4. Map existing tests to those transitions. Identify only concrete untested
   failure points, such as partial content attachment or cleanup after a
   callback has been registered. Keep display-dependent behavior separate
   from fake-widget tests.
5. Rank any repeated cleanup policy against differences in construction stage
   and rollback semantics. Select at most one bounded change only if it removes
   duplicated obligations without weakening rollback or obscuring resource
   ownership. A documented no-change decision is valid.
6. If justified, add deterministic failure-injection tests before changing
   code. Verify that replacement rollback preserves the old panel, successful
   replacement closes it exactly once, and normal close releases each
   controller- and view-owned resource exactly once.
7. Run focused panel lifecycle, representative view-close, store-binding, and
   VTK cleanup tests. Record skipped native GUI cases and any optional
   dependency constraints.
8. Update the assessment with the verified transition map, decision,
   validation, limitations, and the re-ranked next candidate. Update dataflow
   or subsystem design only if verified runtime ownership changes.

## Required behavior and constraints

- Preserve default-view uniqueness, independent duplicated panel instances,
  stable panel IDs, stack placement, and selected-panel behavior.
- Preserve transactional replacement: the previous panel remains usable when
  construction or attachment of its replacement fails.
- Preserve exception transparency; rollback must not turn a failed open into
  a success-shaped result or mask the original setup failure.
- Disconnect controller-owned canvas callbacks and observers exactly once;
  close view-owned store bindings and selection subscriptions.
- Preserve backend-specific cleanup, especially VTK interactor detachment and
  render-window finalization.
- Keep cleanup safe when construction failed partway through and when a view
  is closed more than once if that behavior is already required by its
  implementation.
- Do not merge resource owners or add a generic lifecycle framework solely to
  shorten `_open_view` or its cleanup paths.
- Keep native GUI/context claims separate from fake widgets and headless tests.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 8/8 checklist items.
- [x] Trace successful creation, replacement commit, and setup failure in
      `_open_view`, recording resource acquisition and rollback order.
- [x] Trace normal close and compare `_dispose_open_view` with
      `_release_open_view_resources`.
- [x] Map view-owned cleanup for a history view, Ground Track, station view,
      and VTK backend; distinguish it from panel/controller cleanup.
- [x] Map existing tests to lifecycle transitions and determine which paths
      use real wx/VTK resources versus fakes.
- [x] Rank only evidence-backed duplicated obligations or lifecycle gaps;
      select at most one bounded experiment.
- [x] If justified, add failure-injection and exactly-once cleanup assertions
      before changing production code; otherwise record the no-change decision.
- [x] Run focused lifecycle, binding, representative view-close, and backend
      cleanup tests; record skips and environment limitations.
- [x] Update the assessment with findings, decision, test results, and the next
      candidate. Update other architecture documentation only if ownership
      changes.

**Done when:** panel creation, rollback, replacement, and disposal are traced
alongside representative view-owned resources; tests support each reported
claim; and any change is narrowly justified or explicitly deferred.

## Execution record

The successful path registers the new `_OpenView` before releasing the
replaced view, so a failed replacement leaves the old panel and its resources
usable. Setup rollback disconnects any callback already installed, unsubscribes,
closes the partial view, restores or removes the attempted panel, destroys it,
and re-raises the setup exception. Normal disposal removes controller mappings,
releases resources, then removes and destroys the panel using `finally` blocks.

Resource ownership remains intentionally split: `StoreViewBinding` manages
store subscriptions and its context; views release their own listeners,
artists, and selection subscriptions; the VTK backend finalizes and detaches
its native rendering resources. The only duplicated low-level sequence was
callback disconnection, unsubscribe, and `view.close()`. It is now shared by
setup rollback and normal resource release in `_release_view_resources`;
panel restoration, registry mutation, and destruction remain phase-specific.
Exactly-once close assertions cover ordinary close, replacement, failed
construction rollback, and frame shutdown.

Validation passed: the complete app lifecycle suite (88 passed) and the
representative binding/view/backend suites (70 passed, 3 skipped). The skips
are display-dependent wx cases; VTK cleanup coverage uses a fake widget and
does not validate native desktop integration. No runtime resource ownership
changed, so no subsystem or dataflow design update is needed.
