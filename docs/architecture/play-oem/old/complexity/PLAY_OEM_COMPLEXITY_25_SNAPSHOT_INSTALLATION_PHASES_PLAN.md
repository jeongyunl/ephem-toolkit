# play-oem — Snapshot Installation Phase-Boundary Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and candidate priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Load lifecycle contract:
[PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md).
Snapshot policy reductions:
[PLAY_OEM_COMPLEXITY_23_SNAPSHOT_INSTALLATION_DEDUPLICATION_PLAN.md](./PLAY_OEM_COMPLEXITY_23_SNAPSHOT_INSTALLATION_DEDUPLICATION_PLAN.md),
[PLAY_OEM_COMPLEXITY_24_BATCH_INSTALL_GUARD_PLAN.md](./PLAY_OEM_COMPLEXITY_24_BATCH_INSTALL_GUARD_PLAN.md).

## Goal

Reduce the effort required to understand and modify
`PlayerApp._install_store_snapshot` by evaluating whether its first-append
transition and subsequent-append refresh are distinct, cohesive responsibilities
that should be made explicit in the implementation.

This is a larger local-reasoning experiment than plans 23–24, not a request to
split the controller or introduce a snapshot framework. Keep a phase boundary
only if it reduces the state and behavior a maintainer must hold in mind; do
not move code solely to shorten the method.

## Evidence and hypothesis

The method has a major `first_append` branch. The first append replaces the
playback clock and installed store, restores saved bounds, initializes slider
and file metadata, and starts progressive coverage. Later appends require the
same active store and a `StoreCursor`, extend coverage, refresh the cursor, and
apply pending range behavior. Both paths then update common metadata, store
view context, range hints, interpolation settings, display state, and recent
file state.

Plans 23 and 24 consolidated two smaller repeated policies. The remaining
candidate is whether the first-append versus later-append phase distinction
can be clearer at the code level without obscuring their shared tail or
creating helpers that merely relocate implementation detail.

**Hypothesis:** an explicit phase boundary may make replacement setup and
ongoing append behavior easier to reason about separately. Reject it if the
phases depend on too many shared mutable fields, require broad parameter lists
or return tuples, duplicate the common metadata tail, or add navigation cost
without reducing coordination.

## Procedure

1. Trace state reads and writes in the first-append branch, later-append
   branch, and shared tail. Record which state is owned by each phase and which
   behavior must remain ordered across phases.
2. Map existing tests for old-store retention, first usable append, later
   coverage extension, pending playback bounds, metadata updates, and failed
   or cancelled replacement.
3. Sketch the smallest candidate boundary without editing: identify helper
   inputs/outputs, shared state dependencies, and the resulting call path.
4. Compare the sketch with the current method. Reject it if moving code creates
   broad arguments, result tuples, duplicate updates, or hidden ordering
   obligations.
5. If the boundary is cohesive, implement it with narrow signatures while
   retaining the common metadata/view-context tail in one place. Do not add a
   state object or general transaction abstraction.
6. Run focused app lifecycle, loader, clock, and time-range tests. Compare
   the before/after responsibilities, calls, state dependencies, and code
   volume; code movement alone does not count as reduction.
7. Keep the change only if the resulting phase model is easier to explain and
   verify. Otherwise leave production code unchanged and record why.
8. Update the assessment and subsystem overview with the outcome and next
   candidate.

## Required behavior

- Preserve installed-old-store behavior until the replacement has a usable
  first prefix.
- Preserve first-append clock/cursor initialization and rate/direction.
- Preserve pending/fixed/follow-coverage playback-bound behavior.
- Preserve later-append store identity checks, coverage extension, and cursor
  refresh ordering.
- Preserve metadata, view-context, observer, and range-hint updates.
- Preserve valid-prefix behavior on late failure and stale-generation
  rejection.

## Implementation checklist

- **Status:** Complete — first and later append phases are explicit.
- **Progress:** 8/8 checklist items.
- [x] Map reads, writes, and ordering across first append, later append, and
      their shared tail.
- [x] Map the existing tests to the required lifecycle behavior.
- [x] Evaluate one bounded phase boundary and its signatures before editing.
- [x] Extract the first-append transition and later-append advancement into
      named private phases with narrow explicit inputs.
- [x] Keep the shared metadata/view-context tail in one place.
- [x] Run app lifecycle, loader, clock, and time-range validation.
- [x] Keep the change because the dispatcher now shows the lifecycle choice,
      while each phase owns its distinct invariants.
- [x] Update the assessment and subsystem overview with the outcome.

**Done when:** The first-append and later-append responsibilities are easier to
understand in code, or a proposed boundary is rejected with a concrete
complexity tradeoff and no production code is changed.

## Execution record — 2026-11-11

`_install_store_snapshot` now dispatches to `_install_first_store_snapshot`
or `_advance_store_snapshot`, then performs the shared metadata, view-context,
and range-hint updates once. The first-append helper owns clock/store
replacement, saved-range setup, slider/file state, and initial cursor creation.
The later-append helper owns active-store/cursor validation, coverage
extension, cursor refresh, and follow-coverage behavior. Both have narrow
explicit inputs; no result tuple, mode flag, or new state owner was introduced.

This makes the method's main sequence a readable phase dispatcher and keeps
each phase's invariants together. It adds two named methods and cross-method
navigation, so the change is limited to this one cohesive transition rather
than a broader controller split. The app lifecycle, incremental-loader, clock,
and time-range suites passed (**173 passed**) on macOS with Python 3.9.6.
Existing warnings were Matplotlib/Pyparsing deprecations. GTK/MSW behavior is
unchanged and remains unverified.
