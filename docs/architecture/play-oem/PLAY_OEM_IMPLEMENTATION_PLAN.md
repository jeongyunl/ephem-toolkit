# Play-OEM Implementation Guide

**Status:** implemented

This document describes the current implementation boundaries and the acceptance checks for
Play-OEM. Detailed behavior is defined by:

- [PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md)
- [PLAY_OEM_DATAFLOW.md](./PLAY_OEM_DATAFLOW.md)
- [PLAY_OEM_DATA_VIEWS_SOFTWARE_DESIGN.md](./PLAY_OEM_DATA_VIEWS_SOFTWARE_DESIGN.md)
- [PLAY_OEM_DATA_VIEWS_IMPLEMENTATION.md](./PLAY_OEM_DATA_VIEWS_IMPLEMENTATION.md)

## 1. Runtime architecture

Play-OEM uses one wxPython event loop. `PlayerApp` composes focused mixins for loading, snapshot
installation, playback, range changes, view refresh, preferences, workspace UI, and panel lifecycle.
A background loader streams OEM rows directly into `OemDataStore`; the wx thread installs snapshots,
captures store contexts, and refreshes open panels.

## 2. Data ownership

- `OemDataStore` owns raw samples and lazy derived tiers.
- `StoreViewContext` captures a stable snapshot plus plot range and coverage.
- `StoreViewBinding` owns view tier subscriptions.
- Views consume bounded query results and retain only display state and artists.
- `PlaybackClock` advances over the store's live sample-time view.
- `StoreCursor` performs snapshot-bound point lookup.

No whole-history prepared batch or duplicate data owner is part of the shipped path.

## 3. Data-view implementation

Public view classes are canonical implementations in `src/ephem_toolkit/play_oem/views/`. Standard
2D orbit/diagnostic views inherit `OrbitTimeSeriesView`, which combines store/range support,
elapsed-time conversion, wx presentation, status, and legends.

All view categories implement the same lifecycle:

```python
build_from_store(context)
update_from_store(context)
set_time_range(bounds, coverage)
update(t_s)
close()
```

View modules own view-specific figure/artist logic. Shared support owns cross-view cursor, range,
store, and wx behavior.

## 4. Registry and construction

`DataViewRegistry` owns canonical names, labels, preset expansion, duplicate prevention, and
opener dispatch. `DataViewSpecMixin` exposes public view metadata to the registry.

`player_data_view_factory.py` constructs standard 2D, station, Ground Track, pass, and sky views.
`player_3d_data_view_factory.py` constructs Matplotlib or VTK 3D views. `player_panel_management.py`
owns host construction, attachment, replacement, rollback, disposal, and callback cleanup.

## 5. Panel lifecycle

A panel opens in this sequence:

1. Resolve panel target and stack.
2. Resolve existing or replacement state.
3. Construct and insert `DataViewPanelHost`.
4. Construct the view instance.
5. Build with a store context or compatibility series path.
6. Attach the returned Matplotlib Figure or native wx window.
7. Register open-panel state and resource cleanup.
8. Publish range hints for refresh scheduling.

A failed replacement closes the candidate, releases callbacks and resources, restores the prior
panel position, and preserves the prior default-view mapping.

## 6. Refresh lifecycle

Snapshot, append, reset, and tier notices are routed to affected panel IDs.

For each affected store-bound panel:

1. Refresh `StoreViewContext` from the active snapshot if needed.
2. Rebuild the panel if store replacement requires reconstruction.
3. Call `update_from_store(context)`.
4. Call `set_time_range(resolved_range, coverage)`.
5. Call `update(current_time)`.
6. Request a canvas or native panel redraw.

Range hints prioritize bounded derived work. Incremental refresh retains artists and updates them
when the structure remains compatible.

## 7. Cursor and range behavior

Standard 2D views convert absolute OEM TT seconds to elapsed display-axis units using the active
coverage origin and display divisor. Finite plot ranges hide cursors outside the range. Shared X
limits and range callbacks keep all axes synchronized.

Segment boundaries remain separate in plots. Point lookup reports gap status and does not carry
values across segment gaps.

## 8. Specialized views

### 3D Orbit

Matplotlib and VTK implement the same view contract. Panel management accepts a Matplotlib Figure
or native wx window. VTK close handling detaches interactor, render window, renderer, and wx links.

### Ground Track

Ground Track owns projection, track, station, footprint, marker, pan, and projection settings.
Data comes from bounded store queries.

### Ground Station

Ground Station profiles share station selection and store support. Elevation, Azimuth, and Range
renderers own profile-specific axes, units, filtering, and status formatting.

### Pass List and Sky View

Pass List and Sky View share interval selection while maintaining independent table/polar layouts.

## 9. Implementation modules

```text
src/ephem_toolkit/play_oem/
  app/
    player_app.py
    player_data_view_factory.py
    player_3d_data_view_factory.py
    player_panel_management.py
    player_store_data_view_refresh.py
  views/
    data_view_base.py
    data_view_registry.py
    orbit_time_series.py
    speed_altitude.py
    state_components.py
    rtn.py
    angular_velocity.py
    direction_change.py
    distance.py
    ground_track.py
    ground_station.py
    ground_station_passes.py
    plotting.py
    time_series_support.py
    trajectory3d/
```

## 10. Acceptance requirements

- View registry names and presets expand uniquely.
- Store contexts preserve snapshot identity and range state.
- Incremental refresh is bounded and coalesced.
- 2D axes use shared elapsed-time metadata.
- Range changes update only needed artists and limits.
- Ground Track and station views use store-bound queries.
- Panel replacement restores the prior panel and default mapping on failure.
- View close disconnects callbacks and unsubscribes tier interests.
- Matplotlib and native wx content close cleanly.
- The complete Play-OEM suite passes in the project `.venv` environment.

## 11. Verification

Run:

```bash
.venv/bin/python -m pytest -q tests/ephem_toolkit/play_oem
.venv/bin/ruff check src/ephem_toolkit/play_oem/views src/ephem_toolkit/play_oem/app
```

Related tests cover registry expansion, store contexts and bindings, 2D and raw-backed views,
Ground Track, station profiles/passes, panel lifecycle, incremental refresh, and replacement
rollback.
