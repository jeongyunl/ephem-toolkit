# play-oem — Panel-Open Keyword Arguments Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior panel lifecycle evidence:
[PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md).
Panel preflight:
[PLAY_OEM_COMPLEXITY_38_PANEL_OPEN_PREFLIGHT_PLAN.md](./PLAY_OEM_COMPLEXITY_38_PANEL_OPEN_PREFLIGHT_PLAN.md).

## Goal

Make the target panel explicit at `open_panel_view` call sites by making
`panel_id` and `stack` keyword-only, while preserving all current panel
selection, pending-data, replacement, and rollback behavior.

This is a signature-clarity change only. Do not introduce a `PanelRequest`
object or change how panels are created or disposed.

## Evidence and hypothesis

`PanelManagementMixin.open_panel_view` currently accepts `name`, `panel_id`,
and `stack` positionally; `force_replace` is already keyword-only. The
corresponding `PlayerAppState` protocol repeats this signature. Application
code and tests use both positional and keyword forms. Requiring explicit
keywords for the panel target should make the call intent clearer and reduce
argument-order mistakes.

The implementation resolves aliases, validates registered names, handles
unloaded OEMs through pending-data views, and forwards the target to a
view-specific opener. These behaviors are not part of the proposed signature
change.

## Scope and invariants

- Change only the `open_panel_view` signature and its direct call sites.
- Keep `name` positional; require `panel_id` as a keyword-only argument.
- Make `stack` keyword-only with its current `"middle"` default.
- Keep `force_replace` keyword-only with its current `False` default.
- Update the matching `PlayerAppState` protocol and every in-repository
  caller, including controller code, panel-management helpers, and tests.
- Preserve default stack placement, stable panel identity, alias expansion,
  unknown-view errors, pending-data views, and forced-replacement behavior.
- Preserve view cleanup, rollback, restored default-view mappings, and
  observer/subscription lifetimes.
- Do not change signatures of individual `open_*_view` methods unless a
  concrete inconsistency blocks this scoped change.
- Do not add a request dataclass or enum for panel placement; current call-site
  evidence does not establish a repeated larger parameter bundle.

## Investigation procedure

1. Record the current revision and worktree state. Reuse Plans 12 and 38 for
   lifecycle and preflight invariants.
2. Search the full repository for `open_panel_view` and inspect the protocol,
   mixin implementation, controller, helpers, examples, and tests. Record all
   positional argument uses.
3. Confirm that no dynamic invocation or string-based callback depends on the
   current positional signature.
4. Change the protocol and implementation signatures together to make
   `panel_id` and `stack` keyword-only.
5. Convert every in-repository call site to explicit `panel_id=...` and
   `stack=...` where needed. Keep default-stack callers concise when the
   required panel ID is named.
6. Run focused panel/app tests for legacy aliases, default and comparison
   stacks, duplicated panel instances, pending-data opening, forced
   replacement, failure rollback, and close/cleanup.
7. Search again to ensure no positional `panel_id` or `stack` call remains.
   Record the signature and validation results in this plan and the assessment.

## Decision criteria

- Make the signature change if all internal call sites can be made explicit
  without altering panel behavior.
- If an authorized external compatibility requirement appears, pause and
  resolve the versioning decision before changing the signature. Under the
  current maintainer decision recorded in Plan 34, external compatibility is
  not a gate for this internal cleanup.
- Keep `name` positional because it is the primary operation selector and
  changing it adds no demonstrated clarity.
- Reject a panel request object unless future call sites repeatedly pass a
  larger shared set of panel options.

## Expected output

- An inventory of positional call sites and their keyword replacements.
- A consistent implementation/protocol signature.
- Focused panel lifecycle test results.
- No changes to view construction, placement policy, or cleanup semantics.

## Execution results

Baseline revision: `10524597`. The signature was updated in both the
`PlayerAppState` protocol and `PanelManagementMixin`. All in-repository
controller, panel-management, and test call sites now pass `panel_id` and
`stack` by keyword; calls that use the default stack omit only `stack`.

The focused five-module regression run passed all 157 tests, including app
panel selection, duplicate panel placement, replacement rollback, graph-panel
lifecycle, and pending-data paths. Alias handling, panel identity, defaults,
and cleanup behavior are unchanged.

No panel-request object or changes to individual `open_*_view` methods were
needed.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 7/7.
- [x] Record revision, worktree state, and relevant panel lifecycle findings.
- [x] Inventory signatures and all positional call sites.
- [x] Update the implementation and protocol signatures together.
- [x] Convert all internal callers to keyword arguments.
- [x] Run focused panel/app lifecycle tests.
- [x] Verify no positional panel target arguments remain.
- [x] Update the assessment and this plan with the outcome.
