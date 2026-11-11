# play-oem — Domain and Performance Hotspots Investigation Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Baseline and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Store scheduling and cache findings:
[PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md](./PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md).
View refresh findings:
[PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md](./PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md).
Saved-state findings:
[PLAY_OEM_COMPLEXITY_8_SAVED_STATE_PARSING_VALIDATION_PLAN.md](./PLAY_OEM_COMPLEXITY_8_SAVED_STATE_PARSING_VALIDATION_PLAN.md).
Current dataflow: [PLAY_OEM_DATAFLOW.md](./PLAY_OEM_DATAFLOW.md).

## Goal

Execute authoritative assessment priority 6, **Investigate domain and
performance hotspots separately**. Examine three candidates independently:
station-access interval construction, ASCII OEM capacity scanning, and the
large `Workspace` constructor. Use domain boundary tests for the first,
reproducible performance evidence for the second, and lifecycle/layout evidence
for the third. The score and line count are starting signals, not instructions
to refactor.

Do not combine the candidates into a broad cleanup. A finding that existing
code is appropriately complex, or that evidence does not justify a change, is
an acceptable result. At most one bounded implementation experiment should be
selected at a time, with its own behavioral or performance acceptance criteria.

## Planning baseline and initial evidence

At planning time, the worktree is clean at commit
`5efc83a71769da7c8ce65b6a0365536a4ffe3b94`. The assessment's source metrics
were measured at commit `cf93496` and have not been recomputed at this planning
commit. That assessment identified:

| Candidate | Assessment signal | Initial interpretation |
| --- | --- | --- |
| `station_access._intervals_for_segment` | 166 lines; decision score 42 | State-machine-like interval construction with access transitions, missing samples, boundary refinement, and coverage/gap flags. |
| `oem_data_store._capacity_for_ascii_file` | 179 lines; decision score 46 | Performance-sensitive mmap/NumPy scanner with chunk, encoding, marker, line-limit, and cancellation behavior. |
| `Workspace.__init__` in `workspace/core.py` | 398 lines; decision score 30 | GUI construction and layout orchestration; much of its volume may be necessary widget setup. |

These are not current measurements, defect reports, or change targets.

### Station-access intervals

`_intervals_for_segment` consumes parallel sample-time/metrics iterables and
tracks an active pass, its start and end metrics, peak elevation, minimum
slant-range sample, and coverage/gap flags. It closes intervals on missing
metrics, refines sampled access crossings, and handles a pass still active at
the end of the segment. `_refine_crossing` uses
`CROSSING_TIME_TOLERANCE_S`; the surrounding access code also limits source
gaps, sample spacing, and total samples. These rules encode domain semantics;
simplifying branches without a transition table and boundary oracle risks
changing pass times or clipping behavior.

Existing higher-level coverage is in `test_oem_data_store.py` and the station
access/analysis/pass-view tests. Map exactly which access transitions and
coverage/gap conditions they exercise; do not assume each `_intervals_for_segment`
branch already has direct unit coverage.

### ASCII capacity scan

`_capacity_for_ascii_file` mmaps ASCII input and scans in 1 MiB chunks. It
counts line separators, validates the line-length bound, excludes covariance
sections, checks cancellation during scanning, and returns `None` for
non-ASCII input so the text path can handle it. Chunk boundaries, CRLF pairs,
marker lines, EOF, and cancellation all affect correctness.

`test_oem_data_store.py` already includes targeted capacity tests for physical
line endings, markers across chunk boundaries, complete covariance marker
lines, CRLF line limits, UTF-8 fallback/cancellation, covariance exclusion,
and Unicode line length. This is substantial correctness coverage, but not by
itself a performance benchmark. `test_loader_benchmark.py` measures a broader
store session; isolate scan cost before attributing end-to-end startup time to
this function.

### Workspace construction

`Workspace.__init__` owns widget and splitter setup, feature navigation,
ground-station manager construction, the shared timeline, and callback wiring.
The layout is wx-specific and may be correctly explicit rather than
algorithmically complex. `test_workspace_resizing.py` constructs a real wx
workspace and is display-gated; trace which related application tests exercise
construction and which require a GUI before proposing extraction.

The candidate is not a request to split `workspace/core.py`, reorder GUI
creation, or change layout. Identify distinct initialization phases, shared
state dependencies, event binding order, resource ownership, and teardown
expectations first. Any smaller constructor helper must leave widget parenting,
callback identity, and event ordering unchanged.

## Investigation workstreams

Keep the evidence and decision for each candidate separate.

### A. Verify interval state and domain boundaries

- Trace callers from station-access query through segment selection,
  `_intervals_for_segment`, crossing refinement, and `AccessInterval` output.
- Build a transition table for below/above threshold, entering/leaving access,
  `None` metrics/gaps, coverage start/end, and an active interval at segment
  completion.
- Record which fields must remain internally consistent: clipped and
  gap-limited flags, refined boundaries, peak time/elevation, minimum-range
  time/value, and endpoint look angles.
- Compare existing public-query tests with missing boundary cases. Add a
  deterministic test only when it captures a meaningful uncovered rule.
- Consider a refactor only if it reduces state that must be coordinated without
  obscuring those transitions or changing numerical tolerance.

### B. Measure capacity scan cost before optimizing

- Trace `OemDataStore.capacity_for_file` dispatch to ASCII and text paths and
  the later loader capacity consumer. Separate the scan from parsing,
  allocation, and worker scheduling.
- Establish repeatable baselines across representative small and large files,
  including LF/CRLF, covariance markers, and non-ASCII fallback. Record file
  sizes, environment, trial count, median/range, and cancellation behavior.
- Where feasible, measure peak memory as well as elapsed time; mmap virtual
  size is not the same as resident memory. State tool and platform limitations.
- Preserve exact capacity, line-limit, covariance, encoding, and cancellation
  semantics. Do not alter the 1 MiB chunking or replace the scanner based only
  on source length or synthetic microbenchmarks.
- Define a meaningful acceptance criterion from the observed use case before
  keeping a performance change; require no material regression in correctness,
  memory use, or cancellation responsiveness.

### C. Trace Workspace initialization and testability

- Map constructor statements into phases (initial state, splitters/panes,
  navigation and ground stations, timeline controls, callbacks/layout).
- Identify which values cross phase boundaries and which work is simple
  widget composition. Distinguish size from duplicated policy or genuinely
  coupled state.
- Map available construction, resize, and application tests, including their
  display requirements. Identify a deterministic test seam before extracting
  any helper.
- Consider a small helper only when it has a clear ownership boundary and
  demonstrably reduces dependencies or caller coordination. Preserve wx parent
  relationships, bindings, sizing, initial state, and resource lifecycle.

## Required behavior and constraints

- Treat each candidate independently; no omnibus refactor or module split.
- Keep station interval times, coverage/gap semantics, and numerical
  tolerances unchanged unless a separately proven defect is approved.
- Keep scanner output and error behavior identical for all supported OEM
  encodings and line-ending/marker cases; retain cancellation checks.
- Keep workspace widget hierarchy, event order, sizing, callbacks, and cleanup
  behavior unchanged.
- Reuse existing domain helpers and test fixtures; avoid parallel
  implementations or generic frameworks.
- Require evidence appropriate to the claim: boundary tests for domain
  behavior, reproducible measurements for performance, and testable ownership
  boundaries for construction clarity.
- Update dataflow or subsystem design only if verified ownership or runtime
  behavior changes.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 8/8 checklist items.
- [x] Trace callers and dependencies for all three candidates. Record what each
      candidate owns, what calls it, and which state or resource contracts cross
      its boundary.
- [x] Build an interval transition/boundary map and map existing tests to it.
      Identify any missing cases without changing numerical behavior.
- [x] Establish a reproducible ASCII capacity-scan baseline, separate from
      parsing and store allocation; record file shape, trials, timing, memory
      measurement limits, and cancellation behavior.
- [x] Map Workspace constructor phases, cross-phase state, event bindings,
      resource ownership, and available GUI/headless test coverage.
- [x] Rank potential changes independently by demonstrated consequence,
      frequency, evidence strength, expected benefit, regression risk, and
      testing cost. Select at most one bounded experiment.
- [x] Add or adjust deterministic boundary/integration tests only for a
      demonstrated gap or behavior touched by the selected experiment.
- [x] Run the smallest relevant test set and any justified benchmark; compare
      exact behavior and measurements with the baseline.
- [x] Update the assessment with separate decisions, validation, limitations,
      and the next priority. Update other architecture documentation only if
      ownership or runtime behavior changes.

## Execution record — 2026-11-10

### A. Station-access interval state and boundaries

`OemDataStore.station_access` selects ready profile row spans per contiguous
station-profile layout, creates event streams from those rows, and passes the
events plus layout-derived coverage/gap flags to `_intervals_for_segment`.
Non-finite profile rows become `None` metrics. Within a pass, the helper tracks
start metrics, peak elevation, minimum slant range, and the last access metrics.
A missing metric closes a preceding active interval as clipped at its end,
clears extrema, and permits a later interval to start. Coverage and source-gap
flags are then attached separately; threshold transitions use crossing
refinement at the existing tolerance.

Existing store tests exercise an ordinary access pass and policy-dependent
profile behavior, while view tests mostly supply prebuilt `AccessInterval`
values. There was no direct test of the helper's non-finite-row split/reset
path. Added two focused tests in `test_station_access.py`: one checks that a
missing metric splits intervals and resets peak/range extrema; the other checks
the combined coverage and gap endpoint flags. No production interval logic or
numerical tolerance changed. No incorrect result was demonstrated, so a
state-machine rewrite is not justified by the current evidence.

### B. Capacity-scan measurement

Measured `OemDataStore.capacity_for_file` directly; file creation was outside
the timed interval, and every shape was scanned five times with `perf_counter`.
The generated files used 64-byte ASCII LF or CRLF rows, exact covariance marker
lines around a large row body, or a final valid UTF-8 non-ASCII line. Capacities
were asserted for every trial. This measures capacity discovery and its ASCII
or text dispatch, not OEM parsing, array allocation, or a full load session.

| Input shape | File size | Capacity | Median | Trial range |
| --- | ---: | ---: | ---: | ---: |
| ASCII LF | 1 MiB | 16,384 | 1.78 ms | 1.62-6.52 ms |
| ASCII LF | 16 MiB | 262,144 | 31.24 ms | 23.70-36.28 ms |
| ASCII LF | 64 MiB | 1,048,576 | 79.71 ms | 78.44-110.75 ms |
| ASCII CRLF | 16 MiB | 262,144 | 19.67 ms | 19.36-25.18 ms |
| Covariance-heavy ASCII | 16,777,262 bytes | 2 | 62.36 ms | 54.06-81.41 ms |
| UTF-8 fallback | 16,777,219 bytes | 262,145 | 64.04 ms | 63.75-67.23 ms |

These are synthetic local-file timings; OS cache state was not controlled and
peak RSS was not measured. The capacity scan runs in the incremental-loader
worker thread before streaming parse begins, so its cost delays load progress
but does not directly block the wx thread. The existing capacity tests cover
line endings, marker recognition, chunk boundaries, covariance exclusion,
Unicode/UTF-8, line limits, and cancellation. The measured scan cost is
plausible load-start latency for large files, but no production-file
distribution or user-facing load-time target was available. No optimization
was selected.

### C. Workspace construction

The constructor's phases are visible in source: initialize callback/layout
state; create splitters and graph panes; build feature navigation and the
ground-station manager; construct timeline rows, slider, text entry, and
playback controls; bind events; then install sizers on the frame. The operations
are GUI composition with shared parentage, state, callbacks, and event order.
The source trace did not identify a repeated policy or a stable extraction
boundary that would reduce coordination rather than relocate it.

The only direct `Workspace(...)` construction found under tests is
`test_workspace_resizing.py`, which was run but skipped because the environment
has no `DISPLAY`. Therefore native resize/layout behavior was not verified in
this run. No constructor extraction or timing claim is justified without a
display-backed test and stronger evidence of a concrete ownership boundary.

### Validation and decisions

Before adding the station tests, the selected store tests passed (15 passed).
After adding them, the complete `test_oem_data_store.py` plus
`test_station_access.py` run passed: 80 passed. The direct workspace resize test
was skipped due to the missing display. Existing Matplotlib/Pyparsing warnings
were emitted by the wx test process.

**Decision by candidate:** keep station interval logic and numerical
refinement unchanged, with the two targeted boundary tests; keep the capacity
scanner unchanged because synthetic measurements alone do not establish a
production bottleneck, and the work occurs off the wx thread; keep Workspace
construction unchanged because the body is explicit layout composition, no
duplication or stable smaller owner was found, and GUI validation was
unavailable. No production source, dataflow, or subsystem ownership changed.

Priority 6 is complete. The next authoritative work item is priority 7,
inventorying cursor and 3D-backend compatibility variants.

**Done when:** all three candidates have evidence-based findings; tests and
measurements match the claims made; any chosen experiment preserves its
behavioral constraints and demonstrates a net benefit; and the assessment
records what to retain, change, or defer.
