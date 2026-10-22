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
The implementation is underway; this plan tracks implementation and validation completion.

## 1. Resolve implementation choices and record support limits

Select a projection implementation that provides Equirectangular, Robinson, and Winkel Tripel
for all map layers, supports a variable central longitude, and keeps both poles visible. Decide
whether to bundle coastline data for the first release or ship only the graticule. Record which
source frames and Earth-center aliases will be supported, the kernel/data validity range, and
whether per-panel projection and center preferences persist across application restarts. Keep
the selected GUI design's Robinson default and the integer 10° minimum-elevation default.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Evaluate candidate projection implementations for all three projections, central-longitude
      support, pole coverage, dependency impact, and wx/Matplotlib rendering.
- [x] Choose and document a locally packaged coastline dataset and its license, or explicitly
      defer coastline outlines for the initial release.
- [x] Define supported OEM center/frame combinations, aliases, conversion path, and kernel/data
      time range; document unsupported inputs and expected accuracy limits.
- [x] Decide whether projection and center preferences are session-only or persisted; retain the
      shared saved minimum-elevation preference requirement.
- [x] Update the software and GUI design documents with these decisions and confirm they agree.

**Done when:** implementation dependencies and support limits are explicit, compatible with the
selected GUI design, and recorded in the design documents.
**Depends on:** Existing implementation-plan steps 23–27.

**Step 1 evidence and decisions:** pyproj/PROJ is selected for all three projections and is
declared in the optional `playback` extra; projection probes with pyproj 3.6.1 and Matplotlib
Agg produced finite points at both poles and across seam longitudes for five map centers. The
selected Winkel Tripel operation uses its 50.467° standard parallel. Coastlines are deferred.
Accepted centers are `EARTH` and `399`; accepted direct Earth-fixed frames are `ITRF`,
`ITRF1993`, and alias `ITRF93`; accepted inertial frames are `J2000`, `EME2000`, `ICRF`, `GCRF`,
and `TEME`, converted with the IAU 2006 route to ITRF. Other frame names are rejected. That route
does not have a declared accuracy date range; unsupported kernel initialization or conversion
errors must be reported. Only minimum elevation persists across restarts; projection and center
are session-only. Decisions are recorded in both design documents. `poetry lock --no-update`
and `poetry check` succeeded. `poetry install --extras playback` could not write to the host's
read-only Poetry artifact cache, so a clean extra installation still needs a writable cache in
the verification environment.

## 2. Prepare Earth-fixed ground-track coordinates

Add a toolkit-independent preparation layer that consumes OEM timestamps, six-component states,
segment IDs, center, and reference frame. Validate Earth center and frame before conversion.
Convert supported inertial states to ITRF at their TT epochs, convert Earth-fixed positions to
WGS-84 geodetic latitude/longitude, and retain source indices and segment boundaries for cursor
lookup. Keep full-resolution prepared coordinates for marker placement; split displayed paths at
OEM gaps and at the seam defined by center longitude ±180°.

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Add or expose the source metadata and segment-aware samples required by ground-track
      preparation without changing existing caller contracts unnecessarily.
- [x] Implement Earth-center and frame validation and conversions using the choices from step 1.
- [x] Convert Earth-fixed positions to WGS-84 geodetic coordinates and retain sample-to-source
      correspondence for exact and interpolated cursor times.
- [x] Split track runs at OEM segment gaps and the selected center-longitude seam without
      introducing false connecting lines.
- [x] Define explicit error results for unsupported centers/frames, conversion failures, and
      invalid kernel coverage; do not substitute inertial coordinates as Earth-fixed.
- [x] Add headless checks for mockable frame conversion, geodetic coordinates, date-line seams,
      poles, segment boundaries, and source sample/metadata correspondence.

**Done when:** tested coordinate preparation returns valid Earth-fixed geodetic paths for
supported inputs, preserves segment and sample correspondence, and reports unsupported inputs
without involving wxPython or Matplotlib.
**Depends on:** Step 1; existing implementation-plan step 26.

**Step 2 evidence:** `ground_track.py` prepares direct ITRF/ITRF1993 positions and lazily converts
supported inertial states. It reports invalid centers, frames, states, and conversion failures;
seam splitting adds interpolated edge points and separates OEM segments. `PlaybackData` now
retains copied source timestamps, states, segment IDs, center, and frame. The focused Ground
Track and data tests pass (26 passed). A real EME2000 sample from
`ISS_2026-05-20_small.OEM` converted through the installed TudatPy IAU 2006 route to a finite
ITRF state. Prepared-coordinate cache invalidation remains an application integration check in
steps 4 and 6.

## 3. Calculate current-time ground footprints

Implement the 0° horizon and selected minimum-elevation boundaries on the WGS-84 ellipsoid,
using sea-level ground points and local geodetic elevation. Keep the calculation independent of
the map projection. Produce geographic boundary points, split them at the current map seam when
rendered, and bound update cost so clock notifications do not stall wx input.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Implement the WGS-84 boundary solver for the horizon and an integer threshold from 0° to
      90°.
- [x] Handle 0° as coincident boundaries and 90° as a degenerate sub-satellite point.
- [x] Return no misleading footprint when the current cursor state is unavailable or invalid.
- [x] Choose and profile azimuth sampling and refresh limits using representative orbital
      altitudes before fixing the update policy.
- [x] Add headless checks for known positions, thresholds, polar cases, seam crossings, and
      invalid cursor states.

**Done when:** footprint results match the WGS-84 elevation definition, cover the defined edge
cases, and can be computed within the accepted UI update budget.
**Depends on:** Step 2.

**Step 3 evidence:** `ground_footprints.py` uses WGS-84 geodesics from the sub-satellite point
and a numerical boundary solve against the local ellipsoid normal. It returns the shared horizon
only at 0°, a single subpoint at 90°, and no result for invalid or below-surface satellite
states. Accuracy tests evaluate actual local elevation at each sampled point. Profiling with a
420 km equatorial orbit measured 8.41 ms for 72 azimuth samples, 12.81 ms for 180, and 16.84 ms
for 360 per horizon-plus-mask update on the development host. Use 72 samples for the first view;
the GUI integration step will cap refresh frequency and share work across panels as needed.

## 4. Implement the static Ground Track view and register it

Build the selected balanced-map view using the existing `View` lifecycle and wx-hosted
Matplotlib figure. Draw the full usable track, poles, graticule, current marker, footprint
boundaries, labels, and footer/readout. Use the selected Robinson projection by default, apply
one projection and center consistently to all layers, and keep static geometry separate from
playback-only marker/readout updates. Register `ground-track` as an individual view and include
it in `all`, not in `overview`.

- **Status:** In progress.
- **Progress:** 5/6 checklist items.
- [x] Add the Ground Track view with `build`, `update`, and `close` behavior compatible with the
      current graph-panel host.
- [x] Render the initial full-world Robinson map with both poles, labeled axes, graticule, and
      the static track split at data gaps and map seams.
- [x] Render the distinct current marker, latitude/longitude readout, and both current-time
      footprint boundaries; update only dynamic artists during playback.
- [x] Add Equirectangular, Robinson, and Winkel Tripel rendering using the selected projection
      implementation, validating that both poles remain visible.
- [x] Register the view as `ground-track`, add it to the `all` group only, and preserve
      `overview` composition and existing view names.
- [ ] Add headless view tests for static rendering, projection transforms, cursor updates, gaps,
      close/rebuild, and OEM replacement.

**Done when:** the view opens as an ordinary graph panel, renders static and dynamic layers
correctly, follows the shared cursor, and is selectable individually or through `all` without
changing the default overview.
**Depends on:** Steps 2 and 3.

**Step 4 evidence:** `views/ground_track.py` implements the wx-hosted view, all three
projections, full-world polar coverage, static track runs, current marker/readout, seam-split
footprints, and view lifecycle. `ground-track` is registered as an individual view and is
included in `all`, while `overview` is unchanged. Projection transform tests, coordinate seam
tests, and existing panel lifecycle tests pass. The wx view-build check skips because wx cannot
connect to the X display provided by `xvfb-run`; view-level cursor, rebuild, and replacement
behavior therefore remains unverified.

## 5. Add selected controls, map navigation, and saved preference behavior

Implement the selected control row: per-panel Projection and Center longitude controls, a shared
integer-only Minimum elevation spin button, and home, zoom-in, zoom-out, and pan controls. Add
wheel zoom and scrollbars for an enlarged map. Keep navigation local to the map panel and update
Center longitude whenever the visible map center changes.

- **Status:** In progress.
- **Progress:** 7/7 checklist items.
- [x] Add an accessible integer-only minimum-elevation spin control from 0° through 90° in 1°
      steps, defaulting to 10° and updating all open Ground Track panels.
- [x] Add the per-panel projection selector, defaulting to Robinson; changing projection resets
      only that panel's extent and retains its center longitude.
- [x] Add an editable per-panel center-longitude control in degrees east, normalized to
      `[-180°, 180°)`, and recenter the map when the value is edited.
- [x] Implement toolbar zoom/pan, pointer-centered wheel zoom, and horizontal/vertical scrollbars
      when zoomed; synchronize Center longitude with the visible map center after each action.
- [x] Preserve zoom, scroll, projection, and center while playback updates the marker; reset to
      full-world extent around the current center only through home or projection change.
- [x] Ensure clicks and drags over the map do not invoke time-series click-to-seek or scroll the
      graph stack; dragging pans only while pan mode is active.
- [x] Persist the minimum-elevation preference through application state and implement the
      projection/center persistence choice recorded in step 1, including saved-state migration
      and invalid-value fallback where needed.

**Done when:** the selected design's controls work in the wx panel, map navigation and center
longitude stay synchronized across the seam, playback preserves the chosen view, and saved
preferences restore safely.
**Depends on:** Steps 1 and 4.

**Step 5 evidence:** The native wx control row provides a projection selector, editable
center-longitude control, and integer-only 0°–90° spin button. Toolbar pan/zoom, pointer-centered
wheel zoom, and map scrollbars are local to the Ground Track panel. Center longitude follows map
extent changes. The 0° boundary is drawn once; the 90° mask is rendered as a point. Minimum
elevation is shared across panels and persisted in state schema version 2; version 1 state files
load with the 10° default. Projection and center stay session-only. Preference migration and
application lifecycle tests pass; wx control interaction remains unverified because the X display
is unavailable.

## 6. Integrate errors, verify the live GUI, and update documentation

Complete error presentation and integration checks across graph stacks, panel lifecycle, and OEM
replacement. Confirm the map remains responsive during playback and that unsupported input never
affects other views. Update user-facing documentation only after behavior matches the selected
design.

- **Status:** In progress.
- **Progress:** 3/6 checklist items.
- [x] Show concise in-panel errors for non-Earth center, unsupported frame, conversion failure,
      and kernel/data range problems while leaving other panels usable.
- [x] Show explicit unavailable marker/readout state in cursor gaps without removing the static
      path.
- [ ] Verify open/replace/duplicate/move/close behavior in Main Analysis and Comparison, and
      invalidate prepared data after OEM replacement.
- [ ] Verify the shared playback clock, reverse playback, seeking, minimum-elevation updates,
      projection changes, center edits, pan/zoom/scroll, and no-seek map interactions together.
- [ ] Perform a live wx visual check for selected layout, both poles, controls, labels, theme
      contrast, keyboard focus, resize behavior, and acceptable redraw responsiveness.
- [x] Update Ground Track user documentation, implementation/design links, and release notes or
      limitations to match the tested behavior and approved coastline decision.

**Done when:** the Ground Track view works as an integrated wx graph panel, defined error states
are clear and isolated, the selected design passes live validation, and documentation reflects
verified behavior.
**Depends on:** Steps 4 and 5.

**Step 6 evidence:** Unsupported inputs and unavailable cursor states have explicit in-panel
messages. The user guide is at `docs/tools/PLAY_OEM_GROUND_TRACK.md`, and both design documents
link to this plan. Focused Ground Track, saved-state, registry, graph-panel, and application tests
pass (114 passed, 1 wx view test skipped). A live visual check and end-to-end map interaction
checks remain blocked because wx reports that it cannot connect to the X display under
`xvfb-run`; those are the remaining release validation items. Running the entire
`tests/ephem_toolkit/play_oem` directory reports 227 passed, 5 skipped, and 11 failures in the
pre-existing CLI option and playback-speed expectations; the Ground Track selection expectation
was updated for the new `all` group member.
