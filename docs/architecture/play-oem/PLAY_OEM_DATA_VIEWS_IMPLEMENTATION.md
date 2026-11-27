# Play-OEM Data Views Implementation Guide

**Status:** implemented

This guide describes how canonical Play-OEM data-view implementations are structured and carried
through construction, store refresh, range changes, cursor updates, and close.

## Source layout

```text
src/ephem_toolkit/play_oem/
  views/
    data_view_base.py
    data_view_registry.py
    orbit_time_series.py
    time_series_support.py
    plotting.py
    speed_altitude.py
    state_components.py
    rtn.py
    angular_velocity.py
    direction_change.py
    distance.py
    ground_track.py
    ground_station.py
    ground_station_passes.py
    trajectory3d/
  app/
    player_data_view_factory.py
    player_3d_data_view_factory.py
    player_panel_management.py
    player_store_data_view_refresh.py
```

Public modules in `views/` are canonical view implementations.

## Canonical implementation pattern

A standard 2D view follows this shape:

```python
class ExampleView(OrbitTimeSeriesView):
    name = "example"
    label = "Example"
    group = "motion"

    def __init__(self, start_time_s, object_name, *, panel=None, on_seek=None):
        super().__init__(start_time_s, panel=panel, on_seek=on_seek)
        self._object_name = object_name

    def build_from_store(self, context):
        ...

    def update_from_store(self, context):
        ...

    def set_time_range(self, bounds, coverage):
        ...

    def update(self, time_s):
        super().update(time_s)

    def close(self):
        self._close_time_series_wx()
        self._close_store_series_plot()
```

The public class owns metadata and view-specific behavior. Shared support supplies lifecycle and
presentation mechanics.

## Registry pattern

Every public view exposes `name`, `label`, and `group`. `DataViewSpecMixin.view_spec()` converts
those fields and an app opener into `DataViewSpec`.

Registration:

1. Define presets in `PlayerApp._initialize_data_view_registry()`.
2. Register canonical public classes.
3. Register station/pass views separately when needed.
4. Expand CLI/panel selections through `DataViewRegistry.expand()`.
5. Open or raise each resolved view once.

Unknown names, unknown presets, duplicate registrations, and missing openers are rejected before
panel construction.

## Store context

The app captures a context after usable store data is available:

```python
context = StoreViewContext.capture(
    store,
    time_unit=time_unit,
    plot_range=resolved_range,
    coverage=(clock.t_start, clock.t_end),
)
```

Range-aware helpers include:

- `series(group, max_samples=...)`
- `series_groups(groups, max_samples=...)`
- `earth_fixed_positions()`
- `ground_track()`
- `station_access(station)`
- `station_metrics_at(station, t_s)`
- `footprints(t_s, minimum_elevation_deg)`
- `state_at(t_s)`

Prefer these helpers over direct snapshot iteration except for narrow raw-backed implementations
such as State Components and 3D Orbit.

## Store binding

`StoreSeriesPlotView` and `StoreStationViewSupport` initialize `StoreViewBinding` with required
tiers. Binding unsubscribes old tiers when the store changes, subscribes new tiers once, updates
the active context, and provides range-bound contexts. `close()` unsubscribes and clears context.

## 2D view implementation

### Figure construction

Use `create_figure()` and `style_axes()` for base setup. Define view-specific figure size, axis
layout, labels, titles, grids, cursor lines, and empty-state artists. Configure shared range
state with `_configure_time_range()`.

### Store refresh

The refresh path should:

1. Clear prior store-owned artists.
2. Query or bind the required range.
3. Build bounded PathPatch/Line2D artists.
4. Preserve or rescale Y limits as appropriate.
5. Set shared X limits.
6. Update empty-state text.
7. Move the cursor to the latest context cursor time.

Do not recreate range callbacks or store subscriptions on each snapshot refresh.

### Range changes

Call `_store_context_for_range()` and reapply context with `rescale_y=False` when only X range or
coverage changed. Reset Y limits only for an actual data/snapshot change. Non-store
`OrbitSeries` updates use `_update_history_data()` and `super().set_time_range()`.

### Cursor updates

Convert absolute TT seconds to elapsed axis units using the active coverage origin and display
divisor. Hide cursors outside a finite plot range. The app owns the clock; `update(t_s)` moves
presentation state.

### wx presentation

`OrbitTimeSeriesView._present_figure()` records the Figure and axes, applies time-axis metadata,
creates `MatplotlibPanel`, creates status/legend floating panels, registers click-to-seek, and
performs an initial cursor/status update. Without a wx parent it returns the Figure.

## Specialized implementations

### Ground Track

Bind store context, rebuild only affected track/footprint state, update effective bounds on range
changes, and clear map artists, callbacks, floating panels, and subscriptions on close.

### Ground Station

`GroundStationView` maintains station selection/store context and forwards range, station, time,
and close operations to the profile renderer. The renderer creates the profile panel, queries
station access, draws bounded segments, applies elevation-mask behavior, and updates live status.

### Pass List and Sky

Pass views share selection context but split layout. Pass List shows the table; Sky View shows the
polar plot. Selecting a pass updates shared interval selection.

### 3D

Matplotlib 3D returns a `Figure`. VTK returns a native wx window and implements store refresh,
cursor/range updates, close cleanup, and render-context validation. Backend selection belongs to
the 3D factory and selector.

## Panel construction flow

`PanelManagementMixin._open_data_view()`:

1. Publishes a range hint.
2. Resolves existing/pending/replacement state.
3. Constructs and inserts the panel host.
4. Constructs the view instance.
5. Builds store-backed or non-store content.
6. Attaches Matplotlib or wx content.
7. Registers close/callback resources.
8. Adds the panel to `_open_panels`.
9. Publishes range hints for refresh scheduling.

On failure, the candidate view closes and `_rollback_open_data_view()` restores the prior panel.

## Snapshot refresh flow

`PlayerStoreViewRefreshMixin._refresh_store_data_views()` suppresses deferred partial refreshes,
refreshes `StoreViewContext` if snapshot/revision/policy changed, takes affected panel IDs,
rebuilds views that require store replacement, calls `update_from_store()`, `set_time_range()`,
`update(t_s)`, and redraw. No view silently accepts a context from another store.

## Incremental loading

Initial display waits for playback and plot coverage. The producer pauses at a committed batch
boundary, initial views build from the covered snapshot, append notices refresh affected
snapshots, range hints prioritize derived work, and views update bounded artists in place.

## Testing recipe

Test metadata/registry, store build, range query, empty range, snapshot refresh, revision update,
cursor placement, out-of-range visibility, range rescaling, segments/gaps, wx callbacks/close,
panel rollback, and absence of orbit-sized copies.

Store tests should verify bounded timestamps, aligned grids, display-point caps, and backing-array
ownership. App tests should verify direct factory constructor kwargs and rollback close behavior.

## Adding a view

1. Add `views/<name>.py`.
2. Define canonical metadata.
3. Implement the store lifecycle.
4. Add a factory opener.
5. Register the class and preset membership.
6. Add store and panel tests.
7. Update software-design, implementation, and diagram documents.

## Related diagrams

- [Data-view class hierarchy](./PLAY_OEM_DATA_VIEWS_CLASS_HIERARCHY.mmd)
- [Data-view data flow](./PLAY_OEM_DATA_VIEWS_DATA_FLOW.mmd)
- [Data-view control flow](./PLAY_OEM_DATA_VIEWS_CONTROL_FLOW.mmd)
