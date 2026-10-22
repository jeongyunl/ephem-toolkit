# `play-oem` — Ground Track View Software Design

This document records the software architecture for the Ground Track graph view in
`play-oem`. The feature is registered; live visual validation remains outstanding. This
design follows the shared playback architecture in
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md) and the workspace interaction
guidance in [PLAY_OEM_GROUND_TRACK_GUI_DESIGN.md](./PLAY_OEM_GROUND_TRACK_GUI_DESIGN.md).
Implementation sequencing is tracked in
[PLAY_OEM_GROUND_TRACK_IMPLEMENTATION_PLAN.md](./PLAY_OEM_GROUND_TRACK_IMPLEMENTATION_PLAN.md).
End-user guidance is in [PLAY_OEM_GROUND_TRACK.md](../../tools/PLAY_OEM_GROUND_TRACK.md).

## Purpose

Show the satellite's sub-satellite path on Earth and move a marker along that path with the
shared playback clock. The view is an ordinary graph panel: it can be selected, moved, replaced,
or closed using the existing panel controls, and it stays synchronized with other open views.

## Proposed user-facing contract

- Register the individual view as `ground-track`, labeled **Ground Track**.
- Use the current OEM timeline and shared `PlayerApp` clock. Playback, reverse, seek, and OEM
  replacement must update or rebuild the view through the established view lifecycle.
- Draw a static path for all usable samples and a separate marker for the current cursor time.
- Draw two current-time coverage boundaries: the 0° elevation horizon footprint and the
  footprint at a user-selected minimum elevation.
- Let the user set the minimum elevation as an integer from 0° through 90°, in 1° steps. The
  initial default is 10°.
- Let the user set each map's center longitude and keep the value synchronized with map
  navigation; center and projection remain per-panel session preferences.
- Draw each OEM segment independently. Do not connect across segment gaps or across the map's
  current seam at center longitude ±180°.
- Let the user select the map projection independently in each Ground Track graph panel.
- Identify the Earth-fixed frame and geodetic convention used. The proposed target is ITRF and
  WGS-84 geodetic latitude/longitude.
- If the OEM center or reference frame cannot be supported, show an actionable graph-panel
  message instead of a misleading or silently incorrect path.
- Do not change the `overview` group. Include the new view in `all` through the registry's
  existing group construction.

## Data and coordinate pipeline

Ground track requires Earth-fixed coordinates at each sample epoch. The OEM's Cartesian state
must not be treated as Earth-fixed merely because the general playback series contains Cartesian
positions. Retain or provide the ground-track calculation with the source timestamps, states,
segment IDs, center name, and OEM reference frame.

Proposed path preparation:

1. Confirm the OEM center identifies Earth and normalize the reference-frame name.
2. For Earth-fixed `ITRF` or `ITRF1993` input, use the source positions directly. For supported
   inertial frames (`J2000`, `EME2000`, `ICRF`, `GCRF`, or `TEME`), convert each six-component
   state to `ITRF` at its TT epoch with `core.frame_utils.convert_frame`.
3. Convert the Earth-fixed positions from EPSG:4978 to EPSG:4979 with pyproj's WGS-84
   transformer. Keep latitude and longitude in radians internally and convert to degrees only
   at the plotting boundary. Do not use the toolkit's legacy `core.wgs` ellipsoid constants for
   this view; its equatorial radius differs from WGS-84 by 0.7 m.
4. Build separate drawable line runs at OEM segment boundaries and longitude wrap boundaries.
   Normalize plotted longitude to `[-180°, 180°]` without drawing a line across the map.
5. Cache the prepared path for the lifetime of the loaded OEM. Playback updates move only the
   marker; they do not repeat the full history conversion.

For the moving marker, resolve the current state through `OemCursor.lookup(t_s)` so marker
position follows the same OEM interpolation and gap rules as the other playback readouts. Convert
that state to ITRF at the requested epoch and then to geodetic coordinates. If the cursor is in a
gap or has no usable state, hide the marker or show an explicit unavailable state. Never
interpolate across an OEM segment boundary.

## Ground-footprint calculation

At the current playback time, compute the visible ground region on a WGS-84 ellipsoid. A ground
point is in a footprint when the straight line of sight to the satellite has elevation at or
above the selected mask angle, measured from the local geodetic horizon at the ground point.
Assume sea-level ellipsoid height; terrain, buildings, atmospheric refraction, and antenna
patterns are outside the initial model.

Draw both threshold boundaries:

- **0° horizon**: the outer visibility boundary where the line of sight is tangent to the
  ellipsoid.
- **Minimum elevation**: the inner boundary for the selected threshold. It must remain inside
  or coincide with the 0° footprint.

The minimum-elevation control accepts 0° to 90°. At 0°, the two boundaries coincide, so draw one
clearly identified line instead of overpainting it. At 90°, the minimum-elevation footprint
collapses to the sub-satellite point; represent it as a point or explain the zero-area result.
When the satellite position is unavailable or invalid, hide both boundaries and show an explicit
unavailable state.

Compute boundary coordinates from the current satellite state and Earth-fixed epoch. Sample
azimuths along WGS-84 geodesics from the geodetic sub-satellite point using `pyproj.Geod`; solve
for distance until the line of sight has the requested elevation against the ellipsoid's local
geodetic normal. Do not use a spherical-Earth approximation silently. Split resulting polylines
at the map seam. A first implementation uses 72 azimuth samples; profiling at 420 km measured
about 8.4 ms for a horizon-plus-mask update on the development host. Bound refresh rate and
share results among panels so calculation does not impede wx input or playback.

The minimum-elevation value is an integer number of degrees from 0 through 90, shared by Ground
Track panels and a mutable UI preference. Save
it in application-maintained state rather than writing it into the user-edited config file. A
projection remains a per-panel display choice. The UI design document specifies the controls and
line treatment.

The current `frame_utils` module imports TudatPy and loads SPICE kernels at module import. Keep
that dependency lazy to the ground-track path so opening other views and starting playback do not
acquire new import-time work. Conversion failures for an explicitly selected ground-track view
must be surfaced to the user; do not fall back to interpreting inertial coordinates as
Earth-fixed. Confirm that the installed kernels and frame-conversion model cover the OEM epochs
before claiming accuracy outside the supported kernel range.

## Package and lifecycle integration

Proposed implementation boundaries:

```text
play_oem/
  playback_data.py              # expose source frame/context needed by the view
  ground_track.py               # Earth-frame conversion and cached coordinate data
  views/
    ground_track.py             # Matplotlib graph and moving marker
  app/
    view_factory.py             # construct the view from current OEM context
    panel_management.py         # honor per-view interaction capabilities
  views/registry.py             # name, label, and group registration
```

Keep the coordinate preparation independent of wxPython and Matplotlib so frame support,
segment handling, and seam splitting can be tested without a display. Keep the renderer within
the existing `View` lifecycle (`build`, `update`, `close`) and return a Matplotlib `Figure` for
hosting in `GraphPanelHost`. Replace or invalidate cached ground-track data whenever another OEM
is loaded, and release figure artists when a panel closes.

The current generic Matplotlib click handler interprets `event.xdata` as elapsed time. On a
ground-track plot, `xdata` is longitude; allowing the generic handler to run would seek to an
unrelated time. Add an explicit per-view interaction capability or equivalent panel metadata so
this view does not use time-series click-to-seek. A future nearest-track-point seek action would
need a separate interaction design because a ground location can occur more than once in an
orbit.

Do not add an independent timer, playback clock, or frame update loop. Existing observer updates
must move the marker on the wx UI thread. The static map and path should be built once; playback
updates should modify only the marker and any small current-coordinate readout.

## Rendering and dependencies

Keep prepared ground-track coordinates in geodetic latitude/longitude, independent of the display
projection and center longitude. Apply the same selected projection and center to the coastline or
surface image, graticule, OEM track, and current-position marker. Split the path at both OEM gaps
and the current map seam (center longitude ±180°) before drawing. Changing projection or center
must redraw these map layers without recomputing the OEM frame conversion.
Decimate only the displayed static line when needed; retain full-resolution coordinates for
marker lookup and future interactions.

Use pyproj, the Python interface to PROJ, for the two map projections. Keep it in the optional
`playback` dependency extra so base and headless installs do not acquire a map dependency. Use
the spherical PROJ forms with a fixed authalic Earth radius for display; Earth-fixed coordinates
and footprint calculations remain WGS-84. Supply the panel center as PROJ's `lon_0`, and verify
both poles have finite coordinates before drawing the initial full-world extent. PROJ documents
the Robinson global spherical form and central-meridian parameter
([Robinson](https://proj.org/en/stable/operations/projections/robin.html),
[Equidistant Cylindrical](https://proj.org/en/stable/operations/projections/eqc.html)); pyproj
exposes forward longitude/latitude to projected-coordinate transforms
([pyproj `Proj`](https://pyproj4.github.io/pyproj/stable/api/proj.html)).

The proposed projection choices are:

| Projection | Use and trade-offs |
|---|---|
| Equirectangular | Simple latitude/longitude reference with straight meridians and parallels; distorts shape and area increasingly toward the poles. |
| Robinson | Compromise world projection with a familiar overall shape and less extreme polar enlargement; neither conformal nor equal-area. Default. |

Projection selection is a per-panel **Projection** control. Changing it resets that panel to the
full-world extent around its current center longitude and leaves the shared playback time and
other graph panels alone. Both poles must be visible simultaneously in every available
projection. Do not add a projection that clips either pole or only shows one hemisphere.

Provide a per-panel **Center longitude** control in degrees east, normalized to `[-180°, 180°)`.
Editing it recenters that map on the requested meridian without changing projection or playback
time. After every zoom, pan, or scrollbar movement, calculate the longitude at the center of the
visible map and update the control automatically. Mouse-wheel zoom anchored away from the map
center may therefore change the displayed center longitude. Longitude wrapping at ±180° must be
handled without a jump or an out-of-range displayed value. Retain the panel's center while the
marker and footprints move; playback must not make the map follow the satellite automatically.

Support map navigation within each graph panel: the Matplotlib toolbar provides zoom and pan,
the mouse wheel zooms about the pointer while it is over the map, and horizontal/vertical
scrollbars let the user scroll the enlarged map through the panel viewport. Every navigation
action updates **Center longitude** to the visible map center. Preserve each panel's zoom and
center while the playback marker and footprints update. A home/reset action restores the
full-world extent around the current center longitude. Changing projection restores the
full-world extent and retains the current center longitude. Map navigation must not seek the
playback clock or scroll the surrounding graph stack when the pointer is over the map.

Retain a panel's projection and center for the current session when it is redrawn or the OEM is
replaced. Whether to persist the preferred projection and center across application restarts
belongs in the saved-state schema decision. Use a vetted projection library or well-tested
projection routines; do not add ad hoc coordinate formulas without reference tests.

Do not include coastline outlines in the initial release. No local dataset and redistribution
license have been approved. Show the graticule and ground track without runtime downloads; a
coastline dataset can be proposed later with a license and package-size review.

## Failure behavior

The graph must communicate unsupported or unavailable data without hiding the reason:

- Non-Earth center: explain that ground track requires an Earth-centered OEM.
- Unknown or unsupported OEM frame: identify the frame and explain that conversion is
  unavailable.
- Missing frame-conversion kernels or conversion error: report the failure in the graph panel or
  status area and preserve playback and other views.
- Cursor in a data gap: keep the path segments visible and mark the current position unavailable.
- Empty/no-OEM application: show the normal empty graph state or a prompt to load an Earth-centered
  OEM; do not attempt conversion on placeholder data.

Opening the ground-track view must not terminate the GUI or invalidate other panels when any of
these conditions occurs.

## Verification requirements

Implementation should cover:

- Frame conversion at known epochs for each supported source frame, with direct handling of
  `ITRF` and `ITRF1993`.
- Geodetic latitude/longitude values against known Earth-fixed positions, including poles and
  longitudes near the date line.
- Segment-boundary and ±180° seam splitting, with no false connecting lines.
- North- and south-pole coordinates and near-polar paths in every available projection, with
  neither pole clipped or omitted.
- Ground footprints for known satellite positions and elevation masks, including 0°, a positive
  threshold, coincident boundaries at 0°, the degenerate 90° case, and invalid cursor states.
- Minimum-elevation control range, default, persistence, and redraw/update behavior.
- Cursor marker placement at exact samples, interpolated times, both playback directions, and
  times inside OEM gaps.
- OEM replacement, graph-panel replacement/close, and cache invalidation.
- A regression check proving map clicks cannot invoke time-series click-to-seek.
- Toolbar and wheel zoom, pan, scrollbar navigation, preserved extent during playback,
  center-longitude synchronization, and projection-change reset behavior.
- Headless coordinate and view tests plus a live wx visual check for map labels, path visibility,
  marker updates, resizing, toolbar behavior, and error presentation.

Record the supported center/frame matrix and the kernel/data range used for any accuracy claim.

## Support limits and saved preferences

Accept Earth center names `EARTH` and `399`, normalized for case and surrounding whitespace.
Reject other centers, including the Earth-Moon barycenter. Accept `ITRF`, `ITRF1993`, and the
toolkit alias `ITRF93` as already Earth-fixed positions and convert their positions directly to
WGS-84 geodetic coordinates. For inertial input, accept `J2000`, `EME2000`, `ICRF`, `GCRF`, and
`TEME`, and convert to `ITRF` at the OEM epoch with the existing frame conversion utility.
Reject other permitted ODM frame names (including `ITRF1997`, `ITRF2000`, `TOD`, `GRC`, and
`MCI`) until a conversion route is implemented and validated.

The selected inertial-to-ITRF path uses TudatPy's IAU 2006 GCRS-to-ITRS rotation model and does
not use the bundled Earth binary PCK for Earth orientation. Direct ITRF/ITRF1993 positions also
do not require that binary PCK's coverage. No high-precision Earth-orientation accuracy or
unverified epoch range is promised: catch conversion/kernel initialization errors, test the
actual OEM epoch span, and report failures in the view. ITRF1993 is treated as Earth-fixed for
the map; this is not a centimeter-level realization transformation to WGS-84.

Save the shared minimum elevation (integer 0–90°, default 10°) in the application state file.
Keep per-panel projection and center for the current session and when an OEM is replaced, but do
not persist them across application restarts in the first implementation. The view belongs in
`all`, not `overview`; map clicks do not seek playback, and nearest-track-point seek is deferred.
