# `play-oem` — Ground Station Visual Analysis Implementation Report

**Status: Complete.**

## Summary

Ground Station Visual Analysis adds saved-station context to Ground Track and a dedicated
Ground Station Passes view. The view filters cached access intervals to the shared Plot Range,
displays pass details, and plots the selected pass in a sky-oriented polar view. The polar view
is placed below the full-width pass table.

## Delivered

- Added selectable Ground Track station markers, optional labels, accessible station details,
  and an **Open Passes** action that does not seek playback or prepare access history.
- Extended the shared station-access cache to retain per-segment azimuth/elevation profiles and
  refined look angles at interval boundaries. The existing Ground Station Access elevation graph
  continues to use the shared cached data.
- Added a pass table with UTC Plot Range readout, overlap filtering, full interval details,
  coverage/gap status, stable selection, **Focus pass**, and **Seek to peak** actions.
- Added a sky plot with compass/elevation references, the station mask, selected pass path,
  start/peak/end markers, and a playback marker. Paths stop at invalid samples and segment
  boundaries; the plot uses cached look-angle profiles.
- Registered the view and connected station edits, OEM replacement, shared Plot Range, panel
  lifecycle, and the shared access/ECEF caches.
- Updated the [Ground Stations user guide](../../../tools/PLAY_OEM_GROUND_STATIONS.md).

## Verification

- `python3 -m pytest -q tests/ephem_toolkit/play_oem`: **404 passed, 4 skipped**.
- The display-backed pass-panel layout test passed separately using the workspace-selected
  interpreter.
- `git diff --check` passed.
- Manual light/dark visual inspection was not performed.

## Archived design materials

The completed feature's design and mockup are retained for reference:

- [Software design](./PLAY_OEM_GROUND_STATION_ANALYSIS_SOFTWARE_DESIGN.md)
- [GUI design](./PLAY_OEM_GROUND_STATION_ANALYSIS_GUI_DESIGN.md)
- [Visual mockup](./mockup-ground-station-visual-analysis.svg)
