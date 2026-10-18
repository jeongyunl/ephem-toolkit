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
- Provide seven controls in this order, from left to right: **1000× reverse**, **100× reverse**,
  **10× reverse**, **1× Reverse/Play-Pause**, **10× forward**, **100× forward**, **1000×
  forward**. Use progressively larger direction glyphs: `<<<`, `<<`, `<` for reverse and `>`,
  `>>`, `>>>` for forward.
- The central 1× Reverse/Play-Pause button starts reverse playback at 1× when paused and pauses
  playback when playing. Its icon changes to Pause (`Ⅱ`) during playback and returns to the
  reverse-play icon when paused.
- Clicking a directional speed button while paused selects that signed speed without starting
  playback. Clicking it while playing selects that signed speed and continues playback in that
  direction.
- Repeated clicks on a speed button advance through that button's directional speed series by
  factors of ten: 10× → 100× → 1000× (cap); 100× → 1000× (cap); 1000× remains at 1000×.
- Clicking a lower-speed button while playing in the same direction at that speed or any higher
  multiple switches to the button's base speed. For example, clicking reverse 10× while playing
  reverse at 100× or 1000× selects reverse 10×. A click on the opposite-direction button selects
  that button's base speed and changes direction.
- Forward controls select positive speeds; reverse controls select negative speeds. The central
  button starts at -1× when paused; while playing, it pauses without changing the selected
  direction or speed. Preserve existing reverse-playback behavior outside this cluster.
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
   make the central 1× reverse/play-pause role understandable without relying on position alone.

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

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Trace the shared timeline and playback controls from layout construction through clock
      updates.
- [ ] Record current frame and timeline dimensions, slider labels, play/pause state cues, and
      speed-setting behavior at default and minimum window sizes.
- [ ] Identify existing clock methods and tests for setting speed, starting, pausing, and reaching
      timeline endpoints.
- [ ] Record keyboard, accessibility, and platform-native constraints relevant to the new buttons.
- [ ] Identify which current speed and transport controls are superseded, retained, or relocated by
      this proposal.

**Done when:** the current layout, behavior, dependencies, and compatibility constraints are
documented well enough to design without duplicating clock state or regressing seeking.
**Depends on:** None.

### 2. Create alternative controller mock-ups

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Create at least three materially distinct mock-ups showing the controller above the bottom
      time slider.
- [ ] Include all seven controls, directional glyphs, and the playing-state Pause icon in each
      applicable mock-up.
- [ ] Show representative paused and forward/reverse playing states, including selected speed
      feedback.
- [ ] Save mock-ups in the `play-oem` architecture documentation area and link them here.

**Done when:** at least three alternatives communicate the complete requested control set and its
relationship to the slider.
**Depends on:** Step 1.

### 3. Evaluate mock-ups and select the final design

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Compare every mock-up against the evaluation criteria in this plan.
- [ ] Check each alternative at the default and minimum window sizes using the baseline dimensions.
- [ ] Record the trade-offs and any rejected alternatives.
- [ ] Select one design and document its control order, labels/icons, selected-state feedback, and
      placement.
- [ ] Confirm that the selected design preserves slider operation and reverse playback behavior
      outside the new controller.

**Done when:** one final design is explicitly selected with rationale and its complete interaction
behavior is settled before implementation.
**Depends on:** Step 2.

### 4. Implement the selected playback controller

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Add the selected native wx control cluster above the shared time slider.
- [ ] Wire Play/Pause to the existing playback state and update the icon whenever playback state
      changes, including endpoint pauses.
- [ ] Implement the signed 10×, 100×, and 1000× repeated-click progression, cap, reset to the
      directional base speed, and direction switching.
- [ ] Implement the central 1× reverse/play-pause behavior and its playing/paused icon state.
- [ ] Provide accessible names and state cues for transport and speed controls, including tooltips
      or equivalent guidance for repeated-click behavior.
- [ ] Update directly related GUI design or requirements documentation if implementation decisions
      change their documented behavior.

**Done when:** the selected layout and all required interactions work through the existing
playback clock without changing seek behavior or reverse semantics outside the new controls.
**Depends on:** Step 3.

### 5. Verify behavior, layout, and regression coverage

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Add focused tests for paused speed selection and playing speed changes.
- [ ] Test each directional speed button's repeated-click progression, 1000× cap, reset to its
      base speed when clicked during playback at a higher same-direction speed, and direction
      switching.
- [ ] Test Play/Pause icon and accessible state changes on start, pause, and automatic endpoint
      pause.
- [ ] Verify keyboard operation, slider seek behavior, and unchanged reverse-playback behavior
      outside the new controls.
- [ ] Verify control bounds and slider usability at the default and minimum window sizes.
- [ ] Run the focused `play-oem` GUI and clock test suites; record the command and result.

**Done when:** focused tests and native layout checks pass, and existing timeline and clock
behavior remains intact outside the documented new reverse controller behavior.
**Depends on:** Step 4.
