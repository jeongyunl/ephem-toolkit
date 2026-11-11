# play-oem — Candidate Re-ranking and Next-Step Decision Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and candidate inventory:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Latest native lifecycle evidence:
[PLAY_OEM_COMPLEXITY_21_NATIVE_WX_ACTIVE_LOAD_SHUTDOWN_PLAN.md](./PLAY_OEM_COMPLEXITY_21_NATIVE_WX_ACTIVE_LOAD_SHUTDOWN_PLAN.md).
Deferred cross-platform verification:
[PLAY_OEM_COMPLEXITY_19_HOSTED_WX_TEST_PILOT_PLAN.md](./PLAY_OEM_COMPLEXITY_19_HOSTED_WX_TEST_PILOT_PLAN.md).

## Goal

Re-rank the remaining Play-OEM complexity candidates after plan 21 and decide
whether there is a specific, evidence-backed next investigation. The output is
one of:

1. a clearly scoped candidate with an observable complexity hypothesis and
   feasible validation;
2. a concrete blocker that keeps a candidate deferred; or
3. no ready candidate, in which case pause the current complexity-reduction
   sequence rather than creating another low-value test-only plan.

This is a documentation and decision checkpoint, not a new code audit,
refactor, or request to expand test coverage.

## Baseline

Plan 21 verified real wx active-load shutdown on macOS Cocoa with wxPython
4.2.4 / wxWidgets 3.2.8; the app lifecycle suite passed 98 tests and no
production change was needed. Plans 17–19 document that GTK/Linux and
MSW/Windows execution is unavailable and deferred. The assessment already
holds raw-ingestion reservation and load-event-consumption leads absent a
concrete gap.

The strategy's success criterion is reduced effort to understand, change, and
verify behavior—not the number of plans, tests, or files changed. Use that
criterion to avoid serially combining adjacent scenarios without a complexity
hypothesis.

## Procedure

1. Review the assessment's prioritized candidate inventory and the recorded
   outcomes of completed plans. Mark each candidate complete, still open with
   evidence, deferred with a specific blocker, or unsupported by current
   evidence.
2. For every candidate still open, state the concrete coordination or
   comprehension cost, the likely bounded change or decision, and how the
   before/after effect on local and overall complexity could be measured.
3. Exclude candidates that only add confidence to already-covered behavior
   unless that evidence is required by a specific planned design change or
   observed failure.
4. Keep GTK/MSW platform verification deferred until non-macOS runners are
   available. Do not rank it as an executable local task.
5. Select at most one next candidate. If the evidence does not justify one,
   explicitly conclude that no next implementation investigation is selected
   and identify what new evidence would reopen the decision.
6. Update the assessment's priority order and the subsystem overview with the
   decision. Do not create another detailed execution plan unless a candidate
   is actually selected.

## Decision criteria

- The candidate is in the Play-OEM scope and is consistent with the strategy.
- There is concrete evidence of costly coordination, duplicated policy, or
  an unintuitive invariant—not just high line or branch counts.
- A bounded experiment could reduce the rules/callers/interactions a
  maintainer must understand without shifting complexity elsewhere.
- The experiment can be validated with available tools and platforms.
- The expected understanding or maintenance benefit is proportionate to the
  test and implementation cost.

## Implementation checklist

- **Status:** Complete — no new candidate is ready.
- **Progress:** 6/6 checklist items.
- [x] Reconcile the candidate inventory with completed and deferred plans.
- [x] State the evidence and complexity hypothesis for each remaining
      candidate.
- [x] Reject test-only extensions without an identified design or behavior
      gap.
- [x] Conclude that no remaining candidate currently meets the evidence and
      benefit threshold for a new implementation investigation.
- [x] Record reopening conditions for deferred candidates.
- [x] Update the assessment and subsystem overview with the decision.

**Done when:** The repository has an evidence-based next-step decision and no
candidate is promoted solely to keep the plan sequence active.

## Execution record — 2026-11-11

The assessment's primary candidates have been investigated:

| Candidate | Current disposition |
| --- | --- |
| Load lifecycle and replacement | Plan 4 mapped transitions; bounded event draining is implemented and tested. Plans 20–21 verified close during active parsing with test doubles and real Cocoa resources. No additional state abstraction is supported by current evidence. |
| Store scheduling/cache lifecycle | Plan 5 extracted one repeated request-bound calculation; broader extraction remains unsupported without memory, latency, or ownership evidence. |
| Derived store queries | Plan 6 centralized a repeated frame-validation invariant; query-specific coverage semantics remain intentionally distinct. |
| View refresh coordination | Plan 7 mapped routing and tested bounded/coalesced behavior. Revisit batching only with representative queue-depth or UI-latency evidence. |
| Cursor and 3D backend variants | Plan 10 verified current behavior; no consolidation was justified. External consumer evidence and native VTK integration remain unknown, not demonstrated defects. |
| Large GUI views | Plan 11 made a narrow scrollbar-mapping extraction; whole-view separation was not justified. |
| Panel/view lifecycle | Plan 12 centralized shared low-level release; transaction-specific cleanup remains distinct. |
| Controller initialization | Plan 13 fixed two concrete ordering defects; no separate state owner was identified. |
| Raw-ingestion reservation and load-event policy | Deferred: one production row-sink caller and no duplicated event consumer or concrete mismatch. Reopen only on a second independent caller, observed failure, or transition defect. |
| Cross-platform wx cleanup | Deferred: GTK/MSW execution requires non-macOS runners, which are unavailable. Reopen when such access is provided. |
| Native active-load shutdown | Plan 21 passed on macOS Cocoa; no production defect was found. Additional native test expansion is not currently an independent complexity target. |

No uncompleted candidate currently combines a concrete complexity cost, a
bounded reduction hypothesis, and a feasible validation path. Therefore no
new implementation plan is selected. Re-rank only when new evidence appears,
such as repeated protocol use, representative queue/latency measurements, a
reproducible state mismatch, a concrete change blocked by current ownership,
or access to a non-macOS runner.
