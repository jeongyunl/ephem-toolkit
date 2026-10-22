# `play-oem` — Ground Track Implementation Plan

Requirements and architecture: [PLAY_OEM_GROUND_TRACK_SOFTWARE_DESIGN.md](./PLAY_OEM_GROUND_TRACK_SOFTWARE_DESIGN.md).
Selected user interface: [PLAY_OEM_GROUND_TRACK_GUI_DESIGN.md](./PLAY_OEM_GROUND_TRACK_GUI_DESIGN.md).
The plan follows the lifecycle and checklist conventions in
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md).

## How to use this plan

Work **one pending numbered step at a time, in order**. Do not begin a later pending step until
the current step's checklist and completion criteria pass. Keep steps in dependency order and
update status and progress as work advances.

- **Not started** — no work begun.
- **In progress** — implementation or its checks are underway.
- **Blocked** — cannot proceed; record the blocker.
- **Done** — all checklist items and completion criteria pass.

Progress is the number of checklist items completed. Do not mark a step done based only on code
being written. When architecture, interfaces, user-visible behavior, or dependencies change,
update the software and GUI design documents before proceeding with dependent work.

## Prerequisites

The shared wxPython application, graph-panel lifecycle, playback cursor, OEM segment handling,
and rendering foundations are in place in
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md), including steps 23–27.
Implement this feature after those foundations and before treating Ground Track as release-ready.
The feature is not implemented or registered yet.

## 1. Resolve implementation choices and record support limits

Select a projection implementation that provides Equirectangular, Robinson, and Winkel Tripel
for all map layers, supports a variable central longitude, and keeps both poles visible. Decide
whether to bundle coastline data for the first release or ship only the graticule. Record which
source frames and Earth-center aliases will be supported, the kernel/data validity range, and
whether per-panel projection and center preferences persist across application restarts. Keep
the selected GUI design's Robinson default and the integer 10° minimum-elevation default.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Evaluate candidate projection implementations for all three projections, central-longitude
      support, pole coverage, dependency impact, and wx/Matplotlib rendering.
- [ ] Choose and document a locally packaged coastline dataset and its license, or explicitly
      defer coastline outlines for the initial release.
- [ ] Define supported OEM center/frame combinations, aliases, conversion path, and kernel/data
      time range; document unsupported inputs and expected accuracy limits.
- [ ] Decide whether projection and center preferences are session-only or persisted; retain the
      shared saved minimum-elevation preference requirement.
- [ ] Update the software and GUI design documents with these decisions and confirm they agree.

**Done when:** implementation dependencies and support limits are explicit, compatible with the
selected GUI design, and recorded in the design documents.
**Depends on:** Existing implementation-plan steps 23–27.

## 2. Prepare Earth-fixed ground-track coordinates

Add a toolkit-independent preparation layer that consumes OEM timestamps, six-component states,
segment IDs, center, and reference frame. Validate Earth center and frame before conversion.
Convert supported inertial states to ITRF at their TT epochs, convert Earth-fixed positions to
WGS-84 geodetic latitude/longitude, and retain source indices and segment boundaries for cursor
lookup. Keep full-resolution prepared coordinates for marker placement; split displayed paths at
OEM gaps and at the seam defined by center longitude ±180°.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Add or expose the source metadata and segment-aware samples required by ground-track
      preparation without changing existing caller contracts unnecessarily.
- [ ] Implement Earth-center and frame validation and conversions using the choices from step 1.
- [ ] Convert Earth-fixed positions to WGS-84 geodetic coordinates and retain sample-to-source
      correspondence for exact and interpolated cursor times.
- [ ] Split track runs at OEM segment gaps and the selected center-longitude seam without
      introducing false connecting lines.
- [ ] Define explicit error results for unsupported centers/frames, conversion failures, and
      invalid kernel coverage; do not substitute inertial coordinates as Earth-fixed.
- [ ] Add headless checks for known frame conversions, geodetic coordinates, date-line seams,
      poles, segment boundaries, and cache invalidation on OEM replacement.

**Done when:** tested coordinate preparation returns valid Earth-fixed geodetic paths for
supported inputs, preserves segment and sample correspondence, and reports unsupported inputs
without involving wxPython or Matplotlib.
**Depends on:** Step 1; existing implementation-plan step 26.

## 3. Calculate current-time ground footprints

Implement the 0° horizon and selected minimum-elevation boundaries on the WGS-84 ellipsoid,
using sea-level ground points and local geodetic elevation. Keep the calculation independent of
the map projection. Produce geographic boundary points, split them at the current map seam when
rendered, and bound update cost so clock notifications do not stall wx input.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Implement the WGS-84 boundary solver for the horizon and an integer threshold from 0° to
      90°.
- [ ] Handle 0° as coincident boundaries and 90° as a degenerate sub-satellite point.
- [ ] Return no misleading footprint when the current cursor state is unavailable or invalid.
- [ ] Choose and profile azimuth sampling and refresh limits using representative orbital
      altitudes before fixing the update policy.
- [ ] Add headless checks for known positions, thresholds, polar cases, seam crossings, and
      invalid cursor states.

**Done when:** footprint results match the WGS-84 elevation definition, cover the defined edge
cases, and can be computed within the accepted UI update budget.
**Depends on:** Step 2.

## 4. Implement the static Ground Track view and register it

Build the selected balanced-map view using the existing `View` lifecycle and wx-hosted
Matplotlib figure. Draw the full usable track, poles, graticule, current marker, footprint
boundaries, labels, and footer/readout. Use the selected Robinson projection by default, apply
one projection and center consistently to all layers, and keep static geometry separate from
playback-only marker/readout updates. Register `ground-track` as an individual view and include
it in `all`, not in `overview`.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Add the Ground Track view with `build`, `update`, and `close` behavior compatible with the
      current graph-panel host.
- [ ] Render the initial full-world Robinson map with both poles, labeled axes, graticule, and
      the static track split at data gaps and map seams.
- [ ] Render the distinct current marker, latitude/longitude readout, and both current-time
      footprint boundaries; update only dynamic artists during playback.
- [ ] Add Equirectangular, Robinson, and Winkel Tripel rendering using the selected projection
      implementation, validating that both poles remain visible.
- [ ] Register the view as `ground-track`, add it to the `all` group only, and preserve
      `overview` composition and existing view names.
- [ ] Add headless view tests for static rendering, projection transforms, cursor updates, gaps,
      close/rebuild, and OEM replacement.

**Done when:** the view opens as an ordinary graph panel, renders static and dynamic layers
correctly, follows the shared cursor, and is selectable individually or through `all` without
changing the default overview.
**Depends on:** Steps 2 and 3.

## 5. Add selected controls, map navigation, and saved preference behavior

Implement the selected control row: per-panel Projection and Center longitude controls, a shared
integer-only Minimum elevation spin button, and home, zoom-in, zoom-out, and pan controls. Add
wheel zoom and scrollbars for an enlarged map. Keep navigation local to the map panel and update
Center longitude whenever the visible map center changes.

- **Status:** Not started.
- **Progress:** 0/7 checklist items.
- [ ] Add an accessible integer-only minimum-elevation spin control from 0° through 90° in 1°
      steps, defaulting to 10° and updating all open Ground Track panels.
- [ ] Add the per-panel projection selector, defaulting to Robinson; changing projection resets
      only that panel's extent and retains its center longitude.
- [ ] Add an editable per-panel center-longitude control in degrees east, normalized to
      `[-180°, 180°)`, and recenter the map when the value is edited.
- [ ] Implement toolbar zoom/pan, pointer-centered wheel zoom, and horizontal/vertical scrollbars
      when zoomed; synchronize Center longitude with the visible map center after each action.
- [ ] Preserve zoom, scroll, projection, and center while playback updates the marker; reset to
      full-world extent around the current center only through home or projection change.
- [ ] Ensure clicks and drags over the map do not invoke time-series click-to-seek or scroll the
      graph stack; dragging pans only while pan mode is active.
- [ ] Persist the minimum-elevation preference through application state and implement the
      projection/center persistence choice recorded in step 1, including saved-state migration
      and invalid-value fallback where needed.

**Done when:** the selected design's controls work in the wx panel, map navigation and center
longitude stay synchronized across the seam, playback preserves the chosen view, and saved
preferences restore safely.
**Depends on:** Steps 1 and 4.

## 6. Integrate errors, verify the live GUI, and update documentation

Complete error presentation and integration checks across graph stacks, panel lifecycle, and OEM
replacement. Confirm the map remains responsive during playback and that unsupported input never
affects other views. Update user-facing documentation only after behavior matches the selected
design.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Show concise in-panel errors for non-Earth center, unsupported frame, conversion failure,
      and kernel/data range problems while leaving other panels usable.
- [ ] Show explicit unavailable marker/readout state in cursor gaps without removing the static
      path.
- [ ] Verify open/replace/duplicate/move/close behavior in Main Analysis and Comparison, and
      invalidate prepared data after OEM replacement.
- [ ] Verify the shared playback clock, reverse playback, seeking, minimum-elevation updates,
      projection changes, center edits, pan/zoom/scroll, and no-seek map interactions together.
- [ ] Perform a live wx visual check for selected layout, both poles, controls, labels, theme
      contrast, keyboard focus, resize behavior, and acceptable redraw responsiveness.
- [ ] Update Ground Track user documentation, implementation/design links, and release notes or
      limitations to match the tested behavior and approved coastline decision.

**Done when:** the Ground Track view works as an integrated wx graph panel, defined error states
are clear and isolated, the selected design passes live validation, and documentation reflects
verified behavior.
**Depends on:** Steps 4 and 5.
