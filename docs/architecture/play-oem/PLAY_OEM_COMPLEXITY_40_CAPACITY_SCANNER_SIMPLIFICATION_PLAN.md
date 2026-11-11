# play-oem — Capacity Scanner Simplification Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior scanner evidence:
[PLAY_OEM_COMPLEXITY_9_DOMAIN_PERFORMANCE_HOTSPOTS_PLAN.md](./PLAY_OEM_COMPLEXITY_9_DOMAIN_PERFORMANCE_HOTSPOTS_PLAN.md).

## Goal

Evaluate whether `OemDataStore.capacity_for_file` can use one bounded
streaming capacity scanner instead of maintaining separate ASCII mmap/NumPy
and UTF-8 text implementations. The target is fewer independently maintained
rules and less scan state, not faster loading or a broader loader redesign.

This is a new structural-simplification hypothesis after Plan 9's scanner
measurements. It does not resume Plan 32's deferred representative-workload
study and does not pre-approve replacing the specialized scanner.

## Baseline and hypothesis

At the assessment baseline revision
`c422b94c7ec3b938ff104e16fe5e35d8672e863d`,
`_capacity_for_ascii_file` was 179 lines with a decision score of 46. It scans
the mapped file once for separators and line limits, then again for covariance
markers. Non-ASCII input falls back to `_capacity_for_text_file`, which
independently tracks line counts, covariance state, chunk carryover, line
limits, and cancellation.

Plan 9 measured capacity discovery separately from parsing and allocation.
Its synthetic medians were 31.24 ms for 16 MiB ASCII LF, 79.71 ms for 64 MiB
ASCII LF, 19.67 ms for 16 MiB ASCII CRLF, 62.36 ms for covariance-heavy input,
and 64.04 ms for UTF-8 fallback. The scan runs on the loader worker, not the
wx thread. These measurements are guardrails, not an optimization target or a
production workload profile.

**Hypothesis:** routing all supported UTF-8 input through one bounded text
scanner, or another smaller shared line-scanning path, could remove the
separate ASCII implementation without moving its policies into a new generic
framework. Reject the hypothesis if the common path retains equivalent
branch/state complexity, changes an edge-case result, exceeds the performance
guardrail below, or weakens bounded cancellation and memory behavior.

## Scope and constraints

- Inspect only `capacity_for_file`, `_capacity_for_ascii_file`,
  `_capacity_for_text_file`, and their direct tests.
- Preserve exact capacity results, including the minimum capacity of one for
  empty or metadata-only input.
- Preserve physical-line handling for LF, CRLF, lone CR, and a final
  unterminated line.
- Treat only a complete, stripped `COVARIANCE_START` or
  `COVARIANCE_STOP` line as a block boundary; continue excluding covariance
  rows from the capacity bound.
- Preserve strict UTF-8 decoding, Unicode character line-length limits, and
  the ASCII line-length limit.
- Keep cancellation checks bounded by the existing 1 MiB scan chunk and avoid
  reading or materializing the complete file or an unbounded line.
- Do not change OEM parsing, store allocation/reservation, loader event
  handling, or user-facing load behavior.
- Do not reopen Plan 32's representative load/query/range-change study.

## Procedure

1. Compare both scanners' line-count, covariance, line-limit, EOF, encoding,
   and cancellation rules. Map each rule to current tests before proposing a
   shared path.
2. Sketch the smallest candidate, starting with using the existing chunked
   text scanner for ASCII as well as UTF-8. Compare branches, state variables,
   memory bounds, and code removed against the existing two-path design.
3. Keep the candidate only if it removes a complete independent
   implementation or a material set of duplicated rules. Reject a wrapper
   that merely dispatches into both scanners or a generic line-processing
   framework with equivalent state.
4. If a candidate survives, run `test_oem_data_store.py` and the focused
   incremental-loader capacity path. Add a test only for a concrete parity
   gap found during the comparison.
5. Re-run Plan 9's same synthetic file shapes and five-trial method only if a
   production candidate is prototyped. As an initial guardrail, reject a
   simpler path if its median scan time exceeds twice Plan 9's recorded median
   for any of the 16/64 MiB ASCII LF, 16 MiB CRLF, or covariance-heavy shapes.
   This is a maintainability trade-off bound, not a performance goal.
6. Compare line/code volume, independent state and branch counts, exact
   capacities/errors, cancellation bound, memory behavior, and measured scan
   time. Retain no code change if complexity reduction does not outweigh a
   guardrail regression.
7. Record the decision in the assessment and subsystem overview. Keep the
   historical Plan 9 result intact.

## Done when

The two scanner paths are either replaced by one demonstrably simpler,
behavior-equivalent bounded scanner within the stated guardrail, or retained
with evidence that their distinct implementation costs are justified. No
broader performance or loader refactor is included.

## Execution record

**Decision:** Keep the simplification. `capacity_for_file` now routes ASCII
and non-ASCII input through one bounded, strict UTF-8 scanner. The
ASCII-specific mmap/NumPy scan and its byte-marker regular expression were
removed. The existing mmap import remains in use elsewhere in the module.
The unified scanner checks cancellation after opening the file and before its
first read, preserving pre-cancel behavior without decoding a cancelled
invalid-UTF-8 file.

The two baseline helpers were 179 lines/score 46 and 66 lines/score 22. They
are replaced by one 68-line/score 24 helper: 177 fewer helper lines and a
combined decision-score reduction from 68 to 24, with no new public API or
configurable policy. The remaining scanner reads at most one 1 MiB chunk at a
time and retains only the current chunk and incomplete line; it no longer
stores a file-sized separator index.

The store and incremental-loader suites passed before and after the change:
88 tests passed in 1.16 seconds after the change. The existing cases cover
newline variants, EOF, chunk-boundary markers and line limits, strict UTF-8,
Unicode limits, covariance exclusion, and pre-set cancellation.

Capacity scans were measured with file creation outside the timed interval;
five `perf_counter` trials were run per shape and capacity was asserted on
every trial. The generated row widths and file sizes match the Plan 9 shapes.
No peak-RSS measurement was taken.

| Input shape | Size | Capacity | Plan 9 median | Plan 40 median (range) | 2x guard |
| --- | ---: | ---: | ---: | ---: | ---: |
| ASCII LF | 1 MiB | 16,384 | 1.78 ms | 2.09 ms (1.92–4.50) | 3.56 ms |
| ASCII LF | 16 MiB | 262,144 | 31.24 ms | 35.64 ms (33.68–50.45) | 62.48 ms |
| ASCII LF | 64 MiB | 1,048,576 | 79.71 ms | 122.75 ms (116.59–124.25) | 159.42 ms |
| ASCII CRLF | 16 MiB | 262,144 | 19.67 ms | 37.88 ms (37.43–38.20) | 39.34 ms |
| Covariance-heavy ASCII | 16,777,262 bytes | 2 | 62.36 ms | 22.78 ms (22.34–23.23) | 124.72 ms |
| UTF-8 final line | 16,777,219 bytes | 262,145 | 64.04 ms | 30.02 ms (29.87–30.29) | 128.08 ms |

All specified guardrail shapes remain below twice their Plan 9 medians; the
CRLF result is the closest to its ceiling. The simplification is retained
because it removes one complete implementation and its file-sized separator
state while preserving capacity and error behavior within the measured
operating envelope.

**Status:** Complete; single bounded scanner retained.
