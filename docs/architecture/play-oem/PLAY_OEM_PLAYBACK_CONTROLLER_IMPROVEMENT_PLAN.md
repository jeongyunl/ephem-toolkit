# `play-oem` — Playback Controller Interface Improvement Plan

This plan defines an improvement cycle for the shared playback controller at the bottom of the
`play-oem` window. It follows the planning and completion-evidence conventions in
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md) and the GUI improvement
workflow in [PLAY_OEM_GUI_DESIGN.md](./PLAY_OEM_GUI_DESIGN.md).

## Objective and scope

Design and implement a compact set of playback controls directly above the shared time slider.
The transport controls should make reverse and forward play/pause and progressively faster
playback in either direction easy to discover and operate, without displacing or making the
timeline harder to use.

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
- Provide eight controls in this order, from left to right: **1000× reverse**, **100× reverse**,
  **10× reverse**, **1× Reverse Play/Pause**, **1× Forward Play/Pause**, **10× forward**,
  **100× forward**, **1000× forward**. Use progressively larger direction glyphs: `<<<`, `<<`,
  `<` for reverse and `>`, `>>`, `>>>` for forward.
- Keep the 1× Reverse Play/Pause and 1× Forward Play/Pause buttons separate. The reverse button
  starts reverse playback at 1× when paused; the forward button starts forward playback at 1×
  when paused. While playback is running in that button's direction, the button shows Pause (`Ⅱ`)
  and pauses playback when clicked. While playback is running in the opposite direction, clicking
  the other play button switches direction at 1× and continues playback.
- Clicking a directional speed button while paused selects that signed speed without starting
  playback. Clicking it while playing selects that signed speed and continues playback in that
  direction.
- Repeated clicks on a speed button advance through that button's directional speed series by
  factors of ten: 10× → 100× → 1000× (cap); 100× → 1000× (cap); 1000× remains at 1000×.
- Clicking a lower-speed button while playing in the same direction at that speed or any higher
  multiple switches to the button's base speed. For example, clicking reverse 10× while playing
  reverse at 100× or 1000× selects reverse 10×. A click on the opposite-direction button selects
  that button's base speed and changes direction.
- Forward controls select positive speeds; reverse controls select negative speeds. The two 1×
  play buttons select their respective direction and start playback when paused. Preserve existing
  reverse-playback behavior outside this cluster.
- Communicate the selected speed and playing state with an accessible name and state indication;
  do not rely on icon shape or color alone.

The repeated-click rule applies when the current selected playback speed has the same direction
as the clicked button and its magnitude is the button's base speed or a lower speed in that
button's series. If the current speed has the same direction but is above the clicked button's
base speed, the click selects the base speed instead. A click in the opposite direction selects
the clicked button's base speed. Speed progression is capped at 1000× and must never exceed the
application's supported maximum.

## Working rules

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
7. Update this plan's status, progress, checklist, and evidence as work proceeds. Keep the
   implementation and any user-facing design documentation consistent with the selected behavior.
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
- [x] Include all eight controls, directional glyphs, and the playing-state Pause icon in each
      applicable mock-up.
- [x] Show representative paused and forward/reverse playing states, including selected speed
      feedback.
- [x] Save mock-ups in the `play-oem` architecture documentation area and link them here.

**Done when:** at least three alternatives communicate the complete requested control set and its
relationship to the slider.
**Depends on:** Step 1.

**Alternatives:** [left-aligned cluster](./mockup-playback-controller-left.svg),
[centered compact cluster](./mockup-playback-controller-centered.svg), and
[single-row transport with speed status](./mockup-playback-controller-status.svg).

### 3. Evaluate mock-ups and select the final design

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Compare every mock-up against the evaluation criteria in this plan.
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
below the controls. The selected row orders controls from 1000× reverse through 10× reverse, distinct 1× reverse and
forward play/pause buttons, then 10× through 1000× forward. Direction and magnitude remain visible
in each button's accessible name and tooltip; the existing speed readout continues to show the
signed current speed in the Playback page.

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
- [x] Implement separate 1× reverse and forward play/pause behavior and their playing/paused icon
      states.
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
