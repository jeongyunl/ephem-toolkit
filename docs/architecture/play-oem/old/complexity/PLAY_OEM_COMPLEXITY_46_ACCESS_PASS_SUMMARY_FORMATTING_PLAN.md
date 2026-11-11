# play-oem — Access-Pass Summary Formatting Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior Ground Station Access reviews:
[PLAY_OEM_COMPLEXITY_44_ACCESS_GRAPH_INTERVAL_ANNOTATION_PLAN.md](./PLAY_OEM_COMPLEXITY_44_ACCESS_GRAPH_INTERVAL_ANNOTATION_PLAN.md) and
[PLAY_OEM_COMPLEXITY_45_ACCESS_GRAPH_EMPTY_STATE_RENDERING_PLAN.md](./PLAY_OEM_COMPLEXITY_45_ACCESS_GRAPH_EMPTY_STATE_RENDERING_PLAN.md).

## Goal

Assess whether the repeated interval-detail formatting in
`GroundStationAccessView._pass_summary` can be expressed once for previous or
active and next passes without changing which intervals are selected, the
summary text, or coverage annotations. This is a local formatting review, not
a change to access-interval computation or time labeling.

## Evidence and hypothesis

`_pass_summary` is 63 lines with an AST decision score of 15. Its
previous/active and next branches repeat the duration, peak, peak-time, and
minimum-range formatting, as well as both coverage-note checks. Their visible
labels differ, but the interval fields and annotation rules are the same.
`_time_label` separately applies the configured display timezone.

The method first returns an empty string when no station result exists, and
returns a result limitation verbatim before considering intervals. Otherwise,
it selects an interval containing the current time as previous/active, falling
back to the most recent prior interval; the next interval is the first
upcoming interval. The direct access-view tests do not currently call
`_pass_summary` or pin its output.

**Hypothesis:** a narrow local formatter may remove duplicated interval-detail
and coverage-note formatting while leaving result handling and interval
selection visible in `_pass_summary`. Reject the extraction if its helper
indirection obscures the distinct labels or selection rules, or if the
combined implementation does not become simpler.

## Scope and invariants

- Inspect only `_pass_summary` and direct tests in
  `test_ground_station_access_view.py`.
- Preserve the empty-result and limitation early returns.
- Preserve active interval inclusion at both endpoints, fallback to the most
  recent prior interval, and selection of the first upcoming interval.
- Preserve exact labels, ordering, duration and metric precision, configured
  timezone formatting, and the `clipped_at_start` /
  `clipped_at_end` coverage notes.
- Do not change `_time_label`, update/readout behavior, interval construction,
  station metrics, or other view responsibilities.

## Procedure

1. Trace the result/limitation returns, active/previous/next selection, and
   both output-formatting branches.
2. Add direct characterization for no result, a limitation, no intervals,
   an active interval, previous and upcoming intervals, and each coverage
   note. Pin the summary text and interval-selection boundaries.
3. Compare the smallest shared formatter with the repeated blocks. Record
   source lines and the assessment's AST decision score, accounting for any
   nested helper as the assessment defines it. Do not treat line count alone
   as proof.
4. Keep a change only if it reduces duplicated formatting without obscuring
   selection policy or increasing total reasoning and indirection. Otherwise
   retain the existing branches and record why.
5. If implementation is justified, run:

   ```sh
   python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_access_view.py
   ```

6. Update the assessment and subsystem overview with the decision. Do not
   broaden this into interval-generation, timezone, or performance work.

## Done when

The repeated interval details use a tested shared formatter while selection
and labels remain clear, or the formatting stays duplicated because extraction
does not provide a net complexity reduction.

## Execution result

A nested `format_interval_summary` now formats interval bounds, duration, peak,
peak time, minimum range, and both coverage notes once. The result and
limitation returns, active/previous/next selection, and distinct labels remain
in `_pass_summary`.

The characterization was added and passed against the original implementation
before the refactor. It covers empty results, limitations, no intervals,
latest-prior and first-upcoming selection, both coverage notes, and active
interval inclusion at both endpoints. The focused suite passed afterward:

```text
python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_access_view.py
8 passed
```

`_pass_summary` decreased from 63 to 54 source lines and its AST decision score
decreased from 15 to 13. The nested formatter is 17 lines with a score of 3;
the enclosing method's score includes its nested definitions, per the
assessment method.

**Status:** Complete; retain the shared local formatter.
