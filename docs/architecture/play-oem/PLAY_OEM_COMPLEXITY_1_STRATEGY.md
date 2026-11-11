# play-oem complexity reduction strategy

## Purpose and scope

This document defines the approach and starting point for reducing `play-oem`
complexity. It is a strategy, not a completed audit or implementation plan.
The aim is to identify where a change requires understanding too many
interacting concepts, and then evaluate whether a proposed change makes
the application easier to understand, modify, and verify.

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

Start with **replacing an OEM while an incremental load is active**. It exercises
generation changes, cancellation, event delivery, store replacement, snapshots,
view refresh, and cleanup. Follow both successful replacement and failure or
cancellation; establish what happens to late events and previously visible data.

Then sample these other behaviors:

1. Open an OEM and display its first usable data, then finish loading.
2. Advance or seek playback, including a segment gap and reverse playback.
3. Change the plot range while derived data is pending, then refresh a view.
4. Close a panel or the application while work is pending.

For each trace, count components crossed, asynchronous handoffs, and distinct
state transitions as aids to discussion. Record the assumptions needed to
reason about the result. Counts alone cannot tell whether a handoff or state is
unnecessary.

### 2. Map responsibilities horizontally

Create a matrix with components as rows and responsibilities as columns. Mark
the component that owns each state or decision, those that coordinate it, and
those that consume it. Include loading, raw data, interpolation, scheduling,
cache lifetime, playback, ranges, configuration, panel lifecycle, rendering,
and station analysis. Capture important invariants and the interfaces through
which each responsibility is accessed.

Review the store and controller first, then compare a representative history
view, Ground Track, a station view, and both 3D backends. Look for duplicated
policy, knowledge of another component's internals, and changes that require
coordinated edits in several places. Also record useful separation already
present so it is preserved.

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

Choose one or two bounded experiments only after the traces and baseline. For
example:

- Sketch an explicit load-generation lifecycle and event ownership contract;
  check it against late events, failed replacement, and shutdown tests.
- Explore a narrower internal boundary around a store responsibility, retaining
  one raw-data owner and checking snapshot, cache, and concurrency invariants.
- Compare a shared view lifecycle helper against two or three actual views,
  including one with different rendering needs, before generalizing it.

Each experiment should state a hypothesis, expected benefit, affected
interfaces and invariants, and a way to reject it. Compare the same trace,
responsibility map, tests, and relevant performance measurements before and
after. Assess the effect on local reasoning, overall interactions, and code
volume. Account for new indirection and concepts as well as code removed or
moved. A sketch or small prototype is sufficient if it exposes the tradeoff;
production refactoring is a separate decision.

## First effort: OEM replacement during loading

The detailed behavior, implementation checklist, and completion criteria are in
the [load lifecycle plan](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md).

Start with **replacing an OEM while incremental loading is active**. This
behavior crosses the loader, store, controller, and views, and makes both
local complexity and cross-component coordination visible. The objective is to
develop a repeatable way to reduce complexity while preserving observable
behavior, not to begin with a broad file split or a package-wide line target.

1. **Establish the contract.** Create a transition table for load, first
   append, replacement, completion, failure, cancellation, and close. Record
   the current and pending stores, generation, epoch, owning thread, and visible
   data. Link each transition to existing tests and identify meaningful gaps.
   In particular, check old-data retention before a replacement is usable,
   valid-prefix behavior after a later failure, and rejection of stale events.
2. **Identify costly coordination.** Use the table to find related flags,
   state, or ordering rules maintained across components, including obligations
   imposed on callers. Distinguish necessary asynchronous behavior from
   avoidable duplication or distributed coordination.
3. **Try one bounded change.** For example, prototype a more explicit
   load-lifecycle state or contract. Compare the same behavior trace and tests,
   state relationships, caller obligations, and relevant performance before and
   after. Keep the change only if it reduces the rules needed to understand the
   behavior without moving equivalent complexity elsewhere or weakening the
   contract.

Use what this first effort teaches to refine the method and priorities. The
assessment next prioritized derived-data scheduling and cache lifetime, where
epochs, in-flight work, partial coverage, and pinned views interact. The
[logical-complexity research](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md) describes
these interactions; the [assessment](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md)
records the baseline and work-item inventory.

The expected output is a transition table, a responsibility and invariants map,
test evidence, and a decision on whether a bounded change improves the design.
Update the existing assessment as findings and priorities change.

## Execution status

The lifecycle effort and prioritized follow-on investigations through Plan 30
are recorded in the [assessment](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md), with
detailed traces and decisions in the linked plans and subsystem research. They
produced several bounded local simplifications and rejected other abstractions
where evidence did not support them. The current review is complete for the
available evidence; Plan 31 found that the repository's Play-OEM history spans
only 27 days and does not justify a new implementation candidate. This is not
an exhaustive audit of every runtime, external caller, or platform. Reopen the
work when longer-term maintenance evidence, representative performance data,
a reproducible defect, or access to GTK/MSW runners supports a concrete
candidate.
