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

### 1. Fix Playback toggle event bindings

`Reverse` and the speed-preset buttons were `wx.ToggleButton` widgets bound to `wx.EVT_BUTTON`.
Change them to `wx.EVT_TOGGLEBUTTON`, and exercise that event in tests. The user confirmed in the
running app that Reverse and the speed presets work as designed.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Reproduce in the running app: click `Reverse` and confirm the direction behaves as designed.
- [x] Reproduce in the running app: click each speed preset and confirm playback speed changes.
- [x] Bind `wx.EVT_TOGGLEBUTTON` for `Reverse` and the speed-preset buttons.
- [x] Update [test_play_oem_control_window.py](/Users/jeongyun/Projects/ephem-toolkit/tests/ephem_toolkit/play_oem/test_play_oem_control_window.py)
      so these buttons are triggered with the event a real click emits.
- [x] Run `tests/ephem_toolkit/play_oem` and confirm all tests pass (154 passed).

**Done when:** a real click on `Reverse` and on each speed preset changes the direction or speed,
and the tests exercise the same event.
**Depends on:** None.

### 2. Make every Playback control visible or reachable

The Playback controls were arranged in wide horizontal rows that exceeded the available Controls
& Info width. The fix uses a vertically scrollable Playback page with keyboard focus scrolling.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Measure the Playback viewport at default and minimum frame sizes and check control bounds.
- [x] Choose vertical scrolling with single-column control rows; wrap long static labels to the
      available content width.
- [x] Apply the layout and keyboard-focus scrolling in
      [control_window.py](/Users/jeongyun/Projects/ephem-toolkit/src/ephem_toolkit/play_oem/control_window.py).
- [x] Verify at the default (1100 x 760) and minimum (920 x 480) frame sizes that no interactive
      Playback control overflows horizontally and off-screen controls scroll into view on focus.
- [x] Add layout and focus-scroll tests that cover the seek field and the Seek button.

**Done when:** no Playback control is clipped at the default size, and every control is reachable
by keyboard at the minimum size. Native wx geometry and focus-event checks passed; the full
`tests/ephem_toolkit/play_oem` suite reports 154 passed.
**Depends on:** None.

### 3. Investigate the black 3D Orbit render area

The screenshot showed only part of the 3D Orbit scene against a mostly black panel. The issue was
not reproduced in the current native wx/VTK environment using `JPSS-1_small.oem`; no speculative
VTK sizing change was made. The original screenshot could still reflect a dataset- or
startup-specific condition.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Exercise default and minimum window sizes, then open and close Comparison using the normal wx
      event loop.
- [x] Compare VTK widget dimensions with render-window dimensions and the display scale factor:
      widget sizes were 843 x 599, 663 x 319, and 514 x 599; render-window sizes were 1686 x 1198,
      1326 x 638, and 1028 x 1198, respectively, at scale factor 2.0.
- [x] Do not change VTK sizing because the issue did not reproduce and the render-window dimensions
      tracked the widget at the expected HiDPI scale.
- [x] Verify rendered buffers after each layout change: no exact-black pixels, foreground scene
      pixels present, and `GetNeverRendered()` remained 0.
- [x] Run the VTK and `play-oem` tests; the full suite passed (154 passed).

**Done when:** native VTK rendering fills the panel after resize and Comparison changes without a
black region. This was verified in the current environment; the screenshot-specific condition
remains unconfirmed.
**Depends on:** None.

### 4. Remove truncated label and button text

Playback controls, time readouts, and OEM metadata were clipped at the narrow Controls & Info
width. Step 2 made button controls occupy individual rows; this step wraps long static text to each
pane's available width.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Keep the full button labels; native best-size measurements showed the longest label fits the
      available control width, so shortening would remove useful information unnecessarily.
- [x] Wrap the UTC value, playback-speed description, seek prompt, and OEM metadata labels to the
      current pane width.
- [x] Verify default and minimum window sizes: no Playback button overflows; the UTC, speed, seek,
      and metadata text widgets wrap to the available width.
- [x] Test Playback wrapping and OEM metadata wrapping, preserving full visible labels and
      accessible control names.

**Done when:** no label or button text is cut off at the default size, and the test assertions
match the visible text. Native wx geometry showed button best sizes at or below the available
width; focused and full-suite tests passed (155 passed).
**Depends on:** Step 2.
