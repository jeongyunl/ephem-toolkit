# play-oem complexity reduction strategy

## Purpose and scope

This document defines the approach and starting point for reducing `play-oem`
complexity. It is a strategy, not a completed audit or implementation plan.
The aim is to identify where a change requires understanding too many
interacting concepts, and then evaluate whether a proposed change makes
the application easier to understand, modify, and verify.

### Scope boundary

This effort targets implementation complexity, not algorithmic efficiency.
Reducing asymptotic time complexity or space complexity (Big-O runtime or
memory) is out of scope. Runtime, latency, queue, and RSS measurements may
establish operating constraints and help verify that a maintainability change
preserves required behavior; they are not optimization targets. Any separate
performance or memory optimization should be tracked independently.

The ultimate goal is to reduce Play-OEM's implementation complexity while
preserving required behavior. Plans, measurements, documentation, and tests are
means to find, evaluate, and safely validate that reduction; producing those
artifacts without a plausible simplification is not itself progress toward the
goal.

The assessment and subsystem research draw on a limited inspection of the package
and its existing design documentation. Their leads do not establish that the code
is defective or should be split. The
[dataflow description](./PLAY_OEM_DATAFLOW.md) and
[software design](./PLAY_OEM_SOFTWARE_DESIGN.md) provide starting models to
check against the implementation.

Read this document first for the strategy and method. The
[complexity assessment](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md) owns the measured
baseline, candidate inventory, and prioritized work items. The
[subsystem research](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md) explains the detailed
state, concurrency, and domain interactions behind selected findings. Update
the assessment when priorities change; add detailed evidence to the subsystem
research rather than maintaining another work-item list here.

## Understanding complexity

### Local complexity, overall complexity, and code volume

**Local complexity** is the effort required to understand and change a
particular function, class, or module. Branches, state changes, special cases,
and implicit invariants can make a small area difficult to reason about and
test. Size and branch counts help locate candidates for inspection, but do not
establish that the code is unnecessarily complex.

**Overall complexity** is the effort required to understand and change the
application as a system. It includes the concepts, ownership rules, supported
variants, and interactions a developer must understand for a change. Even
simple individual methods can form a difficult system if behavior is spread
across many components and callbacks.

**Code volume** is the amount of code that must be read, tested, and
maintained. It is useful context for both local and overall analysis, but is
not a complexity score. More code can express necessary behavior clearly;
fewer lines can conceal complexity in indirection or a highly configurable
abstraction. Some duplication may be easier to maintain than a shared mechanism
that must accommodate many unrelated cases.

### Vertical and horizontal analysis

These perspectives help investigate both local and overall complexity:

**Vertical analysis** follows one behavior through
the application: layers, calls, events, thread handoffs, state transitions,
and error or cancellation paths. A useful unit of analysis is a user action
from input to visible result, including what happens when it is interrupted.

**Horizontal analysis** examines the breadth of concepts and variants that coexist:
responsibilities within a component, dependencies between components, similar
view implementations, alternative backends, configuration options, and supported
compatibility paths. A useful unit of analysis is a responsibility or feature
and all the places that implement or coordinate it.

These directions overlap. For example, a single store can make data ownership
clearer while also accumulating many responsibilities. An assessment should
consider both effects and preserve necessary performance and correctness
properties.

## Investigation method

### 1. Trace representative behaviors vertically

For each scenario, trace the actual code from trigger to visible result. Record
the participating components, state owners, calls and events, thread handoffs,
invariants, and error, cancellation, and cleanup paths. Compare the trace with
the existing dataflow documentation and note discrepancies separately from
proposed design changes.

The replacement-during-load trace is complete; see the
[load lifecycle plan](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md) and
[subsystem research](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md). Reuse its
transition and test map rather than repeating that investigation. The combined
range/derived-work measurement is documented in
[Plan 32](./PLAY_OEM_COMPLEXITY_32_REPRESENTATIVE_LOAD_MEASUREMENT_PLAN.md) and
is deferred indefinitely, with no scheduled resumption. Do not resume it
without explicit reprioritization. Its runtime and memory measurements remain
constraints, not optimization targets, if it is ever reinstated.

Existing tests and investigations already cover first usable data, playback
across gaps and in reverse, range rules, and shutdown with work pending. These
remain reference evidence; no representative-workload measurement or trace
extension is currently scheduled under Plan 32.

For each trace, count components crossed, asynchronous handoffs, and distinct
state transitions as aids to discussion. Record the assumptions needed to
reason about the result. Counts alone cannot tell whether a handoff or state is
unnecessary.

### 2. Map responsibilities horizontally

Plan 33 completed the initial import/call and responsibility map across the
store, controller, representative views, workspace, and 3D backends. Its
execution record documents ownership, callbacks, dynamic registration, change
paths, scan limits, and the decision to retain current boundaries. Refresh or
extend that map only when a concrete change or new evidence raises a specific
boundary question; do not repeat it as a general refactoring exercise.

### 3. Maintain a reproducible baseline

Collect measurements at a recorded commit and document the commands, tool
versions, scope, and exclusions. Prefer trends and specific examples over a
single aggregate score:

| Evidence | Question it can help answer | Limitation |
| --- | --- | --- |
| File, class, and method sizes; cyclomatic complexity | Where should a reviewer inspect local control flow? | Size and branch counts do not establish difficulty or necessity. |
| Code volume by responsibility and variant | Where is code concentrated or repeated, and what must be maintained? | Line counts do not distinguish necessary behavior from accidental complexity. |
| Internal imports, dependencies, and cycles | Which components depend on each other? | Imports alone miss callbacks, dynamic registration, and runtime coupling. |
| State owners, event types, thread handoffs, and lifecycle transitions | Where must behavior be coordinated? | A smaller count is not automatically safer or simpler. |
| Public interfaces, callers, and compatibility paths | What could a change affect? | Dynamic callers and external users may not appear in repository searches. |
| Similar implementations and variants | Is policy duplicated or merely adapted to different needs? | Textual similarity is not proof that an abstraction is appropriate. |
| Test scenarios and setup for representative changes | How hard is behavior to verify? | Test count or coverage alone does not establish test quality. |
| Change frequency and files changed together in Git history | Which areas repeatedly change together? | History may reflect large migrations or incomplete usage data. |

Supplement static measurements with the scenario traces: neither is sufficient
on its own. Record unknowns, including external API users and runtime behavior
that cannot be observed without a GUI or representative OEM files.

### 4. Rank findings and test possible improvements

For each finding, describe a concrete change scenario, evidence, the people or
components affected, and the cost of a mistake. Rank by how often the scenario
arises, the difficulty of understanding and testing it, and its consequences;
use judgment rather than presenting a calculated score as fact. Distinguish
inherent domain and performance complexity from complexity caused by the
current design.

Choose a bounded evidence-gathering experiment before proposing a code change.
The current candidates and holds are:

- Extend the completed Plan 33 map only to investigate a new, concrete
  dependency or responsibility concern. Do not split a module based on size or
  the map alone.
- Keep Plan 32 deferred indefinitely. Do not execute its representative
  incremental-load and range-change workflow unless it is explicitly
  reprioritized.
- Treat the cursor type-contract work in
  [Plan 35](./PLAY_OEM_COMPLEXITY_35_CURSOR_TYPE_CONTRACT_PLAN.md) as historical;
  [Plan 36](./PLAY_OEM_COMPLEXITY_36_OEM_CURSOR_RETIREMENT_FEASIBILITY_PLAN.md)
  records the completed single-`StoreCursor` design. Reopen it only for a
  concrete cursor correctness or lifecycle regression.
- [Plan 37](./PLAY_OEM_COMPLEXITY_37_SAVED_STATE_VALIDATION_BOUNDARY_PLAN.md)
  completed with no shared validation helper: it would add error plumbing
  without reducing rules or caller obligations. [Plan 38](./PLAY_OEM_COMPLEXITY_38_PANEL_OPEN_PREFLIGHT_PLAN.md)
  retained the inline preflight and fixed failed replacement losing the old
  default-view lookup. [Plan 39](./PLAY_OEM_COMPLEXITY_39_TERMINAL_LOAD_CLEANUP_PLAN.md)
  deduplicated terminal drag cleanup while retaining the single event loop.
  No broader refactor was selected.
- [Plan 40](./PLAY_OEM_COMPLEXITY_40_CAPACITY_SCANNER_SIMPLIFICATION_PLAN.md)
  completed the capacity-scanner simplification: the separate ASCII and UTF-8
  paths now use one bounded scanner. All 88 focused store/loader tests passed,
  and the measured synthetic medians remained within the plan's guardrails.
  Plan 32 remains deferred; do not infer a production performance target from
  these synthetic measurements.
- [Plan 41](./PLAY_OEM_COMPLEXITY_41_PASS_ENDPOINT_LOOK_ANGLE_POLICY_PLAN.md)
  completed the local endpoint-policy review. Its resolver reduced the two
  methods plus helper from 124 to 115 lines and their combined AST decision
  score from 42 to 36; all 27 focused tests passed, with one display-gated
  skip. Profile-coverage and interpolation rules remain at their callers.
- [Plan 42](./PLAY_OEM_COMPLEXITY_42_SKY_PLOT_EMPTY_STATE_RENDERING_PLAN.md)
  completed the local sky-plot status-message review. Reusing the centered
  text options shortened `_draw_sky_plot` by 15 lines while its AST decision
  score remained 27; the five message cases and their precedence remain
  unchanged. All 28 focused tests passed, with one display-gated skip.
- [Plan 43](./PLAY_OEM_COMPLEXITY_43_SKY_PLOT_LAYOUT_PADDING_PLAN.md)
  completed the local layout-padding review. Sharing one subplot adjustment
  reduced `_draw_sky_plot` from 157 to 152 lines while keeping its AST decision
  score at 27. The legend/no-legend bottom margins and legend ordering remain
  unchanged; all 29 focused tests passed, with one display-gated skip.
- [Plan 44](./PLAY_OEM_COMPLEXITY_44_ACCESS_GRAPH_INTERVAL_ANNOTATION_PLAN.md)
  completed the access-graph annotation review. Selecting the label and hatch
  together reduced `_draw_elevation_graph` from 122 to 119 lines and its AST
  decision score from 26 to 24. Gap precedence and legend de-duplication are
  covered by the focused tests (5 passed).
- [Plan 45](./PLAY_OEM_COMPLEXITY_45_ACCESS_GRAPH_EMPTY_STATE_RENDERING_PLAN.md)
  reused local centered text options across five status-message calls in
  `_draw_elevation_plot`, reducing it from 82 to 77 lines with its AST decision
  score unchanged at 15. The focused suite passed (5); message precedence,
  axes-on/off behavior, and axes-relative styling are characterized.
- [Plan 46](./PLAY_OEM_COMPLEXITY_46_ACCESS_PASS_SUMMARY_FORMATTING_PLAN.md)
  reused a nested formatter for repeated interval details and coverage notes
  in `_pass_summary`, reducing it from 63 to 54 lines and its AST decision score
  from 15 to 13. The focused suite passed (8); result handling, interval
  selection, labels, and timezone formatting were preserved.
- [Plan 47](./PLAY_OEM_COMPLEXITY_47_ACCESS_GRAPH_RUN_SEGMENTATION_PLAN.md)
  characterized non-finite and below-mask profile gaps, then retained the two
  explicit contiguous-index splits: a shared helper would not reduce method
  size or decision score and would add indirection. The focused suite passed
  (10); `_draw_elevation_graph` remains 119 lines with score 24.
- The hosted native wx pilot in
  [Plan 19](./PLAY_OEM_COMPLEXITY_19_HOSTED_WX_TEST_PILOT_PLAN.md) is deferred
  indefinitely. Do not resume it without explicit reprioritization, even if
  non-macOS runner access becomes available.

The project maintainer has stated that there are not yet external users and
compatibility is not a concern. Plan 34 is closed before its evidence matrix
was completed; compatibility evidence is not a gate for current changes.
Longer-term maintenance frequency remains deferred until there is a longer
period of ordinary maintenance.

Each experiment should state a hypothesis, expected benefit, affected
interfaces and invariants, and a way to reject it. Compare the same trace,
responsibility map, tests, and relevant performance measurements before and
after. Assess the effect on local reasoning, overall interactions, and code
volume. Account for new indirection and concepts as well as code removed or
moved. A sketch or small prototype is sufficient if it exposes the tradeoff;
production refactoring is a separate decision.

## Reprioritized execution

The lifecycle and selected follow-on investigations through Plan 31 are
summarized in the [assessment](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md); detailed
traces and decisions remain in their linked plans and the subsystem research.
They produced bounded local simplifications and rejected abstractions that
were not supported by evidence. Plan 33 has now mapped internal dependencies,
ownership, callbacks, and representative change paths. It found explicit
coordination points but no avoidable cost that justifies a boundary change.
Do not repeat the map or begin a broad refactor without new evidence:

1. Keep current boundaries. Revisit explicit view-registration and
   tier-to-view refresh coordination only if ordinary changes expose repeated
   missed updates or unnecessary cross-component knowledge. The map and its
   limits are recorded in [Plan 33](./PLAY_OEM_COMPLEXITY_33_INTERNAL_DEPENDENCY_RESPONSIBILITY_MAP_PLAN.md).
2. Keep representative OEM load, derived-query, and range-change measurements
   under [Plan 32](./PLAY_OEM_COMPLEXITY_32_REPRESENTATIVE_LOAD_MEASUREMENT_PLAN.md)
   deferred indefinitely. Do not resume or schedule them without explicit
   reprioritization.
3. Keep the completed cursor retirement under
   [Plan 36](./PLAY_OEM_COMPLEXITY_36_OEM_CURSOR_RETIREMENT_FEASIBILITY_PLAN.md)
   as the current design; reopen only for a concrete regression.
4. Keep [Plan 37](./PLAY_OEM_COMPLEXITY_37_SAVED_STATE_VALIDATION_BOUNDARY_PLAN.md)
   complete with its no-change result. Plan 38 kept its preflight inline and
   fixed the failed-replacement lookup regression. Plan 39 deduplicated the
   terminal range-drag reset without extracting event handlers. Reopen these
   decisions only for a concrete regression or new evidence of net
   simplification.
5. Keep the single bounded scanner completed under
   [Plan 40](./PLAY_OEM_COMPLEXITY_40_CAPACITY_SCANNER_SIMPLIFICATION_PLAN.md).
   Reopen the ASCII-specific path only for a demonstrated correctness issue or
   a measured regression outside the documented guardrails.
6. Keep the endpoint-policy result from
   [Plan 41](./PLAY_OEM_COMPLEXITY_41_PASS_ENDPOINT_LOOK_ANGLE_POLICY_PLAN.md):
   retain its local resolver and keep profile-coverage and interpolation rules
   in their respective callers.
7. Keep the local status-text options from
   [Plan 42](./PLAY_OEM_COMPLEXITY_42_SKY_PLOT_EMPTY_STATE_RENDERING_PLAN.md).
   Preserve the message-selection branches and precedence; do not extract a
   broader empty-state abstraction.
8. Keep the shared subplot adjustment from
   [Plan 43](./PLAY_OEM_COMPLEXITY_43_SKY_PLOT_LAYOUT_PADDING_PLAN.md).
   Preserve the legend ordering and the exact `0.28`/`0.08` bottom margins.
9. Keep the paired gap/coverage annotation classification from
   [Plan 44](./PLAY_OEM_COMPLEXITY_44_ACCESS_GRAPH_INTERVAL_ANNOTATION_PLAN.md).
   Preserve gap precedence, label de-duplication, and hatches.
10. Keep the hosted wx pilot in
   [Plan 19](./PLAY_OEM_COMPLEXITY_19_HOSTED_WX_TEST_PILOT_PLAN.md) deferred
   indefinitely unless it is explicitly reprioritized. Retain the platform
   limitation and select no production refactor.
11. Revisit maintenance trends after several months of ordinary maintenance.

The [assessment's current evidence priorities](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md#current-evidence-priorities)
owns the detailed limits and next observations. Do not select a production
refactor unless measurements or dependency evidence identify a concrete rule,
ownership boundary, or coordination cost that can be reduced and validated.
