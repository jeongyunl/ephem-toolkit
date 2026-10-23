# `play-oem` Ground Track view

The Ground Track view plots the spacecraft's sub-satellite path on a whole-Earth map. Add it
from a graph panel's view selector, or include `ground-track` in the startup plot selection. The
`all` plot group includes Ground Track; `overview` remains the 3D orbit and speed/altitude views.

## Requirements

The OEM must be Earth-centered (`EARTH` or `399`) and use a supported reference frame:

- Earth-fixed: `ITRF`, `ITRF1993`, or `ITRF93`.
- Inertial: `J2000`, `EME2000`, `ICRF`, `GCRF`, or `TEME`.

Inertial states are transformed to ITRF using the available TudatPy/SPICE Earth-orientation
route. Conversion or kernel errors appear in the Ground Track panel. Unsupported centers and
frames are reported in the panel while other graph views remain available. The displayed path
is split at OEM segment gaps and at the map seam.

## Map and controls

The map opens in Robinson projection and shows the full Earth, both poles, graticule, ground
track, current sub-satellite point, 0° horizon, and the selected minimum-elevation footprint.
Projection choices are Equirectangular and Robinson. Choose the NASA shaded-relief, satellite
imagery, or high-resolution political map background from the Background control. The bundled
4320 × 2160 backgrounds work offline. The political map uses Natural Earth 1:10m country
boundaries and labels; Natural Earth data are public domain.
The satellite background uses NASA's global Blue Marble Next Generation composite, avoiding the
coverage gaps in single-day satellite imagery. The shaded-relief background is NASA GIBS Blue
Marble. The default minimum elevation is 10°; its integer control accepts 0° through 90°.
At 0°, the two footprint boundaries coincide. At 90°, the minimum-elevation footprint contracts
to the sub-satellite point.

Center longitude is entered in degrees east and wraps to `[-180°, 180°)`. The Home button
restores a full-world extent around the selected center. Use the toolbar's pan mode, the zoom
buttons, the mouse wheel, or the map scrollbars to navigate. Navigation applies only to the map
panel and does not seek the playback timeline. The center control follows horizontal map
navigation.

The selected minimum elevation is shared by open Ground Track panels and saved in the application
state file. Projection and center are per-panel session preferences and are not restored after
restarting `play-oem`.

See the [Ground Track software design](../architecture/play-oem/PLAY_OEM_GROUND_TRACK_SOFTWARE_DESIGN.md),
[selected GUI design](../architecture/play-oem/PLAY_OEM_GROUND_TRACK_GUI_DESIGN.md), and
[implementation plan](../architecture/play-oem/PLAY_OEM_GROUND_TRACK_IMPLEMENTATION_PLAN.md).
