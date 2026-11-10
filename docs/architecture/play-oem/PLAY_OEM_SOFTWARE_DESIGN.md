# `play-oem` — Software Design

Requirements: [PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md). Baseline code: `src/ephem_toolkit/plot_oem/`.

The shipped incremental loading path is summarized in the
[implementation report](./old/PLAY_OEM_INCREMENTAL_LOADING_IMPLEMENTATION_REPORT.md); the original
[design](./old/PLAY_OEM_INCREMENTAL_LOADING.md) is archived.

GUI toolkit: **wxPython** is the sole GUI framework (§3). The earlier Tkinter design is superseded
by the migration in [PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md), steps 15–23.

Implemented Ground Track view: see the [completion report](./old/PLAY_OEM_GROUND_TRACK_IMPLEMENTATION_PLAN.md) and [end-user guide](../../tools/PLAY_OEM_GROUND_TRACK.md).

Implemented Ground Stations feature: see the
[completion report](./old/PLAY_OEM_GROUND_STATIONS_IMPLEMENTATION_REPORT.md) and
[user guide](../../tools/PLAY_OEM_GROUND_STATIONS.md). The original software/GUI designs and
mockups are archived in [old/](./old/).

Modular Ground Station Analysis is implemented; see its
[implementation report](./old/PLAY_OEM_GROUND_STATION_ANALYSIS_2_IMPLEMENTATION_REPORT.md) and
archived [software design](./old/PLAY_OEM_GROUND_STATION_ANALYSIS_2_SOFTWARE_DESIGN.md) and
[GUI design](./old/PLAY_OEM_GROUND_STATION_ANALYSIS_2_GUI_DESIGN.md). The prior composite
[implementation report](./old/PLAY_OEM_GROUND_STATION_ANALYSIS_IMPLEMENTATION_REPORT.md) and
[mockup](./old/mockup-ground-station-visual-analysis.svg) remain archived for reference.

## 1. Historical origin: copy and modify `plot-oem`

The initial prototype reused `plot_oem.py` (~870 lines), then split its plotting, data, and CLI
responsibilities. This history does not describe the shipped loading or data-ownership path:
the current direct-to-store architecture is documented in
[PLAY_OEM_DATAFLOW.md](./PLAY_OEM_DATAFLOW.md).

| `plot_oem.py` piece | Destination in `play_oem/` | Change |
|---|---|---|
| `TimeUnit` | `time_unit.py` | copy verbatim |
| `read_oem_states` | `data.py` | initial prototype; current playback loading streams directly into `OemDataStore` |
| `OrbitSeries`, `compute_orbit_series` | `series.py` | copy verbatim; add `t_s` array use for lookup |
| `plot_*` functions (7) | `views/*.py` | split into *build* (draw static data, return artists) and *update(t)* (move cursor) |
| `plot_oem_cli.py` | `play_oem_cli.py` | adapt file, display, and view-selection options |
| `__main__.py` | `__main__.py` | load and prepare OEM data, then launch the interactive application |

Keep `plot-oem` as the separate static plotting command and `play-oem` as the interactive
playback application. Shared numerical/data-processing code may be extracted later only after
compatibility with both commands is verified.

## 2. Current package layout

Key current modules (the package contains additional focused modules):

```
src/ephem_toolkit/play_oem/
  __main__.py          # create workspace before loading; CLI entry point
  play_oem_cli.py      # PlayOemArgs and command-line parsing
  streaming_oem.py     # parse OEM rows directly into store reservations
  incremental_loader.py # generation-scoped worker, cancellation, and load events
  oem_data_store.py    # raw samples and lazily computed derived tiers
  clock.py             # playback bounds, sample-time view, and clock logic
  cursor.py            # OemCursor compatibility path and StoreCursor point queries
  series.py time_unit.py time_range.py
  app/
    controller.py      # load generations, snapshots, playback, and panel lifecycle
    view_factory.py    # registered store-backed views and backend selection
  workspace/
    core.py features.py ground_stations.py graph_stack.py timeline.py
  views/
    base.py registry.py
    trajectory3d/       # Matplotlib and optional VTK backends
    ground_track.py
    ground_station_*.py # store-backed station views
    state_components.py speed_altitude.py rtn.py angular_velocity.py
    direction_change.py distance.py
```

`pyproject.toml` registers `play-oem` and declares a `playback` extra containing wxPython,
Matplotlib, and pyproj. VTK is a separate optional extra; install the GUI and VTK integrations
with `pip install "ephem-toolkit[playback,vtk]"`. The base install does not require the GUI stack.

Playback dependency validation was performed on macOS arm64 with Python 3.9; this is an install
check, not cross-platform certification. Linux and Windows installs and GUI rendering have not
been exercised in this environment. The repository ignores `poetry.lock`, so local lock validation
is not a committed exact dependency set; clean installs resolve from the optional-dependency
constraints in `pyproject.toml`.

The wxPython migration acceptance and its 105-test run are historical. The current complete
`play-oem` suite was run on 2026-11-09 with Python 3.9: 593 passed and 4 skipped. This automated
result does not replace manual GUI input checks; Linux and Windows GUI installation/rendering
remain unverified in this environment.

`__main__.py` creates exactly one `wx.App`; `PlayerApp` owns its event-loop lifecycle, playback
clock, timer and main workspace frame. The frame has a File menu with **Open File...**, a status
bar for load and error messages, and a `Workspace` that places a `Controls & Info` feature area
beside the `Main Analysis` graph stack and optional `Comparison` stack. The workspace package
composes its layout, feature navigation, graph stacks and shared timeline through focused modules.
When another OEM is loaded, existing views are rebuilt in their graph-panel slots so the stack
structure, panel sizing and scroll position remain intact. Graph views are hosted inside
independently identified graph panels rather than detached plot frames. Closing one panel closes
only its view and unsubscribes it from clock updates; closing the workspace frame stops the timer,
closes all graph panels, removes observers and exits the one `MainLoop()`.
The VTK view disables its interactor, finalizes the render window, removes its renderer and breaks
both interactor/render-window links before wx destroys the panel, so native VTK resources do not
remain in an ownership cycle until interpreter shutdown. Once the event loop stops,
`PlayerApp.run()` releases its wx wrappers and collects remaining Python callback cycles while wx
is still initialized, avoiding native wrapper destruction during interpreter teardown.

## 3. GUI toolkit decision

Options:

| Option | Pros | Cons |
|---|---|---|
| A. Matplotlib only (TkAgg/QtAgg), control window = a Matplotlib figure with `Slider`, `Button`, `RadioButtons` | no new deps; one event loop | clunky toolbar, widget look, slider/timer coupling |
| B. Tkinter control window + Matplotlib figures (`TkAgg`); superseded by D | stdlib Tk, native-ish controls and toolbar, single Tk event loop shared by all figures; no new dependency | Tk must be available (usually bundled; not on some Linux distros); legacy Tk may have rendering limitations |
| C. Qt (PySide6) | best widgets | heavy new dependency |
| D. **wxPython workspace + embedded Matplotlib figures** (`WXAgg`, `FigureCanvasWxAgg`) | native widgets and toolbars on each platform; one wx event loop for controls and Matplotlib canvases; no Tk dependency | new GUI dependency with platform-dependent wheels; `wx.Slider` is integer-only; tests that create a `wx.App` need a display |

**Decision: D (wxPython).** wxPython is the sole GUI framework for `play-oem`, per the migration
directive. The Controls & Info pane, graph-panel hosts, and any VTK widget are owned by one `wx.App`
and one `MainLoop()`. Tk is removed from the runtime path (implementation plan steps 15–23). The
`View`/`Clock` layers are toolkit-agnostic, so the GUI toolkit remains replaceable.

## 4. Core components

### 4.1 `PlaybackClock` (pure logic)

State: OEM coverage `t_start`/`t_end`, independent playback bounds, `t_now`, signed `rate`
(`|rate|` in 1…9000), `playing`, and `loop`.
Speed and direction are stored together as the signed `rate`; the UI shows `|rate|` plus a direction indicator.

- `tick(wall_dt)`: advance within the configured playback bounds; at a playback endpoint pause,
  or wrap to the opposite playback bound if `loop`.
- `seek(t)`: clamps to the playback bounds, sets `t_now`, keeps `rate` and `playing`, and notifies
  observers. O(1), with no replay of intermediate time.
- `set_speed(x)` (`|x|` clamped to `[1, 9000]`, sign preserved), `set_direction(±1)` / `reverse()` (negates `rate`; `t_now` unchanged), `play()`, `pause()`, `toggle()`.
- `step(n_samples | seconds)`: seek relative to `t_now`, used by step buttons/keys.
- `extend_coverage(...)`: publishes appended sample-time coverage during incremental loading;
  playback bounds that follow coverage grow without moving the current cursor or auto-resuming.
- `set_playback_bounds(start, end)`: constrains playback independently inside observed OEM
  coverage and clamps the current time once.
- Observers: `subscribe(callback(t_now))`. The app timer counts complete frame periods from
  monotonic elapsed time. If drawing overruns, the clock advances across all elapsed periods in
  one update and intermediate redraws are dropped.

Unit tests: advance, clamp, loop wrap (both directions), speed clamp, sign preserved on speed change,
reverse mid-play without `t_now` jump, seek while playing/reversed/paused, end-of-timeline pause — no display.

### 4.2 Cursor lookup

`CursorState` contains the state vector, derived quantities, status, and segment identity at
`t_now`. The default incremental path uses `StoreCursor` against a bound `OemDataStore` snapshot;
`OemCursor` remains available for compatibility and non-store use. Each raw sample retains its
OEM segment ID.
`status` distinguishes an exact OEM sample, a valid interpolated state inside a segment, and a
time gap/out-of-segment time. In a gap, do not bridge interpolation across the gap or fabricate
a state: keep the timeline cursor at the requested time, mark the status, and show unavailable
state readouts until it reaches valid data.

`StoreCursor` delegates point lookup to the store's interpolation policy, which honors the
configured or OEM-declared interpolation method and degree, with the documented fallback when
metadata is absent. Range-derived plot columns and point-state queries share the store's raw
snapshot and segment boundaries.

Random seek and reverse require lookup to be **stateless and direction-independent**: a query
must not assume monotonically increasing times, and must never interpolate across a segment gap.
Tests assert `state(t)` is identical when reached forward, backward, or by seek.

### 4.3 Views

```python
class View(Protocol):
    name: str
    def build(self, series: OrbitSeries, time_unit: TimeUnit, /) -> Figure | wx.Window: ...
    def update(self, t_s: float, /) -> None: ...
    def set_time_range(self, bounds, coverage, /) -> None: ...
    def close(self) -> None: ...
```

- Views bind to a `StoreViewContext` containing a stable store snapshot, resolved plot range,
  coverage, and time unit. They request only the named series, Earth-fixed, Ground Track, station,
  or point-state data they use. Appends, range changes, and derived-tier notices refresh data;
  playback-time updates move cursors, markers, and current-state metrics.
- The store owns raw samples and lazily computed derived tiers. Views may create bounded display
  paths or decimated indices, but do not retain independent full-history derived owners.
- Derived calculations operate only on requested, not-yet-ready sample rows. Chunking is for cache
  allocation, accounting, pinning, and eviction; touching a chunk does not calculate its other rows.
  Calculations may read raw support samples needed to produce an in-range result. Station-access
  analysis also expands the requested interval by its documented pass-boundary margin, so results
  near either edge can include a complete access interval.
- Plot each OEM segment separately; do not draw lines across gaps. Mark segment boundaries
  clearly, and update the cursor/readout style or status when `t_now` lies in a gap.
- **WxAgg redraws**: most updates schedule a full canvas draw; the state-components view uses a
  guarded cursor-only blit when the plot range and axes are unchanged. Range/limit changes and
  unsafe blits fall back to a full draw. 3D backends apply their own display-update throttles.
- 2D histories use min/max bucket decimation to at most 2,000 display points per segment;
  Matplotlib 3D uses at most 500 points per segment and VTK uses the shared decimation helper.
  Point-state lookup still uses full-resolution raw samples.
- The registry includes orbit and diagnostic views, Ground Track, and the Ground Station panels.
  `overview` opens trajectory and speed/altitude; `state` opens state components; `motion` opens
  RTN, angular velocity, direction change, and distance; `access-overview` and `pass-study` are
  optional station presets; `all` expands to every registered view. The registry powers
  `--plots` and panel selection.

### 4.3.1 3D trajectory backends (Matplotlib/wx and VTK)

Only the 3D trajectory is backend-pluggable; every 2D time-series view stays Matplotlib.
The plot-oem state-vector diagnostics are split into two views:

- `trajectory-3d`: the 3D orbit, Earth and satellite marker (pluggable backend).
- `state-components`: X/Y/Z, VX/VY/VZ histories (Matplotlib).

The `state` group opens the state-components view. Keep `state-vectors` as a compatibility
alias that opens both trajectory and state-components views.

The state-components view uses a 3-by-2 Matplotlib layout: position X/Y/Z and velocity VX/VY/VZ,
with frame and unit labels, one shared elapsed-time axis, and synchronized cursor lines. Each 2D view
is a `FigureCanvasWxAgg` canvas in an embedded graph-panel host. Clicks map through per-axes plot bounds to preserve
synchronized seeking. The PPM/PhotoImage raster path from the Tk implementation is removed in step 18.

```
views/trajectory3d/
  base.py            # Trajectory3DView protocol + backend selection
  mpl_backend.py     # Axes3D (copied from plot_state_vectors, split build/update)
  vtk_backend.py     # VTK scene
```

```python
class Trajectory3DView(View, Protocol):
    def build(self, series, time_unit) -> None: ...
    def update(self, t_s: float) -> None: ...      # same contract as every View
    def set_tail(self, seconds: float | None) -> None: ...
    def close(self) -> None: ...
```

**Selection** (`select_3d_backend(choice)`):

| `--3d-backend` | Behavior |
|---|---|
| `auto` (default) | Use the embedded VTK backend only if VTK's wx interactor and an actual render context initialize; otherwise use Matplotlib and emit one concise stderr notice with the fallback reason. |
| `vtk` | Require the VTK wx interactor and a working embedded render context. Fail with an actionable error and the VTK-extra install hint if either is unavailable; never silently fall back. |
| `matplotlib` | Always Matplotlib. |

Resolve the backend once when the first trajectory view is created and show the selected backend
in the workspace frame title/status line. `auto` may fall back only for a recognized VTK
installation or render-context unavailability; do not hide unrelated implementation errors with
a broad exception handler. Both backends implement the same interface, so the toolbar, clock and
`PlayerApp` never branch on backend.

**Matplotlib/wx backend.** The initial overview draws the static orbit path, start/end markers,
labeled axes and object/frame context in `build`; `update` moves the satellite marker from the shared
cursor state. The figure and navigation toolbar are hosted in a `GraphPanelHost` within either
graph stack. Redraws are requested with `draw_idle()` and playback updates are throttled to at most
10 Hz. Earth rendering and trajectory tails remain planned enhancements.

**VTK backend.** Scene built in `build`:

- Import `vtkOpenGLRenderWindow` from `vtkmodules.vtkRenderingOpenGL2` before creating the wx
  interactor so VTK registers its shared OpenGL render-window factory; importing
  `vtkRenderingCore` alone can produce a wx window that initializes but remains visually blank.
  Factory registration does not prove native context support: Cocoa, GTK and Windows rendering
  must be visually smoke-tested independently before claiming support.
- Orbit polyline: the default store-backed path selects and display-decimates positions from the
  current raw snapshot, preserving segment boundaries and the selected time range; it then builds
  `vtkPoints`, `vtkPolyLine` cells, and a `vtkPolyDataMapper` → `vtkActor` chain. The legacy
  non-store backend path accepts orbit-series arrays.
- Earth: semi-transparent WGS84 ellipsoid (`vtkSphereSource` scaled by the flattening).
  Inertial-frame view with a static Earth in v1; a rotating, textured Earth needs the ECI→ECEF rotation at
  `t_now` (via `core/frame_utils`) and is a follow-up.
- Satellite: small sphere actor; `update(t_s)` moves it from the cursor state and renders on the
  wx thread. The static orbit path is display-decimated and 3D updates are capped at 10 Hz; the
  cursor and tail still use full-resolution samples. GPU rendering does not by itself guarantee
  the N1 playback target.
- Tail: a second direction-aware polyline over the recent samples, following the cursor in forward
  or reverse playback.
- Camera/interaction: `vtkInteractorStyleTrackballCamera` (rotate/zoom/pan) with the camera left untouched by `update`, so you can orbit while it plays.

**Step 20 outcome: `VTK-KEEP`; use the embedded wx interactor.** Host VTK through
`vtkmodules.wx.wxVTKRenderWindowInteractor.wxVTKRenderWindowInteractor` inside the trajectory
`GraphPanelHost` in Main Analysis or Comparison. Its wx event bindings deliver paint, resize, mouse,
and keyboard events to the VTK interactor. The application owns the only GUI loop: call
`widget.Enable(1)`, let wx's main loop drive the widget, and call `Render()` on the wx thread when
the shared cursor changes. Do not call VTK's `Start()` or manually pump a second event loop. The
VTK widget's own timer requests use `wx.Timer` events and therefore remain on the same loop.

The prototype used wxPython 4.2.4 and VTK 9.6.2 on macOS. Eight wx timer callbacks completed while
the scene rendered; a wx frame resize changed the VTK render-window size; simulated trackball
mouse input moved the camera; and closing the frame shut down the loop cleanly. Linux and Windows
were not available for this check and remain unverified. The VTK wx widget selects a
`wx.glcanvas.GLCanvas` base on GTK and a `wx.Window` base elsewhere, so Linux/Windows integration
must be validated before claiming support there. The production fix registers the shared OpenGL
factory and rejects a non-OpenGL render-window class, but that guard does not replace visual
verification of each platform's native wx/OpenGL context.

After showing a trajectory graph panel, the application yields pending wx paint events and verifies
that the VTK render window completed its initial render. Backend selection errors are explicit:
`vtk` reports a missing VTK package or failed wx/GL initialization with an install or
graphics-support hint; `auto` falls back to Matplotlib only for those recognized VTK-unavailable
conditions and reports the reason once. Install the optional integration with
`pip install "ephem-toolkit[playback,vtk]"`.

**Testing.** The backend-neutral contract is tested on both backends: `build` + several `update` calls,
and marker position == cursor-state position (Matplotlib: artist data; VTK: `actor.GetPosition()`).
VTK tests are skipped via `pytest.importorskip("vtk")`.

### 4.4 Workspace panes

The active workspace uses one `wx.Frame` with three named regions: **Controls & Info** at left,
**Main Analysis** in the middle, and the optional **Comparison** pane at right. These names appear
in visible pane headings and matching wx window names. Controls & Info contains the feature rail and
`wx.Simplebook`; its Settings page embeds the render-rate control, while OEM metadata has
its own page, and current-state readouts live on the State page. Main Analysis and Comparison each
contain an independently scrollable graph stack with per-panel lifecycle. Startup opens `overview`
by default in Main Analysis: the 3D orbit and combined speed/altitude time-series view. `--plots`
can replace that selection with individual views or named groups.

The Controls & Info pane uses a four-page feature rail: Settings, OEM file information,
Ground Stations, and State. Settings contains the render-rate control; `Workspace` owns the shared
playback timeline below the three-pane splitter. Main Analysis and Comparison own their graph
stacks:

```
[Settings page]
Render rate: 30 FPS
[FPS slider: 1–30]

[Shared timeline footer]
Start UTC … | Current UTC [editable time] | End UTC …
[reverse speed presets] [reverse play] [forward play] [forward speed presets]
━━━━━━━━━━━━━━●━━━━━━━━━━━━━━

[OEM file information page]
object … | frame … | center … | epochs … | samples …
Details ▸ (additional OEM metadata and diagnostics)

[Ground Stations page]
station list | Add | inline edit/save/cancel/remove

[State page]
r=(x,y,z) km   v=(vx,vy,vz) km/s   speed=… km/s   altitude=… km
Cursor: interpolated / sample / gap / unavailable

[Main Analysis / Comparison]
graph stacks with per-panel view selector, actions, and close controls
```

- Settings page: the `ControlWindow` provides only a render-rate slider from 1 to 30 FPS (default
  30). Playback controls, navigation, and current UTC are available in the shared timeline footer.
- Shared timeline footer: `Workspace` places a separator, start/current/end UTC row, playback
  direction and speed controls, and the timeline slider below the pane splitter. The range-enabled
  slider uses a custom-painted track and thumb with the playable playback interval highlighted
  separately from seek progress; sibling grips display playback bounds and plot endpoints.
  Playback bounds constrain clock movement. By default plot filtering selects samples inside
  those bounds and follows playback-bound edits; each plot endpoint can instead use a playback-
  time offset or a fixed UTC timepoint. Right-click a plot handle to choose its mode; drag Offset
  and Fixed handles to change their position. See
  [PLAY_OEM_TIME_RANGE_IMPLEMENTATION_REPORT.md](./old/PLAY_OEM_TIME_RANGE_IMPLEMENTATION_REPORT.md)
  for implemented behavior and current validation status. Earlier specifications are archived
  under `old/`.
- Loading-aware timeline: the reader publishes each segment's UTC metadata at `META_STOP`,
  before parsing its state rows. The controller unions valid segment bounds with observed sample
  bounds for the slider domain while keeping playback coverage sample-bounded. The parser's latest
  committed timestamp marks progress; the unread suffix is amber and its hover text reports
  unavailable time. During a loading-time handle drag, plot updates and redraw requests are
  deferred and coalesced, then refreshed from the latest store snapshot when the drag ends or
  capture is lost. Outside loading-time drags, existing redraw behavior is unchanged.
- Footer time entry: a `wx.TextCtrl` accepts `1h30m` (elapsed) or a UTC epoch. Enter submits the
  value to `clock.seek`; invalid input is shown beside the entry without changing `t_now`. Its
  existing value is selected once when it gains focus, and later clicks place the caret normally.
- Footer playback controls: signed speed presets select rates without starting or pausing. Separate reverse
  and forward buttons start or pause playback in that direction while retaining the speed magnitude.
  Direction-specific speed controls cover 1x, 10x, 100x and 1000x.
- Settings page render-rate slider: selects the UI update limit from 1 through 30 frames per
  second. Playback rate is controlled by the shared timeline footer.
- Native sizing and keyboard focus come from wx. The frame-level File menu provides **Open File...**;
  the status bar reports successful loads and errors.
- Click-to-seek: each time-series view connects `button_press_event` (left click inside axes, toolbar zoom/pan mode inactive) → `clock.seek(x * unit_divisor)`.
- The graph-panel selector opens individual registered views. Presets and `--plots` open named
  groups; an already-open view is raised rather than duplicated. Closing one graph panel does not
  affect the clock or other panels. Closing the workspace frame destroys all panels and stops the
  single wx event loop.
- Current-state readouts on State come from the same `CursorState` as the plots, including explicit
  sampled/interpolated/gap status. In gaps, show state values as unavailable rather than carrying
  forward the last sample. Altitude is shown only when its frame/center assumptions are valid;
  units and reference frame are visible. OEM object/frame/center/time span/sample count remain on
  the OEM file information page, with less-used metadata in its collapsed details panel.
- Keys: `Space` play/pause, `R` reverse, `←/→` step (∓/± 1 sample), `Shift+←/→` ∓/± 1 min, `Home/End` jump to start/end.
  These are wx accelerators on the workspace frame and are inactive while the shared footer time-entry field has focus.

### 4.5 `PlayerApp` and the frame loop

`PlayerApp` behavior is split across controller, view-factory, playback-action, and panel-management
mixins. Their shared `PlayerAppState` protocol lives in `app/state.py`; `_plots` is a tuple there
because the controller stores the expanded plot selection as an immutable tuple. The constructor
still accepts any `Sequence[str]` for the initial plot selection.

One `wx.Timer` (`wx.EVT_TIMER`) uses a millisecond interval approximating
`1000/render_rate_fps`:

1. Measure monotonic elapsed time and count complete selected frame periods, retaining the
   fractional remainder for the next event.
2. Advance the playback clock by the sum of elapsed periods in one tick, then update the slider
   and readouts once.
3. Update and redraw each open view once. Any intermediate display frames missed during a slow
   redraw are dropped rather than queued.

The app has one wx main loop, plus a background load worker and store-managed derived-tier work.
`__main__.main()` creates an empty startup model and the workspace; the controller starts a
generation-scoped incremental load. The worker scans for capacity when needed and streams raw rows
directly into the new `OemDataStore`. The wx thread drains generation-tagged events, installs
snapshots, captures `StoreViewContext` values, and refreshes open panels. No whole-history
`OrbitSeries` is prepared before the workspace appears.

## 5. CLI flow (`__main__.py`)

1. Parse the optional OEM path, `--plots`, `--3d-backend`, and `--config`.
2. Load user configuration and saved workspace state, then construct the `wx.App` and workspace
   with an empty startup model.
3. Show the workspace and start the selected file's generation-scoped background load. The worker
   commits parsed rows directly to the store; the wx thread installs usable snapshots and refreshes
   the selected views as loading progresses. Completion publishes validated metadata.
4. Playback, seeking, and render-rate controls operate in the GUI. `--plots` defaults to
   `overview`; `auto` selects VTK only when its wx integration initializes successfully, otherwise
   it uses Matplotlib with a notice. An explicit unavailable VTK request fails with an actionable
   error.
5. SIGINT is forwarded with `wx.CallAfter` to the close routine, which shuts down the worker,
   hosted views, and workspace frame before ending the single wx main loop.

## 6. Testing

- Playback/store tests live under `tests/ephem_toolkit/play_oem/` and cover clock behavior,
  incremental parsing, store queries, segment/gap handling, and view refresh.
- View tests cover store-bound range queries, plot updates, click-to-seek, station selection, and
  explicit unavailable/partial-coverage states.
- App and CLI tests cover wx lifecycle, `--plots`, config precedence, backend selection, and
  incremental replacement. Matplotlib-only tests can run headlessly; tests creating `wx.App`
  require a usable wx display environment.
- Current complete package test check (2026-11-09): `PYTHONPATH=src python3 -m pytest -q
  tests/ephem_toolkit/play_oem` — 593 passed, 4 skipped.
- Manual visual/input checks and cross-platform GUI verification remain separate from this
  automated test result.

## 7. Implementation plan

The dependency-ordered, demo-first implementation sequence is maintained separately in
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md).

## 8. Risks

- Blitting with 3D axes is unreliable → the Matplotlib 3D backend updates the marker and redraws at a reduced rate (e.g. 10 fps) without blitting; VTK avoids this.
- Embedded VTK uses the wx interactor and shares the application's wx event loop; do not start or pump a separate VTK loop. Linux and Windows rendering remain unverified.
- VTK wheels may lag new Python versions; hence optional extra and automatic Matplotlib fallback (only if `VTK-KEEP`).
- GUI dependency availability is platform- and Python-version-specific; verify installation in
  each target environment rather than inferring support from a successful local install.
- `wx.Slider` is integer-only. The timeline and speed controls use explicit integer ranges with documented mappings (§4.4).
- SIGINT may not be handled promptly inside the wx main loop; the `wx.CallAfter` forwarding in §5 handles it.
- Multiple Matplotlib figures in one wx loop: use the `WXAgg` backend only and never mix backends.
- wx absent → report a clear GUI dependency error; core logic remains testable without a display.

## 8.1 Performance findings and deferred work

The step-27 benchmark predates the full-redraw workaround below and used 100,000 synthetic
orbit samples, all seven views, 1000x playback,
and a five-second native wx measurement on macOS. It measured about 6.7 playback updates/s with
the automatic VTK backend and about 11.4 updates/s with Matplotlib 3D throttled to 10 Hz. A
Matplotlib run with a 5 Hz 3D cap reached about 14.4 updates/s. These short host-specific runs
are below the N1 target of 15 updates/s; the user accepted the current behavior and requested
that further performance work be deferred. This is an accepted deviation, not evidence that
the target was reached.

A separate headless Agg render-loop benchmark with cached blitting measured about 538 view
updates/s across the seven views; it also predates the full-redraw workaround and is not a
measurement of the current wx path. Agg is CPU software rendering; this result does not predict
native wx/compositor performance. Full-resolution data remains available for cursor lookup:
display-only 2D histories are limited to 2,000 min/max-selected points per segment, the
Matplotlib 3D path to 500 points per segment, and the VTK display path to 2,000 points per
segment. Playback-clock advancement is independent of the 3D render throttle.

Deferred follow-ups:

- Repeat the all-view benchmark on representative macOS, Linux, and Windows hardware with both
  Matplotlib and VTK, including a real 100k-sample OEM and segmented inputs.
- Record timer cadence, per-view update time, wx full-draw/VTK render time, and interaction
  latency separately; report sustained and percentile values, not just short-run averages.
- Profile the roughly 10-second 100k-state derived-series preparation observed in the synthetic
  run. Consider vectorizing the per-sample RTN work only after profiling identifies it as a
  relevant startup bottleneck.
- Revisit 3D point budgets, adaptive display decimation, and render-rate/frame-dropping policy
  against a measured input-responsiveness target. Preserve full-resolution cursor calculations.
- Compare hardware/software rendering and compositor behavior per platform; do not infer GPU
  acceleration from Agg or wx bitmap presentation alone.

Platform/implementation-dependent considerations (hypotheses, not conclusions from the
benchmark):

- wx timer delivery, native paint scheduling, high-DPI scaling, and the compositor may change
  actual event cadence and blit cost between macOS, GTK/Linux, and Windows. The current
  measurements do not isolate those causes.
- Matplotlib WxAgg still performs Matplotlib rasterization through Agg on the CPU; wx/native
  compositing may use different presentation paths on each platform. The benchmark did not
  measure GPU utilization.
- VTK uses an OpenGL render window, but its frame cost and whether rendering is hardware
  accelerated depend on the active driver/context. The successful VTK backend selection and
  lower measured rate than Matplotlib in this run do not prove either hardware acceleration or
  that VTK is generally slower.
- OEM sample spacing, segment count/length, orbital geometry, figure dimensions, and display
  scale may change decimation quality and render cost. The synthetic orbit does not represent
  every customer OEM.
- The 10 Hz 3D cap limits 3D marker updates independently of the clock. Consequently, the
  N1 interaction target should be evaluated separately from 3D visual smoothness at 1000x.
