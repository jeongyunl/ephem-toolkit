# `play-oem` — GUI Improvement Plan

Source: review of the running wxPython application after the migration recorded in
[PLAY_OEM_GUI_COMPLETION_REPORT.md](./PLAY_OEM_GUI_COMPLETION_REPORT.md). Requirements:
[PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md). Selected layout:
[PLAY_OEM_GUI_DESIGN.md](./PLAY_OEM_GUI_DESIGN.md). Architecture:
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md).

## How to use this plan

Work **one pending numbered step at a time, in order**. Do not begin a later pending step until
the current step's checklist and completion criteria pass. Each dependency field names its
prerequisite. Step 1 has no dependency.

When a step is complete, move its full entry to `Completed steps` at the end of this document,
keeping its number, status, progress, checklist, completion criteria, and dependency for audit.

Status values:

- `Not started` — no work begun.
- `In progress` — implementation or its checks are underway.
- `Blocked` — cannot proceed; record the blocker.
- `Done` — all checklist items and completion criteria pass.

Progress is the number of checklist items completed. Do not mark a step done based only on code
being written.

## Milestone G — Post-migration usability fixes

Each step records an observation from the running application. Observations are hypotheses until
the reproduction checklist in the step confirms them.

### 1. Fix Playback toggle event bindings

`Reverse` and the speed-preset buttons in [control_window.py](/Users/jeongyun/Projects/ephem-toolkit/src/ephem_toolkit/play_oem/control_window.py)
are `wx.ToggleButton` widgets bound to `wx.EVT_BUTTON`. wxPython emits `wx.EVT_TOGGLEBUTTON` for
toggle buttons, so a real click may never reach these handlers. The focused tests trigger
`EVT_BUTTON` directly, so they pass without exercising a real click. This is the same binding
mistake that was fixed for the feature rail.

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Reproduce in the running app: click `Reverse` and each speed preset, and record whether the
      direction label and playback speed change.
- [ ] Bind `wx.EVT_TOGGLEBUTTON` for `Reverse` and the speed-preset buttons.
- [ ] Update [test_play_oem_control_window.py](/Users/jeongyun/Projects/ephem-toolkit/tests/ephem_toolkit/play_oem/test_play_oem_control_window.py)
      so these buttons are triggered with the event a real click emits.
- [ ] Run `tests/ephem_toolkit/play_oem` and confirm all tests pass.

**Done when:** a real click on `Reverse` and on each speed preset changes the direction or speed,
and the tests exercise the same event.
**Depends on:** None.

### 2. Make every Playback control visible or reachable

In the Controls & Info column, the seek row, the Seek button, `-1 min`, `+1 min`, `Next sample`,
`End`, the speed label, and the speed presets are clipped at the rail width. Labels and buttons
are fixed-width and do not wrap. The fix should allow the Playback page to scroll or wrap, and set
the left pane's minimum width from the widest required row.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Measure the minimum width of each Playback row at the default window size.
- [ ] Choose scrolling or wrapping for the Playback page based on the measurements, and record the
      decision here.
- [ ] Apply the layout change in [control_window.py](/Users/jeongyun/Projects/ephem-toolkit/src/ephem_toolkit/play_oem/control_window.py)
      and, if needed, the left-pane sizing in [workspace.py](/Users/jeongyun/Projects/ephem-toolkit/src/ephem_toolkit/play_oem/workspace.py).
- [ ] Verify at the default and minimum window sizes that every control is visible or reachable.
- [ ] Add a layout test that asserts the seek field and the Seek button are reachable.

**Done when:** no Playback control is clipped at the default size, and every control is reachable
by keyboard at the minimum size.
**Depends on:** None.

### 3. Reproduce and fix the black 3D Orbit render area

The 3D Orbit panel shows only the lower-left part of the scene, with a hard rectangular edge, and
the rest is black. This suggests the VTK drawable and the widget disagree on size after layout,
possibly on a HiDPI display. This is unverified.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Reproduce at the default size, then resize the window and toggle Comparison, capturing a
      screenshot at each step.
- [ ] Compare the VTK render-window size and drawable size with the widget size, including the
      display scale factor, in [vtk_backend.py](/Users/jeongyun/Projects/ephem-toolkit/src/ephem_toolkit/play_oem/views/trajectory3d/vtk_backend.py).
- [ ] Fix the sizing or the re-render-on-size-change path in `vtk_backend.py` and, if needed,
      [graph_panel.py](/Users/jeongyun/Projects/ephem-toolkit/src/ephem_toolkit/play_oem/graph_panel.py).
- [ ] Verify the full scene draws after resize, after toggling Comparison, and after reopening.
- [ ] Run the VTK-related focused tests.

**Done when:** the 3D Orbit fills its panel at the default and resized window sizes, with no black
region.
**Depends on:** Step 2 (the left-column width changes the 3D host size during reproduction).

### 4. Remove truncated label and button text

The following text is cut off at the default size: `UTC: 2026-07-06T00:00:00`,
`Playback speed (log …`, `Previou...`, `State C...`, and `Seek to elapsed time or UTC:`.

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Shorten the button labels, and move longer descriptions into tooltips or hints.
- [ ] Ensure the UTC value fits or wraps inside the Info column.
- [ ] Verify no label or button text is truncated at the default size.
- [ ] Update tests that assert these labels, and keep accessible names consistent with the visible
      labels.

**Done when:** no label or button text is cut off at the default size, and the test assertions
match the visible text.
**Depends on:** Step 2.

### 5. Make toggle button states visually unambiguous

`Reverse` and `Comparison` both appear pressed in the screenshot, while playback is forward and the
Comparison pane is hidden. `Comparison` is synchronized in `show_right_pane`, so this may be the
native macOS bezel style rather than a state mismatch. This is unverified.

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Check `Reverse` at start and after each direction change, and `Comparison` before and after
      each show/hide, comparing the visual state with the logical state.
- [ ] Choose one visual cue for on/off that is consistent across `Reverse`, the speed presets, and
      `Comparison`.
- [ ] Apply the chosen cue in the affected controls.
- [ ] Verify the visual states match the logical states in the running app and in tests.

**Done when:** each toggle's visual state matches its logical state, and the same cue is used
across all toggles.
**Depends on:** Step 1.

### 6. Remove duplicate graph header labels

Each graph stack header repeats its selector name: `3D Orbit` appears in the dropdown and again as
a label, and `Speed / Altitude` appears in the same way.

- **Status:** Not started.
- **Progress:** 0/3 checklist items.
- [ ] Decide whether to remove the label or replace it with useful status, such as units or the
      data span.
- [ ] Update the header code in [workspace.py](/Users/jeongyun/Projects/ephem-toolkit/src/ephem_toolkit/play_oem/workspace.py)
      and any tests that look up these labels.
- [ ] Verify the headers at the default size and run the focused tests.

**Done when:** no graph header repeats its selector name, and the tests pass.
**Depends on:** None.

### 7. Make clipped graph stacks visibly scrollable

The Speed/Altitude stack is clipped at the bottom, and its second plot is cut off with no visible
cue that more content exists. The stacks scroll in code, but the affordance is not visible with
macOS overlay scrollbars.

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Confirm that scrolling a stack reaches the lowest plot.
- [ ] Choose a visible cue, such as always-visible scrollbars for graph stacks or another visible
      indicator, and record the decision here.
- [ ] Apply the cue in [workspace.py](/Users/jeongyun/Projects/ephem-toolkit/src/ephem_toolkit/play_oem/workspace.py).
- [ ] Verify scrolling with the mouse wheel and the keyboard.

**Done when:** the lowest plot in each stack is reachable, and a visible cue shows when content
extends below the visible area.
**Depends on:** Step 6 (header changes alter stack heights).

### 8. Add time labels to the timeline

The shared timeline in [workspace.py](/Users/jeongyun/Projects/ephem-toolkit/src/ephem_toolkit/play_oem/workspace.py)
is a bare slider, with no time readout or ticks.

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Show start, current, and end times, using elapsed time or UTC consistently with the Info
      column.
- [ ] Keep the timeline in the workspace footer, outside feature pages, so label updates do not
      trigger seek events.
- [ ] Verify the labels update during playback without emitting a seek.
- [ ] Run the focused tests.

**Done when:** the timeline shows start, current, and end times that update during playback, and
label updates do not emit seek events.
**Depends on:** None.

## Completed steps

None yet.
