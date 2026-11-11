# play-oem — Sky-Plot Empty-State Rendering Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior local simplification:
[PLAY_OEM_COMPLEXITY_41_PASS_ENDPOINT_LOOK_ANGLE_POLICY_PLAN.md](./PLAY_OEM_COMPLEXITY_41_PASS_ENDPOINT_LOOK_ANGLE_POLICY_PLAN.md).
Prior view-boundary assessment:
[PLAY_OEM_COMPLEXITY_11_LARGE_GUI_VIEW_RESPONSIBILITIES_PLAN.md](./PLAY_OEM_COMPLEXITY_11_LARGE_GUI_VIEW_RESPONSIBILITIES_PLAN.md).

## Goal

Assess whether the repeated centered status-message rendering in
`GroundStationPassesView._draw_sky_plot` can be consolidated without changing
which message is selected, when a sky path is drawn, or the view's ownership
boundaries. This is a local rendering review, not a view split or a new message
framework.

## Evidence and hypothesis

`_draw_sky_plot` contains five status-message cases: an unavailable selected
path, no selected station, no loaded OEM, a station-result limitation, and no
selected interval. Each uses the same centered `axes.text` presentation
arguments, while the conditions and their precedence express distinct states.
The method remains 172 lines with an AST decision score of 27 in the latest
package-wide source snapshot. Existing pass-view tests cover sky-plot behavior,
but do not appear to assert these message strings or their precedence.

**Hypothesis:** rendering boilerplate may be consolidated locally to reduce
repeated presentation code while leaving state selection visible and ordered
as it is now. Reject the change if it adds indirection or decisions without a
clear reduction in total implementation size and reasoning.

## Scope and invariants

- Inspect only `_draw_sky_plot` and direct tests in
  `test_ground_station_passes_view.py`.
- Preserve message text, centered alignment, axes transform, and every state's
  existing precedence.
- Preserve the selected-path rendering branch, including the unavailable-path
  message only when no valid path segment was plotted.
- Preserve the early return when axes or figure are absent, all plot clearing
  and styling, marker behavior, and legend behavior.
- Do not change endpoint normalization, profile sampling, pass selection,
  access-query preparation, view ownership, or panel lifecycle.
- Do not add a generic empty-state abstraction or split the view.

## Procedure

1. Trace the five message cases and document their condition order, including
   the nested unavailable-path case in the selected-pass rendering branch.
2. Check which messages and precedence rules are covered by existing tests.
   Add characterization only for unpinned behavior needed to compare a
   candidate.
3. Compare the smallest local consolidation with the current repeated
   `axes.text` calls. Count added indirection and compare the combined source
   lines and AST decision score; do not treat line count alone as proof.
4. Keep a change only if it reduces repeated presentation code without
   changing state selection or increasing combined decision score. Otherwise
   retain the current calls and record the reason.
5. If implementation is justified, run:

   ```sh
   python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_passes_view.py
   ```

6. Update the assessment and subsystem overview with the decision. Do not
   broaden this into a platform-validation or whole-view decomposition task.

## Done when

The centered message rendering is consolidated with state precedence and plot
behavior preserved, or the repeated calls are retained because a candidate
adds complexity or obscures the distinct states.

## Execution result

The five message cases and their precedence were retained inline. A single
local `status_text_kwargs` mapping now supplies the shared centered alignment
and axes transform to each call; no helper or new decision branch was added.
The selected-path-unavailable case remains nested in the selected-pass branch,
and the message-selection `if`/`elif` chain is unchanged.

The test characterization pins the exact message for each case, verifies that
no status message is drawn for a valid path, and checks centered alignment and
axes-relative positioning. The method decreased from 172 to 157 source lines;
its AST decision score remained 27.

```text
python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_passes_view.py
28 passed, 1 skipped
```

**Status:** Complete; retain the shared local text options.
