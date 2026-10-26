# `play-oem` Ground Stations

Ground Stations lets you define sites, inspect geometric access to the loaded OEM, and follow
those results while playback advances. Station definitions are available without an OEM; access
calculation requires a supported Earth-centered OEM.

## Manage stations

Open **Ground Stations** in the Controls & Info rail. Choose **Add Ground Station** to expand an
inline draft, or expand an existing row to edit it. Save applies valid changes; Cancel discards
them. Removing a station requires confirmation. If you move away from edited fields, choose
whether to save, discard, or remain in the editor.

Names must be non-empty but do not have to be unique. The station ID remains stable when its name
or coordinates change. Definitions are saved in `play-oem.toml` under `[ground_stations]`.
Window placement, recent files, and open panels remain in the separate
`play-oem-state.toml` file. Existing station definitions in an older state file are migrated to
the configuration file when it does not already define stations.

| Field | Units and limits |
|---|---|
| Latitude | WGS-84 geodetic degrees, -90° through +90° |
| Longitude | Degrees east, normalized to [-180°, 180°) |
| Altitude | Meters above the WGS-84 reference ellipsoid; finite values below sea level are allowed |
| Minimum elevation | Integer degrees, 0° through 90° |

The station elevation mask is independent from the Ground Track footprint setting.

## View access

Open **Ground Station Access** from a graph panel's view selector, or use
`--plots ground-station-access` when starting `play-oem`. The `all` view group includes it;
`overview` is unchanged. The view is available with no stations or no OEM and displays a relevant
empty state. Use **Manage Ground Stations** to open the manager.

The graph shows the selected station's elevation versus time only while it is at or above that
station's minimum-elevation mask; access intervals are marked on the curve. Its vertical scale is
fixed at 0°–95°. It follows the application's Plot Range; adjust that range to zoom or move through
time. The graph does not use wheel zoom or separate pan controls. Click the graph to move playback.
Choose a station to see its current access state, azimuth, elevation, slant range, and previous/next
pass details.

- **Azimuth** is clockwise from geodetic north.
- **Elevation** is above the local geodetic horizon.
- **Slant range** is the station-to-spacecraft distance in kilometers.
- **Access** means elevation meets or exceeds the station's configured mask. It does not
  guarantee a communications link.

Access uses the OEM's Earth-fixed or supported inertial frame converted to ITRF. The view follows
the shared playback cursor, including seeking and reverse playback. If playback is outside usable
OEM data or inside a segment gap, current metrics are unavailable rather than zero.

## Ground Track stations and pass inspection

Open **Ground Track** to show the **Ground Stations** layer. Select a marker on the map or use
the station selector; the details row shows the station name, coordinates, and elevation mask.
Use **Station labels** to label all markers. **Open Passes** opens the Ground Station Passes view
for that station. Selecting a marker does not seek playback or prepare access history. With no
stations, the station controls are disabled and the map remains usable.

Open **Ground Station Passes** from a graph panel's view selector or with
`--plots ground-station-passes`. The view includes OEM coverage and a persistent UTC Plot Range
readout. Its chronological table contains:

- pass start and end in UTC;
- duration when both access crossings are known;
- peak elevation and its UTC time;
- minimum slant range and its UTC time; and
- coverage status for complete, coverage-boundary, or gap-limited intervals.

The table lists cached access intervals that overlap Plot Range, including a pass that starts
before or ends after the range. The full OEM-bounded pass times and metrics remain visible; Plot
Range changes only filter the prepared results. If no cached pass overlaps, the view says so and
suggests widening Plot Range; this is distinct from no access anywhere in OEM coverage and from
unavailable predictions.

Select a table row to inspect its sky path. Azimuth is clockwise from north, with north at the top;
the horizon is the outside ring, zenith the center, and the station's minimum elevation is shown
as a mask ring. The path, start/peak/end markers, and textual summary describe the selected
pass. The playback marker appears only while the playhead is within that pass. Use **Focus pass**
to set the shared Plot Range to the pass, or **Seek to peak** to move playback to its stored peak.
Row selection alone does neither.

## Prediction limits

Historical access is prepared lazily when either the Ground Station Access or Ground Station
Passes view first needs it. Each valid OEM segment is evaluated on a uniform grid no coarser than
30 seconds, regardless of source sample density. Local elevation maxima are refined to catch
sub-step passes, and access crossings are refined to within 0.5 seconds of the selected cursor
interpolation. These tolerances describe the numerical calculation, not physical accuracy.

Both views share cached per-station histories and Earth-fixed sample positions; adding a panel or
changing Plot Range does not repeat the historical calculation.

The view reports pass predictions as unavailable when a segment contains a sample gap over five
minutes, fewer than two samples, or would require over one million evaluation samples. Passes are
never joined across OEM segment gaps. An access interval that reaches a coverage boundary is
visually marked and described as in progress at the start or continuing beyond the end; a pass
that reaches an OEM segment gap is labeled as gap-limited. Terrain, buildings, atmospheric
refraction, antenna characteristics, link budgets, and station schedules are not modeled.

For implementation and GUI details, see the
[Ground Stations implementation report](../architecture/play-oem/old/PLAY_OEM_GROUND_STATIONS_IMPLEMENTATION_REPORT.md),
[archived software design](../architecture/play-oem/old/PLAY_OEM_GROUND_STATIONS_SOFTWARE_DESIGN.md), and
[archived GUI design](../architecture/play-oem/old/PLAY_OEM_GROUND_STATIONS_GUI_DESIGN.md).
