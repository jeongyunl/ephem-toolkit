# `play-oem` — Ground Station Visual Analysis Software Design

This proposal extends the implemented [Ground Track](./old/PLAY_OEM_GROUND_TRACK_SOFTWARE_DESIGN.md)
and [Ground Stations](./old/PLAY_OEM_GROUND_STATIONS_SOFTWARE_DESIGN.md) features. It adds
station context to the existing Ground Track map and a pass-inspection view that pairs an access
table with a sky-oriented plot. The companion interface specification is
[PLAY_OEM_GROUND_STATION_ANALYSIS_GUI_DESIGN.md](./PLAY_OEM_GROUND_STATION_ANALYSIS_GUI_DESIGN.md);
the dependency-ordered work is in
[PLAY_OEM_GROUND_STATION_ANALYSIS_IMPLEMENTATION_PLAN.md](./PLAY_OEM_GROUND_STATION_ANALYSIS_IMPLEMENTATION_PLAN.md).

## Purpose and scope

Improve inspection of ground-station access over the loaded OEM:

- Show configured station locations on the existing Ground Track map.
- Provide a selectable table of access intervals with useful pass metrics.
- Plot the selected interval as an azimuth/elevation path in a local sky view.
- Keep the pass table and sky plot together in one graph view so selecting a pass updates its
  sky path without app-wide selection state.

The feature remains geometric and bounded by the loaded OEM. It does not add a second global map,
compute station coverage footprints on the map, extrapolate beyond OEM coverage, or model terrain,
communications links, antenna limits, or scheduling.

## Existing contracts to preserve

- Ground Track continues to own the world map, projection, center longitude, map navigation,
  spacecraft subpoint, and spacecraft coverage boundaries. Station markers are an overlay on
  that view, not a replacement map.
- Ground Station Access continues to own the elevation-versus-time graph, current station metrics,
  fixed 0°–95° vertical scale, and shared Plot Range behavior.
- A station's minimum elevation remains independent of the Ground Track footprint setting.
- Station records remain zero-or-more, persisted in `play-oem.toml`; no default station is required.
- Ground Track and station access continue sharing exact-sample ECEF positions through the
  app-scoped `EarthFixedPositionCache`.
- Access history remains lazy and shared. Opening a pass or sky view may request cached station
  history; playback ticks, plot-range changes, and opening additional panels must not repeat
  history preparation.
- Keep the current `overview` group unchanged. Add the new pass-inspection view to `all` through
  the existing registry behavior.

## Ground Track station overlay

Project each configured station's WGS-84 geodetic latitude and longitude through the active
Ground Track projection and center longitude. This is a display-only transformation; it does not
require an OEM state conversion or station-access preparation.

Show station markers in a separately toggleable **Ground Stations** map layer. When enabled,
display every configured station. Keep the currently focused station visually distinct with a
selection ring and persistent label; unselected names may be revealed on hover or through the
station-label toggle to limit clutter. The layer is on by default when at least one station exists.
Store the layer toggle as a map-panel display preference, not in the station records.

Selecting a station marker shows its name, coordinates, and minimum-elevation mask. Provide an
explicit **Open Passes** action that opens the pass-inspection view for that station. Marker
selection and map navigation never seek the shared clock. Empty station collections simply have
no markers and no disabled map controls.

Do not draw station-centered access footprints on the map. They would require additional
time-dependent geometry and could imply that access has been calculated before an access view is
opened.

## Cached pass and look-angle data

Reuse `StationAccessCache` and its `EarthFixedPositionCache`. Extend the existing per-segment
elevation samples to retain topocentric azimuth at the same evaluation epochs:

```text
LookAngleProfile
  times_s
  azimuths_deg
  elevations_deg
```

Keep each profile confined to one valid OEM segment. Store the look angles at refined minimum-mask
crossings in the corresponding `AccessInterval`, or include those crossing epochs in the profile,
so the sky path begins and ends at the actual interval boundaries. Do not infer values across OEM
gaps or unsupported regions. The existing cursor lookup, maximum 30-second evaluation grid,
crossing refinement, sample limits, and explicit prediction limitations remain authoritative.

The pass-inspection view obtains `StationAccess` through the same app-scoped cache as
Ground Station Access. The cache retains intervals and look-angle profiles for the usable OEM
coverage; the view filters the table to intervals that overlap the current shared Plot Range:

```text
interval.start_s <= plot_range.end_s
and interval.end_s >= plot_range.start_s
```

This inclusive overlap filter includes a pass that crosses either Plot Range boundary. Keep the
interval's full OEM-bounded start/end and metrics in its row; the Plot Range filters which passes
are listed, it does not truncate pass details or the selected sky path. If no interval overlaps,
show a Plot Range-specific empty state distinct from a station with no access intervals anywhere
in OEM coverage.

The view consumes `AccessInterval` fields for start/end time, peak elevation and time, minimum
range and time, and coverage/gap flags. It must not run a second pass over the OEM states to
construct either the table or the sky plot.

Changing a station definition removes or replaces only that station's cached result according to
the existing invalidation behavior. OEM replacement or cursor-policy changes invalidate the
corresponding access history. A Plot Range change filters the displayed rows and changes only the
displayed range; it never recomputes or truncates cached access history.

## Pass-inspection view

Register one graph type named `ground-station-passes`, labeled **Ground Station Passes**. The view
contains:

1. A station selector and concise OEM-coverage/status summary.
2. A persistent readout of the shared Plot Range's start and end, formatted as UTC.
3. A chronological table of the selected station's access intervals overlapping the shared Plot
   Range.
4. A sky plot for the selected table row.
5. Explicit actions to focus the shared Plot Range on a pass or seek to a pass event.

For each interval, show start and end UTC, duration when both endpoints are known, peak elevation
and its time, minimum slant range and its time, and any coverage/gap limitation. Use the interval's
mask threshold as its access definition. Do not present a coverage-clipped endpoint as a known
AOS/LOS or report a complete duration when the crossing is unavailable.

Keep pass selection local to this view. A station or Plot Range change retains the selected
interval only if it remains in the filtered table; otherwise select the interval containing the
playback time, then the next interval in the filtered table, then the first row. If the station has
cached intervals but none overlap the Plot Range, show an explicit Plot Range-specific empty
state with the range bounds. If the station has no intervals in OEM coverage, show the distinct
no-access state.

Selecting a table row updates the sky plot but does not move the playback clock or alter Plot
Range. **Focus pass** sets the shared Plot Range to the selected interval, clipped to OEM coverage.
**Seek to peak** explicitly moves the shared clock to the stored peak epoch. These actions must
not trigger access-history preparation.

## Sky plot geometry and playback

Render a top-down azimuth/elevation plot from the selected interval's cached look-angle profile:

- Azimuth is degrees clockwise from geodetic north: 0° at the top, 90° east, 180° south, and
  270° west.
- The horizon is the outer ring at 0° elevation; the zenith is the center at 90°.
- Draw elevation rings with labeled angles and a distinct ring for the station's minimum-elevation
  mask.
- Draw only the selected pass at or above that station's mask. Mark the pass start, peak elevation,
  and end with distinct shapes or line styles as well as color.
- Draw a separate playback-time marker only while the clock lies within the selected interval and
  usable OEM data. Otherwise keep the path visible and state that the playhead is outside the
  selected pass or unavailable.
- Break lines at invalid samples, segment boundaries, or an access interval boundary. Never bridge
  OEM gaps. The azimuth wrap at north is naturally continuous when samples are transformed to
  Cartesian polar coordinates.
- At zenith, where azimuth is undefined, render the point at the plot center without inventing an
  azimuth.

Use the same `GroundStation` minimum elevation and `AccessInterval` selected by the table. The sky
plot is a visualization of geometric line of sight, not a radio-visibility or link-quality claim.

## Application boundaries and failure behavior

Keep look-angle preparation in toolkit-independent access code. The wx view renders cached
intervals and profiles; it does not call frame conversion or cursor interpolation for historical
samples. Current-time marker updates may use the existing current-station-metrics path and shared
position cache.

Pass the app-scoped `StationAccessCache`, current station collection, OEM context, shared clock,
and Plot Range/seek callbacks into the view through the established factory/controller boundary.
Do not make the view own a second cache or write station/view-selection state to `play-oem.toml`.

Show explicit states for no configured stations, no OEM, unsupported center/frame, unavailable
pass prediction, no intervals in coverage, and a selected interval limited by coverage or a gap.
Keep the map and station manager usable when pass preparation is unsupported or unavailable.

## Validation requirements

- Station markers project correctly for both existing Ground Track projections, center longitude
  changes, and seam-adjacent stations.
- Marker interactions do not seek; opening a pass view from a marker retains the station identity.
- Pass rows match cached intervals, including peak/range metrics and coverage/gap limitations.
- Sky coordinates follow the documented azimuth convention; mask clipping and interval endpoints
  match the selected pass.
- Playback updates only the current-time marker and current metrics. Pass-table sorting, selection,
  focus, and additional pass views do not repeat access preparation.
- Zero stations, unsupported OEMs, OEM gaps, and no-pass OEM coverage produce clear states.
- Existing Ground Track navigation, footprint controls, Ground Station Access graph, and shared
  Plot Range behavior remain unchanged.
