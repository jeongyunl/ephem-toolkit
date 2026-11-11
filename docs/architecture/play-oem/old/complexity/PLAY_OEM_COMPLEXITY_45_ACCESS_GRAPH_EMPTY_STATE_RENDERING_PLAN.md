# play-oem — Access-Plot Empty-State Rendering Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior local rendering review:
[PLAY_OEM_COMPLEXITY_42_SKY_PLOT_EMPTY_STATE_RENDERING_PLAN.md](./PLAY_OEM_COMPLEXITY_42_SKY_PLOT_EMPTY_STATE_RENDERING_PLAN.md).

## Goal

Assess whether repeated centered status-message rendering in
`GroundStationAccessView._draw_elevation_plot` can reuse local text options
without changing message selection, precedence, axes state, or plot behavior.
This is a local rendering review, not a view split or a shared empty-state
framework.

## Evidence and hypothesis

`_draw_elevation_plot` is 82 lines with an AST decision score of 15. It has
five `axes.text` calls with the same centered alignment and axes-relative
transform: no stations, OEM not loaded, no data in the applied Plot Range, no
selected station, and an unavailable profile or result limitation. The direct
access-view tests currently assert the exact text for the no-stations and
no-data-in-Plot-Range cases; they do not pin the other messages or shared
presentation options.

The state order is significant. No stations and unloaded OEM turn the axes
off. With an OEM loaded, the view turns axes on, then checks the applied range
before station selection and profile availability. The profile branch displays
the result limitation when present, otherwise the generic unavailable message.

**Hypothesis:** a local `status_text_kwargs` mapping, as used in Plan 42, can
remove repeated presentation arguments while leaving each status call and its
state branch in place. Reject the change if it obscures the state order, adds
decisions or helper indirection, or does not reduce the method's source size.

## Scope and invariants

- Inspect only `_draw_elevation_plot` and direct tests in
  `test_ground_station_access_view.py`.
- Preserve all message text and selection precedence, including the
  result-specific limitation.
- Preserve centered alignment and axes-relative positioning for all five
  message cases.
- Preserve axes-off behavior for the no-stations and unloaded-OEM states;
  preserve axes-on behavior for loaded-OEM states.
- Preserve plot clearing, labels, limits, grid, `tight_layout`, time-range
  application, and canvas refresh.
- Do not change access-result preparation, interval annotations, profile
  sampling, view ownership, or panel lifecycle. Do not add a generic helper
  or message abstraction.

## Procedure

1. Trace the five status cases and record their exact condition order and
   axes-on/off behavior.
2. Verify existing test coverage. Add focused characterization for unpinned
   messages, precedence, and centered axes-relative placement as needed.
3. Compare the smallest local options mapping with the repeated arguments.
   Record method line count and AST decision score; do not treat line count
   alone as proof.
4. Keep a change only if it reduces repeated presentation code without adding
   decisions or indirection, and preserves every state and rendering
   invariant. Otherwise retain the current calls and record why.
5. If implementation is justified, run:

   ```sh
   python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_access_view.py
   ```

6. Update the assessment and subsystem overview with the decision. Do not
   broaden this into a whole-view decomposition or performance task.

## Done when

The status calls reuse a local set of centered text options with message
precedence and axes behavior preserved, or the repeated options are retained
because a candidate does not provide a net complexity reduction.

## Execution result

The five status calls now share one local `status_text_kwargs` mapping. The
message-selection branches and their order remain unchanged; no helper or
decision branch was added.

The characterization covers the no-stations state taking precedence over an
unloaded OEM, the unloaded-OEM message, an empty Plot Range taking precedence
over station selection, no selected station, the generic unavailable-profile
message, and a result-specific limitation. It also checks each message's
centered axes-relative placement and verifies that axes are off only for the
no-stations and unloaded-OEM states.

`_draw_elevation_plot` decreased from 82 to 77 source lines; its AST decision
score remained 15.

```text
python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_access_view.py
5 passed
```

**Status:** Complete; retain the shared local text options.
