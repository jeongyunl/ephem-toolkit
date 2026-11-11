# play-oem — View Query Alias Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Compatibility decision:
[PLAY_OEM_COMPLEXITY_34_EXTERNAL_COMPATIBILITY_EVIDENCE_PLAN.md](./PLAY_OEM_COMPLEXITY_34_EXTERNAL_COMPATIBILITY_EVIDENCE_PLAN.md).

## Goal

Decide whether `StoreViewContext.query_series` should be removed as an unused
compatibility spelling of `series_groups`. If removed, keep the single-group
`series` and multi-group `series_groups` APIs and preserve their existing
results and query semantics.

This is a bounded interface cleanup, not a redesign of view contexts, query
coverage, or store ownership.

## Evidence and hypothesis

In `views/base.py`, `query_series` delegates directly to `series_groups` with
the same arguments and result shape. A repository search found no invocation
sites in source, tests, examples, or user documentation. This suggests that
the alias adds an entry point without providing a distinct operation.

`series` is not redundant: it unwraps the result for one named group.
`series_groups` returns the mapping for multiple groups. Keep these two
different result shapes.

Plan 34 records the maintainer's decision that external compatibility is not
a concern for the current work. Reuse that decision; do not repeat a broad
external-consumer investigation. Reopen compatibility review only if that
scope decision changes.

## Scope and invariants

- Inspect and, if justified, remove only `StoreViewContext.query_series`.
- Preserve `StoreViewContext.series` and `series_groups`, including argument
  names, defaults, and return shapes.
- Preserve snapshot identity and revision stamps, bound-range resolution,
  no-range empty-query behavior, partial coverage, and `wait` semantics.
- Preserve unsupported-group validation and its error behavior.
- Do not change `OemDataStore` query methods, query result types, cache
  scheduling, view bindings, or refresh routing.
- Do not add a replacement alias, query-options type, or another facade.

## Investigation procedure

1. Record the current revision and worktree state. Reuse Plan 34's compatibility
   decision and this plan's initial in-repository search.
2. Search the full repository for `query_series`, including source, tests,
   examples, and documentation. Classify mentions separately from invocation
   sites and confirm there are no callers.
3. Check package exports and type protocols for an intentional compatibility
   contract. Do not infer a public guarantee solely from the method being
   importable.
4. Compare the remaining one-group and multi-group APIs and their view callers.
   Verify that neither is a substitute for the other without a result-shape
   change.
5. If no distinct caller or contract is found, remove the alias and its
   docstring. Otherwise retain it and record the reason; do not add a
   deprecation mechanism unless a concrete compatibility requirement exists.
6. Run focused view/data tests. Include no-range, multi-group query, partial
   coverage, and store refresh/binding cases.
7. Record the decision, changed surface (if any), and validation in this plan
   and the assessment.

## Decision criteria

- Remove the alias only if repository inspection confirms no distinct
  behavior, caller, or documented contract.
- Keep `series` and `series_groups` if their different result shapes are used
  by callers.
- If a new compatibility promise is identified, make no source change and
  document the evidence and owner decision required.
- Reject any broader query-context or store-interface refactor that is not
  required to remove this one redundant spelling.

## Expected output

- A verified caller and compatibility inventory for `query_series`.
- A keep/remove decision with a short rationale.
- If removed, a minimal source change and focused regression results.
- No change to query behavior, data ownership, or other view APIs.

## Execution results

Baseline revision: `10524597`. The initial worktree contained the previously
created complexity-plan documentation, with no pending source changes.

The full repository search found no invocation sites for `query_series` in
source, tests, or examples. Its remaining documentation mentions were
descriptions of the candidate itself. Plan 34 records the maintainer's
decision that external compatibility is not a concern for this work.

Removed `StoreViewContext.query_series`; the distinct `series` and
`series_groups` methods remain. No snapshot, range, coverage, or wait behavior
changed. The focused five-module regression run passed all 157 tests:
`test_store_series_views.py`, `test_play_oem_data.py`,
`test_incremental_loader.py`, `test_play_oem_app.py`, and
`test_graph_panel.py`.

The alias removal is complete. No deprecation shim or replacement alias was
added.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 7/7.
- [x] Record revision, worktree state, and focused scope.
- [x] Verify `query_series` references across source, tests, examples, and docs.
- [x] Recheck the compatibility decision and package/type protocol exposure.
- [x] Confirm the distinct contracts of `series` and `series_groups`.
- [x] Remove the alias without changing the remaining query methods.
- [x] Run focused view/data tests and record results.
- [x] Update the assessment with the decision.
