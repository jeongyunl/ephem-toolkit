# `play-oem` — Ground Stations Software Design

This document proposes the software architecture for managing ground stations and displaying
spacecraft access in `play-oem`. It extends the shared playback architecture in
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md). The companion user-interface
specification is [PLAY_OEM_GROUND_STATIONS_GUI_DESIGN.md](./PLAY_OEM_GROUND_STATIONS_GUI_DESIGN.md);
implementation sequencing is tracked in
[PLAY_OEM_GROUND_STATIONS_IMPLEMENTATION_PLAN.md](./PLAY_OEM_GROUND_STATIONS_IMPLEMENTATION_PLAN.md).

## Purpose and scope

Ground stations are user-defined sites used to evaluate geometric access to the currently loaded
OEM. The application supports zero or more stations. A station remains available when no OEM is
loaded, and its definition is independent of any particular OEM file.

The initial feature includes:

- Add, edit, and remove station definitions.
- Persist the definitions in app-maintained state.
- Show current line-of-sight metrics and pass intervals for the loaded OEM.
- Synchronize those results with the shared playback clock.
- Recompute or invalidate results when station definitions or the OEM change.

The initial model is geometric. Terrain, buildings, atmospheric refraction, antenna patterns,
transmitter power, link budgets, station operating schedules, and contact scheduling across
multiple spacecraft are out of scope.

## Station model and persistence

Represent each station as an immutable domain record:

| Field | Type | Meaning |
|---|---|---|
| `station_id` | string | Stable identity generated when the station is created |
| `name` | string | User-facing station name |
| `latitude_deg` | float | WGS-84 geodetic latitude, from -90° through +90° |
| `longitude_deg` | float | WGS-84 geodetic longitude, normalized to [-180°, 180°) |
| `altitude_m` | float | Height above the WGS-84 reference ellipsoid |
| `minimum_elevation_deg` | integer | Station access mask, from 0° through 90° |

Names are required but need not be unique; identity and view state use `station_id`, not the
display name. Allow finite altitudes below sea level. Do not silently coerce malformed numbers,
non-finite values, or out-of-range coordinates.

Store station definitions in the user configuration file, `play-oem.toml`, alongside the
playback preferences. Keep them in their own `[ground_stations]` table containing a `stations`
array of inline tables. For example:

```toml
config_version = 1

[ground_stations]
stations = [
  { id = "station-uuid", name = "North Site", latitude_deg = 64.1, longitude_deg = -21.9, altitude_m = 45.0, minimum_elevation_deg = 10 },
]
```

The exact ID representation may be UUID text; it must remain stable through rename and edit.
Validate station data when loading or saving configuration, and preserve unrelated playback,
display, interpolation, and comment content when station definitions change. For compatibility,
read station data from legacy state files and migrate it into `play-oem.toml` when no station
configuration is present. Continue to keep window, recent-file, and workspace settings in the
app-maintained `play-oem-state.toml`.

## Access calculation

### Coordinate conventions

Use WGS-84 geodetic station coordinates and height. Convert each station once to Earth-centered,
Earth-fixed (ECEF) Cartesian coordinates. For a spacecraft position in ITRF and a station ECEF
position, form the station-to-spacecraft vector and rotate it into the local east-north-up (ENU)
frame using the station's geodetic latitude and longitude.

Report:

- **Azimuth**: degrees clockwise from geodetic north, normalized to [0°, 360°).
- **Elevation**: degrees above the local geodetic horizon.
- **Slant range**: line-of-sight distance in kilometers.
- **Access**: elevation greater than or equal to the station's configured minimum elevation.

The station's elevation mask is independent of the shared Ground Track footprint setting. A
zero-degree station mask is allowed. This model does not account for terrain or other obstructions.

Use the existing Earth/frame support contract from
[ground_track.py](../../src/ephem_toolkit/play_oem/ground_track.py): accept Earth-centered OEMs
and supported Earth-fixed or inertial frames, and convert inertial position states to ITRF at the
requested TT epoch. Do not treat an unsupported frame or center as Earth-fixed. Keep frame
conversion lazy so other views and headless paths do not import the frame-conversion stack
unnecessarily.

### Current-time state

Resolve the spacecraft state with the shared `OemCursor` at `clock.t_now`. This keeps ground
station results consistent with the playback readout and respects OEM segment and interpolation
rules. If the cursor is in a gap or outside usable data, report current metrics as unavailable;
do not interpolate across a segment boundary.

### Pass intervals

Prepare access intervals separately from wx rendering. Evaluate access on the OEM's valid
segments and refine each threshold crossing by repeatedly resolving the cursor state within that
same segment. Never bridge OEM gaps. Preserve only intervals inside OEM coverage and label
truncated intervals at the start or end of coverage as such.

Each valid OEM segment is evaluated on a uniform grid with steps no longer than 30 seconds,
independent of the segment's source sample density. The active `OemCursor` interpolation resolves
the state at each grid epoch. Sampled local elevation maxima are refined to detect sub-step passes,
then AOS/LOS boundaries are bisected to within 0.5 seconds. A within-segment source sample gap
greater than five minutes, a single-sample segment, or more than one million grid evaluations makes
pass prediction unavailable with a visible limitation; no interval is inferred across those
regions. These limits describe numerical resolution of the selected OEM interpolation, not
physical orbit truth. Cache results by OEM/cursor identity and immutable station definition, and
invalidate them when an input changes. Preparation is lazy: it starts only when the Ground Station
Access view is opened and is never repeated on a playback tick.

For each interval, retain start/end TT seconds, peak elevation and its epoch, and minimum slant
range and its epoch. AOS and LOS are relative to the configured mask. At the OEM boundaries,
display “in progress at coverage start” or “continues beyond coverage” as appropriate rather than
inventing a crossing time.

## Application integration and module boundaries

Use focused modules consistent with the current package:

```text
play_oem/
  ground_stations.py             # station type, validation, coordinate conversion
  station_access.py              # current metrics and cached access intervals
  config.py                      # persisted station collection in play-oem.toml
  saved_state.py                 # legacy station migration and workspace state
  workspace/
    features.py                  # Ground Stations manager page
    ground_stations.py           # expandable inline station editor
  views/
    ground_station_access.py     # access timeline and selected-station details
    registry.py                  # view name and label
  app/
    controller.py                 # station mutation, state save, invalidation
    state.py                      # controller/view contracts
    view_factory.py               # construct view from current data and stations
```

Keep station validation and access calculations independent of wxPython and Matplotlib. The
controller owns the station collection, passes immutable snapshots to the view, persists changes,
and invalidates derived access data. Ground Track and Ground Station Access share an app-scoped
ECEF sample-position cache, so exact OEM sample conversions are reused without changing cursor
interpolation between samples. Access panels also share prepared pass histories; a new station
definition produces a new cache key, while OEM replacement or interpolation-policy changes
invalidate access results. Views observe the shared clock and receive refreshed station or OEM
data through the existing panel lifecycle. Replacing an OEM updates open access panels in place or
rebuilds them through the established view factory; closing a panel releases its clock observer and
plotting resources.

Register the individual graph view as `ground-station-access`, labeled **Ground Station Access**.
Keep the existing `overview` group unchanged and include this view in `all` through the registry's
existing group construction. The view remains openable with zero stations and displays an empty
state with a route to station management.

## Errors and empty states

- No stations: show an actionable empty state; do not show fictitious access rows.
- No OEM loaded: keep station definitions and management usable; access metrics indicate that an
  OEM is needed.
- Unsupported center/frame or failed conversion: show an actionable error in the view; keep the
  station manager and other views usable.
- Cursor in an OEM gap: retain the historical access timeline, mark current metrics unavailable.
- Pass touching an OEM segment gap: stop at the segment edge and identify the crossing as
  unavailable rather than extending the interval through the gap.
- Malformed saved station: follow the established saved-state warning/reset behavior and report
  the state-file path and reason.
- Calculation failure for one station: identify that station and preserve results for other
  stations where possible; do not show a success-shaped zero-access result.

## Performance and acceptance

The UI must not recompute an entire pass schedule on every clock notification. Test and record
the preparation cost with a representative OEM, multiple stations, and a large sample count.
Use bounded UI refresh work; update current metrics at the playback render cadence and prepare
pass intervals outside the render callback. Cache exact calculations only where the cache key
contains every relevant input.

Acceptance requires:

1. Zero, one, and multiple stations can be loaded, edited, removed, and persisted.
2. Existing state files without stations still load unchanged.
3. Current azimuth, elevation, range, and access agree with independently verified ENU examples.
4. Pass boundaries are refined within the documented tolerance and do not cross OEM gaps.
5. Seeking, reverse playback, and OEM replacement keep the access view synchronized.
6. Empty and unsupported-data states are explicit; other workspace views remain available.
7. The access view does not affect the existing Ground Track view or its shared elevation setting.
