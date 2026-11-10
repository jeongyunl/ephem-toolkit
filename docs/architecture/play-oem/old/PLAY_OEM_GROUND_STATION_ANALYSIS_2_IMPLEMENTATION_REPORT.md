# `play-oem` — Ground Station Analysis Implementation Report

> **Status: Implemented; GUI acceptance remains partial.** This report replaces the implementation
> plan. The original software and GUI proposals are archived as
> [software design](./PLAY_OEM_GROUND_STATION_ANALYSIS_2_SOFTWARE_DESIGN.md) and
> [GUI design](./PLAY_OEM_GROUND_STATION_ANALYSIS_2_GUI_DESIGN.md).

## Delivered

- Added eight independently selectable panels: Station Status, Pass Strip, Elevation Profile,
  Azimuth Profile, Range Profile, Pass List, Sky View, and Pass Ground Track.
- Added the optional Access Overview and Pass Study presets while preserving the existing
  `overview` default and legacy Ground Station Access/Passes selections.
- Added per-stack station/pass selection sharing. Main Analysis and Comparison remain independent
  unless Follow selection is enabled.
- Reused store-backed station-access and Earth-fixed data for profiles, pass intervals, and
  pass-bounded ground tracks. Panels do not independently prepare full OEM histories.
- Preserved Plot Range filtering, OEM segment/gap boundaries, coverage-limited pass status,
  explicit Focus pass and Seek to peak actions, and distinct unavailable/empty states.
- Added a responsive paired Pass List/Sky View layout for the Ground Track **Open Passes**
  workflow. The named Pass Study preset opens the two independently selectable panels as stackable
  graph panels.

## Validation

Focused station-view, app, and CLI tests passed:

```text
PYTHONPATH=src python3 -m pytest -q \
  tests/ephem_toolkit/play_oem/test_station_analysis.py \
  tests/ephem_toolkit/play_oem/test_ground_station_access_view.py \
  tests/ephem_toolkit/play_oem/test_ground_station_passes_view.py \
  tests/ephem_toolkit/play_oem/test_play_oem_app.py \
  tests/ephem_toolkit/play_oem/test_play_oem_cli.py
139 passed, 1 skipped
```

These tests cover shared data preparation, profile/pass filtering, selection propagation and
cleanup, gap/coverage states, aliases and presets, and responsive pass-panel layout.

## Remaining acceptance work

- Keyboard accessibility and accessible names for table selection, station controls, pass actions,
  and layout controls have not been fully verified.
- Light/dark theme contrast and visual presentation need interactive desktop verification.
- A manual desktop smoke test of all individual panels, both presets, responsive layouts, and
  two-stack comparison remains outstanding. Focused automated tests do not certify those visual
  workflows.

See the [Ground Stations user guide](../../../tools/PLAY_OEM_GROUND_STATIONS.md) for current
behavior and usage.
