# `play-oem` Ground Track Implementation Report

This report records the completed Ground Track view implementation and its verified behavior. The software and interface designs, selected mockup, alternative mockups, and implementation plan are archived alongside this report. End-user instructions remain in [PLAY_OEM_GROUND_TRACK.md](../../../tools/PLAY_OEM_GROUND_TRACK.md).

## Outcome

Ground Track is available as an individual graph view and through the `all` group. It uses the shared playback cursor and supports Earth-centered OEM data in ITRF-family and supported inertial frames. Unsupported centers, frames, or conversions are reported within the view without preventing other graphs from opening.

The map offers Robinson and Equirectangular projections, adjustable center longitude, three bundled offline backgrounds, and coverage outlines at 0° and the selected minimum elevation. It supports zoom and horizontal map rotation; horizontal panning reprojects around the pointer-driven center longitude while keeping the map centered. Vertical panning is constrained by the poles and disabled at full-world scale. Minimum elevation is an integer from 0° to 90°, shared across Ground Track panels and saved in application state. The view’s Matplotlib toolbar is hidden; its own Home, zoom, and Pan controls remain available.

## Implementation

- `ground_track.py` prepares Earth-fixed coordinates, preserves OEM segments, and splits paths at the current map seam.
- `ground_footprints.py` computes WGS-84 horizon and minimum-elevation boundaries with 36 azimuth vertices.
- `views/ground_track.py` renders the track, current subpoint, footprints, bundled map backgrounds, controls, and navigation.
- Application registry, saved state, and user documentation include Ground Track behavior.

## Verification

The user confirmed that all implementation and live GUI checks are verified. Focused automated checks cover coordinate preparation, footprint geometry, projections, map panning, view integration, and saved application state. The view tests report 8 passed and 1 skipped in the headless environment; the skipped case requires a wx display. Footprint tests report 12 passed.

## Archived design material

The software design, GUI design, selected balanced-map mockup, and three unselected mockups are retained in this `old` directory for reference. The active end-user guide is [PLAY_OEM_GROUND_TRACK.md](../../../tools/PLAY_OEM_GROUND_TRACK.md).
