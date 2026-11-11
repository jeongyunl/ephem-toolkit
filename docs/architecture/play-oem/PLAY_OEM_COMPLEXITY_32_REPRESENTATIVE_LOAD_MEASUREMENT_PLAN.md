# play-oem — Representative Load and Responsiveness Measurement Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Current evidence priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Existing benchmark harness:
[`bench_play_oem.py`](../../../scripts/bench_play_oem.py).
Existing benchmark tests:
[`test_loader_benchmark.py`](../../../tests/ephem_toolkit/play_oem/test_loader_benchmark.py).

## Goal

Measure the representative incremental-load workflow with derived work and
plot-range changes overlapping. Determine whether it produces a material,
repeatable cost in first-data latency, query latency, GUI responsiveness, queue
backlog, or memory held while views retain derived data.

This is an evidence-gathering plan, not a performance optimization or
refactoring proposal. Make no production-code changes. If a result identifies
a concrete complexity cost, document one bounded follow-up hypothesis rather
than changing the design in this plan.

## Why this step

The assessment originally ranked representative runtime and memory as the next
evidence priority. Plans 4–31 established lifecycle, query, cache, and refresh
contracts and rejected abstractions not supported by code evidence, but they do
not measure this combined workload on representative OEM data. This plan is
now deferred for later; Plan 33 is the current next evidence task.

The existing [`bench_play_oem.py`](../../../scripts/bench_play_oem.py) already
measures direct-store ingestion and range-bound queries. Its optional
`--gui-stall-probe` records wx timer gaps, first-batch installation, controls
readiness, first visible render, completion, refresh duration, and process peak
RSS during a real incremental load. It does not currently drive a derived
query and range change during append, or report queue occupancy and
store-accounted memory with pinned views. The test
[`test_loader_benchmark.py`](../../../tests/ephem_toolkit/play_oem/test_loader_benchmark.py)
validates headless benchmark helpers; it does not establish GUI performance.

Plan 9 measured capacity scanning and direct-store queries with synthetic
inputs. Those results are useful component baselines, not evidence of
end-to-end application responsiveness or production-scale memory behavior.

## Scope and baseline

- Record the exact source revision and benchmark-harness revision used for
  every run. Do not compare results across code or harness changes without
  labeling them.
- Record OS, Python, wx port, display/backend, CPU, memory, power mode, relevant
  application settings, and whether the machine is otherwise idle.
- Start with checked-in OEM samples such as
  [`JPSS-1.oem`](../../../tests/data/JPSS-1.oem) and its smaller variants.
  Characterize file size, sample count, coverage duration, segment/gap shape,
  and capacity before deciding whether they represent the target workload.
  If they do not, use representative local files without adding private or
  large data files to the repository.
- Keep each measured GUI trial in a fresh process. Separate warm-up from
  measured runs, use at least five measured trials where runtime permits, and
  report individual values plus median and range or percentiles.
- Record whether process RSS includes application startup and warm-up. Measure
  store-accounted derived memory separately from process RSS; allocator
  behavior means closing a view need not immediately lower RSS.
- Use the native GUI available for the run, currently macOS Cocoa. GTK/MSW and
  native VTK behavior are conditional platform work, not a requirement for
  this measurement.

## Workloads and measurements

Use the same OEM file, application configuration, and view set for the
load-only baseline and the overlapping workload.

| Workload | Actions | Measurements |
| --- | --- | --- |
| Incremental-load baseline | Start from an empty session, load the OEM incrementally, show the first usable plot, and allow loading to complete without range interaction. | Request-to-first-batch, first usable controls, first visible render, full completion, wx timer-gap distribution, refresh duration, process peak RSS, and event totals. |
| Overlapping derived work and range changes | During incremental append, keep one range-sensitive derived view open (use Ground Track unless the initial trace shows it is unsuitable), request derived data, and change the plot range at reproducible points while work is pending. | Baseline metrics plus query/request-to-visible-update latency, range-update latency, queue backlog over time, and whether work completes, is superseded, or is repeated. |
| Pinned-view retention | During the overlapping workload, retain the view and its derived result across range changes, then close/unbind it and let pending work settle. | Store-accounted resident derived bytes and pinned-chunk counts while retained and after release; process RSS as a separate measure; configured memory budget and any over-budget interval. |

Measure queue occupancy as diagnostic evidence, not as a correctness
invariant. Prefer explicit enqueue/dequeue counters in the benchmark harness
when the existing queues do not expose sufficiently reliable measurements;
do not add production logging or change queue policy to collect the data.
Likewise, use existing store accounting if available. If benchmark-only
instrumentation is needed for resident bytes or pinned chunks, keep it
opt-in and behavior-neutral; do not create a new public store API for this
measurement.

## Procedure

1. Inspect the existing GUI probe and the actual range-change path. Confirm
   which view triggers range-bound derived work and how to identify when that
   work is pending. Keep the interaction on the normal GUI-thread path.
2. Select at least two suitable OEM samples if available, ideally with
   different sizes or segment/gap characteristics. Record why each is or is
   not representative; do not treat a checked-in fixture as production-like
   without evidence.
3. Run the existing direct-store benchmarks and load-only GUI probe as
   baselines. For example:

   ```sh
   python3 scripts/bench_play_oem.py tests/data/JPSS-1.oem \
     --repeats 5 --store-session-bench auto --gui-stall-probe
   ```

   Use the actual selected input path for each run. Preserve the tool's
   separation between direct-store measurements and GUI measurements.
4. If the current GUI probe cannot reproducibly issue range changes while
   derived work is pending, add only an opt-in benchmark driver or
   benchmark-only instrumentation. It should request the same range changes
   at defined load milestones, record the requests and outcomes, and leave
   normal application behavior unchanged.
5. Run the overlapping workload and pinned-view retention case in fresh
   processes with the same files and view set as the baseline. Record the
   instrumentation overhead and avoid comparing instrumented and uninstrumented
   runs as if they were identical.
6. Repeat trials, report distributions and failures, and distinguish query
   computation time from time waiting for scheduling, append, GUI refresh, or
   drawing. If a queue cannot be measured reliably without changing behavior,
   document that limitation rather than infer depth from event counts.
7. Compare results with the component-only Plan 9 measurements and the
   configured store memory budget. State explicitly which observations are
   new and which conclusions remain unsupported.
8. Update the assessment and subsystem research with the dataset, environment,
   commands, metrics, limitations, and a decision: retain current design,
   gather more evidence, or propose one separate bounded investigation.

## Decision criteria

- Do not invent an absolute latency or memory threshold when no product SLO is
  available. Report distributions and observable effects, and identify any
  threshold that comes from an existing requirement.
- Treat a result as actionable only when it is repeatable on a representative
  workload and tied to a specific coordination, ownership, scheduling, or
  retention cost.
- A growing queue, a long GUI timer gap, a slow first visible result, or
  over-budget pinned memory is a signal to investigate, not proof that a
  particular abstraction or algorithm should change.
- If the measurements show no material cost, or the available fixtures cannot
  represent the intended workload, record the limitation and do not produce a
  speculative refactor plan.
- Any code change requires a separate plan with a concrete before/after
  hypothesis, preserved behavior, focused tests, and repeatable performance
  evidence.

## Required constraints

- Keep OEM contents local; do not add private or large representative datasets
  to the repository.
- Do not change production queue bounds, scheduling, cache policy, event
  handling, or view refresh behavior while measuring.
- Preserve the normal incremental-load path and existing GUI-thread ownership.
- Report process RSS and store-accounted derived memory as different measures;
  neither alone describes the full memory behavior.
- Do not use line counts, synthetic-only timings, or one run as evidence for a
  complexity reduction.

## Expected output

- Exact revision, environment, input characterization, commands, and trial
  protocol.
- Separate load-only and overlapping-workload results, including the first
  usable result and GUI timer-gap distributions.
- Queue and memory measurements with method, instrumentation, and limitations
  stated.
- An evidence-based decision about whether a distinct complexity cost exists;
  no production refactor unless a separate follow-up is justified.

## Implementation checklist

- **Status:** Deferred.
- **Progress:** Exploratory harness work was performed, but no checklist item
  has been completed as a final measurement result.
- **Note:** Preliminary benchmark instrumentation, focused tests, and
  exploratory GUI runs are not controlled final results. Complete the matched
  workload trials and document their limits if this plan is resumed.
- [ ] Record revision, environment, harness version, and candidate input files.
- [ ] Verify which checked-in or local OEM files are representative and
      characterize their sample, coverage, and segment counts.
- [ ] Run repeated direct-store and load-only GUI baselines.
- [ ] Reproduce range changes while derived work is pending during append using
      the normal GUI path.
- [ ] Measure first-data/query timing, GUI timer gaps, queue backlog, and
      pinned-view memory with behavior-neutral instrumentation.
- [ ] Repeat and compare the baseline and overlapping workloads; record
      instrumentation and platform limitations.
- [ ] Update the assessment and subsystem research with results and the
      keep/change/defer decision.
- [ ] Create a separate implementation plan only if measurements demonstrate a
      concrete, repeatable complexity cost.

**Done when:** The combined workload has reproducible measurements on
characterized OEM data, the limitations are explicit, and the next decision is
supported by observed behavior rather than synthetic-only evidence or hotspot
scores.
