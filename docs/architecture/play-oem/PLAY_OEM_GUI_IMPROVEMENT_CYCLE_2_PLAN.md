# `play-oem` — Controls & Info Improvement Plan (Cycle 2)

This plan defines the second post-migration GUI improvement cycle, focused on the **Controls &
Info** pane: its feature navigation, Playback controls, OEM information, and current-state
readouts. It is informed by the four screenshots supplied for this cycle and by the current wx
implementation.

The completed first cycle is recorded in
[PLAY_OEM_GUI_IMPROVEMENT_CYCLE_1.md](./PLAY_OEM_GUI_IMPROVEMENT_CYCLE_1.md). Steps 5–8 remain
active; evidence for completed Steps 1–4 is grouped at the end of this document.

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

## How to use this plan

Work one pending numbered step at a time in dependency order. Keep pending steps at the beginning
of the document. When a step is complete, move its full entry to `Completed steps` at the end,
preserving its original number, status, progress, checklist, completion criteria, dependency, and
evidence. Update status and progress only after the checklist and completion criteria pass.

## Initial observations

These screenshot observations were treated as hypotheses and assessed during completed Step 1:

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
3. Preserve existing playback actions, registered graph types and group APIs, metadata,
   state-status distinctions, keyboard accelerators, and error feedback.
4. Prefer measured, native-wx layouts over fixed pixel assumptions. Validate both default and
   minimum window sizes, including keyboard-only use.
5. Do not repeat or undo completed Cycle 1 work: control reachability, wrapped labels, playback
   toggle behavior, graph-stack scrolling, timeline labels, or graph-panel scroll preservation.

## Remaining planned steps

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
- [ ] Confirm all graph types remain available through graph-pane selectors, along with the
      metadata set and cursor-status cases.
- [ ] Update this plan with measured outcomes and move completed steps into a cycle completion
      report when the cycle is finished.

**Done when:** focused tests pass, native wx checks show no clipped or unreachable Controls & Info
content, all existing behavior is preserved, and the completion evidence is recorded.
**Depends on:** Steps 2–7.

## Completed steps

### 1. Establish a Controls & Info baseline

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Reproduce the supplied Playback, OEM information, and State pages in the running application.
- [x] Record pane and page dimensions at the default (1100 x 760) and minimum (920 x 480) frame
      sizes; include the height and scroll range of each page.
- [x] Inventory initially visible and below-the-fold Playback controls, the focusable-control
      sequence, and existing focus-scroll test coverage.
- [x] Check whether the selected page is identifiable without relying on a transient tooltip.
- [x] Record long and unavailable metadata/state values and verify wrapping and clipping at minimum
      width; note any cases not represented by the chosen fixture.

**Done when:** the visible and below-the-fold content, page identity cues, and narrow-size
limitations are recorded for all three feature pages.
**Depends on:** None.

**Baseline findings (native wx, macOS; `JPSS-1_small.15m.oem`):**

- At 1100 x 760, the left pane measured 240 x 651 px; each feature page measured 184 x 619 px.
  Playback's scroll viewport was 169 x 619 px, with 993 px of virtual content (100 scroll units,
  61-unit thumb). At the top, time, transport, presets, seek, and sample/minute navigation were
  visible; the speed slider and graph launchers continued below.
- At 920 x 480, the left pane measured 240 x 371 px; each feature page measured 184 x 339 px.
  Playback's scroll viewport was 169 x 339 px, with 1009 px of virtual content (101 scroll units,
  33-unit thumb). The top view showed controls through **Seek**; navigation, rate slider, groups,
  and the seven individual view buttons required scrolling.
- The focusable playback sequence is Play, Reverse, four rate presets, time entry, Seek, six
  navigation actions, rate slider, four groups, and seven individual views. Existing tests verify
  focus scrolling for the time entry, Seek, and last navigation control. A native Tab traversal
  was not independently confirmed in this baseline.
- Feature buttons are icon-only: their accessible names and tooltips identify the pages, and the
  active button's toggle state marks selection, but there is no persistent visible page title.
- With actual OEM times, the Info page's content minimum height was 464 px. It fit in the 619 px
  default page but exceeded the 339 px minimum-height page; only the first nine of twelve metadata
  labels were visible there. Long UTC values wrapped. `Frame epoch` was explicitly unavailable.
- The State page fit vertically, but its content minimum width was 318 px against a 184 px page.
  Position, velocity, and derived-value labels remained single-line in 160 px controls, leaving
  likely horizontal clipping at both frame sizes. The fixture showed a sampled state; other cursor
  statuses are covered by the existing state-formatting tests rather than this native run.

- [x] Reproduced all three pages in the running application.
- [x] Recorded actual pane/page dimensions, Playback virtual size, and scroll range/thumb at both
      planned frame sizes.
- [x] Recorded the visible and below-the-fold Playback controls, focusable sequence, and existing
      focus-scroll test coverage.
- [x] Confirmed the page-name cues available without hovering.
- [x] Recorded actual long/unavailable OEM values and State-page width constraints; noted state
      statuses not present in the fixture.

**Baseline conclusion:** the greatest measurable density issue is the Playback catalog's long
scrolling list. At minimum size, the Info page also hides lower metadata, and State values exceed
the available width. The selected page has a toggle cue but no persistent textual identity.

### 2. Make feature-page identity and selection clear

The screenshots show an icon-only rail next to a fixed **Controls & Info** heading. Verify whether
the selected feature's name is sufficiently apparent when tooltips are not open.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Evaluate a persistent selected-page title or caption alongside the feature rail.
- [x] Ensure selected, focused, and hovered states remain visually distinct and consistent with
      native wx appearance.
- [x] Preserve accessible names, tooltips, keyboard activation, and Up/Down feature navigation.
- [x] Check that a page switch does not unexpectedly reset that page's scroll position or focus.

**Done when:** a user can identify the selected feature without hovering, and page selection
remains clear to mouse, keyboard, and assistive-technology users.
**Depends on:** Step 1.

**Outcome:** the pane heading now includes the selected feature name; at minimum size, the OEM
information title wraps onto two lines without exceeding the pane width. Native wx confirmed that
switching Playback to OEM information and back preserved Playback's scroll position. Existing
workspace tests cover selected-state synchronization and Up/Down keyboard navigation.

### 3. Reorganize the Playback page by task priority

The Step 1 baseline placed time and transport controls, seek and stepping controls, speed selection,
view groups, and individual view launchers in one long vertical list. Define a hierarchy that
reduces visual scanning while retaining the existing playback actions.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Group controls by task: playback status/transport, seek and time navigation, and playback
      rate.
- [x] Identify the primary controls that should remain visible at the default size without
      scrolling; record the chosen set before implementing the layout.
- [x] Keep secondary actions reachable by scrolling or an explicitly labeled disclosure; do not
      place essential Play/Pause, Reverse, or current-time information only in a menu.
- [x] Keep seek validation errors adjacent to the seek field and retain both elapsed-time and UTC
      entry.
- [x] Compare the resulting vertical scan and scroll extent with the Step 1 baseline.

**Done when:** Playback's control hierarchy reflects common tasks, primary actions are readily
available, and all playback actions remain reachable at the minimum size.
**Depends on:** Steps 1 and 2.

**Outcome:** the primary set is elapsed/UTC time, Play/Reverse, rate presets, Seek, and time
navigation. Native wx showed that set in the initial viewport at the default size. With the
launcher catalog removed in Step 4, Playback content height fell by 316 px at both measured sizes:
993 to 677 px at 1100 x 760, and 1009 to 693 px at 920 x 480. The speed slider remains reachable
below the fold; graph launching is handled by the graph panes.

### 4. Use graph-pane controls to add and select graph types

The Step 1 baseline showed separate view-group and individual-view launchers in Playback. Remove
that duplicate catalog and use the existing Add graph action and graph-type selector in the
Main Analysis and Comparison panes. Candidate launcher layouts considered earlier are recorded in
[controls-info-launcher-alternatives.svg](./controls-info-launcher-alternatives.svg).

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Remove the View groups and individual-view launcher controls from Playback.
- [x] Verify that Add graph creates a panel with a graph-type selector in both graph stacks.
- [x] Keep Empty as the default graph type and retain every registered individual graph type in
      the selector.
- [x] Preserve graph replacement, duplicate-panel, and keyboard interaction behavior.
- [x] Measure and report the change in Playback page height and confirm launch controls remain
      available outside Playback.

**Done when:** Playback has no duplicate graph catalog, while users can add an empty graph and
select any registered graph type from the graph panes without regressing panel workflows.
**Depends on:** Step 3.

**Decision and outcome:** the initial Option 1 implementation was superseded by the user's
subsequent direction. Playback no longer contains group buttons or an individual-view picker.
Add graph creates a panel whose type selector includes Empty and all seven registered graph
types; users can also change an existing panel's type there. Existing graph replacement and
duplicate-panel workflows remain covered by app tests. Native wx measured Playback content at
677 px in the default 619 px viewport and 693 px in the minimum 339 px viewport. It also confirmed
that Add graph is present, the new panel defaults to Empty, and all graph types are selectable.
