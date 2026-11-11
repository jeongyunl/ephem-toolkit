# play-oem — Access-Graph Run Segmentation Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior access-graph reviews:
[PLAY_OEM_COMPLEXITY_44_ACCESS_GRAPH_INTERVAL_ANNOTATION_PLAN.md](./PLAY_OEM_COMPLEXITY_44_ACCESS_GRAPH_INTERVAL_ANNOTATION_PLAN.md) and
[PLAY_OEM_COMPLEXITY_45_ACCESS_GRAPH_EMPTY_STATE_RENDERING_PLAN.md](./PLAY_OEM_COMPLEXITY_45_ACCESS_GRAPH_EMPTY_STATE_RENDERING_PLAN.md).

## Goal

Assess whether the repeated contiguous-index splitting in
`GroundStationAccessView._draw_elevation_graph` can be expressed once without
changing finite-profile segmentation, minimum-mask clipping, or plotted
segments. This is a local profile-rendering review, not a change to sampling,
interpolation, or decimation.

## Evidence and hypothesis

`_draw_elevation_graph` is 119 lines with an AST decision score of 24. It
splits index arrays into contiguous runs twice using the same operation:

1. `valid_indices` are split where source indices have gaps, so non-finite
   times or elevations do not get bridged.
2. `visible_indices` are split where samples fall below the station's
   minimum-elevation mask, so separate visible segments do not get joined.

The direct access-view tests cover ordinary profile rendering and elevation
mask behavior, but do not currently characterize non-finite sample gaps or an
interior below-mask sample that divides a visible run.

**Hypothesis:** a small local contiguous-index helper could remove duplicated
split-boundary calculation while keeping the two distinct call sites visible.
Reject it if the helper obscures why each input is split, does not reduce the
method's source size, or adds more reasoning than the two explicit blocks.

## Scope and invariants

- Inspect only `_draw_elevation_graph` and direct tests in
  `test_ground_station_access_view.py`.
- Preserve the finite-time/elevation filter and never connect plotted samples
  across a non-finite source index.
- Preserve minimum-elevation filtering and never connect visible samples
  across an interior below-mask sample.
- Preserve interval-bound clipping, endpoint interpolation and threshold
  handling, gap/coverage limitation behavior, decimation, labels, and playback
  cursor rendering.
- Do not change profile selection, access-interval construction, endpoint
  policy, store ownership, or other view responsibilities.

## Procedure

1. Trace both index-splitting blocks and confirm that they apply the same
   contiguous-index rule to different domain inputs.
2. Add focused graph tests for non-finite profile gaps and a below-mask sample
   that separates visible runs. Assert the exact plotted sample groups and
   verify that no segment bridges either gap.
3. Compare the smallest shared operation with the two current blocks. Record
   method lines and the assessment's AST decision score, accounting for a
   nested helper as the assessment defines it.
4. Keep a change only if the total method becomes simpler without hiding the
   distinct segmentation purposes or altering plotted segments. Otherwise
   retain both blocks and record why.
5. If implementation is justified, run:

   ```sh
   python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_access_view.py
   ```

6. Update the assessment and subsystem overview with the decision. Do not
   broaden this into a profile-sampling or performance study.

## Done when

The shared index-splitting operation is implemented with both segmentation
invariants characterized, or the two explicit blocks are retained because a
helper does not provide a net complexity reduction.

## Execution result

Added graph characterization for a profile with both non-finite-time and
non-finite-elevation gaps, and for an interior below-mask sample. Both tests
assert the exact plotted sample groups and passed against the existing
implementation.

The shared helper was rejected. Replacing the two current two-line split
blocks with one-line helper calls would require a two-line helper, leaving the
method's source size unchanged. The nested loops and decision score would also
remain unchanged, while the helper would add indirection. The explicit splits
therefore remain in place.

`_draw_elevation_graph` remains 119 lines with an AST decision score of 24.
The focused suite passed:

```text
python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_access_view.py
10 passed
```

**Status:** Complete; retain the explicit segmentation blocks.
