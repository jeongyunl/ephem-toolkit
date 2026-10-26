# `play-oem` — Ground Station Visual Analysis Implementation Plan

Requirements and technical contracts:
[PLAY_OEM_GROUND_STATION_ANALYSIS_SOFTWARE_DESIGN.md](./PLAY_OEM_GROUND_STATION_ANALYSIS_SOFTWARE_DESIGN.md).
GUI behavior and mockup:
[PLAY_OEM_GROUND_STATION_ANALYSIS_GUI_DESIGN.md](./PLAY_OEM_GROUND_STATION_ANALYSIS_GUI_DESIGN.md).
Existing access behavior:
[Ground Stations implementation report](./old/PLAY_OEM_GROUND_STATIONS_IMPLEMENTATION_REPORT.md).

This is a proposed follow-on plan; no code changes are included in this planning task. Follow the
steps in order. Do not begin a later pending step until the current step's checklist and
completion criteria pass. Keep any implementation evidence with the completed step.

## 1. Add station markers to Ground Track

Add a toggleable station layer to the existing Ground Track view. Project saved station
coordinates through the active map projection, provide selectable markers and an **Open Passes**
action, and keep the interaction separate from playback seeking.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Pass the current station snapshot and pass-view action through the established view factory.
- [ ] Draw all configured stations with a focused-marker treatment and optional label control.
- [ ] Add accessible marker details and **Open Passes** action seeded with the station ID.
- [ ] Verify zero stations, station edits/removal, both projections, center-longitude changes,
  seam-adjacent locations, and map navigation.
- [ ] Verify marker interaction does not seek or prepare access history.

**Done when:** station markers remain correct through OEM/view updates and do not change existing
Ground Track projection, footprint, navigation, or playback behavior.
**Depends on:** None.

## 2. Retain topocentric look-angle profiles in the shared access cache

Extend the existing per-segment elevation profiles to retain azimuth at the same evaluation
epochs. Preserve refined interval-boundary look angles so the selected pass can be rendered
without another history calculation.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Introduce a per-segment look-angle profile containing times, azimuths, and elevations.
- [ ] Retain start/end azimuth and elevation for refined access crossings.
- [ ] Keep sample limits, segment isolation, crossing refinement, and coverage/gap flags intact.
- [ ] Update the existing Ground Station Access graph to consume the new profile shape without
  changing its appearance or Plot Range behavior.
- [ ] Test azimuth convention, finite values, interval endpoints, invalid samples, and cache reuse.

**Done when:** elevation and azimuth history are available from one cached access preparation,
with the existing elevation graph and pass intervals unchanged.
**Depends on:** None.

## 3. Implement the Ground Station Passes table view

Register `ground-station-passes` and implement station selection, chronological interval rows,
coverage/gap labels, Plot Range filtering, stable row selection, **Focus pass**, and **Seek to
peak** actions.

- **Status:** Not started.
- **Progress:** 0/7 checklist items.
- [ ] Build the wx view from the existing `StationAccessCache` and current OEM context.
- [ ] Render start/end, duration, peak elevation/time, minimum range/time, and limitation status.
- [ ] Show only intervals overlapping the shared Plot Range, including passes crossing a range
  boundary; display their full OEM-bounded details.
- [ ] Display both shared Plot Range endpoints in UTC in the panel header and update the readout
  on every range change, including when no pass overlaps.
- [ ] Refresh rows on Plot Range changes without recomputing access history; preserve selection
  while it remains in range.
- [ ] Wire Focus pass to shared Plot Range without seeking; wire Seek to peak to the shared clock.
- [ ] Test range-boundary overlap, range filtering/readout updates, selection fallback, and
  no-overlap separately from no-access, unsupported, clipped, and gap-limited cases.

**Done when:** the table accurately filters cached intervals to Plot Range, preserves full pass
details, and explicit actions affect only their documented shared state.
**Depends on:** Step 2.

## 4. Add the selected-pass sky plot

Add the azimuth/elevation sky plot beside the pass table, stacking it below the table at narrow
panel widths. Selecting a row updates the plot; playback only moves the current-time marker.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Draw compass directions, elevation rings, horizon, and station mask.
- [ ] Plot only the selected access interval at or above the station mask.
- [ ] Mark interval start, peak, and end; show the playback marker only inside the interval.
- [ ] Break the path at invalid values and segment/gap boundaries; handle zenith explicitly.
- [ ] Test polar coordinates, pass selection, mask clipping, playback movement, and unavailable
  states.

**Done when:** the sky plot is a faithful, accessible rendering of the selected cached pass and
does not calculate historical look angles in the view.
**Depends on:** Steps 2 and 3.

## 5. Integrate, validate, and publish the feature guidance

Complete registry, lifecycle, station/OEM updates, GUI validation, and end-user documentation.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Include the new view in `all` and leave `overview` unchanged.
- [ ] Verify additional Access/Passes panels share access histories and exact-sample ECEF
  conversions.
- [ ] Verify OEM replacement, station edits/removal, selection retention, panel close, and
  Plot Range updates.
- [ ] Run focused station-access, Ground Track, registry, and wx GUI tests.
- [ ] Live-check the mockup behavior in the wx application at normal and minimum panel sizes and
  in light/dark appearances.
- [ ] Update the Ground Stations user guide with map markers, pass-table columns, sky plot, and
  action semantics.

**Done when:** the new interactions are integrated and tested, the existing Ground Track and
Ground Station Access behaviors are preserved, and user-facing guidance matches the implementation.
**Depends on:** Steps 1, 3, and 4.
