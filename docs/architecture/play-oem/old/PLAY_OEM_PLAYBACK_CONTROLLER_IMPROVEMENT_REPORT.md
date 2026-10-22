# `play-oem` — Playback Controller Improvement Report

This report records the completed improvement cycle for the shared playback controller at the
bottom of the `play-oem` window. It follows the completion-evidence conventions in
[PLAY_OEM_IMPLEMENTATION_PLAN.md](../PLAY_OEM_IMPLEMENTATION_PLAN.md) and the GUI workflow in
[PLAY_OEM_GUI_DESIGN.md](./PLAY_OEM_GUI_DESIGN.md).

All five stages are complete: baseline inspection, mock-up design, design selection, implementation,
and focused verification. The selected centered controller is implemented above the shared
timeline slider, and the existing seek behavior and reverse-playback controls remain available.

## Objective and scope

The cycle designed and implemented a compact set of playback controls directly above the shared
time slider. The transport controls make reverse and forward play/pause and progressively faster
playback in either direction easy to discover and operate without displacing or making the timeline
harder to use.

In scope:

- Several distinct mock-ups for the compact transport cluster and its relationship to the slider.
- Evaluation of those mock-ups against usability, layout, accessibility, and platform-native
  control requirements.
- Selection and documentation of one final design before implementation.
- Implementation and focused verification of the selected control behavior and layout.

Out of scope:

- Changes to time seeking, timeline bounds, interpolation, clock accuracy, or view synchronization.
- Changes to reverse-playback semantics outside the new transport cluster.
- Changes to the playback speed range or command-line playback options.

## Required behavior

- Place a compact transport cluster immediately above the shared time slider at the bottom of the
  window.
- Provide ten controls in this order, from left to right: **1000× reverse**, **100× reverse**,
  **10× reverse**, **1× reverse speed**, **reverse Play/Pause**, **forward Play/Pause**,
  **1× forward speed**, **10× forward**, **100× forward**, **1000× forward**. Use progressively
  larger direction glyphs: `<<<`, `<<`, `<` for reverse and `>`, `>>`, `>>>` for forward.
- Keep the 1× reverse and forward speed selectors separate from the Play/Pause buttons. The 1×
  selectors set the signed playback speed to exactly 1× without changing whether playback is
  paused or running. Play buttons preserve the current speed magnitude: while playback is running
  in that button's direction, the button shows Pause (`Ⅱ`) and pauses playback when clicked;
  otherwise it selects that direction and plays or resumes at the current speed. Switching
  direction while playing does not change the speed.
- Clicking a directional speed button while paused selects that signed speed without starting
  playback. Clicking it while playing selects that signed speed and continues playback in that
  direction.
- Repeated clicks on a directional speed button increase the current speed by that button's
  magnitude while the current speed is within its progression range. For example, reverse 10×
  advances reverse playback from 10× to 20×, then 30×; clicking at 90× advances to 100×.
- If playback is below the button's base speed, in the opposite direction, or at/above the next
  tenfold boundary, clicking selects the button's signed base speed. The 1× speed buttons always
  select exactly 1× and do not use the repeated-increment behavior.
- Forward controls select positive speeds; reverse controls select negative speeds. Speed
  selectors do not start or pause playback. The Play/Pause buttons select their respective
  direction while preserving speed, and pause/resume playback. Preserve existing reverse-playback
  behavior outside this cluster.
- Communicate the selected speed and playing state with an accessible name and state indication;
  do not rely on icon shape or color alone.

The repeated-increment rule applies when the current selected playback speed has the same
direction as the clicked button, is at least the button's base speed, and is below the next
tenfold boundary. In that range, each click adds the button's magnitude, up to the clock's maximum
speed. At or above the boundary, or when selecting an opposite direction, the click selects the
button's base signed speed. The 1× selectors always select exactly 1×.

## Design and implementation constraints

1. Establish the current timeline layout and playback-clock API before proposing mock-ups.
2. Create multiple materially distinct mock-ups; do not implement a speculative layout before
   comparing alternatives.
3. Evaluate the alternatives against the criteria below and record the selected design and
   rationale before implementation.
4. Keep the slider's existing seek behavior, range, labels, and keyboard operation intact.
5. Use the existing playback clock and UI update paths; avoid a second timer or independent speed
   state.
6. Use native wx controls and preserve keyboard focus, accessible names, and clear active-state
   feedback.
7. Keep the implementation and user-facing design documentation consistent with the selected
   behavior; this report retains the completed checklists and verification evidence.
8. Keep reverse and forward controls visually grouped or otherwise clearly distinguished, and
   keep the 1× reverse and forward play/pause controls separate and clearly named.

## Mock-up evaluation criteria

Evaluate each mock-up for:

- Clear hierarchy and visual proximity among playback state, direction, speed choices, and the
  time slider.
- Readability and practical hit targets at the default and minimum window sizes.
- Unambiguous distinction between selecting a signed speed/direction and starting/pausing
  playback.
- Discoverability and feedback for repeated-click speed progression, direction selection, and
  speed capping.
- Keyboard and assistive-technology operation, including accessible names and selected/playing
  state.
- Compatibility with native wx control appearance and the current bottom timeline layout.
- Preservation of slider labels, seek affordance, and usable space for the application content.

## Steps

### 1. Establish the current controller baseline

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Trace the shared timeline and playback controls from layout construction through clock
      updates.
- [x] Record current frame and timeline dimensions, slider labels, play/pause state cues, and
      speed-setting behavior at default and minimum window sizes.
- [x] Identify existing clock methods and tests for setting speed, starting, pausing, and reaching
      timeline endpoints.
- [x] Record keyboard, accessibility, and platform-native constraints relevant to the new buttons.
- [x] Identify which current speed and transport controls are superseded, retained, or relocated by
      this proposal.

**Done when:** the current layout, behavior, dependencies, and compatibility constraints are
documented well enough to design without duplicating clock state or regressing seeking.
**Depends on:** None.

**Baseline:** `Workspace` owns the shared bottom timeline panel and slider; UTC start/current/end
labels are above the slider. `ControlWindow` currently owns Play, Reverse, speed presets, and the
logarithmic speed slider in the scrollable Playback feature page. `PlaybackClock` exposes
`toggle()`, `set_speed()` (preserving signed direction), `set_direction()`, and `reverse()`; the
application refreshes both feature-page state and the shared timeline through its existing update
path. The frame is 1100 × 760 px by default and 920 × 480 px minimum. Existing reverse remains
available in the Playback page and on the `R` accelerator. The new cluster will be added to the
timeline panel without changing slider bounds, labels, or seek handling.

### 2. Create alternative controller mock-ups

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Create at least three materially distinct mock-ups showing the controller above the bottom
      time slider.
- [x] Include all ten controls, directional glyphs, and the playing-state Pause icon in each
      applicable mock-up.
- [x] Show representative paused and forward/reverse playing states, including selected speed
      feedback.
- [x] Save mock-ups in the `play-oem` architecture documentation area and link them here.

**Done when:** at least three alternatives communicate the complete requested control set and its
relationship to the slider.
**Depends on:** Step 1.

**Alternatives:** [left-aligned cluster](../mockup-playback-controller-left.svg),
[centered compact cluster](../mockup-playback-controller-centered.svg), and
[single-row transport with speed status](../mockup-playback-controller-status.svg).

### 3. Evaluate mock-ups and select the final design

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Compare every mock-up against the evaluation criteria in this report.
- [x] Check each alternative at the default and minimum window sizes using the baseline dimensions.
- [x] Record the trade-offs and any rejected alternatives.
- [x] Select one design and document its control order, labels/icons, selected-state feedback, and
      placement.
- [x] Confirm that the selected design preserves slider operation and reverse playback behavior
      outside the new controller.

**Done when:** one final design is explicitly selected with rationale and its complete interaction
behavior is settled before implementation.
**Depends on:** Step 2.

**Evaluation and decision:** select the centered compact cluster. It keeps both directions equally
discoverable, separates the transport row visually from the UTC range labels, and uses less
horizontal space than distributing speed labels across the timeline width. The left-aligned option
leaves the right half of the control area visually unbalanced; the speed-status option adds a
second information line and competes with the centered UTC readout. All three retain the slider
below the controls. The selected row orders controls from 1000× reverse through 1× reverse speed, distinct reverse
and forward play/pause buttons, then 1× through 1000× forward speed. Direction and magnitude remain
visible in each button's accessible name and tooltip; the existing speed readout continues to show
the signed current speed in the Playback page.

For each directional speed button, a click at a lower speed (or in the other direction) selects
that button's base signed speed. A subsequent click at exactly that speed advances by one decade,
capped at 1000×. Clicking that button while at a higher same-direction speed selects its base
speed. Thus clicking 10× repeatedly advances 10× → 100×, while clicking 10× when already at
100× or 1000× resets to 10×, as required.

### 4. Implement the selected playback controller

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Add the selected native wx control cluster above the shared time slider.
- [x] Wire Play/Pause to the existing playback state and update the icon whenever playback state
      changes, including endpoint pauses.
- [x] Implement the signed 10×, 100×, and 1000× repeated-click progression, cap, reset to the
      directional base speed, and direction switching.
- [x] Keep exact 1× reverse and forward speed selection separate from play/pause; preserve the
      current speed magnitude when the directional play buttons switch direction or resume.
- [x] Provide accessible names and state cues for transport and speed controls, including tooltips
      or equivalent guidance for repeated-click behavior.
- [x] Update directly related GUI design or requirements documentation if implementation decisions
      change their documented behavior.

**Done when:** the selected layout and all required interactions work through the existing
playback clock without changing seek behavior or reverse semantics outside the new controls.
**Depends on:** Step 3.

### 5. Verify behavior, layout, and regression coverage

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Add focused tests for paused speed selection and playing speed changes.
- [x] Test each directional speed button's repeated-click progression, 1000× cap, reset to its
      base speed when clicked during playback at a higher same-direction speed, and direction
      switching.
- [x] Test Play/Pause icon and accessible state changes on start, pause, and automatic endpoint
      pause.
- [x] Verify keyboard operation, slider seek behavior, and unchanged reverse-playback behavior
      outside the new controls.
- [x] Verify control bounds and slider usability at the default and minimum window sizes.
- [x] Run the focused `play-oem` GUI and clock test suites; record the command and result.

**Done when:** focused tests and native layout checks pass, and existing timeline and clock
behavior remains intact outside the documented new reverse controller behavior.
**Depends on:** Step 4.

**Verification evidence:** `poetry run pytest tests/ephem_toolkit/play_oem -q` passed (176 passed).
A native wxPython macOS measurement found the centered cluster's best-size width is 704 px, within
the slider's 896 px at the 920 × 480 minimum frame and 1076 px at the 1100 × 760 default frame.
Workspace tests also assert that the transport row remains above the unchanged timeline slider and
that rate selection dispatches signed values. The existing seek handler and reverse accelerator
remain unchanged.
