# Play-OEM Matplotlib Abstractions and Call-Site Design

**Status: implemented.** The shared helpers and wx wrapper are used by the
Play-OEM graph and station views. The local tests cover the pure layout rules,
wx resize fitting, and the specialized Ground Track behavior; a separate
HiDPI desktop smoke test remains useful. Existing Ground Track behavior documented in
[PLAY_OEM_GUI_DEBUGGING.md](./PLAY_OEM_GUI_DEBUGGING.md) remains in force.

## Purpose and scope

Play-OEM uses Matplotlib both for figures returned by data views and for
figures embedded directly in wx view panels. Figure construction, canvas
fitting, and axes styling now share a small helper/widget API without changing
view-specific plot content or the separate CLI plotting tools.

In scope:

- Shared figure construction and axes styling helpers.
- A composable wx panel that owns a Matplotlib figure canvas and optionally a
  toolbar.
- Common figure proportions, resize behavior, minimum canvas dimensions,
  padding, typography, and grid styling.
- Migration of compatible Play-OEM figure and canvas call sites.

Out of scope:

- Changes to `plot-oem`, `plot-oem-diff`, or other non-Play-OEM plotting tools.
- Process-global Matplotlib `rcParams` or a new user-selectable theme.
- Changes to plotting data, segment boundaries, decimation policy, view
  labels, scientific units, or playback behavior.
- Replacing Ground Track's custom pan behavior or its renderer-measured
  floating-legend presentation.

## Existing use cases

The shared design must fit three patterns:

1. **Migrated orbit/diagnostic time-series views.** `angular_velocity.py`,
   `direction_change.py`, `distance.py`, `rtn.py`, `speed_altitude.py`, and
   `state_components.py` expose canonical public view implementations. Each class
   combines its public metadata and figure/store/wx behavior while inheriting
   `OrbitTimeSeriesView` for `StoreTimeSeriesView`, `TimeSeriesWxPanelMixin`,
   expanded live status, floating legends, minimum-size canvas behavior, and
   explicit seek metadata.
2. **Views that own their wx layout.** `ground_station.py` owns unified
   profile/status/access renderers; `ground_station_passes.py` owns Pass List
   and Sky panels. These build native wx panels
   containing controls, status text, and a `FigureCanvasWxAgg`.
3. **Specialized Ground Track.** `ground_track.py` combines a custom pan
   toolbar, a map canvas, and a floating legend. The map axes use a fixed 2:1
   box; the reusable floating legend widget sizes its figure from renderer
   bounds and converts physical pixels to wx logical pixels using the DPI
   scale.

The existing data/artist helpers in `views/plotting.py` are a separate layer:
`SegmentedPlotHistory`, segmentation, decimation, sample bounds, time-range
conversion, and shared x limits. Keep these out of the wx widget and preserve
their established behavior.

## Store and artist binding abstractions

Store-backed Matplotlib views use shared bindings rather than view-local
remove/rebuild loops:

- `StoreArtistBinding` owns one Matplotlib axis's reusable `Line2D`/
  `PathPatch` collection. It supports store-derived segments, raw-state
  segments, and arbitrary point pairs.
- `StoreLineSegmentBinding` owns reusable `Line2D` artists for projected or
  otherwise post-processed segments. It syncs a sequence of `(x, y)` pairs,
  removes excess artists, and preserves the caller's style and marker policy.
- `StationProfileArtistBinding` owns reusable Ground Station profile
  `Line2D`, access `Polygon`, and mask `Line2D` artists. It synchronizes
  sampled profiles and range overlays without clearing the station axes or
  rebuilding the playback/canvas structure.
- `StationAccessBinding` owns station/store/range identity and repeated
  station-access preparation. It returns one set of store queries and adapted
  station results. Cursor-only updates and unchanged station/range contexts
  do not reissue store queries.

Bindings are presentation/query owners, not data-store owners. They never
copy orbit-size arrays or replace store snapshot lifecycle. Store snapshots,
range hints, coverage, tier subscriptions, and station policy remain owned by
`StoreViewContext`, `StoreViewBinding`, and `OemDataStore`.

Range-only dispatch is separate from store-snapshot refresh. `_dispatch_time_range`
updates visible view ranges directly and defers hidden panels; `_refresh_store_data_views`
is reserved for snapshot/tier/coverage and panel-rebuild changes. This avoids
one plot-range edit triggering both a range setter and a full store-view refresh.

### Ground Track call-site shape

Ground Track keeps projection, map axes, station controls, and dynamic
footprint overlays view-specific. Store track rows and projected track lines
move behind bindings:

```python
self._track_binding.sync(
    self._axes,
    store_query.value,
    projection=self._projection,
    center_longitude_deg=self.center_longitude_deg,
)
```

The binding reconstructs only projected display segments. It reuses existing
track `Line2D` instances and calls no store query when the bound context,
projection center, or range key has not changed.

### Ground Station call-site shape

Ground Station profile and pass views share `StationAccessBinding`:

```python
changed = self._station_access_binding.prepare(
    self._active_station_store_context,
    stations=self._stations,
    oem_loaded=self._oem_loaded,
    extra_key=(...),
)
if changed:
    self._draw()
```

The binding owns exact preparation keys and deduplicates repeated
`station_access()` calls across snapshot, range, coverage, policy, station
configuration, pass-range mode, and view-specific extra keys. It does not
filter pass intervals or select pass UI state; Pass List and Sky View retain
those view-specific operations.

Profile renderers synchronize presentation artists through
`StationProfileArtistBinding`:

```python
self._profile_artist_binding.sync(
    self._axes,
    profile_segments,
    profile_labels=profile_labels,
    interval_polygons=interval_polygons,
    mask_segment=mask_segment,
)
```

The binding retains compatible artists across range changes and station
updates, removes excess segments, and does not call `Axes.clear()`. The
playback marker remains an in-place artist, while range/coverage changes only
update x limits and synchronized profile data.

Ground Station Pass/Sky polar rendering also uses shared `StoreLineSegmentBinding`
instances for the mask circle, selected-pass path, endpoint markers, and
playback marker. `_draw_sky_plot()` updates polar axes configuration and
legend/text state in place instead of calling `axes.clear()` and recreating
every line artist. Pass selection and interval filtering remain view-specific.

## Proposed architecture: make the common path the easy path

### Pure Matplotlib helpers

`src/ephem_toolkit/play_oem/matplotlib_helpers.py` provides the operations
that remove repeated setup from callers:

```python
create_figure(
    figsize: tuple[float, float],
    *,
    dpi: float | None = None,
    constrained_layout: bool = True,
) -> Figure

style_axes(*axes: Axes) -> None
```

`create_figure` uses Matplotlib's configured figure DPI unless a caller
explicitly overrides it, and applies the shared constrained-layout defaults,
including the documented spacing. Callers still choose figure dimensions and
construct their view-specific axes, projections, labels, and artists.
`style_axes` applies shared typography and major-grid defaults to one or more
axes; it does not change labels, limits, data colors, or specialized aspect
rules. `style_legend` and `create_figure_legend` apply shared legend typography
and construct optional figure-level legends; `legend_canvas_size_px` returns
renderer-measured bounds with a compact physical-pixel inset. Figures with a
suptitle set its 12-point size when the title is created.
The non-constrained fallback uses `tight_layout(pad=0.2)` only when subplot
parameters remain at Matplotlib defaults.

Store-backed orbit time-series views use
`constrained_layout=False` because they have fixed stacked-axis topology.
`configure_figure_layout(figure)` is called once after those axes exist, applying
the same default-subplot fallback before panel realization. This removes
per-redraw constrained-layout execution from these views while preserving a
single fixed layout pass.

### `MatplotlibPanel`

`src/ephem_toolkit/play_oem/widgets/matplotlib_panel.py` provides a
`MatplotlibPanel(wx.Panel)` composite. Its normal constructor is small:

- Inputs: parent, figure, and an optional toolbar factory that returns a wx
  window.
- Owns a `FigureCanvasWxAgg` and, when requested, the toolbar returned by the
  factory.
- Exposes typed `figure`, `canvas`, and `toolbar` attributes. Callers connect
  Matplotlib events and draw through the actual backend canvas.
- Provides a vertical layout with toolbar above canvas and the standard canvas
  inset. It does not own view-specific controls, labels, or status messages.
- Does not constrain the canvas aspect ratio by default; time-series plots
  expand to the available width and height. Set `preserve_aspect_ratio=True`
  for semantically constrained views such as 3D trajectories and polar plots.
- Keeps a 320-DIP minimum width and a minimum height of 240 DIPs or 60% of the
  preferred figure height, whichever is greater. When aspect preservation is
  enabled, the minimum dimensions are paired to the figure aspect. Renderer
  pixels are converted to wx logical dimensions at this boundary. An explicit
  minimum-size override is reserved for exceptional cases. The data-view panel's
  scroller remains responsible for content that exceeds its viewport.

Data views keep returning `Figure`; wx-owned views keep returning wx windows.
The wrapper is introduced at the embedding boundary, so view build and update
contracts do not change. `DataViewPanelHost` retains its redraw throttling,
cursor blitting, mouse-wheel routing, sizing, and visibility behavior while
receiving a `MatplotlibPanel` and using its exposed canvas and toolbar. Native
specialized canvases outside the wrapper retain their compact native spacing.

### `FloatingMatplotlibLegend`

`src/ephem_toolkit/play_oem/widgets/floating_matplotlib_legend.py` provides a
`FloatingMatplotlibLegend` built on `FloatingPanel`. Callers supply view-owned
artist handles through `set_handles`; the widget creates and styles a
figure-level legend, draws it to measure its renderer bounds, sizes the figure
to fit, applies the 2-physical-pixel inset, and converts its minimum canvas size
to wx logical pixels. View code manages artist handles rather than a separate legend figure,
backend canvas, or DPI conversion.

The widget is for floating legend content rather than ordinary in-axes
legends. `style_axes` continues to style existing axes legends in place.

### Call-site shape

The API removes backend and styling boilerplate while leaving the plot
definition in each view:

```python
figure = create_figure(FIGURE_SIZE_INCHES)
axes = figure.subplots(2, 1, sharex=True)
style_axes(*axes)
```

A wx-owned view embeds that figure without constructing its own backend canvas:

```python
plot = MatplotlibPanel(parent, figure)
sizer.Add(plot, 1, wx.EXPAND)
self._canvas = plot.canvas
```

Graph-panel attachment supplies a toolbar factory only when it needs one:

```python
plot = MatplotlibPanel(
    parent,
    figure,
    toolbar_factory=NavigationToolbar2WxAgg,
)
panel.set_matplotlib_content(plot)
```

This replaces repeated `FigureCanvasWxAgg` construction, toolbar realization,
canvas sizer insertion, and shared layout setup. Direct backend construction
should remain only inside the wrapper, Ground Track's specialized legend/map
path where required, and backend-specific tests.

## Proposed visual standard

These are the implemented defaults; continue to verify them against dense
axes, native wx layout, and HiDPI screens.

### Figure dimensions and aspect

All dimensions below are preferred initial figure sizes in inches, not fixed
screen dimensions. Renderer pixel sizes follow Matplotlib's configured figure
DPI and the active display's scale factor.

| Plot layout | Preferred figure size | Notes |
|---|---:|---|
| One plot row | 8 x 4.5 | Wide single-panel baseline |
| Two stacked rows | 8 x 6 | Shared-x time-series baseline |
| Three stacked rows | 8 x 7.5 | Three-component time-series baseline |
| Three rows by two columns | 10 x 8 | State component comparison |
| 3D view | 8 x 6 | Keep equal-unit cube axes |
| Polar view | 5 x 4.5 | Keep circular axes |
| Ground Track | 9 x 5 | Keep map axes box at 2:1 |

Time-series figure canvases fill the available width and height independently;
do not preserve their initial figure ratio during resize. Keep the plot's
minimum height even when the host is short. Preserve canvas aspect only for
views that require it, such as the equal-unit 3D trajectory and circular polar
plots. Do not equate canvas aspect with data-space aspect: elapsed time and
physical units on ordinary time-series axes remain `aspect="auto"`. Ground
Track's map uses its own canvas and retains `set_box_aspect(0.5)`.

### Minimum dimensions

The default canvas minimum is:

- Width: at least 320 wx logical pixels (DIPs), aligned with the current
  minimum graph pane width.
- Height: at least 240 DIPs and at least 60% of the preferred figure height,
  converted to wx logical units. Time-series panels use this height floor
  independently of their width; aspect-preserving panels pair the minimum
  dimensions to the figure ratio.

The data-view stack already scrolls when content exceeds the viewport, so a
minimum plot size must not be reduced just to force the entire figure into a
short panel. Keep renderer-pixel measurements and wx logical sizes distinct
and apply `GetDPIScaleFactor()` at the conversion boundary.

### Padding and subplot spacing

- Embedded canvas outer inset: 8 DIPs.
- Constrained layout: begin with `w_pad=0.08`, `h_pad=0.08` inches,
  `wspace=0.04`, `hspace=0.08`.
- Figures without a layout engine: use `tight_layout(pad=0.2)` only when the
  caller has not customized subplot parameters.
- Ground Track legend: retain its compact renderer-measured 2-physical-pixel
  canvas inset and 1-DIP floating-panel border; this is intentionally not the
  standard plot-panel margin.

The goal is enough room for ticks, labels, titles, and legends without the
large default margins. Do not apply both constrained layout and tight layout
to the same figure.

### Typography, grid, and colors

- Keep Matplotlib's default font family for cross-platform consistency.
- Axis titles: 11 pt; figure suptitles: 12 pt.
- Axis labels: 10 pt; tick labels and legends: 9 pt.
- Major grid: below data, alpha 0.25, linewidth 0.6 pt.
- Preserve the existing Matplotlib color cycle and semantic colors such as the
  red playback cursor.
- Apply styles through helpers on each figure/axes; do not mutate global
  `rcParams`.

## Migration boundaries

1. Standard data views use `create_figure` and `style_axes`; their axes count,
   grid topology, labels, projections, artists, and data behavior remain
   view-specific.
2. The view-panel attachment boundary passes one `MatplotlibPanel` to
   `DataViewPanelHost`; redraw, blit, event, natural-height, and scroller behavior
   remain in the host.
3. Wx-owned station views use `MatplotlibPanel` for canvas construction and
   retain their own controls, callbacks, and parentage.
4. Ground Track remains specialized: its map canvas/custom pan toolbar keep
   their dedicated path, while its floating legend uses
   `FloatingMatplotlibLegend`.
5. Existing sample/artist helpers and their tested contracts remain in
   `views/plotting.py`; no numerical plotting behavior was moved into the wx
   widget.

## Verification and acceptance

Focused tests cover the small helper/widget API, then the existing view-panel
and affected view tests exercise regressions. Use the repository `.venv`.

- Draw representative figures at multiple sizes and DPI scales. Tests assert
  flexible time-series canvases fill the available area, aspect-preserving
  canvases remain within 1% of their target aspect, and axes/text bounds stay
  within the figure with a 2-pixel tolerance.
- Verify the figure-derived minimum size, 320-DIP width floor, independent
  time-series height floor, and logical pixel conversion at multiple scale
  factors. Aspect-preserving plots retain their paired minimum dimensions.
  The scroller remains responsible for overflow.
- Verify constrained-layout padding and the default-subplot fallback; explicit
  subplot parameters are not overwritten.
- Verify typography/grid settings while retaining view-specific labels,
  semantic colors, and aspect rules.
- Ground Track's map/legend behavior remains covered by its dedicated view
  tests; verify its legend bounds after changes to entries or spacing.
- Preserve Ground Track's 2:1 axes box, 3D equal-unit box, polar circular
  axes, DataViewPanelHost redraw/blit behavior, and existing plotting-data tests.

Focused validation should cover
`test_play_oem_plotting.py`, `test_graph_panel.py`, the new widget tests, and
the affected station/trajectory view tests. If those pass, run the complete
Play-OEM test directory and Ruff on changed Python files. These checks do not
replace a wx GUI resize smoke test at standard and HiDPI scales.
