# `play-oem` — Design

Requirements: [PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md). Baseline code: `src/ephem_toolkit/plot_oem/`.

GUI toolkit: **wxPython** is the sole GUI framework (§3). The earlier Tkinter design is superseded
by the migration in [PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md), steps 15–23.

## 1. Approach: copy and modify `plot-oem`

`plot_oem.py` (~870 lines) mixes three things; we split them while copying:

| `plot_oem.py` piece | Destination in `play_oem/` | Change |
|---|---|---|
| `TimeUnit` | `time_unit.py` | copy verbatim |
| `read_oem_states`, `filter_states_by_duration` | `data.py` | copy verbatim |
| `OrbitSeries`, `compute_orbit_series` | `series.py` | copy verbatim; add `t_s` array use for lookup |
| `plot_*` functions (7) | `views/*.py` | split into *build* (draw static data, return artists) and *update(t)* (move cursor) |
| `plot_oem_cli.py` | `play_oem_cli.py` | copy; add playback options |
| `__main__.py` | `__main__.py` | load and prepare OEM data, then launch the interactive application |

Keep `plot-oem` as the separate static plotting command and `play-oem` as the interactive
playback application. Shared numerical/data-processing code may be extracted later only after
compatibility with both commands is verified.

## 2. Package layout

```
src/ephem_toolkit/play_oem/
  __init__.py          # cli = main
  __main__.py          # main(argv)
  play_oem_cli.py      # PlayOemArgs, build_arg_parser
  data.py  series.py  time_unit.py              # copied from plot_oem
  clock.py             # PlaybackClock (pure Python, no GUI)
  cursor.py            # CursorState lookup at t_now
  app.py               # PlayerApp: owns wx.App, clock, views, control window
  control_window.py    # wx.Frame: slider, play/pause, speed, toolbar
  views/
    base.py            # View protocol
    trajectory3d/      # mpl_backend.py; vtk_backend.py only if VTK-KEEP (see 4.3.1)
    state_components.py speed_altitude.py rtn_deltas.py angular_velocity.py
    direction_change.py geocentric_distance.py
    registry.py        # view/group names -> factories
```

`pyproject.toml`: add `play-oem = "ephem_toolkit.play_oem:cli"` and an optional extra
`playback = ["wxpython>=<minimum recorded in step 15>", "matplotlib>=3.7"]`. The base install does not
require wxPython. Add `vtk = ["vtk>=9.2"]` only if step 20 records `VTK-KEEP`.

## 3. GUI toolkit decision

Options:

| Option | Pros | Cons |
|---|---|---|
| A. Matplotlib only (TkAgg/QtAgg), control window = a Matplotlib figure with `Slider`, `Button`, `RadioButtons` | no new deps; one event loop | clunky toolbar, widget look, slider/timer coupling |
| B. Tkinter control window + Matplotlib figures (`TkAgg`); superseded by D | stdlib Tk, native-ish controls and toolbar, single Tk event loop shared by all figures; no new dependency | Tk must be available (usually bundled; not on some Linux distros); legacy Tk may have rendering limitations |
| C. Qt (PySide6) | best widgets | heavy new dependency |
| D. **wxPython control frame + Matplotlib figures** (`WXAgg`, `FigureCanvasWxAgg`) | native widgets and toolbars on each platform; one wx event loop for the control frame and Matplotlib canvases; no Tk dependency | new GUI dependency with platform-dependent wheels; `wx.Slider` is integer-only; tests that create a `wx.App` need a display |

**Decision: D (wxPython).** wxPython is the sole GUI framework for `play-oem`, per the migration
directive. The control frame, Matplotlib plot frames, and any VTK window are owned by one `wx.App`
and one `MainLoop()`. Tk is removed from the runtime path (implementation plan steps 15–23). The
`View`/`Clock` layers are toolkit-agnostic, so the GUI toolkit remains replaceable.

## 4. Core components

### 4.1 `PlaybackClock` (pure logic)

State: `t_start`, `t_end`, `t_now` (seconds from start), `rate` (signed float, `|rate|` in 1…1000), `playing`, `loop`.
Speed and direction are stored together as the signed `rate`; the UI shows `|rate|` plus a direction indicator.

- `tick(wall_dt)`: if playing, `t_now += rate * wall_dt`; at `t_end` (forward) or `t_start` (reverse) pause, or wrap to the opposite end if `loop`.
- `seek(t)`: clamps to `[t_start, t_end]`, sets `t_now`, keeps `rate` and `playing`; notifies observers. O(1), no replay of intermediate time.
- `set_speed(x)` (`|x|` clamped to `[1, 1000]`, sign preserved), `set_direction(±1)` / `reverse()` (negates `rate`; `t_now` unchanged), `play()`, `pause()`, `toggle()`.
- `step(n_samples | seconds)`: seek relative to `t_now`, used by step buttons/keys.
- Observers: `subscribe(callback(t_now))`. Wall-time driven by the app timer using
  `time.monotonic()` deltas, so slow frames don't slow simulated time (frames drop instead).

Unit tests: advance, clamp, loop wrap (both directions), speed clamp, sign preserved on speed change,
reverse mid-play without `t_now` jump, seek while playing/reversed/paused, end-of-timeline pause — no display.

### 4.2 Cursor lookup

`CursorState` = `{t, r_km, v_kms, speed, altitude, distance, status, segment_id}` at `t_now`.
`status` distinguishes an exact OEM sample, a valid interpolated state inside a segment, and a
time gap/out-of-segment time. In a gap, do not bridge interpolation across the gap or fabricate
a state: keep the timeline cursor at the requested time, mark the status, and show unavailable
state readouts until it reaches valid data.

Series arrays are sample-based, so the cursor is found with `np.searchsorted` on `series.t_s`,
then linear interpolation for plotted scalars (cheap), restricted to the containing segment.
For the 3D marker and readouts use the
interpolators from `core/interpolator` (Lagrange/Hermite per OEM `INTERPOLATION`/degree) via
`InterpolatorFactory`, falling back to linear. Keeps N4 (state depends only on `t_now`).

Random seek and reverse require lookup to be **stateless and direction-independent**: every
lookup does a fresh `searchsorted` (O(log n)) and never assumes monotonically increasing
queries. The interpolators' sliding-window caches are only an optimization; the window is
re-selected whenever the query leaves it, in either direction, so a backward or far jump costs
one window rebuild. Tests assert `state(t)` is identical when reached forward, backward, or by seek.

### 4.3 Views

```python
class View(Protocol):
    name: str
    def build(self, series: OrbitSeries, time_unit: TimeUnit) -> Figure: ...
    def update(self, t_s: float) -> None: ...   # move cursor artists only
```

- Static data drawn once in `build` (reuse existing `plot_*` drawing code).
- `update` modifies artists: `Line2D.set_xdata` for vertical cursor (`axvline`), `set_data_3d`
  for the satellite marker, optional trailing tail slice.
- Plot each OEM segment separately; do not draw lines across gaps. Mark segment boundaries
  clearly, and update the cursor/readout style or status when `t_now` lies in a gap.
- **Blitting** (validated in step 27 on `FigureCanvasWxAgg`): after the first full draw, cache the background (`canvas.copy_from_bbox`) and
  redraw only cursor artists with `restore_region`/`draw_artist`/`blit`. Resize/`draw_event`
  invalidates the cache. This is what makes 1000x with 7 views feasible (N1).
- Large series are decimated for display (min/max per pixel bucket) when > ~50k points; the
  full data stays for lookup.
- Registry maps individual views (`trajectory-3d`, `state-components`, `speed-altitude`,
  `rtn`, `angular-velocity`, `direction-change`, `distance`) and view groups to factories.
  `overview` = trajectory + speed/altitude; `state` = state components; `motion` = RTN,
  angular velocity and direction change; `all` = every view. The same registry powers the
  toolbar and `--plots`; opening a group raises existing windows rather than duplicating them.

### 4.3.1 3D trajectory backends (Matplotlib/wx and VTK)

Only the 3D trajectory is backend-pluggable; every 2D time-series view stays Matplotlib.
The plot-oem state-vector diagnostics are split into two views:

- `trajectory-3d`: the 3D orbit, Earth and satellite marker (pluggable backend).
- `state-components`: X/Y/Z, VX/VY/VZ histories (Matplotlib).

The `state` group opens the state-components view. Keep `state-vectors` as a compatibility
alias that opens both trajectory and state-components views.

The state-components view uses a 3-by-2 Matplotlib layout: position X/Y/Z and velocity VX/VY/VZ,
with frame and unit labels, one shared elapsed-time axis, and synchronized cursor lines. Each 2D view
is a `FigureCanvasWxAgg` canvas in a wx frame. Clicks map through per-axes plot bounds to preserve
synchronized seeking. The PPM/PhotoImage raster path from the Tk implementation is removed in step 22.

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
| `auto` (default) | `vtk` if `import vtk` succeeds and a render window can be created, else `matplotlib` (one-line notice on stderr when falling back). |
| `vtk` | Use VTK; error with install hint (`pip install -e '.[vtk]'`) if unavailable. |
| `matplotlib` | Always Matplotlib. |

The choice is made once at startup and shown in the control window title/status line.
Both backends implement the same interface, so the toolbar, clock and `PlayerApp` never branch on backend.

**Matplotlib/wx backend.** The initial overview draws the static orbit path, start/end markers,
labeled axes and object/frame context in `build`; `update` moves the satellite marker from the shared
cursor state. The figure is hosted in a wx frame through `FigureCanvasWxAgg`, and the Matplotlib
navigation toolbar is hosted by wx. Redraws are requested with `draw_idle()`. Throttling this 3D
backend is covered by step 27. Earth rendering and trajectory tails remain planned enhancements.

**VTK backend (only if step 20 records `VTK-KEEP`).** Scene built in `build`:

- Orbit polyline: `vtkPoints` filled zero-copy from `series` position arrays via
  `vtk.util.numpy_support`, one `vtkPolyLine` cell, `vtkPolyDataMapper` → `vtkActor`.
- Earth: WGS84 ellipsoid (`vtkSphereSource` scaled by the flattening), semi-transparent, plus graticule lines.
  Inertial-frame view with a static Earth in v1; a rotating, textured Earth needs the ECI→ECEF rotation at
  `t_now` (via `core/frame_utils`) and is a follow-up.
- Satellite: small sphere actor (and optional axis/velocity arrow); `update(t_s)` only calls
  `actor.SetPosition(r)` from the cursor state, then `renderWindow.Render()`. The GPU draws it, so no
  blitting or decimation is needed and 1000x playback is cheap even for 100k-point orbits.
- Tail: a second polyline over the index range `[i(t - tail), i(t)]` (reversed side when playing in reverse); or the full path when `tail` is `None`.
- Camera/interaction: `vtkInteractorStyleTrackballCamera` (rotate/zoom/pan) with the camera left untouched by `update`, so you can orbit while it plays.

**Event loop integration (validated in step 20).** The app owns exactly one loop (the wx main loop).
VTK must not run its own loop. Two candidate approaches:

1. **Embedded:** host the VTK render window in a wx panel through VTK's wx integration, so the window
   follows wx sizing, focus, and close behavior. Use this only if step 20 confirms it works on each
   supported platform.
2. **Pumped separate window (fallback):** a top-level VTK window pumped from a `wx.Timer`. The timer
   calls `interactor.ProcessEvents()` and then `Render()` for each open VTK view, so rotate/zoom works
   and the window is redrawn in lockstep with the clock. Closing it is detected through the
   interactor's `ExitEvent` observer and unregisters the view, like a Matplotlib window.

The chosen approach and the `VTK-KEEP`/`VTK-DROP` outcome are recorded here after step 20.

**Testing.** The backend-neutral contract is tested on both backends: `build` + several `update` calls,
and marker position == cursor-state position (Matplotlib: artist data; VTK: `actor.GetPosition()`).
VTK tests are skipped via `pytest.importorskip("vtk")`.

### 4.4 Control window

The control window is the compact dashboard and remains useful independently of which plot
windows are open. Startup opens `overview` by default: the 3D orbit and combined speed/altitude
time-series view. `--plots` can replace that selection with individual views or named groups.
Users can open additional views at any time; the clock and readouts stay in the main window.

A `wx.Frame` with wx sizers and a status bar, containing:

```
[ ▶/⏸ ] [◀/▶] [speed ▼ 1 10 60 100 300 1000] ━━━●━━━━━━━━━━━  UTC …  elapsed …
Readout: r=(x,y,z) km   v=(vx,vy,vz) km/s   speed=… km/s   altitude=… km (WGS84)
Toolbar: [3D Orbit] [State] [Speed/Altitude] [RTN] [Angular] [Direction] [Distance]
Groups: [Overview] [State] [Motion diagnostics] [All]
Data: object … | frame … | center … | samples … | cursor: interpolated / sample / gap
Details ▸ (additional OEM metadata and diagnostics)
```

- Widgets: `wx.Button` for play/pause, step and direction; `wx.TextCtrl` for time entry; `wx.Slider`
  for the timeline and speed. Native sizing and keyboard focus come from wx.
- Timeline: a `wx.Slider` with an integer range mapped linearly to `[t_start, t_end]`. The
  resolution (proposed 10,000 steps) is fixed in implementation-plan step 15. Slider events call
  `clock.seek`; clock updates set the slider value under a suppression flag so they do not feed
  back into `seek`.
- Speed: log-scale `wx.Slider` (integer `v` in 0…300 mapped to `10^(v/100)`, i.e. 10^0…10^3) plus
  1x/10x/100x/1000x preset buttons, all bound to `clock.set_speed`.
- Direction: toggle button `◀ / ▶` (key `R`) bound to `clock.reverse`; label shows e.g. `−60x`.
- Time entry: `wx.TextCtrl` accepting `1h30m` (elapsed) or a UTC epoch; Enter (`wx.EVT_TEXT_ENTER`) or
  the Seek button → `clock.seek`; invalid input is flagged in the status bar without changing `t_now`.
- Click-to-seek: each time-series view connects `button_press_event` (left click inside axes, toolbar zoom/pan mode inactive) → `clock.seek(x * unit_divisor)`.
- Toolbar buttons open views/groups via `PlayerApp.open_view(name)` / `open_group(name)`; an
  already-open view is raised rather than duplicated. Closing a view removes it from the active
  set but does not affect the clock. Closing the control window destroys all.
- Current-state readouts come from the same `CursorState` as the plots, including explicit
  sampled/interpolated/gap status. In gaps, show state values as unavailable rather than carrying
  forward the last sample. Altitude is shown only when its frame/center assumptions are valid;
  units and reference frame are visible. OEM object/frame/center/time span/sample count remain
  available as data context, with less-used metadata in the collapsed details panel.
- Keys: `Space` play/pause, `R` reverse, `←/→` step (∓/± 1 sample), `Shift+←/→` ∓/± 1 min, `Home/End` jump to start/end.
  These are wx accelerators on the control frame and are inactive while the time-entry field has focus.

### 4.5 `PlayerApp` and the frame loop

One `wx.Timer` (`wx.EVT_TIMER`) at about `1000/fps` ms:

1. `dt = monotonic() - last`; `clock.tick(dt)`.
2. Update slider and readouts.
3. For each open view: `view.update(t_now)` then redraw. Blitting, if adopted, is step 27.

Only the wx main loop exists (no threads). Heavy precomputation (`compute_orbit_series`) happens once
before the window appears, with progress printed to stdout like `plot-oem`.

## 5. CLI flow (`__main__.py`)

1. Parse args (`PlayOemArgs`), parse duration/time-unit exactly as `plot-oem`.
2. Read and filter states, then compute the series.
3. Select the `WXAgg` Matplotlib backend, create the `wx.App` and `PlayerApp`, open the requested `--plots` (default `overview`),
   apply `--start/--speed/--reverse/--autoplay` (reverse without `--start` begins at `t_end`;
   otherwise playback starts at `t_start`),
   `wx.App.MainLoop()`.
   Trailing tails in trajectory views are drawn on the side behind the direction of motion.
4. SIGINT closes all windows. A Python signal handler may not run promptly inside the wx main loop, so
   the handler only forwards the request with `wx.CallAfter` to a close routine that closes the views
   and the control frame and ends the main loop. The mechanism is fixed in implementation-plan step 15.

## 6. Testing

- `clock.py`: pure unit tests (`tests/play_oem/test_clock.py`).
- Cursor lookup vs. interpolator on `tests/data/ISS_2026-05-20.OEM` and `JPSS-1.oem`.
- Data loading and series tests: compare behavior with `plot-oem` on representative OEM files.
- Views: with a non-interactive Matplotlib backend, `build` + several `update` calls without exceptions; cursor artist
  positions equal expected values.
- CLI parse and input-loading tests (`--duration`, `--time-unit`, speed bounds, `--start`, `--plots` validation).
- wx tests: tests that create a `wx.App` run under `xvfb-run` on Linux CI; pure-Python tests run without a display.
- Baseline: wx values for `tests/data/ISS_2026-05-20.OEM` must match the Tk-era baseline fixture recorded in step 15.
- Manual: GUI smoke tests on macOS, Linux, and Windows (step 23 checklist); 1000x with all views on a large OEM, check fps (step 27).

## 7. Implementation plan

The dependency-ordered, demo-first implementation sequence is maintained separately in
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md).

## 8. Risks

- Blitting with 3D axes is unreliable → the Matplotlib 3D backend updates the marker and redraws at a reduced rate (e.g. 10 fps) without blitting; VTK avoids this.
- VTK alongside wx: two GUI toolkits could compete for the event loop. Mitigated by a single wx main loop, with VTK either embedded or pumped from a `wx.Timer`; verify on macOS, Linux (X11/Wayland) and Windows in step 20.
- VTK wheels may lag new Python versions; hence optional extra and automatic Matplotlib fallback (only if `VTK-KEEP`).
- wxPython wheels may be unavailable for some Python versions or Linux distributions. Supported combinations are recorded in step 15; a missing wx install fails with a clear install error.
- `wx.Slider` is integer-only. The timeline and speed controls use explicit integer ranges with documented mappings (§4.4).
- SIGINT may not be handled promptly inside the wx main loop; the `wx.CallAfter` forwarding in §5 handles it.
- Multiple Matplotlib figures in one wx loop: use the `WXAgg` backend only and never mix backends.
- wx absent → report a clear GUI dependency error; core logic remains testable without a display.
