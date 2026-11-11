# play-oem — Readout Status Initialization Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior Ground Station Access reviews:
[PLAY_OEM_COMPLEXITY_46_ACCESS_PASS_SUMMARY_FORMATTING_PLAN.md](./PLAY_OEM_COMPLEXITY_46_ACCESS_PASS_SUMMARY_FORMATTING_PLAN.md) and
[PLAY_OEM_COMPLEXITY_47_ACCESS_GRAPH_RUN_SEGMENTATION_PLAN.md](./PLAY_OEM_COMPLEXITY_47_ACCESS_GRAPH_RUN_SEGMENTATION_PLAN.md).

## Goal

Assess whether the pre-metrics status-label write in
`GroundStationAccessView.update` is needed, or whether removing it would
preserve the final readout while eliminating a redundant status branch. This
is a local readout review, not a change to metric computation or GUI lifecycle.

## Evidence and hypothesis

`update` is 65 lines with an AST decision score of 16. After its no-station,
unloaded-OEM, and preparation-error early returns, it fetches the selected
station result and writes either its limitation or an empty status. It then
requests station metrics. Every handled outcome writes labels again: a
`ValueError` displays its message, missing metrics display the outside-coverage
status, and valid metrics clear status while formatting the readout.

The limitation is also surfaced by `_pass_summary`. The direct
Ground Station Access tests call `update` but do not assert readout label
values or this status-write order. An exception other than the handled
`ValueError` can propagate after the preliminary write, so removing that write
must not silently change required error behavior.

**Hypothesis:** the preliminary result lookup and status write may be redundant
for every normal or handled-metrics outcome. Remove them only if
characterization confirms the final labels, limitation summary, early-return
precedence, and exception propagation remain correct. Otherwise retain the
branch and document why its intermediate label state matters.

## Scope and invariants

- Inspect only `update` and direct tests in
  `test_ground_station_access_view.py`.
- Preserve cursor movement and visibility behavior, including when station
  readouts return early.
- Preserve early-return precedence for no station, unloaded OEM, and
  preparation error.
- Preserve final status, metrics, and pass-label values for successful
  metrics, missing metrics, and handled `ValueError`.
- Preserve propagation of exceptions other than `ValueError`; do not add a
  broad catch or convert failures into success-shaped labels.
- Preserve limitation reporting in the pass summary and all formatted metric
  values.
- Do not change `_set_labels`, station metrics, time-range behavior, or other
  view responsibilities.

## Procedure

1. Trace the preliminary label write and every subsequent exit from `update`.
   Distinguish final label values from intermediate `SetLabel` calls.
2. Add focused characterization for early-return states, result limitation,
   valid metrics, missing metrics, `ValueError`, and propagation of another
   exception. Assert final readout labels and pass-summary behavior.
3. Compare removing the preliminary status block with retaining it. Record
   method lines and the assessment's AST decision score; do not treat fewer
   label calls alone as proof of lower complexity.
4. Keep a change only if it reduces the method's source and decision
   complexity without changing final readouts, documented error behavior, or
   cursor updates. Otherwise retain the explicit status logic and record why.
5. If implementation is justified, run:

   ```sh
   python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_access_view.py
   ```

6. Update the assessment and subsystem overview with the decision. Do not
   broaden this into a full readout redesign or a GUI performance study.

## Done when

The redundant status initialization is removed with final readout and error
behavior characterized, or it is retained because its intermediate state or
complexity tradeoff makes removal unjustified.

## Execution result

Added direct readout characterization for no station, unloaded OEM,
preparation error, successful metrics with a result limitation, missing
metrics, handled `ValueError`, and propagation of an unexpected metrics
exception. The tests also verify cursor updates on early-return paths.

The preliminary status write is retained. On successful or handled metrics
paths, later label writes determine the final readout. If an unexpected
exception propagates, however, the preliminary write replaces stale status
and clears stale metrics and pass labels before control leaves `update`.
Removing it would change that observable error-state behavior.

`update` remains 65 lines with an AST decision score of 16. The focused suite
passed:

```text
python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_access_view.py
14 passed
```

**Status:** Complete; retain the preliminary status write.
