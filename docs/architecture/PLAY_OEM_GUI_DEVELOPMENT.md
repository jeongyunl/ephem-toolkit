# `play-oem` — GUI Development and Improvement

This document guides implementation, validation, and iterative improvement of the
`play-oem` graphical interface. It complements, rather than replaces:

- [PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md), the user-facing requirements and terminology.
- [PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md), the software architecture,
  component contracts, backend decisions, and technical constraints.
- [PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md), the dependency-ordered
  implementation sequence and completion evidence.

Keep those documents authoritative for their respective subjects. Update this guide when the
GUI workflow, validation approach, or improvement priorities change.

## Current GUI direction

`play-oem` is a wxPython application with one `wx.App` and event loop. wx owns the control
window, plot frames, timers, and native controls. Matplotlib plots use WxAgg; the 3D trajectory
may use the optional VTK wx integration when it initializes successfully. The playback clock,
cursor lookup, data loading, and series computation remain independent of the GUI toolkit.

The default startup experience is the compact Overview: a 3D trajectory and a speed/altitude
plot, with playback controls and current-state context in the main control window. Additional
views can be opened independently or as groups. The implementation details and current contracts
are maintained in the software design document.

The current Matplotlib cursor update path uses `canvas.draw_idle()` full redraws. Partial WxAgg
bitmap blitting was removed after click-to-seek produced duplicated and mispositioned plot
content in the reported macOS UI. The automated regression check verifies that cursor updates
request full redraws rather than partial blits; it does not replace visual verification in the
running application.

## Development workflow

For each GUI change:

1. **Identify the user-facing requirement.** Link the change to a requirement in the concepts
   document or record the accepted scope in the implementation plan. Do not change playback or
   data semantics as a side effect of a presentation change.
2. **Trace the existing GUI path.** Follow the relevant event from its wx control or Matplotlib
   callback through the application and playback clock to the view update. Reuse the existing
   clock, cursor, view protocol, registry, and lifecycle patterns.
3. **Keep work on the wx UI thread.** Update widgets, Matplotlib artists, and VTK actors through
   the application's wx event loop. Avoid adding another GUI loop or allowing queued frames to
   accumulate.
4. **Separate model behavior from presentation.** Keep time conversion, cursor lookup, and
   derived data testable without a display. Keep view rendering and wx event handling in their
   existing GUI layers.
5. **Add focused automated coverage.** Test event-to-action wiring, synchronization, redraw
   requests, invalid-input behavior, and view lifecycle as applicable. Use headless Matplotlib
   tests for backend-independent behavior and a display-backed wx test environment for wx
   integration.
6. **Run a manual interaction check for visible behavior.** Exercise the affected window with
   realistic OEM data. Verify that the change is perceivable and that plot interaction, keyboard
   focus, and window lifecycle remain usable.
7. **Record evidence and limitations.** Update the implementation-plan checklist and evidence.
   Distinguish automated results, manual observations, and platform/backend measurements; do
   not generalize a single host's result to untested platforms.

## GUI validation checklist

Use the checks relevant to the change; complete the broader release checks in implementation
plan Step 28.

### Controls and synchronization

- Play, pause, reverse, speed changes, stepping, seeking, and end-of-range behavior remain
  synchronized across the control window and every open view.
- Timeline dragging and click-to-seek move the shared cursor to the expected time. Seeking does
  not change playback speed or direction.
- Direct time entry accepts supported formats; invalid input is clearly reported and does not
  move the cursor.
- Keyboard shortcuts work when appropriate and do not intercept typing while an editable field
  has focus.
- The time slider reflects clock changes without recursively triggering additional seeks.

### Plot interaction and data honesty

- Click-to-seek changes only the requested time; repeated clicks do not duplicate, offset, or
  otherwise corrupt plotted content.
- Matplotlib navigation modes do not accidentally convert zoom/pan gestures into seeks.
- Views remain synchronized after seeking in either direction and when opened during playback.
- OEM segment gaps are visible and are not drawn or interpolated across. Readouts identify
  sampled, interpolated, gap, or unavailable state as appropriate.
- Units, reference frame, and altitude assumptions remain clear in axes and readouts.

### Layout and lifecycle

- Default Overview and requested individual/group views open without duplicate windows.
- Existing windows are raised when their view is requested again.
- Closing one plot does not stop playback or close other views; closing the control window shuts
  down timers, subscriptions, plot frames, and the wx event loop cleanly.
- Resizing and moving windows does not hide controls, clip important readouts, or corrupt plots.
- Error messages for unavailable wxPython, Matplotlib, or explicitly requested VTK are actionable.

### Responsiveness and portability

- Measure the user-visible playback update rate with the documented workload and distinguish it
  from renderer-only or headless throughput.
- Check that UI input remains responsive under high playback rates and with large OEM histories.
- Check the selected 3D backend's initialization and rendering on each supported platform before
  claiming cross-platform support.
- Record operating system, Python and dependency versions, backend, dataset, view selection,
  playback rate, run duration, and measurement method for performance results.

## Improvement priorities

Treat these as ordered investigation areas, not authorization to change requirements or weaken
correctness. Implement a change only after establishing the current behavior and its acceptance
criterion.

### 1. Re-establish the performance baseline

The existing native wx measurements in Step 27 and the software-design document predate the
switch from partial blitting to full `draw_idle()` redraws. They must not be treated as current
performance results. Re-run the all-view workload on the current path before deciding whether
the accepted below-target baseline still applies. Keep the N1 threshold and any acceptance or
deferral explicit.

Measure UI playback updates and interaction responsiveness separately. Include the exact host,
backend, synthetic or real OEM data, number of samples, open views, playback multiplier, run
duration, and counting method. A headless Agg render-loop result is not evidence of native wx UI
responsiveness.

### 2. Verify the click-to-seek correction visually

Exercise click-to-seek in each 2D time-series view in a live wx session. Check ordinary clicks,
repeated clicks, clicks near plot edges, and interaction while playback is active. Confirm that
zoom/pan toolbar modes retain their expected behavior. Record manual results separately from
automated redraw tests.

### 3. Improve usability from observed friction

Use manual checks and user feedback to identify problems with control discoverability, status
messages, slider precision, keyboard focus, layout, and the amount of information in the default
dashboard. Prioritize issues that prevent a required action or make state ambiguous. Avoid adding
controls or dashboard density without evidence that they solve a concrete usability problem.

### 4. Validate accessibility and platform behavior

Check keyboard-only operation, visible focus, control labels, readable sizing, and platform-native
behavior. Verify the wx/Matplotlib/VTK combination independently on macOS, Linux, and Windows.
Document unsupported or unverified behavior rather than assuming consistency across native
window systems and graphics contexts.

### 5. Revisit rendering optimizations only with evidence

If a current-path measurement shows a material responsiveness problem, profile the full update
path before optimizing. Preserve full-resolution data for cursor lookup, maintain the view
contract, and verify that any rendering optimization does not reintroduce corruption or stale
cursor positions. Re-run focused correctness tests and the same benchmark workload after a
change. Keep algorithmic or backend experiments out of the GUI interaction path unless evidence
shows they are needed.

## Completion evidence

A GUI improvement is complete when:

- The intended user-visible behavior is demonstrated or tested.
- Playback and data semantics, plot accuracy, and window lifecycle remain intact.
- Relevant focused tests pass; any manual checks are identified as manual rather than automated.
- Performance claims have reproducible workload details and match the current implementation.
- The implementation plan, software design, and concepts document are updated if the change
  affects their scope.
