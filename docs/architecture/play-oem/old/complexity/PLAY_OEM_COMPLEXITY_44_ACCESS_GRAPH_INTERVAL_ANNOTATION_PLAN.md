# play-oem — Access-Graph Interval Annotation Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior local plot simplifications:
[PLAY_OEM_COMPLEXITY_42_SKY_PLOT_EMPTY_STATE_RENDERING_PLAN.md](./PLAY_OEM_COMPLEXITY_42_SKY_PLOT_EMPTY_STATE_RENDERING_PLAN.md) and
[PLAY_OEM_COMPLEXITY_43_SKY_PLOT_LAYOUT_PADDING_PLAN.md](./PLAY_OEM_COMPLEXITY_43_SKY_PLOT_LAYOUT_PADDING_PLAN.md).

## Goal

Assess whether `GroundStationAccessView._draw_elevation_graph` can select an
interval annotation's label and hatch from one gap/coverage classification
without changing interval spans, legend de-duplication, or rendering behavior.
This is a local policy review, not a graph rewrite or a shared plotting
framework.

## Evidence and hypothesis

`_draw_elevation_graph` is currently 122 lines with an AST decision score of
26. In its `has_line` branch, it calculates `gap_limited` and
`coverage_limited`, then independently encodes gap-over-coverage precedence in
nested conditional expressions for the legend label and hatch. The current
mapping is:

| Classification | Label | Hatch |
| --- | --- | --- |
| Any gap-limited endpoint | `Gap-limited access` | `xx` |
| Otherwise, any coverage-clipped endpoint | `Coverage-limited access` | `//` |
| Neither | `Access interval` | none |

When both flags are true, gap limitation takes precedence. `interval_labels`
suppresses repeated legend labels but does not suppress interval spans. The
direct access-view tests cover graph rendering, mask clipping, and range
behavior, but do not appear to assert these annotation labels or hatches.

**Hypothesis:** an explicit `if`/`elif`/`else` can select the label and hatch
pair once, replacing the two separate nested conditional expressions. The
candidate should reduce the method's AST decision score and remove duplicated
precedence logic without introducing a helper. Reject it if the clearer pairing
does not lower decision complexity or if it obscures the gap-first rule.

## Scope and invariants

- Inspect only `_draw_elevation_graph` and direct tests in
  `test_ground_station_access_view.py`.
- Preserve the mapping and gap-over-coverage precedence shown above,
  including when both flag categories apply.
- Preserve one legend entry per distinct label while drawing every interval
  span.
- Preserve span bounds, color, alpha, playback cursor, profile clipping,
  station-mask behavior, and the no-visible-elevation empty state.
- Do not change access-interval construction, cached profile ownership,
  playback behavior, panel/view ownership, or other graph styling.
- Do not add a generic annotation abstraction or helper.

## Procedure

1. Trace the annotation block inside the `has_line` branch and confirm the
   existing precedence and label de-duplication behavior.
2. Add focused characterization for the complete, coverage-limited,
   gap-limited, and combined gap-plus-coverage cases. Include repeated
   classifications to pin legend de-duplication while verifying each interval
   still gets a span.
3. Compare the smallest paired label/hatch selection with the two current
   conditional expressions. Record method line count and AST decision score
   using the assessment's indicator.
4. Keep a change only if it reduces the duplicated decision policy without
   increasing the method's AST score or altering the rendering invariants.
   Otherwise retain the current expressions and record why.
5. If implementation is justified, run:

   ```sh
   python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_access_view.py
   ```

6. Update the assessment and subsystem overview with the decision. Do not
   broaden this into a profile-sampling or performance study.

## Done when

The interval label and hatch use one tested classification with gap precedence
and legend de-duplication preserved, or the current expressions are retained
because a paired selection does not provide a net complexity reduction.

## Execution result

The annotation branch now selects the label and hatch together with one
gap-first `if`/`elif`/`else`. It preserves the complete, coverage-limited,
gap-limited, and combined mappings. Each interval still draws its own span;
`interval_labels` still suppresses only repeated legend entries.

Added a characterization test for all four classifications and a repeated
gap-limited interval. It verifies the hatch and label for each span, including
gap precedence when both flag categories apply, and passed against the
original conditional expressions before the implementation change. The full
focused suite passed afterward:

```text
python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_access_view.py
5 passed
```

`_draw_elevation_graph` decreased from 122 to 119 lines; its AST decision score
decreased from 26 to 24. The paired selection removes two conditional
expressions without adding a helper or changing the rendering path.

**Status:** Complete; retain the paired annotation classification.
