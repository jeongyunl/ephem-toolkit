# `play-oem` — GUI Design Implementation Plan

Selected design: [PLAY_OEM_GUI_DESIGN.md](./PLAY_OEM_GUI_DESIGN.md). User-facing requirements:
[PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md). Software architecture:
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md). Broader implementation sequence:
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md).

## How to use this plan

Work **one pending numbered step at a time, in order**. Do not begin a later pending step until
the current step's checklist and completion criteria pass. Each dependency field identifies its
prerequisite, including prerequisites recorded in the broader implementation plan.

When a step is complete, move its full entry to the `Completed steps` section at the end of this
document. Preserve its original number, status, progress, checklist, completion criteria and
dependency so the completion record remains auditable.

If implementation cannot progress in the documented order, stop and reevaluate the plan before
starting work out of sequence. Update step order, dependencies, completion criteria, and status
here so the plan reflects the actual dependency order.

If implementation reveals a change to the selected layout, user-facing behavior, or software
architecture, update [PLAY_OEM_GUI_DESIGN.md](./PLAY_OEM_GUI_DESIGN.md),
[PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md), or
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md) as appropriate before proceeding
with dependent steps.

For every step, keep status and progress current:

- `Not started` — no work begun.
- `In progress` — implementation or its checks are underway.
- `Blocked` — cannot proceed; record the blocker.
- `Done` — all checklist items and completion criteria pass.

Progress is the number of checklist items completed. Do not mark a step done based only on code
being written.

## Current directive — implement selected design G

Implement the three-pane analysis workspace selected in
[PLAY_OEM_GUI_DESIGN.md](./PLAY_OEM_GUI_DESIGN.md). The left vertical notebook holds non-graph
features; the middle and optional right pane hold independent, vertically stacked graph panels;
one shared timeline remains below the panes.

Keep the playback clock, OEM loading, cursor lookup, computed series, CLI behavior, and the
single wx event loop unchanged. The layout change replaces detached plot-frame ownership with
embedded panel hosts, so preserve backend behavior, click-to-seek, plot navigation, synchronization,
explicit errors, and exactly-once view cleanup. The optional right pane must retain its graph
selections and size when closed and restore them when reopened.

## Milestone G1 — Workspace shell and embedded view hosts

### 1. Audit the GUI baseline and resolve implementation unknowns

Map the current ownership and interaction paths, run the focused baseline, and complete the
feasibility investigations below before committing to the selected layout's implementation
details.

- **Status:** Not started.
- **Progress:** 0/6 substeps complete.

#### 1-1. Audit the GUI and prototype Matplotlib WxAgg embedding

- **Status:** Not started.
- **Progress:** 0/7 checklist items.
- [ ] Record the control-window, plot-frame, view-factory, clock-subscription, and shutdown
      ownership paths.
- [ ] Inventory registered views, content types, controls, plot interactions, and backend cleanup.
- [ ] Identify focused existing tests and run the `tests/ephem_toolkit/play_oem` baseline.
- [ ] Build a disposable wx host for a representative 2D view and the 3D Matplotlib view.
- [ ] Verify canvas resize, redraw, navigation toolbar modes, and click-to-seek after embedding.
- [ ] Verify each hosted view initializes at and follows the shared playback time.
- [ ] Record the reusable host pattern and any wx/Matplotlib constraints.

**Done when:** a prototype confirms correct embedded WxAgg rendering and interactions, or
documents a concrete blocker before the production host is designed.
**Depends on:** Main plan Steps 23–27.

#### 1-2. Probe VTK wx embedding viability

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Test the currently supported VTK wx path inside a graph-panel host.
- [ ] Verify initialization, resize, hide/show, repeated display, and render-context behavior.
- [ ] Confirm backend failures remain explicit and do not silently select another renderer.
- [ ] Record a retain/defer decision and platform-specific constraints for the VTK host.

**Done when:** VTK support in embedded panes is demonstrated or the limitation and required
backend decision are documented.
**Depends on:** Substep 1-1.

#### 1-3. Prototype repeated view-instance lifecycle

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Verify how the current name-keyed view map and clock subscriptions constrain duplicate
      instances of one view type.
- [ ] Prototype stable panel IDs separate from registry view names.
- [ ] Verify duplicated views have independent callbacks, cursor updates, and cleanup.
- [ ] Record lifecycle changes needed to preserve exactly-once unsubscribe and close behavior.

**Done when:** independent instances can be opened and closed without cross-panel effects or
subscription leaks, or the blocking constraint is identified.
**Depends on:** Substep 1-1.

#### 1-4. Check vertical icon-tab notebook feasibility

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Prototype the selected wx vertical-tab control with icon-only tabs.
- [ ] Verify accessible names, hover tooltips, selected/focus appearance, and keyboard operation.
- [ ] Check native behavior on currently available supported platforms.
- [ ] Record any platform-specific navigation or accessibility compromise before choosing a
      control pattern.

**Done when:** the notebook navigation pattern is usable and accessible, or a specific alternative
is documented for approval.
**Depends on:** Main plan Steps 23–27.

#### 1-5. Prototype nested splitters and scrollable graph stacks

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Prototype the left/middle/right splitter arrangement with a resizable optional right pane.
- [ ] Test right-pane close/reopen while retaining its contents and width.
- [ ] Stack multiple graph panels in independently scrollable regions with minimum plot sizes.
- [ ] Test narrowing the window and moving splitters near their minimum positions.
- [ ] Record layout constraints and a concrete initial sizing/scrolling policy.

**Done when:** the selected pane arrangement behaves predictably at its minimum supported sizes
and preserves hidden right-pane state, or blocking constraints are documented.
**Depends on:** Substeps 1-1 and 1-3.

#### 1-6. Measure the multi-panel rendering risk

- **Status:** Not started.
- **Progress:** 0/4 checklist items.
- [ ] Benchmark representative 2D and 3D panels embedded together at the existing playback rate.
- [ ] Include the maximum expected visible panel count and a representative large OEM history.
- [ ] Separate native wx UI update rate and input responsiveness from headless rendering results.
- [ ] Record a workload baseline and thresholds for deciding whether rendering/throttling changes
      are required.

**Done when:** expected multi-panel rendering cost is measured on the available native wx
environment and remaining platform uncertainty is stated.
**Depends on:** Substeps 1-1 and 1-2.

**Done when:** the active GUI baseline is recorded and all six feasibility substeps have passed
or have a documented blocker/decision.
**Depends on:** Main plan Steps 23–27.

### 2. Build the workspace shell and shared timeline

Create the main workspace frame with placeholder regions for the left feature notebook, middle
and optional right graph stacks, and a shared timeline row below the panes. Keep the existing
content available during the transition; do not change clock or view semantics in this step.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Define a workspace owner and clear ownership for the notebook, stack regions, splitters,
      timeline, and child graph panels.
- [ ] Create the main workspace frame and placeholder regions for the left, middle, and optional
      right pane.
- [ ] Keep the shared time slider below the full pane area and bind it to the existing seek
      callback without introducing recursive slider events.
- [ ] Add focused tests for workspace construction and timeline placement/state.
- [ ] Confirm app shutdown still closes the wx event loop and owned resources once.

**Done when:** the workspace shell is displayed with a global timeline and testable pane
placeholders while the existing GUI behavior remains available.
**Depends on:** Step 1.

### 3. Embed Matplotlib views in reusable graph-panel hosts

Replace the assumption that a Matplotlib view owns a top-level `wx.Frame` with a reusable
graph-panel host. Keep the view registry responsible for available view types and preserve the
existing view contract.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Separate Matplotlib view construction and plot-content hosting from `_open_view` frame
      construction.
- [ ] Parent Matplotlib canvases and navigation toolbars to graph-panel hosts while preserving
      toolbar-mode handling and click-to-seek.
- [ ] Update each embedded view from the shared playback clock and initialize it at the current
      cursor time.
- [ ] Add focused tests for Matplotlib host construction, resize/redraw, and clock-synchronized
      updates.
- [ ] Verify click-to-seek and Matplotlib zoom/pan toolbar behavior in an embedded host.
- [ ] Surface view construction failures through the existing explicit error path.

**Done when:** Matplotlib views render and interact correctly in embedded graph-panel hosts.
**Depends on:** Step 2 and Substep 1-1.

### 4. Define panel-instance lifecycle and embed supported VTK views

Separate panel-instance identity from registered view type so a stack can host independent copies
of the same view. Integrate VTK wx content in the graph host if VTK remains a supported backend.

- **Status:** Not started.
- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Assign each graph panel a stable instance ID independent of its selected view type.
- [ ] Permit separate instances of the same view without sharing callbacks, state, or cleanup.
- [ ] Ensure each instance receives the current clock time and unsubscribes exactly once on close.
- [ ] Reparent VTK wx content into a graph-panel host if VTK remains supported as a backend.
- [ ] Preserve explicit backend-selection, initialization, and rendering errors.
- [ ] Test instance lifecycle and supported VTK host behavior; record if VTK is not retained.

**Done when:** panel identity and cleanup are correct for repeated view types, and supported
backends work in embedded hosts.
**Depends on:** Step 3 and Substeps 1-2 and 1-3.

## Milestone G2 — Graph stacks and feature notebook

### 5. Add graph stacks, selectors, and empty states

Allow each graph stack to contain zero or more graph panels. Each panel selects its view
independently; empty stacks remain discoverable and usable.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Add an **Add graph** action to the middle and optional right stack.
- [ ] Show a clear empty state with an add action when a stack contains no panels.
- [ ] Give each panel a view-selection combobox populated from the view registry.
- [ ] Ensure selection changes update only the chosen panel and clean up its previous view.
- [ ] Surface view-creation errors without leaving a broken or success-shaped panel.
- [ ] Test empty, one-panel, and multi-panel stacks plus independent selector changes.

**Done when:** both stacks support zero or more panels and each panel's view can be selected
independently.
**Depends on:** Steps 2 and 4 and Substep 1-5.

### 6. Implement panel actions and independent lifecycle

Add local actions for moving, duplicating, and closing graph panels. A duplicate must be an
independent panel instance, even when it displays the same registered view type.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Add a panel menu with move within stack, duplicate, and close actions.
- [ ] Reorder panels without losing their selected view or cursor state.
- [ ] Duplicate a panel with a new instance ID and independent view resources.
- [ ] Close one panel without affecting other panels, playback, or the other stack.
- [ ] Disconnect plot callbacks and clock subscriptions and release resources exactly once.
- [ ] Test reorder, duplicate, close, and failure/cleanup paths.

**Done when:** all panel actions operate on the intended instance and lifecycle tests pass.
**Depends on:** Step 5 and Substep 1-3.

### 7. Add stack scrolling and minimum plot sizes

Ensure growing graph stacks do not compress their plots below usable dimensions.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Set and document minimum usable width and height for graph panels.
- [ ] Scroll each stack independently when its contents exceed the available pane height.
- [ ] Keep selectors and panel menus reachable while scrolling.
- [ ] Test short windows, many panels, and resizing around minimum dimensions.
- [ ] Verify Matplotlib and VTK canvases resize and redraw correctly after scrolling or resizing.

**Done when:** overflow is handled by scrolling and panels remain usable at the defined minimum
dimensions.
**Depends on:** Step 5 and Substep 1-5.

### 8. Implement the vertical icon-tab notebook

Build the vertical notebook navigation for non-graph features, with icon-only tabs that remain
discoverable and usable.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Implement vertical notebook tabs for OEM information, playback, state, and in-scope
      settings or other non-graph features.
- [ ] Give each icon tab an accessible name and hover tooltip.
- [ ] Provide visible selected and keyboard-focus states.
- [ ] Support keyboard focus, arrow-key navigation, and keyboard activation.
- [ ] Test tab navigation and accessibility semantics.

**Done when:** each feature page is reachable by mouse and keyboard, and icon tabs expose clear
names and state.
**Depends on:** Step 2 and Substep 1-4.

### 9. Move existing controls and readouts into notebook pages

Populate the feature notebook from the current control dashboard without changing playback or
data semantics. Keep the shared time slider outside the notebook below all panes.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Move OEM file identity, epochs, frame, center, and sample context to the OEM information
      page.
- [ ] Move play/pause, reverse, speed, direct time entry, stepping, and start/end actions to the
      playback page using existing callbacks.
- [ ] Move position, velocity, speed, altitude, and cursor validity/status to the state page.
- [ ] Preserve metadata details, units, gap/unavailable behavior, and error reporting.
- [ ] Keep the global time slider below all panes and prevent recursive seek events.
- [ ] Test page contents and verify every existing playback action remains available.

**Done when:** existing non-graph controls and readouts are available in notebook pages and the
global timeline remains synchronized.
**Depends on:** Steps 2 and 8.

## Milestone G3 — Feature notebook, optional pane, and accessibility

### 10. Implement optional right-pane close and restore behavior

Closing the right pane should expand the middle stack without destroying the hidden pane's
contents, selected views, or size. Reopening should restore its state.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Close the right pane without destroying its graph panels, selected views, or stack state.
- [ ] Expand the middle pane into available space while the right pane is closed.
- [ ] Reopen the pane with its previous panel stack and width.
- [ ] Test repeated close/reopen cycles and interaction with middle-pane resizing.
- [ ] Manually verify both pane states at representative narrow and wide window sizes.

**Done when:** pane visibility changes preserve right-pane state and use the available workspace
area as specified.
**Depends on:** Steps 2 and 5 and Substep 1-5.

## Milestone G4 — Integration validation and handoff

### 11. Verify keyboard and icon-tab accessibility

Verify that the icon-only notebook and all workspace controls remain discoverable and usable
without a mouse.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Test keyboard-only navigation among notebook tabs, graph selectors, panel menus, splitters,
      and timeline controls.
- [ ] Verify icon-tab accessible names, hover tooltips, visible focus, and selected-state cues.
- [ ] Verify selected state is distinguishable from hover and keyboard focus.
- [ ] Check that keyboard accelerators do not intercept typing in editable fields.
- [ ] Record any accessibility limitations and their platform-specific behavior.

**Done when:** all workspace controls are keyboard-accessible, icon tabs expose names and state,
and limitations are documented.
**Depends on:** Steps 8–10.

### 12. Verify interaction, synchronization, and backend behavior

Exercise the complete selected layout with representative OEM data. Verify playback and graph
interactions across visible, hidden, and reopened panels.

- **Status:** Not started.
- **Progress:** 0/7 checklist items.
- [ ] Verify play/pause, reverse, speed, stepping, time entry, slider seek, and click-to-seek
      synchronize every visible panel.
- [ ] Verify Matplotlib zoom/pan tools do not turn navigation gestures into seeks.
- [ ] Verify current cursor state appears when a hidden/reopened panel becomes visible and that
      invisible panels do not create unnecessary render work.
- [ ] Test VTK initialization, resize, hide/show, and rendering through the embedded wx host on
      each supported platform/backend combination.
- [ ] Verify gaps, unavailable cursor state, units, reference frame, and plot labels remain clear.
- [ ] Record automated results separately from manual and platform-specific observations.
- [ ] Manually check the open/closed right pane and multi-panel stacks with representative OEM data.

**Done when:** interactions remain synchronized and accurate across the layout, with backend
behavior and manual observations recorded.
**Depends on:** Steps 3–10.

### 13. Run regression, performance, and release checks

Validate the integrated layout against the current application behavior and coordinate final
cross-platform acceptance with the broader implementation plan.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Run focused GUI, app, registry, view, and playback tests; run the full play-oem suite.
- [ ] Verify clean startup and shutdown, explicit errors, and exactly-once cleanup for all panels.
- [ ] Run the existing all-view playback workload and report native UI responsiveness separately
      from headless rendering results.
- [ ] Compare the new all-visible-panel workload with the recorded baseline; document any
      regression or accepted deviation.
- [ ] Smoke-test supported operating systems and the selected 3D backend; coordinate remaining
      release checks with Main plan Step 28.
- [ ] Update the GUI design document and software design if implementation changes contracts or
      approved behavior; record evidence and limitations in this plan.

**Done when:** the selected layout passes focused and full play-oem regression checks, visible
behavior is manually validated, and cross-platform/performance evidence is recorded.
**Depends on:** Steps 11–12, Substep 1-6, and Main plan Step 28.

## Completed steps

No GUI design implementation steps are complete yet.
