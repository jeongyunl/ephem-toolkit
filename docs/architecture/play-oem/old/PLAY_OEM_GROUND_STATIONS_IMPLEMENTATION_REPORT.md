# `play-oem` — Ground Stations Implementation Report

> Status: **Complete.** The feature is implemented and validated; no implementation-plan items
> remain open.

This report records the delivered feature. The original
[software design](./PLAY_OEM_GROUND_STATIONS_SOFTWARE_DESIGN.md),
[GUI design](./PLAY_OEM_GROUND_STATIONS_GUI_DESIGN.md), and visual mockups for the
[manager](./mockup-ground-stations-manager.svg),
[inline station editor](./mockup-ground-station-editor.svg), and
[access view](./mockup-ground-station-access.svg) are archived alongside this report.
The [shared architecture](../PLAY_OEM_SOFTWARE_DESIGN.md) and active
[user guide](../../../tools/PLAY_OEM_GROUND_STATIONS.md) remain available.

## Delivered

### Station management and persistence

- Added the Ground Stations Controls & Info manager for creating, editing, expanding, and
  removing zero or more stations, including validation and empty-state behavior.
- Persisted station definitions in `play-oem.toml` under `[ground_stations]`.
- Migrated legacy station records from `play-oem-state.toml` when the new configuration section
  is absent; workspace and window state remain in the state file.
- Kept station management available without a loaded OEM.

### Access calculations and caching

- Implemented WGS-84 ECEF/ENU geometry, current azimuth/elevation/range metrics, and
  minimum-elevation access windows for supported Earth-centered OEMs.
- Prepared pass histories lazily when an Access view is created. Playback updates and Plot Range
  changes reuse prepared histories; multiple Access views share results.
- Shared exact-sample ECEF position conversions between Ground Track and Ground Station Access.
- Sampled valid OEM segments at intervals no longer than 30 seconds; refined local elevation
  maxima and access crossings, and kept calculations from bridging OEM segment gaps.
- Retained sampled elevation profiles with access results for graphing, avoiding a second pass
  through state conversion for the elevation plot.

### Ground Station Access view

- Registered `ground-station-access` and included it in the `all` view group; `overview` remains
  unchanged.
- Added a selected-station elevation graph. It plots only elevations at or above that station's
  minimum mask, uses a fixed 0°–95° y-axis, and marks access windows, coverage/gap limits, and
  playback time.
- Bound the time axis to the shared Plot Range. Clicking the graph seeks playback; the view does
  not use wheel zoom or separate Matplotlib pan/zoom controls.
- Added current station metrics, previous/next pass summaries, and explicit no-station,
  unsupported-OEM, unavailable-data, and segment-gap states.

### Documentation

- Added the active [Ground Stations user guide](../../../tools/PLAY_OEM_GROUND_STATIONS.md).
- Archived the feature's original design documents and visual mockups in this `old/` directory.

## Verification

- `python3 -m pytest tests/ephem_toolkit/play_oem -q`: **385 passed, 3 skipped**.
- `git diff --check` passed.
- A synthetic access-preparation benchmark is recorded in the
  [performance report](../PLAY_OEM_PERFORMANCE_REPORT.md): 200,000 samples over 48 hours and
  three stations completed in 0.748 seconds. That benchmark predates retaining elevation-profile
  samples for the graph and is a preparation-time baseline, not a measurement of graph memory.

## Scope limitations

Access is geometric and based on the loaded OEM and configured elevation mask. Terrain,
buildings, atmospheric refraction, antenna patterns, link budgets, and station schedules are not
modeled. Prediction limits for sparse segments and OEM gaps are documented in the user guide.
