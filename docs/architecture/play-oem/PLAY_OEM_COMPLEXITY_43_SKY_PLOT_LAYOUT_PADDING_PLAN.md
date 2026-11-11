# play-oem — Sky-Plot Layout Padding Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior sky-plot simplification:
[PLAY_OEM_COMPLEXITY_42_SKY_PLOT_EMPTY_STATE_RENDERING_PLAN.md](./PLAY_OEM_COMPLEXITY_42_SKY_PLOT_EMPTY_STATE_RENDERING_PLAN.md).

## Goal

Assess whether `GroundStationPassesView._draw_sky_plot` can share the repeated
subplot padding setup between its legend and no-legend branches without
changing layout, legend behavior, or redraw order. This is a local duplication
review, not a broader plotting abstraction or view split.

## Evidence and hypothesis

`_draw_sky_plot` is currently 157 lines with an AST decision score of 27. Its
legend and no-legend branches each call `figure.subplots_adjust` with the same
left, right, and top values; only the bottom margin differs (`0.28` with a
legend, `0.08` without one). The legend is created and marked out of layout
before the adjustment in the legend branch. Playback-marker update and canvas
redraw follow either branch.

The focused tests verify the legend geometry and the `0.28` bottom margin in
the normal plotted case. They do not appear to pin the no-legend `0.08` margin.

**Hypothesis:** initialize the bottom margin to `0.08`, set it to `0.28` in the
existing legend branch, and perform one shared `subplots_adjust` after that
branch. This should remove one duplicated layout call without adding a
decision point. Reject the change if it alters exact margins, legend ordering,
or the method's decision score.

## Scope and invariants

- Inspect only `_draw_sky_plot` and direct tests in
  `test_ground_station_passes_view.py`.
- Preserve legend detection, creation, placement, labels, and
  `legend.set_in_layout(False)` ordering.
- Preserve `left=0.08`, `right=0.92`, `top=0.92`, and `bottom=0.28` with a
  legend or `bottom=0.08` without one.
- Preserve playback-marker update and canvas redraw after layout adjustment.
- Do not change sky-path rendering, empty-state messages, endpoint policy,
  panel sizing, or view ownership.
- Do not add a helper or configurable layout abstraction.

## Procedure

1. Trace the legend and no-legend branch, including the ordering of legend
   creation, layout adjustment, marker update, and redraw.
2. Verify existing coverage for both bottom-margin values. Add a focused
   no-legend characterization only if that state is not already pinned.
3. Compare one shared adjustment call with the existing two-call structure.
   Record method line count and AST decision score before and after.
4. Keep a change only if it removes duplicated setup without changing exact
   layout behavior or increasing the decision score. Otherwise retain the
   current branches and record why.
5. If implementation is justified, run:

   ```sh
   python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_passes_view.py
   ```

6. Update the assessment and subsystem overview with the decision. Do not
   broaden this into a platform-validation or whole-view decomposition task.

## Done when

The subplot adjustment is shared with exact legend/no-legend layout preserved,
or the existing two calls are retained because consolidation does not reduce
complexity.

## Execution result

The legend branch still creates the legend and calls
`legend.set_in_layout(False)` before layout adjustment. It now selects the
bottom margin (`0.28` with a legend, otherwise `0.08`), then shares one
`figure.subplots_adjust` call for the unchanged left, right, and top values.
Playback-marker update and canvas redraw remain after layout adjustment.

The no-legend margin characterization passed against the original two-call
implementation before the change. The focused pass-view suite then passed with
both margin cases and existing legend geometry coverage:

```text
python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_passes_view.py
29 passed, 1 skipped
```

`_draw_sky_plot` decreased from 157 to 152 source lines; its AST decision score
remained 27. The candidate removed one duplicated adjustment block without
adding a decision point or helper.

**Status:** Complete; retain the shared subplot adjustment.
