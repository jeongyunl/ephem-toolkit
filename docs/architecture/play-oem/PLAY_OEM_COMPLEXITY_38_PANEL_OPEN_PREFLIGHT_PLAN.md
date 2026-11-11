# play-oem — Panel-Open Preflight Complexity Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior lifecycle investigation:
[PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md).
Startup rollback contract:
[PLAY_OEM_COMPLEXITY_14_PARTIAL_GUI_STARTUP_CLEANUP_PLAN.md](./PLAY_OEM_COMPLEXITY_14_PARTIAL_GUI_STARTUP_CLEANUP_PLAN.md).

## Goal

Evaluate whether the side-effect-free panel identity and replacement decisions
at the start of `PanelManagementMixin._open_view` can be made easier to reason
about separately from resource acquisition and transactional setup.

Plan 12 already extracted the one shared low-level view-resource release path
and retained phase-specific panel rollback. This plan does not reopen that
decision or propose a generic lifecycle/transaction framework.

## Baseline and hypothesis

At source revision `c422b94c7ec3b938ff104e16fe5e35d8672e863d`,
`_open_view` is 172 lines with a decision score of 39 under the assessment's
AST indicator. Before resource acquisition it resolves default instances,
duplicate opens, stable panel IDs, and replacement/force-replace behavior.

**Hypothesis:** a small preflight boundary for those decisions may reduce
branch interaction with the resource transaction. Reject it if it needs broad
controller-state plumbing, mutates registries before setup succeeds, or merely
moves the same branching into a helper.

## Scope and constraints

- Inspect the preflight decisions and their transition into panel/resource
  acquisition.
- Preserve stable panel IDs, default-instance focus behavior, duplicate
  semantics, `force_replace`, and stack selection.
- Preserve old-panel usability after failed replacement, rollback ordering,
  exception transparency, and exactly-once resource cleanup.
- Keep view-owned cleanup, store subscriptions, and native VTK lifecycle
  ownership unchanged.
- Do not add a transaction object, lifecycle framework, or broad view factory
  abstraction.

## Procedure

1. Trace default open, duplicate open, same-view focus, replacement, forced
   replacement, and invalid-ID paths, marking which paths return before
   acquiring resources.
2. Sketch one side-effect-free preflight boundary; identify its inputs and
   outputs and compare them with the current local variables.
3. Reject any design that transfers controller mappings or resource ownership
   into the preflight phase or adds more state than it removes.
4. Verify tests cover independent panel instances, failed view-change restore,
   replacement, close, and representative backend cleanup. Add a test only for
   a concrete behavior gap affected by the boundary.
5. Implement only if the total open/rollback path becomes easier to follow
   without changing transaction behavior.
6. Run the focused app lifecycle and panel/view cleanup suites. Record
   platform-dependent skips separately.
7. Update the assessment with the comparison and decision.

## Done when

Panel identity/replacement decisions are either isolated with less total
reasoning and no premature side effects, or explicitly retained because the
boundary would add indirection. Existing rollback guarantees remain covered.

**Status:** Complete; no preflight helper added; rollback fix implemented.

## Outcome

The identity/replacement decisions already form a contiguous block before
`GraphPanelHost` construction and the setup `try` block. Closed-app checking,
range-hint publication, stack selection, default-instance focus/ID assignment,
explicit-ID validation, replacement selection, and collision checks have
observable ordering. In particular, range hints are published before stack
and ID validation, and an existing primary view is focused and returned
before any panel or view resources are acquired.

A helper would need controller mappings, the requested name and panel ID,
stack, and `force_replace`, then return the resolved ID, stack parent,
default-instance flag, replacement record, and possibly a focus target. It
would move the same branches and require a new result shape without reducing
the setup/rollback interaction. Keep the current preflight block inline.

The review exposed a rollback defect on the forced replacement path: if setup
failed while replacing a panel with the same default view, rollback restored
the old `_open_panels` entry and panel but unconditionally removed its
`_open_views` lookup. The focused regression test failed with a missing
`speed-altitude` key. Cleanup now removes that lookup only when there was no
panel being replaced, preserving the old default mapping on failed replacement.
The regression test confirms a later default open focuses the restored panel
and the failed view is closed exactly once.

Validation:

```sh
python3 -m pytest \
  tests/ephem_toolkit/play_oem/test_play_oem_app.py \
  tests/ephem_toolkit/play_oem/test_workspace.py \
  tests/ephem_toolkit/play_oem/test_view_registry.py \
  tests/ephem_toolkit/play_oem/test_store_series_views.py
```

Result: 157 passed, no platform-dependent skips, and 14 third-party
Matplotlib/Pyparsing deprecation warnings. Existing coverage exercises
default-instance focus, independent panels, failed view-change restoration,
forced rebuild dispatch, close, and representative VTK/store-view cleanup.
