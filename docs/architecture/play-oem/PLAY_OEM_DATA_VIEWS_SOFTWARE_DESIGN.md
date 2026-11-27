# Play-OEM Data Views Software Design

**Status:** implemented

This document defines the software architecture of Play-OEM data views. It complements
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md) and
[PLAY_OEM_DATAFLOW.md](./PLAY_OEM_DATAFLOW.md).

## Scope

A data view is a registered presentation of OEM data hosted in an independent data-view panel.
A view can be:

- A Matplotlib 2D time-series plot.
- A Matplotlib or VTK 3D trajectory.
- A Matplotlib Ground Track map.
- A native wx station panel with Matplotlib profiles.
- A pass table or Sky plot.

The design covers registry metadata, construction, panel ownership, store/range binding,
shared cursor behavior, resource ownership, incremental refresh, replacement, and specialized
backends. OEM parsing and derived-store scheduling remain outside this document.

## Architectural goals

1. **One lifecycle contract.** Every view implements build, update, range, store-refresh,
   and close behavior.
2. **Canonical public implementations.** Public view modules own the complete implementation;
   view-specific code remains in its public module.
3. **Store ownership.** `OemDataStore` owns raw and derived data. Views consume bounded
   snapshot/query results and retain no orbit-sized projections.
4. **Shared 2D behavior.** Time conversion, range callbacks, cursors, wx embedding, status,
   legends, and click-to-seek are reused.
5. **Specialized isolation.** Ground Track, station, pass, and 3D views use specialized
   renderers while sharing panel and store lifecycle.
6. **Reversible replacement.** Failed replacement closes the candidate and restores the
   existing panel and default-view mapping.

## Primary components

| Component | Responsibility |
|---|---|
| `DataViewSpec` / `DataViewPreset` | Canonical name, label, preset group, and opener. |
| `DataViewRegistry` | Preset expansion, duplicate prevention, labels, and opener dispatch. |
| `DataView` | Non-store build/update/range/close protocol. |
| `StoreView` | Store-backed build/update protocol. |
| `StoreViewContext` | Stable snapshot, range, coverage, time unit, and sampling policy. |
| `StoreViewBinding` | Store-tier subscriptions and rebinding. |
| `StoreSeriesPlotView` | Shared 2D store/range/cursor lifecycle. |
| `StoreTimeSeriesView` | Elapsed-time-axis conversion and seek metadata. |
| `OrbitTimeSeriesView` | Shared public base for standard 2D views and wx presentation. |
| `TimeSeriesWxPanelMixin` | wx panel, canvas, toolbar, status, and legend support. |
| `GroundStationAnalysisMixin` | Station selection and station-store support. |
| `PlayerViewFactoryMixin` | Construct standard and station views. |
| `Player3dViewFactoryMixin` | Construct 3D backend implementations. |
| `PanelManagementMixin` | Construct, attach, replace, roll back, and dispose panels. |

## Registered view taxonomy

| View | Public module | Shared pattern | Store data |
|---|---|---|---|
| 3D Orbit | `trajectory3d/mpl_backend.py`, `trajectory3d/vtk_backend.py` | `DataViewSpecMixin` | Raw positions/times/segments; `state_at()` |
| Speed / Altitude | `speed_altitude.py` | `OrbitTimeSeriesView` | `kinematics` |
| State Components | `state_components.py` | `OrbitTimeSeriesView` | Raw state columns |
| RTN Deltas | `rtn.py` | `OrbitTimeSeriesView` | `rtn` |
| Angular Velocity | `angular_velocity.py` | `OrbitTimeSeriesView` | `direction-rates` |
| Direction Change | `direction_change.py` | `OrbitTimeSeriesView` | `direction-rates` |
| Geocentric Distance | `distance.py` | `OrbitTimeSeriesView` | `kinematics`, `distance-delta` |
| Ground Track | `ground_track.py` | Specialized wx/Matplotlib | Earth-fixed positions, footprints |
| Elevation/Azimuth/Range | `ground_station.py` | Unified station renderer | `station-access` |
| Station Status / Access | `ground_station.py` | Unified station renderer | Station metrics and access |
| Pass List | `ground_station_passes.py` | Specialized pass view | Station access intervals |
| Sky View | `ground_station_passes.py` | Specialized pass view | Selected pass profile |

Presets are `overview`, `state`, `motion`, `access-overview`, `pass-study`, and `all`.

## Lifecycle contract

### Base lifecycle

```python
build(series, time_unit) -> Figure | wx.Window
update(t_s)
set_time_range(bounds, coverage)
close()
```

The base lifecycle supports startup and non-store test cases. The normal GUI path is store-backed.

### Store lifecycle

```python
build_from_store(context) -> Figure | wx.Window
update_from_store(context)
```

A context is immutable with respect to its snapshot. Range changes create a range-bound context
through `with_range()`. `StoreViewBinding.bind()` subscribes the required derived tiers and
rebinds when the active store changes.

### Close lifecycle

Closing a view disconnects Matplotlib callbacks and range callbacks, closes floating wx panels,
unsubscribes from store tiers, clears figures/cursors/artists, and detaches native backend
resources. The panel host remains owned by panel management.

## 2D time-series design

Standard orbit/diagnostic classes inherit `OrbitTimeSeriesView`, which combines:

- `DataViewSpecMixin` metadata.
- `TimeSeriesWxPanelMixin` native wx presentation.
- `StoreTimeSeriesView` elapsed-time/range/cursor support.

The public module owns figure topology, labels, store query columns, artists, rescaling, empty
states, non-store series support, and status formatting. The shared base owns store binding, range
state, cursor placement, seek metadata, wx embedding, legends, and status surfaces.

Axes carry `_play_oem_seek_enabled`, `_play_oem_time_origin_s`, and
`_play_oem_time_divisor_s`. Panel seek handling rejects toolbar modes, right clicks, missing
coordinates, and axes explicitly marked non-seekable.

## Store and range ownership

`StoreViewContext` carries the source store, immutable snapshot, display unit, plot range,
coverage, and sampling policy. Range helpers have explicit no-range semantics. Complete snapshot
coverage alone does not prove samples cover a requested finite range.

Range changes preserve the snapshot and update only view range state. 2D views replace bounded
store artists, rescale Y only when snapshot/data changed, update shared X limits, and preserve
cursor visibility rules.

## Specialized view patterns

### 3D trajectory

Matplotlib and VTK implement the same view contract. Panel management accepts a Matplotlib
`Figure` or native wx `Window`. VTK closes by detaching interactor, render window, renderer,
and wx ownership links.

### Ground Track

Ground Track owns projection, background, track and station artists, marker, footprint state,
pan behavior, and local controls. Data comes from store queries; no independent Earth-fixed or
footprint owner is retained.

### Ground Station profiles

`GroundStationView` owns station selection and store context. A profile renderer owns panel layout
and profile-specific axes/status formatting. Shared support handles access tiers, point metrics,
range, and elevation-mask filtering.

### Pass views

Pass List and Sky View share interval selection but split layout: one shows the table and the
other shows the Sky plot. Range and close behavior remain in the shared pass base.

## Panel and factory architecture

The app resolves a panel target, constructs/replaces the host, constructs a view through the
registered opener, builds store-backed or non-store content, attaches Figure/wx content, registers
cleanup, and adds or raises the panel.

- `player_data_view_factory.py`: 2D and station/specialized views.
- `player_3d_data_view_factory.py`: 3D backend construction.
- `player_panel_management.py`: generic panel lifecycle and attachment.

## Refresh and replacement flow

Initial build captures or refreshes `StoreViewContext`, calls `build_from_store()`, attaches
content, registers resources, and performs the initial cursor update.

Incremental refresh queues affected panel IDs, refreshes snapshot context, calls
`update_from_store()`, `set_time_range()`, `update(t_s)`, and redraw. Store replacement rebuilds
the panel instead of binding the old view to a new store.

If replacement fails, the candidate closes, panel/callback resources release, the prior panel
remains, and the prior default-view mapping is preserved.

## Resource invariants

- A view does not own `OemDataStore`.
- A view retains bounded artists and the latest context, not orbit-sized copies.
- Cursor/range state belongs to shared view support.
- Panel/stack state belongs to `DataViewPanelHost` and panel management.
- Registry state belongs to `DataViewRegistry`.
- Selection context is shared only by explicitly coordinated station views.

## Extension checklist

1. Define `name`, `label`, and `group`.
2. Choose `OrbitTimeSeriesView`, `GroundStationAnalysisMixin`, or specialized support.
3. Implement `build_from_store()` and `update_from_store()`.
4. Implement `set_time_range()` and `close()`.
5. Subscribe only to needed store tiers.
6. Return a Matplotlib `Figure` or native wx `Window`.
7. Add an opener and preset registration.
8. Add store, range, cursor, close, and panel tests.
9. Update the dedicated diagrams.

## Related diagrams

- [Data-view class hierarchy](./PLAY_OEM_DATA_VIEWS_CLASS_HIERARCHY.mmd)
- [Data-view data flow](./PLAY_OEM_DATA_VIEWS_DATA_FLOW.mmd)
- [Data-view control flow](./PLAY_OEM_DATA_VIEWS_CONTROL_FLOW.mmd)

## Related documents

- [Data-view implementation guide](./PLAY_OEM_DATA_VIEWS_IMPLEMENTATION.md)
- [Play-OEM software design](./PLAY_OEM_SOFTWARE_DESIGN.md)
- [Play-OEM dataflow](./PLAY_OEM_DATAFLOW.md)
- [Play-OEM Matplotlib abstractions](./PLAY_OEM_MATPLOTLIB_DESIGN.md)
