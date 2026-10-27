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

## Focused Ground Station panels

The graph selector offers Station Status, Pass Strip, Elevation Profile, Azimuth Profile, Range
Profile, Pass List, Sky View, and Pass Ground Track. Choose **Access Overview** or **Pass Study**
from the preset selector in the Main Analysis header. Access Overview opens Station Status, Pass
Strip, and Elevation Profile; Pass Study opens Pass List and Sky View as separate, stackable graph
panels. Presets are also available through `--plots access-overview` and `--plots pass-study`;
they do not change the default `overview` group. Older selections remain supported:
`ground-station-access` opens Elevation Profile and `ground-station-passes` opens Pass List.

Station Status, Pass Strip, and the time profiles are available with no stations or no OEM and
display a relevant empty state. Use **Manage Ground Stations** to open the manager.

Station Status shows current access, azimuth, elevation, and slant range. Elevation Profile plots
elevation against time with access intervals and the station mask; its vertical scale is fixed at
0°–95°. Each Elevation, Azimuth, and Range Profile has its own **Show only above minimum
elevation** checkbox, checked by default. When checked, below-mask samples are omitted, leaving a
gap in the plotted line; uncheck it to show the full profile. Azimuth Profile also breaks the line
at north-wrap discontinuities, and Range Profile shows slant range in kilometers. Pass Strip shows
access intervals over Plot Range and distinguishes OEM-boundary and segment-gap limitations.
Time profiles follow the application's Plot Range; adjust it to zoom or move through time. Click
a time profile to move playback.

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
for that station in the responsive Pass Study layout. Selecting a marker does not seek playback or
prepare access history. With no stations, the station controls are disabled and the map remains
usable.

Open **Pass List** or **Sky View** independently, or choose **Pass Study** to open both. The
chronological Pass List contains:

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

Select a row to synchronize it with Sky View and Pass Ground Track in that graph stack. Use
**Follow selection** in the Main Analysis header to optionally synchronize station/pass selection
from Main Analysis into Comparison; it is off by default. Azimuth is clockwise from north, with
north at the top;
the horizon is the outside ring, zenith the center, and the station's minimum elevation is shown
as a mask ring. The path, start/peak/end markers, and textual summary describe the selected
pass. The playback marker appears only while the playhead is within that pass. Use **Focus pass**
to set the shared Plot Range to the pass, or **Seek to peak** to move playback to its stored peak.
Row selection alone does neither. Pass Ground Track displays only the selected pass and marks the
selected station; it does not imply radio visibility.

## Prediction limits

Historical access is prepared lazily when a time-based Ground Station panel first needs it. Each
valid OEM segment is evaluated on a uniform grid no coarser than
30 seconds, regardless of source sample density. Local elevation maxima are refined to catch
sub-step passes, and access crossings are refined to within 0.5 seconds of the selected cursor
interpolation. These tolerances describe the numerical calculation, not physical accuracy.

All panels share cached per-station histories and Earth-fixed sample positions; adding a panel or
changing Plot Range does not repeat the historical calculation.

The view reports pass predictions as unavailable when a segment contains a sample gap over five
minutes, fewer than two samples, or would require over one million evaluation samples. Passes are
never joined across OEM segment gaps. An access interval that reaches a coverage boundary is
visually marked and described as in progress at the start or continuing beyond the end; a pass
that reaches an OEM segment gap is labeled as gap-limited. Terrain, buildings, atmospheric
refraction, antenna characteristics, link budgets, and station schedules are not modeled.

For current technical and workspace details, see the
[Ground Station software design](../architecture/play-oem/PLAY_OEM_GROUND_STATION_ANALYSIS_SOFTWARE_DESIGN.md),
[GUI design](../architecture/play-oem/PLAY_OEM_GROUND_STATION_ANALYSIS_GUI_DESIGN.md), and
[implementation plan](../architecture/play-oem/PLAY_OEM_GROUND_STATION_ANALYSIS_IMPLEMENTATION_PLAN.md).
