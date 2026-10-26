# `play-oem` — Ground Station Visual Analysis Implementation Report

Requirements and technical contracts:
[PLAY_OEM_GROUND_STATION_ANALYSIS_SOFTWARE_DESIGN.md](./PLAY_OEM_GROUND_STATION_ANALYSIS_SOFTWARE_DESIGN.md).
GUI behavior and mockup:
[PLAY_OEM_GROUND_STATION_ANALYSIS_GUI_DESIGN.md](./PLAY_OEM_GROUND_STATION_ANALYSIS_GUI_DESIGN.md).
Existing access behavior:
[Ground Stations implementation report](./old/PLAY_OEM_GROUND_STATIONS_IMPLEMENTATION_REPORT.md).

Implementation is complete and the report below records automated evidence. Manual visual
inspection of light and dark appearances remains a follow-up; responsive wx layout checks were
run separately using the workspace-selected interpreter because the standard `python3` test run
skips display-gated tests.

## 1. Add station markers to Ground Track

Add a toggleable station layer to the existing Ground Track view. Project saved station
coordinates through the active map projection, provide selectable markers and an **Open Passes**
action, and keep the interaction separate from playback seeking.

- **Status:** Complete.
- **Progress:** 5/5 checklist items.
- [x] Pass the current station snapshot and pass-view action through the established view factory.
- [x] Draw all configured stations with a focused-marker treatment and optional label control.
- [x] Add accessible marker details and **Open Passes** action seeded with the station ID.
- [x] Verify zero stations, station edits/removal, both projections, center-longitude changes,
  seam-adjacent locations, and map navigation.
- [x] Verify marker interaction does not seek or prepare access history.

**Done when:** station markers remain correct through OEM/view updates and do not change existing
Ground Track projection, footprint, navigation, or playback behavior.
**Depends on:** None.
**Evidence:** Ground Track tests cover projection and station updates/removal; app tests verify
the Open Passes action preserves playback time and does not prepare access history.

## 2. Retain topocentric look-angle profiles in the shared access cache

Extend the existing per-segment elevation profiles to retain azimuth at the same evaluation
epochs. Preserve refined interval-boundary look angles so the selected pass can be rendered
without another history calculation.

- **Status:** Complete.
- **Progress:** 5/5 checklist items.
- [x] Introduce a per-segment look-angle profile containing times, azimuths, and elevations.
- [x] Retain start/end azimuth and elevation for refined access crossings.
- [x] Keep sample limits, segment isolation, crossing refinement, and coverage/gap flags intact.
- [x] Update the existing Ground Station Access graph to consume the new profile shape without
  changing its appearance or Plot Range behavior.
- [x] Test azimuth convention, finite values, interval endpoints, invalid samples, and cache reuse.

**Done when:** elevation and azimuth history are available from one cached access preparation,
with the existing elevation graph and pass intervals unchanged.
**Depends on:** None.
**Evidence:** `test_station_access.py` and `test_ground_station_access_view.py` pass with shared
profile preparation, refined boundaries, and preserved elevation-graph behavior.

## 3. Implement the Ground Station Passes table view

Register `ground-station-passes` and implement station selection, chronological interval rows,
coverage/gap labels, Plot Range filtering, stable row selection, **Focus pass**, and **Seek to
peak** actions.

- **Status:** Complete.
- **Progress:** 7/7 checklist items.
- [x] Build the wx view from the existing `StationAccessCache` and current OEM context.
- [x] Render start/end, duration, peak elevation/time, minimum range/time, and limitation status.
- [x] Show only intervals overlapping the shared Plot Range, including passes crossing a range
  boundary; display their full OEM-bounded details.
- [x] Display both shared Plot Range endpoints in UTC in the panel header and update the readout
  on every range change, including when no pass overlaps.
- [x] Refresh rows on Plot Range changes without recomputing access history; preserve selection
  while it remains in range.
- [x] Wire Focus pass to shared Plot Range without seeking; wire Seek to peak to the shared clock.
- [x] Test range-boundary overlap, range filtering/readout updates, selection fallback, and
  no-overlap separately from no-access, unsupported, clipped, and gap-limited cases.

**Done when:** the table accurately filters cached intervals to Plot Range, preserves full pass
details, and explicit actions affect only their documented shared state.
**Depends on:** Step 2.
**Evidence:** `test_ground_station_passes_view.py` covers filtering, range status, selection,
actions, shared cache use, and sky-plot data. An app test verifies Focus pass changes Plot Range
without seeking.

## 4. Add the selected-pass sky plot

Add the azimuth/elevation sky plot beside the pass table, stacking it below the table at narrow
panel widths. Selecting a row updates the plot; playback only moves the current-time marker.

- **Status:** Complete.
- **Progress:** 5/5 checklist items.
- [x] Draw compass directions, elevation rings, horizon, and station mask.
- [x] Plot only the selected access interval at or above the station mask.
- [x] Mark interval start, peak, and end; show the playback marker only inside the interval.
- [x] Break the path at invalid values and segment/gap boundaries; handle zenith explicitly.
- [x] Test polar coordinates, pass selection, mask clipping, playback movement, and unavailable
  states.

**Done when:** the sky plot is a faithful, accessible rendering of the selected cached pass and
does not calculate historical look angles in the view.
**Depends on:** Steps 2 and 3.
**Evidence:** `test_ground_station_passes_view.py` verifies polar projection, mask clipping,
segmented paths, markers, and cached playback updates.

## 5. Integrate, validate, and publish the feature guidance

Complete registry, lifecycle, station/OEM updates, GUI validation, and end-user documentation.

- **Status:** Implemented; manual visual review remains.
- **Progress:** 6/7 checklist items.
- [x] Include the new view in `all` and leave `overview` unchanged.
- [x] Verify additional Access/Passes panels share access histories and exact-sample ECEF
  conversions.
- [x] Verify OEM replacement, station edits/removal, selection retention, panel close, and
  Plot Range updates.
- [x] Run focused station-access, Ground Track, registry, and wx GUI tests.
- [x] Run display-backed wx tests for the pass-panel responsive layout, Ground Track controls, and
  workspace resizing.
- [ ] Manually inspect the wx application and mockup at normal and minimum panel sizes in light
  and dark appearances.
- [x] Update the Ground Stations user guide with map markers, pass-table columns, sky plot, and
  action semantics.

**Done when:** the new interactions are integrated and tested, the existing Ground Track and
Ground Station Access behaviors are preserved, and user-facing guidance matches the implementation.
**Depends on:** Steps 1, 3, and 4.
**Validation:** `python3 -m pytest -q tests/ephem_toolkit/play_oem` — 404 passed, 4 skipped.
The four display-gated wx tests passed separately using the workspace-selected interpreter.
Pylance reported no errors in the reviewed source modules; remaining diagnostics were
unused-parameter hints. Documentation links and SVG XML were validated, and `git diff --check`
passed.
