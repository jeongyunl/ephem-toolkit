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
[PLAY_OEM_GUI_DESIGN.md](./PLAY_OEM_GUI_DESIGN.md). The left icon-button rail switches among
non-graph feature pages; the middle and optional right pane hold independent, vertically stacked
graph panels; one shared timeline remains below the panes.

Use role-based pane names consistently in visible headings and wx window names:
**Controls & Info** for the left feature area, **Main Analysis** for the middle graph stack, and
**Comparison** for the optional right graph stack.

Make the three main side-by-side panes independently resizable: the left feature pane, middle graph
pane, and optional right graph pane. Use draggable vertical sashes between them. The prerequisite
before Step 4 is complete and recorded under Completed steps. Also make vertically stacked graph
panels individually resizable with horizontal sashes. Keep each graph panel at or above its
320 x 280 pixel minimum, and make each stack scroll independently when minimum-size panels cannot
all fit in the available height. Resizing one sash changes its adjacent panes while respecting
usable minimum dimensions. Preserve user-adjusted sizes when the optional right pane is closed and
restored.

Keep the playback clock, OEM loading, cursor lookup, computed series, CLI behavior, and the
single wx event loop unchanged. The layout change replaces detached plot-frame ownership with
embedded panel hosts, so preserve backend behavior, click-to-seek, plot navigation, synchronization,
explicit errors, and exactly-once view cleanup. The optional right pane must retain its graph
selections and size when closed and restore them when reopened.

## Milestone G2 — Graph stacks and feature pages

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

### 7. Add resizable graph-panel splits, stack scrolling, and minimum plot sizes

After the three main pane widths are resizable, allow users to adjust the heights of graph panels in
each stack while preventing plots from shrinking below usable dimensions.

- **Status:** In progress.
- **Progress:** 5/7 checklist items.
- [x] Provide draggable horizontal sashes between vertically stacked graph panels so each panel's
      height can be resized independently.
- [x] Verify the three main panes remain independently width-resizable; preserve unrelated sash
      positions and the right-pane width across close/reopen.
- [x] Set and document a 320 x 280 pixel minimum usable size for graph panels.
- [x] Scroll each stack independently when its contents exceed the available pane height or
      minimum-size panels cannot all fit.
- [ ] Keep selectors and panel menus reachable while scrolling and resizing.
- [ ] Test every sash orientation, short windows, many panels, and resizing around minimum
      dimensions.
- [x] Verify Matplotlib and VTK canvases resize and redraw correctly after resizing.

**Implementation and validation:** Each graph stack remains independently scrollable and now
builds a nested tree of horizontal `wx.SplitterWindow`s, with the same live-update, 3D-sash style
as the main splitters. Every panel boundary is individually adjustable; splitter gravity preserves
usable resizing space across nested panes, and the aggregate minimum size keeps all panels at
320 x 280 pixels before stack scrolling begins. The native wx smoke test exercised three panels in
each stack at both wide and narrow frame sizes: all four sub-sashes measured 9 pixels, the two
scroll ranges were independent and nonzero at 920 x 760, the VTK widget resized from 622 x 285 to
622 x 310, the Matplotlib canvas resized from 622 x 243 to 622 x 218, and closing an interior
panel collapsed only its own splitter. The complete play-oem suite passed (**146 passed**, with
14 existing Matplotlib/Pyparsing deprecation warnings). Native mouse-drag feel and accessibility
of selectors/menus remain for later manual validation. The selected-layout design and all three
mockups now depict the horizontal sub-pane sashes; mockup proportions remain illustrative.

**Done when:** every pane boundary is independently resizable, overflow is handled by scrolling,
and panels remain usable at their defined minimum dimensions.
**Depends on:** Step 5 and Substep 1-5.

### 8. Implement the vertical icon-button rail and feature pages

Build the approved icon-only button rail and `wx.Simplebook` page host for non-graph features.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Implement icon-only `wx.BitmapToggleButton` controls and `wx.Simplebook` pages for OEM
      information, playback, state, and in-scope settings or other non-graph features.
- [ ] Give each icon button a meaningful accessible name and hover tooltip.
- [ ] Provide visible selected and keyboard-focus states.
- [ ] Support keyboard focus, Up/Down navigation, and keyboard activation.
- [ ] Test page navigation, accessible names, and tooltips.
- [ ] Record native keyboard/screen-reader results or remaining platform-specific limitations.

**Done when:** each feature page is reachable by mouse and keyboard, and icon buttons expose
clear names, tooltips, and selected/focus state.
**Depends on:** Step 2 and Substep 1-4.

### 9. Move existing controls and readouts into feature pages

Populate the feature pages from the current control dashboard without changing playback or data
semantics. Keep the shared time slider outside the page host below all panes.

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

**Done when:** existing non-graph controls and readouts are available in feature pages and the
global timeline remains synchronized.
**Depends on:** Steps 2 and 8.

## Milestone G3 — Feature navigation, optional pane, and accessibility

### 10. Implement optional right-pane close and restore behavior

Closing the right pane should expand the middle stack without destroying the hidden pane's
contents, selected views, or size. Reopening should restore its state.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Close the right pane without destroying its graph panels, selected views, or stack state.
- [ ] Expand the middle pane into available space while the right pane is closed.
- [ ] Reopen the pane with its previous panel stack, user-adjusted width, and panel-height
      allocations.
- [ ] Test repeated close/reopen cycles and interaction with both side-by-side and top/bottom
      sash resizing.
- [ ] Manually verify both pane states at representative narrow and wide window sizes.

**Done when:** pane visibility changes preserve right-pane state and use the available workspace
area as specified.
**Depends on:** Steps 2 and 5 and Substep 1-5.

## Milestone G4 — Integration validation and handoff

### 11. Verify keyboard and icon-button accessibility

Verify that the icon-only feature rail and all workspace controls remain discoverable and usable
without a mouse.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Test keyboard-only navigation among feature buttons/pages, graph selectors, panel menus,
      splitters, and timeline controls.
- [ ] Verify icon-button accessible names, hover tooltips, visible focus, and selected-state cues.
- [ ] Verify selected state is distinguishable from hover and keyboard focus.
- [ ] Check that keyboard accelerators do not intercept typing in editable fields.
- [ ] Manually validate native focus, arrow-key navigation, and screen-reader exposure on
      supported platforms; do not treat the wx window name alone as proof of accessibility.
- [ ] Record any accessibility limitations and their platform-specific behavior.

**Done when:** all workspace controls are keyboard-accessible, icon buttons expose names and state,
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
- [ ] Manually check that every vertical and horizontal sash independently resizes its adjacent
      panes, and that the open/closed right pane and multi-panel stacks preserve their adjusted
      sizes with representative OEM data.

**Done when:** interactions remain synchronized and accurate across the layout, with backend
behavior and manual observations recorded.
**Depends on:** Steps 3–10.

### 13. Run regression, performance, and release checks

Validate the integrated layout against the current application behavior and coordinate final
cross-platform acceptance with the broader implementation plan.

- **Status:** Not started.
- **Progress:** 0/7 checklist items.
- [ ] Run focused GUI, app, registry, view, and playback tests; run the full play-oem suite.
- [ ] Verify clean startup and shutdown, explicit errors, and exactly-once cleanup for all panels.
- [ ] Run the existing all-view playback workload and report native UI responsiveness separately
      from headless rendering results.
- [ ] Compare the new all-visible-panel workload with the recorded baseline; document any
      regression or accepted deviation.
- [ ] Meet the recorded seven-view targets: playback-tick p95 <= 50 ms, posted UI-callback
      p95 <= 50 ms, and posted-callback maximum <= 100 ms, or document an explicitly accepted
      platform-specific limitation.
- [ ] Smoke-test supported operating systems and the selected 3D backend; coordinate remaining
      release checks with Main plan Step 28.
- [ ] Update the GUI design document and software design if implementation changes contracts or
      approved behavior; record evidence and limitations in this plan.

**Done when:** the selected layout passes focused and full play-oem regression checks, visible
behavior is manually validated, and cross-platform/performance evidence is recorded.
**Depends on:** Steps 11–12, Substep 1-6, and Main plan Step 28.

## Completed steps

### 1. Audit the GUI baseline and resolve implementation unknowns

Map the current ownership and interaction paths, run the focused baseline, and complete the
feasibility investigations below before committing to the selected layout's implementation
details.

- **Status:** Done.
- **Progress:** 6/6 substeps complete.

#### 1-1. Audit the GUI and prototype Matplotlib WxAgg embedding

- **Status:** Done.
- **Progress:** 7/7 checklist items.
- [x] Record the control-window, plot-frame, view-factory, clock-subscription, and shutdown
      ownership paths.
- [x] Inventory registered views, content types, controls, plot interactions, and backend cleanup.
- [x] Identify focused existing tests and run the `tests/ephem_toolkit/play_oem` baseline.
- [x] Build a disposable wx host for a representative 2D view and the 3D Matplotlib view.
- [x] Verify canvas resize, redraw, navigation toolbar modes, and click-to-seek after embedding.
- [x] Verify each hosted view initializes at and follows the shared playback time.
- [x] Record the reusable host pattern and any wx/Matplotlib constraints.

**Findings:**

- `PlayerApp` owns/reuses the single `wx.App`, the top-level frame, `ControlWindow`, playback
  timer and open views. `ControlWindow` currently owns OEM context/metadata, state and time
  readouts, playback/navigation controls, sliders, and registry actions. The registry exposes
  seven views and the `overview`, `state`, `motion`, and `all` groups.
- `_open_view` creates one child `wx.Frame` per registered view, builds either a Matplotlib
  `Figure` or native `wx.Window`, initializes the view at `clock.t_now`, attaches a clock
  subscription, and stores state by registered view name. For Matplotlib, the frame owns a
  `FigureCanvasWxAgg`, `NavigationToolbar2WxAgg`, and click-to-seek callback. Closing disconnects
  the callback, unsubscribes, and closes the view; closing the main frame stops the timer and
  closes all open views. Click-to-seek accepts left clicks on 2D axes only when toolbar pan/zoom
  is inactive; 3D axes are excluded.
- The focused baseline was `python3 -m pytest tests/ephem_toolkit/play_oem`: **131 passed**,
  with 14 Matplotlib/Pyparsing deprecation warnings. Existing app/control tests use wx/canvas
  test doubles, so they did not by themselves establish native parented-canvas behavior.
- A disposable native host on macOS with wxPython 4.2.4 (osx-cocoa) and Matplotlib 3.9.4 embedded
  the speed/altitude 2D view and the trajectory 3D view in separate `wx.Panel` hosts. Both
  canvases resized and redrew, toolbar pan/zoom/off modes worked, and the existing click callback
  sought on a 2D click while ignoring pan-mode clicks. Both views initialized at the shared clock
  time and followed `PlaybackClock.seek`; after unsubscribe they stopped receiving updates.
- Reusable host pattern: parent each view to its graph-panel `wx.Panel`, build it at the current
  clock time, and place its toolbar and `FigureCanvasWxAgg` in a vertical sizer. Preserve the
  current click callback and per-view clock subscription; teardown disconnects, unsubscribes,
  calls `view.close()`, and destroys the host. No Matplotlib WxAgg embedding blocker was found
  on the available macOS environment. VTK/native-window hosting remains the separate 1-2 probe.

**Done when:** a prototype confirms correct embedded WxAgg rendering and interactions, or
documents a concrete blocker before the production host is designed.
**Depends on:** Main plan Steps 23–27.

#### 1-2. Probe VTK wx embedding viability

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Test the currently supported VTK wx path inside a graph-panel host.
- [x] Verify initialization, resize, hide/show, repeated display, and render-context behavior.
- [x] Confirm backend failures remain explicit and do not silently select another renderer.
- [x] Record a retain/defer decision and platform-specific constraints for the VTK host.

**Findings:**

- A native wx host on macOS with wxPython 4.2.4 (osx-cocoa) and VTK 9.6.2 parented
  `wxVTKRenderWindowInteractor` to a graph-panel `wx.Panel`. The OpenGL render context
  initialized and passed `validate_render_context()` after the frame was shown.
- The widget resized from 800 x 568 to 620 x 428; the VTK render window tracked the high-DPI
  backing size. Hiding/showing the widget and rendering again succeeded. After finalizing and
  destroying the first host, a second host initialized and rendered successfully.
- Existing error paths remain explicit: import/widget creation and render-context failures raise
  `VTKBackendUnavailableError`; an explicitly requested VTK backend reports failure, while
  `auto` reports its Matplotlib fallback. The four VTK view tests and both app-level error/fallback
  tests passed (6 total).
- **Decision:** retain VTK as an embedded backend for the selected design on the verified macOS
  configuration. This probe does not establish behavior on Windows or Linux; those platforms
  still require their own OpenGL/context validation. The existing factory, explicit-error, and
  `auto` fallback behavior should remain unchanged when the production host is introduced.

**Done when:** VTK support in embedded panes is demonstrated or the limitation and required
backend decision are documented.
**Depends on:** Substep 1-1.

#### 1-3. Prototype repeated view-instance lifecycle

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Verify how the current name-keyed view map and clock subscriptions constrain duplicate
      instances of one view type.
- [x] Prototype stable panel IDs separate from registry view names.
- [x] Verify duplicated views have independent callbacks, cursor updates, and cleanup.
- [x] Record lifecycle changes needed to preserve exactly-once unsubscribe and close behavior.

**Findings:**

- The current `_open_views` map and close callbacks use registry view names as identities, and
  each registered opener raises an existing same-name window instead of creating another
  instance. This prevents duplicate panels of one view type even though separate view objects can
  be built independently.
- A native wx prototype hosted two independent speed/altitude views, both named
  `speed-altitude`, under separate panel IDs. Both received the shared clock seek; a click
  callback on the first canvas invoked only its panel callback and sought the shared clock.
  Disconnecting and closing the first instance left the second updating normally.
- Production lifecycle should key hosted-panel state and close callbacks by stable panel ID, while
  retaining the registry name solely as the selected view type. Each panel must own its view,
  canvas/toolbar callback ID, and clock unsubscribe callback. Teardown disconnects and
  unsubscribes that instance before closing its view and destroying its host; the prototype
  verified exactly one unsubscribe per panel.

**Done when:** independent instances can be opened and closed without cross-panel effects or
subscription leaks, or the blocking constraint is identified.
**Depends on:** Substep 1-1.

#### 1-4. Check vertical icon-button rail feasibility

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Prototype an icon-only feature rail with `wx.BitmapToggleButton` controls and
      `wx.Simplebook` pages.
- [x] Verify feature names, hover tooltips, toggle selection state, and Up/Down handling of a
      wx key event.
- [x] Check native behavior on currently available supported platforms.
- [x] Obtain approval for the selected control pattern and record the platform-specific
      accessibility validation still required.

**Findings:**

- On the available macOS wxPython 4.2.4 osx-cocoa build, a `wx.Notebook` with `wx.NB_LEFT` and
  an image list accepts empty page labels and per-page images. Pages can be named, but the
  notebook exposes no per-page tooltip API; `GetAccessible()` and `GetOrCreateAccessible()` both
  raise `NotImplementedError`. `wx.UIActionSimulator` reported sending an arrow key, but focus
  remained unset and the native notebook selection did not change. Native keyboard and
  screen-reader behavior therefore remain unverified.
- A custom vertical rail made from `wx.BitmapToggleButton` controls with a `wx.Simplebook` can
  retain icon-only navigation, per-button names/tooltips, a toggle-based selected state, and
  explicit Up/Down selection handling. A synthetic wx key event selected the next page, but
  native keyboard focus and screen-reader exposure of the button names still require manual
  verification.
- **Decision (user approved):** use the custom icon-button rail plus `wx.Simplebook`. It preserves
  the icon-only visual design but is not a native `wx.Notebook`. `SetName`, tooltips, toggle
  selection, and synthetic Up/Down handling were verified on the available macOS wxPython build;
  native keyboard focus and screen-reader exposure were not. Validate those semantics in Steps 8
  and 11. Other supported platforms still need their own validation.

**Done when:** the approved feature-rail pattern is prototyped, its core interaction hooks work,
and remaining native accessibility validation is explicitly scheduled.
**Depends on:** Main plan Steps 23–27.

#### 1-5. Prototype nested splitters and scrollable graph stacks

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Prototype the left/middle/right splitter arrangement with a resizable optional right pane.
- [x] Test right-pane close/reopen while retaining its contents and width.
- [x] Stack multiple graph panels in independently scrollable regions with minimum plot sizes.
- [x] Test narrowing the window and moving splitters near their minimum positions.
- [x] Record layout constraints and a concrete initial sizing/scrolling policy.

**Findings:**

- Nested `wx.SplitterWindow` controls work for the left pane and the middle/optional-right pair.
  `Unsplit(right)` hides but does not destroy the right stack; its view selections and 320-pixel
  width were restored by splitting the same window back into place. The middle stack expanded
  while the right pane was closed.
- Independent `wx.ScrolledWindow` stacks with 320 x 280 minimum child panels scrolled correctly
  when three panels exceeded the available height. Each stack had its own scroll range and
  retained its panel children.
- On macOS, `SetSashGravity(1.0)` on the middle/right splitter preserved the right pane while
  the middle pane shrank. `SetMinimumPaneSize(320)` prevented sash dragging below the minimum,
  but programmatically resizing the frame below the combined pane minimum still compressed the
  right pane. A 920-pixel initial frame minimum left approximately 320 pixels for both graph
  panes in the prototype; below that width, the right pane should be closed or the frame should
  remain at its platform minimum. Native user-driven enforcement of the frame minimum still
  needs manual verification.
- **Initial policy:** start near 1100 x 760; target a 920-pixel minimum width with the right pane
  open, 240 pixels for the feature region, and at least 320 pixels for each graph pane. Use
  independent vertical scrollers with a 20-pixel scroll step and 320 x 280 minimum panel
  placeholders. Treat the plot minimum as provisional until real figures are checked in Step 7.

**Done when:** the selected pane arrangement behaves predictably at its minimum supported sizes
and preserves hidden right-pane state, or blocking constraints are documented.
**Depends on:** Substeps 1-1 and 1-3.

#### 1-6. Measure the multi-panel rendering risk

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Benchmark embedded 2D views and each supported 3D backend at the existing 33 ms playback
      timer rate.
- [x] Measure all seven registered view types with the 5,402-sample OEM history; record that
      the design has no limit on additional duplicate panels.
- [x] Measure native playback-timer scheduling and posted UI-callback latency separately from
      headless Agg redraw time.
- [x] Record the workload baseline, performance targets, required mitigation, and remaining
      uncertainty.

**Findings:**

- The reference workload opened all seven registered view types in two vertically scrolling
  stacks with the 5,402-sample `ISS_2026-05-20.OEM` history, at the existing 33 ms playback tick.
  The design permits additional duplicate panels and defines no finite maximum; seven unique
  views is therefore a repeatable reference workload, not a hard upper bound.
- On macOS with wxPython 4.2.4 and Matplotlib 3.9.4, a 3-second native run produced only eight
  playback ticks in about 3.3 seconds. With Matplotlib 3D, playback tick p95 was 473 ms and
  posted `wx.CallAfter` callback p95/max latency was 436/439 ms; the playback handler itself
  took under 0.4 ms p95. With VTK 9.6.2 3D, tick p95 was 434 ms and posted callback p95/max
  latency was 354/365 ms; the timer handler took under 5 ms p95. A 10 ms wx timer sentinel
  recorded similar delays. The posted callback is an event-queue responsiveness measure, not a
  physical mouse/keyboard latency measurement.
- A separate headless Agg run drawing all seven Matplotlib figures sequentially for each update
  cycle measured 612 ms p50, 639 ms p95, and 698 ms maximum per full seven-view redraw. These
  headless figures do not include native wx/OpenGL context costs.
- **Required target:** under the seven-view reference workload, playback-tick interval p95 must
  be at most 50 ms, posted UI-callback p95 at most 50 ms, and posted-callback maximum at most
  100 ms. The baseline misses these targets substantially, so the embedded implementation must
  coalesce/throttle rendering work and avoid redraws for off-screen or hidden panels without
  dropping playback-clock updates. Re-run the native workload after that change; platform and
  duplicate-panel scaling remain unverified.

**Done when:** expected multi-panel rendering cost is measured on the available native wx
environment and remaining platform uncertainty is stated.
**Depends on:** Substeps 1-1 and 1-2.

**Done when:** the active GUI baseline is recorded and all six feasibility substeps have passed
or have a documented blocker/decision.
**Depends on:** Main plan Steps 23–27.

### 2. Build the workspace shell and shared timeline

Create the main workspace frame with placeholder regions for the left feature rail and
`wx.Simplebook` page host, middle and optional right graph stacks, and a shared timeline row below
the panes. Keep the existing content available during the transition; do not change clock or view
semantics in this step.

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Define a workspace owner and clear ownership for the feature rail/page host, stack regions,
      splitters, timeline, and child graph panels.
- [x] Create the main workspace frame and placeholder regions for the left, middle, and optional
      right pane.
- [x] Give the panes visible role-based headings and matching wx window names.
- [x] Keep the shared time slider below the full pane area and bind it to the existing seek
      callback without introducing recursive slider events.
- [x] Add focused tests for workspace construction and timeline placement/state.
- [x] Confirm app shutdown still closes the wx event loop and owned resources once.

**Implementation and validation:**

- `PlayerApp` retains ownership of the top-level frame and timer. The new `Workspace` owns the
  feature rail and `wx.Simplebook`, nested splitters, graph placeholders, and global timeline.
  The pane labels are **Controls & Info**, **Main Analysis**, and **Comparison**.
- The Playback page retains the existing controls; OEM context and metadata are available on the
  separate OEM file information page. The middle stack is visible initially and the optional
  right stack can be hidden/reopened without replacing its panel.
- The timeline footer spans the panes, uses the existing fraction-seek callback, and suppresses
  programmatic slider events while reflecting clock updates. The initial frame size is 1100 x 760
  with a 920 x 480 minimum.
- Workspace, app, and control-window tests passed: **136 passed** with 14 existing
  Matplotlib/Pyparsing deprecation warnings. A native wx smoke test also constructed the controls,
  toggled the right pane, updated the timeline, and closed the frame successfully.

**Done when:** the workspace shell is displayed with a global timeline and testable pane
placeholders while the existing GUI behavior remains available.
**Depends on:** Step 1.

### 3. Embed Matplotlib views in reusable graph-panel hosts

Replace the assumption that a Matplotlib view owns a top-level `wx.Frame` with a reusable
graph-panel host. Keep the view registry responsible for available view types and preserve the
existing view contract.

- **Status:** Done with an accepted performance limitation.
- **Progress:** 7/7 checklist items.
- [x] Separate Matplotlib view construction and plot-content hosting from `_open_view` frame
      construction.
- [x] Parent Matplotlib canvases and navigation toolbars to graph-panel hosts while preserving
      toolbar-mode handling and click-to-seek.
- [x] Update each embedded view from the shared playback clock and initialize it at the current
      cursor time.
- [x] Add focused tests for Matplotlib host construction, resize/redraw, and clock-synchronized
      updates.
- [x] Verify click-to-seek and Matplotlib zoom/pan toolbar behavior in an embedded host.
- [x] Surface view construction failures through the existing explicit error path.
- [x] Coalesce/throttle redraws and skip off-screen panel rendering without dropping clock updates;
      document the measured target miss and accepted limitation.

**Implementation and validation:**

- Matplotlib views are hosted in reusable graph panels with embedded canvases and toolbars. View
  updates remain subscribed to the shared clock, while redraws are coalesced and off-screen
  panels are skipped. Construction failures use the existing explicit cleanup-and-reraise path.
- The focused graph-panel, workspace, app, plotting, and baseline tests passed: **41 passed**.
  A native macOS wx smoke test verified canvas resizing, click-to-seek and pan-mode suppression
  through synthetic Matplotlib events, and clean shutdown.
- In a 3.5-second native run with all seven registered views and the 5,402-sample
  `ISS_2026-05-20.OEM`, playback-tick interval p95 was 93.0 ms and posted UI-callback p95/max
  latency was 92.5/94.5 ms. The targets are 50 ms, 50 ms, and 100 ms, respectively. Thus the
  p95 targets remain unmet; the callback maximum target passed.
- Lowering the state-components figure DPI reduced its isolated median draw from 57.5 ms at
  100 DPI to 49.3 ms at 50 DPI, but this would reduce display resolution and did not establish
  that the seven-view target could be met. Partial WxAgg blitting remains disabled because it
  previously caused stale/offset plot content after click-to-seek.
- The user accepted the measured macOS performance limitation and requested retaining full-redraw
  behavior. Results on other platforms remain unverified; the target miss is documented rather
  than represented as a performance pass.

**Done when:** embedded Matplotlib views render and interact correctly, and the measured
responsiveness limitation is explicitly accepted and documented.
**Depends on:** Step 2 and Substep 1-1.

### Milestone G1 — Workspace shell and embedded view hosts

#### Prerequisite before Step 4 — Make the three main panes resizable

Complete and validate the main workspace's side-by-side pane resizing before starting the next
implementation step.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Make the left feature pane, middle graph pane, and optional right graph pane independently
      width-resizable with draggable vertical sashes.
- [x] Use a visible, non-thin 3D sash style and verify its handle width in dark mode.
- [x] Ensure each sash adjusts its adjacent panes while respecting minimum widths and keeping
      unrelated pane sizes stable.
- [x] Preserve the user-adjusted middle/right widths when the right pane is closed and reopened.
- [x] Test both sashes at normal and minimum window widths, including closing and reopening the
      right pane.

**Implementation and validation:** The outer splitter exposes the left-feature/graph-area sash
and keeps the left width stable as the frame changes size. The graph splitter exposes the
middle/right sash and keeps the right width stable while the left graph area grows or shrinks.
Closing the right pane captures its width, and reopening restores that width subject to pane
minimums. The complete play-oem test suite passed (**145 passed**). A native macOS wx smoke test
moved both sashes through the native wx API, changed the frame width while the right pane was
closed, and confirmed the right pane reopened at its adjusted 400-pixel width. A dark-mode smoke
test confirmed that `wx.SP_3DSASH` increases both native sash widths from 1 to 9 pixels on the
available wxPython 4.2.4 macOS build.

**Blocking gate:** Complete; Step 4 may proceed.
**Done when:** the three main pane widths can be adjusted independently and the right pane restores
its user-set width.

### 4. Define panel-instance lifecycle and embed supported VTK views

Separate panel-instance identity from registered view type so a stack can host independent copies
of the same view. Integrate VTK wx content in the graph host if VTK remains a supported backend.

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Assign each graph panel a stable instance ID independent of its selected view type.
- [x] Permit separate instances of the same view without sharing callbacks, state, or cleanup.
- [x] Ensure each instance receives the current clock time and unsubscribes exactly once on close.
- [x] Reparent VTK wx content into a graph-panel host if VTK remains supported as a backend.
- [x] Preserve explicit backend-selection, initialization, and rendering errors.
- [x] Test instance lifecycle and supported VTK host behavior; record if VTK is not retained.

**Implementation and validation:** `GraphPanelHost` gives each host a stable panel ID and
contains either WxAgg controls or native wx plot content. `PlayerApp` indexes every instance by
panel ID while preserving the default one-per-view registry path. Duplicate instances receive
independent clock subscriptions and are cleaned up independently; native content refreshes when
scheduled without queuing redundant VTK redraw work on every clock update. Explicit VTK
initialization and render failures remain errors. The play-oem suite passed (**145 passed**,
14 existing Matplotlib/Pyparsing deprecation warnings). A native VTK smoke test confirmed host
parenting, independent duplicate close, full cleanup, and canvas resize from 514x248 to 614x248
after frame resizing. In the same dark-mode run, both main sash handles measured 9 pixels.

**Done when:** panel identity and cleanup are correct for repeated view types, and supported
backends work in embedded hosts.
**Depends on:** Step 3, the three-main-pane resizing prerequisite above, and Substeps 1-2 and 1-3.

### 5. Add graph stacks, selectors, and empty states

Allow each graph stack to contain zero or more graph panels. Each panel selects its view
independently; empty stacks remain discoverable and usable.

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Add an **Add graph** action to the middle and optional right stack.
- [x] Show a clear empty state with an add action when a stack contains no panels.
- [x] Give each panel a view-selection combobox populated from the view registry.
- [x] Ensure selection changes update only the chosen panel and clean up its previous view.
- [x] Surface view-creation errors without leaving a broken or success-shaped panel.
- [x] Test empty, one-panel, and multi-panel stacks plus independent selector changes.

**Implementation and validation:** Both graph panes expose an Add graph button, and empty stacks
also show an add action. Each panel has a view selector populated with implemented registry views.
Changing one selector replaces only that panel's view and closes the prior view; creation failures
are shown in an error dialog and the failed panel is removed rather than left in a success-shaped
state. Focused workspace, panel, and app tests passed (**43 passed**); the complete play-oem suite
passed (**147 passed**, 14 existing Matplotlib/Pyparsing deprecation warnings).

**Done when:** both stacks support zero or more panels and each panel's view can be selected
independently.
**Depends on:** Steps 2 and 4 and Substep 1-5.
