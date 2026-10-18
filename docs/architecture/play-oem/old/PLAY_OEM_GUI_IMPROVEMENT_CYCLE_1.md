# `play-oem` — GUI Improvement Cycle 1: Completion Report

This report records the first post-migration GUI improvement cycle for the wxPython `play-oem`
application. All nine items in this cycle are complete. The next cycle, focused on Controls & Info,
is recorded in
[PLAY_OEM_GUI_IMPROVEMENT_CYCLE_2.md](./PLAY_OEM_GUI_IMPROVEMENT_CYCLE_2.md); this document remains
the historical record of cycle 1.

The review was based on the running application and the migration recorded in
[PLAY_OEM_GUI_COMPLETION_REPORT.md](./PLAY_OEM_GUI_COMPLETION_REPORT.md). Requirements:
[PLAY_OEM_CONCEPTS.md](../PLAY_OEM_CONCEPTS.md). Selected layout:
[PLAY_OEM_GUI_DESIGN.md](../PLAY_OEM_GUI_DESIGN.md). Architecture:
[PLAY_OEM_SOFTWARE_DESIGN.md](../PLAY_OEM_SOFTWARE_DESIGN.md).

## Cycle 1 outcomes

### 1. Corrected Playback toggle event bindings

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

**Outcome:** a real click on `Reverse` and each speed preset changes direction or speed, and the
tests exercise the same event.
**Related work:** None.

### 2. Made every Playback control visible or reachable

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

**Outcome:** no Playback control is clipped at the default size, and every control is reachable
by keyboard at the minimum size. Native wx geometry and focus-event checks passed; the full
`tests/ephem_toolkit/play_oem` suite reports 154 passed.
**Related work:** None.

### 3. Investigated the black 3D Orbit render area

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

**Outcome:** native VTK rendering filled the panel after resize and Comparison changes in the
current environment. The screenshot-specific condition was not reproduced and remains unconfirmed.
**Related work:** None.

### 4. Prevented truncated label and button text

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

**Outcome:** no label or button text is cut off at the default size, and the test assertions
match the visible text. Native wx geometry showed button best sizes at or below the available
width; focused and full-suite tests passed (155 passed).
**Related work:** Step 2.

### 5. Confirmed toggle button states are visually unambiguous

The screenshot made `Reverse` and `Comparison` appear pressed while forward playback was active
and the Comparison pane was hidden. Native state checks showed no mismatch: `Reverse` is false in
forward playback and true in reverse playback; Comparison's value follows the pane's shown state.
The speed presets and Comparison control use the same native `wx.ToggleButton` state cue, so no
custom visual styling was needed.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Check Reverse in forward and reverse playback and Comparison before and after showing or
      hiding its pane.
- [x] Keep the native pressed/unpressed cue shared by Reverse, speed presets, and Comparison.
- [x] Preserve the existing native style; no custom styling change was warranted after the state
      checks.
- [x] Assert Reverse and speed-preset values during playback updates and Comparison values after
      each pane transition; focused tests passed (26 passed).

**Outcome:** each toggle's state matches its logical state, and all use the same native visual
cue. Native wx state checks and focused tests passed.
**Related work:** Step 1.

### 6. Removed duplicate graph header labels

The graph-panel header showed its view name in both the selector and a neighboring static label.
The selector now serves as the graph name; panels without a selector retain their static title.

- **Status:** Done.
- **Progress:** 3/3 checklist items.
- [x] Keep the view selector as the graph name and remove the duplicate static label for panels
      that have a selector; retain the label when no selector is available.
- [x] Update [graph_panel.py](/Users/jeongyun/Projects/ephem-toolkit/src/ephem_toolkit/play_oem/graph_panel.py).
      No existing tests looked up the removed labels.
- [x] Verify the selector and fallback title in native wx at the default 1100 x 760 frame size;
      run the focused graph-panel and app tests (34 passed).

**Outcome:** no graph header repeats its selector name, and the tests pass. At default size the
selector remained visible at 908 px wide; a panel without choices retained its title.
**Related work:** None.

### 7. Made clipped graph stacks visibly scrollable

The Speed/Altitude stack was clipped at the bottom with no visible cue that more content existed;
macOS overlay scrollbars hid the affordance. The graph stacks now force their vertical scrollbars
to remain visible only while content overflows. The user confirmed in the running app that the
scrollbar is visible when needed, the mouse wheel scrolls, and keyboard navigation reaches lower
plots.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Confirm that scrolling a stack reaches the lowest plot.
- [x] Use always-visible vertical scrollbars; the user selected this cue.
- [x] Apply the cue in [workspace.py](/Users/jeongyun/Projects/ephem-toolkit/src/ephem_toolkit/play_oem/workspace.py)
      by forcing the vertical scrollbar only when the stack's scroll range exceeds its thumb.
- [x] Verify the scrollbar is visible without scrolling when content overflows, hidden when it
      fits, and confirm mouse-wheel and keyboard scrolling in the running app; workspace tests
      passed (14 passed).

**Outcome:** the lowest plot in each stack is reachable, and a visible cue shows when content
extends below the visible area. Native wx range checks and the user's running-app confirmation
verified the behavior. At default size, one- and two-panel stacks hide the scrollbar; at minimum
size, the two-panel stack shows it; returning to default hides it again.
**Related work:** Step 6 (header changes alter stack heights).

### 8. Added time labels to the timeline

The shared timeline in [workspace.py](/Users/jeongyun/Projects/ephem-toolkit/src/ephem_toolkit/play_oem/workspace.py)
was a bare slider with no time readout. It now shows start, current, and end UTC times, matching
the Info column's ISO 8601 format.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Show start, current, and end times in UTC, matching the Info column's ISO 8601 timestamps.
- [x] Keep the timeline in the workspace footer, outside feature pages, so label updates do not
      trigger seek events.
- [x] Verify the current label updates with playback while programmatic slider synchronization
      emits no seek.
- [x] Run the workspace and app tests (44 passed) and check label widths at default (1100 x 760)
      and minimum (920 x 480) frame sizes; all labels fit.

**Outcome:** the timeline shows start, current, and end times that update during playback, and
label updates do not emit seek events. Workspace tests verified seek suppression and native wx
geometry checks confirmed all three timestamps fit at both frame sizes.
**Related work:** None.

### 9. Preserved graph-stack scroll position when changing views

Changing a panel's selected graph view should replace that panel in place instead of removing it
and appending a new panel. Preserve the panel's stack position and the user's vertical scroll
offset across the change.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Replace the existing graph host in its splitter slot without rebuilding the stack.
- [x] Keep the prior view alive until the replacement has been created successfully; restore it if
      creation fails.
- [x] Test root and nested-splitter replacement, panel ordering, and scroll-offset preservation.
- [x] Run the focused workspace, graph-panel, and app tests (**52 passed**) and verify a native wx
      replacement at a nonzero offset.

**Outcome:** changing a panel's graph view leaves it in the same stack position and retains the
current scroll offset. Tests passed, and native wx preserved the offset at `(0, 5)`.
**Related work:** Step 5 (independent per-panel view selection).
