# `play-oem` — Controls & Info Improvement Plan (Cycle 2)

This plan defines the second post-migration GUI improvement cycle, focused on the **Controls &
Info** pane: its feature navigation, Playback controls, OEM information, and current-state
readouts. It is informed by the four screenshots supplied for this cycle and by the current wx
implementation.

The completed first cycle is recorded in
[PLAY_OEM_GUI_IMPROVEMENT_CYCLE_1.md](./PLAY_OEM_GUI_IMPROVEMENT_CYCLE_1.md). This document is
an active plan; no behavior described below is considered implemented until its validation
criteria pass.

## Objective and scope

Improve the Controls & Info pane's hierarchy, discoverability, and scanability while preserving
playback behavior, displayed data, keyboard operation, and platform-native wx controls.

In scope:

- The icon rail and the Playback, OEM file information, and State pages.
- Organization and presentation of time, transport, seek, navigation, speed, and view-launch
  controls.
- Readability of metadata and cursor-state values at narrow and minimum window sizes.

Out of scope:

- Main Analysis and Comparison graph-panel behavior, splitter layout, and graph rendering.
- The shared timeline along the bottom of the workspace.
- Changes to playback, seek, interpolation, or view-registry semantics.

## Initial observations

Treat these screenshot observations as hypotheses to confirm against the running application
during Step 1:

- The feature rail uses icons without a persistent visible page title. Tooltips and accessible
  names exist in the implementation, but users may need to infer the selected page from its icon.
- Playback content is a long vertical sequence. The screenshots show transport and rate presets
  near the top, with the logarithmic speed slider, view groups, and individual view buttons farther
  down the same scrollable page.
- Speed is represented by a signed status label, four preset toggle buttons, and a separate
  logarithmic slider. Their relationship and the active value should be easy to understand without
  scrolling between controls.
- View-group buttons and individual-view buttons form separate lists. Their combined height makes
  the lower part of Playback expensive to browse.
- OEM information is presented as a single sequence of primary context and detailed metadata;
  long time values consume several lines in the narrow pane.
- State is presented as long text labels for vectors and derived values. The display should make
  components, units, precision, and sampled/interpolated/unavailable status easy to scan.

## Working rules

1. Complete the baseline measurements before selecting a layout solution.
2. Keep primary playback actions discoverable; do not hide them in menus solely to save space.
3. Preserve all existing actions, registered views, metadata, state-status distinctions, keyboard
   accelerators, and error feedback.
4. Prefer measured, native-wx layouts over fixed pixel assumptions. Validate both default and
   minimum window sizes, including keyboard-only use.
5. Do not repeat or undo completed Cycle 1 work: control reachability, wrapped labels, playback
   toggle behavior, graph-stack scrolling, timeline labels, or graph-panel scroll preservation.

## Planned steps

### 1. Establish a Controls & Info baseline

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Reproduce the supplied Playback, OEM information, and State pages in the running application.
- [ ] Record pane and page dimensions at the default (1100 x 760) and minimum (920 x 480) frame
      sizes; include the height and scroll range of each page.
- [ ] Inventory which Playback controls are initially visible, which require scrolling, and the
      order in which keyboard focus reaches them.
- [ ] Check whether the selected page is identifiable without relying on a transient tooltip.
- [ ] Record long and unavailable metadata/state values and verify how they wrap at the minimum
      width.

**Done when:** the visible and below-the-fold content, page identity cues, and narrow-size
limitations are recorded for all three feature pages.
**Depends on:** None.

### 2. Make feature-page identity and selection clear

The screenshots show an icon-only rail next to a fixed **Controls & Info** heading. Verify whether
the selected feature's name is sufficiently apparent when tooltips are not open.

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Evaluate a persistent selected-page title or caption alongside the feature rail.
- [ ] Ensure selected, focused, and hovered states remain visually distinct and consistent with
      native wx appearance.
- [ ] Preserve accessible names, tooltips, keyboard activation, and Up/Down feature navigation.
- [ ] Check that a page switch does not unexpectedly reset that page's scroll position or focus.

**Done when:** a user can identify the selected feature without hovering, and page selection
remains clear to mouse, keyboard, and assistive-technology users.
**Depends on:** Step 1.

### 3. Reorganize the Playback page by task priority

The current page places time and transport controls, seek and stepping controls, speed selection,
view groups, and individual view launchers in one long vertical list. Define a hierarchy that
reduces visual scanning while retaining the existing actions.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Group controls by task: playback status/transport, seek and time navigation, playback rate,
      and graph/view launch.
- [ ] Identify the primary controls that should remain visible at the default size without
      scrolling; record the chosen set before implementing the layout.
- [ ] Keep secondary actions reachable by scrolling or an explicitly labeled disclosure; do not
      place essential Play/Pause, Reverse, or current-time information only in a menu.
- [ ] Keep seek validation errors adjacent to the seek field and retain both elapsed-time and UTC
      entry.
- [ ] Compare the resulting vertical scan and scroll extent with the Step 1 baseline.

**Done when:** Playback's control hierarchy reflects common tasks, primary actions are readily
available, and all existing actions remain reachable at the minimum size.
**Depends on:** Steps 1 and 2.

### 4. Simplify view and group launching

The Playback page currently lists each available view group and each individual graph as a
separate full-width button. Improve browsing without removing any registry entry or changing
launch behavior.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Compare compact alternatives for individual-view and view-group selection, such as a
      labeled picker, categorized list, or clearly separated compact sections.
- [ ] Retain all registered views and groups, including disabled/unavailable group states.
- [ ] Preserve the behavior for opening a view that is already open and the existing duplicate
      panel workflow.
- [ ] Ensure names remain understandable without relying on icons alone; retain keyboard access
      and focus visibility.
- [ ] Measure and report the change in Playback page height and launcher interaction count against
      Step 1.

**Done when:** every existing view and group remains discoverable and launchable, with a measured
improvement in browsing density and no regression in launch behavior.
**Depends on:** Step 3.

### 5. Clarify playback-rate and time-navigation controls

Rate presets and the continuous logarithmic slider provide overlapping ways to select speed. Make
their relationship and the active signed rate clear, and keep seek/navigation feedback coherent.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Verify the selected preset and slider position stay synchronized for preset clicks, slider
      changes, reverse playback, and programmatic playback updates.
- [ ] Make the current signed rate and direction unambiguous at the point users choose a rate.
- [ ] Clarify the slider's logarithmic range and its relationship to the preset values without
      adding redundant labels.
- [ ] Keep Start/End, sample stepping, minute stepping, and direct seek distinguishable by action
      and keyboard operation.
- [ ] Recheck focus scrolling and accelerator behavior while editing the seek field.

**Done when:** the active rate, direction, and rate-selection mechanism are understandable and
synchronized, while all time-navigation actions retain their existing semantics.
**Depends on:** Step 3.

### 6. Improve OEM information scanability

The OEM information page combines summary context with detailed fields, and long time values wrap
in the narrow pane. Improve hierarchy without dropping metadata.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Separate primary context (object, frame, center, time span, and sample count) from secondary
      metadata (object ID, time system, frame epoch, usable interval, and interpolation details).
- [ ] Evaluate clear label/value styling and grouping for long values while preserving readable
      wrapping at minimum width.
- [ ] Keep unavailable values explicit and distinguish an unavailable field from an empty or
      omitted field.
- [ ] Decide, based on Step 1 and user review, whether secondary metadata should remain visible or
      use a labeled disclosure; do not hide primary context.
- [ ] Test representative long values, missing metadata, keyboard navigation, and accessibility
      names.

**Done when:** primary context is quickly scannable, all supplied metadata remains available, and
long or unavailable values are clear at default and minimum widths.
**Depends on:** Step 1.

### 7. Improve current-state readout scanability

The State page shows position, velocity, derived values, and cursor status in long text labels.
Present these as a coherent readout without changing state computation.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Evaluate a structured position and velocity presentation with explicit component names and
      units.
- [ ] Group derived values (speed and altitude) separately from vector components.
- [ ] Preserve the distinction among sampled, interpolated, out-of-range, unavailable, and data-gap
      states; make the status visible alongside the values it qualifies.
- [ ] Verify precision and wrapping for representative values, including unavailable components
      and high-magnitude values.
- [ ] Ensure state updates do not cause unnecessary layout jumps or move keyboard focus.

**Done when:** users can identify each component, unit, derived value, and cursor-data status
without parsing an ambiguous comma-separated string, and all states remain explicit.
**Depends on:** Step 1.

### 8. Validate the Controls & Info cycle

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Run the focused ControlWindow, workspace navigation, and app tests; add regressions for each
      changed interaction.
- [ ] Verify the Playback, OEM information, and State pages at default and minimum frame sizes
      using native wx.
- [ ] Exercise all page and control interactions with keyboard-only navigation, including focus
      scrolling, seek errors, and playback accelerators.
- [ ] Confirm the entire view/group catalog, metadata set, and cursor-status cases remain available.
- [ ] Update this plan with measured outcomes and move completed steps into a cycle completion
      report when the cycle is finished.

**Done when:** focused tests pass, native wx checks show no clipped or unreachable Controls & Info
content, all existing behavior is preserved, and the completion evidence is recorded.
**Depends on:** Steps 2–7.
