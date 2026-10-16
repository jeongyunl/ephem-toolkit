# `play-oem` — Design

Requirements: [PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md). Baseline code: `src/ephem_toolkit/plot_oem/`.

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
  app.py               # PlayerApp: owns clock, views, control window
  control_window.py    # slider, play/pause, speed, toolbar
  views/
    base.py            # View protocol
    trajectory3d/      # mpl_backend.py, vtk_backend.py (see 4.3.1)
    state_components.py speed_altitude.py rtn_deltas.py angular_velocity.py
    direction_change.py geocentric_distance.py
    registry.py        # view/group names -> factories
```

`pyproject.toml`: add `play-oem = "ephem_toolkit.play_oem:cli"` and an optional extra `vtk = ["vtk>=9.2"]`.

## 3. GUI toolkit decision

Options:

| Option | Pros | Cons |
|---|---|---|
| A. Matplotlib only (TkAgg/QtAgg), control window = a Matplotlib figure with `Slider`, `Button`, `RadioButtons` | no new deps; one event loop | clunky toolbar, widget look, slider/timer coupling |
| B. **Tkinter control window + Matplotlib figures** (`TkAgg`) | stdlib Tk, native-ish controls and toolbar, single Tk event loop shared by all figures; no new dependency | Tk must be available (usually bundled; not on some Linux distros); legacy Tk may have rendering limitations |
| C. Qt (PySide6) | best widgets | heavy new dependency |

**Decision: B**, with Tk-managed plot windows sharing one Tk root and event loop. Use Matplotlib
`TkAgg` where supported, with a compatible fallback for legacy Tk rendering limitations. Fall
back with a clear error if Tk is missing. The `View`/`Clock` layers are toolkit-agnostic, so C
remains possible.

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
- **Blitting**: after the first full draw, cache the background (`canvas.copy_from_bbox`) and
  redraw only cursor artists with `restore_region`/`draw_artist`/`blit`. Resize/`draw_event`
  invalidates the cache. This is what makes 1000x with 7 views feasible (N1).
- Large series are decimated for display (min/max per pixel bucket) when > ~50k points; the
  full data stays for lookup.
- Registry maps individual views (`trajectory-3d`, `state-components`, `speed-altitude`,
  `rtn`, `angular-velocity`, `direction-change`, `distance`) and view groups to factories.
  `overview` = trajectory + speed/altitude; `state` = state components; `motion` = RTN,
  angular velocity and direction change; `all` = every view. The same registry powers the
  toolbar and `--plots`; opening a group raises existing windows rather than duplicating them.

### 4.3.1 3D trajectory backends (Matplotlib/Tk and VTK)

Only the 3D trajectory is backend-pluggable; every 2D time-series view stays Matplotlib.
The plot-oem state-vector diagnostics are split into two views:

- `trajectory-3d`: the 3D orbit, Earth and satellite marker (pluggable backend).
- `state-components`: X/Y/Z, VX/VY/VZ histories (Matplotlib).

The `state` group opens the state-components view. Keep `state-vectors` as a compatibility
alias that opens both trajectory and state-components views.

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

**Matplotlib/Tk backend.** The initial overview draws the static orbit path, start/end markers,
labeled axes and object/frame context in `build`; `update` moves the satellite marker from the shared
cursor state. For Tk 8.6 and newer, the figure uses TkAgg. Older Tk versions use Matplotlib Agg to
render a PPM image, which is loaded by classic Tk; the marker is drawn into a copy of that image as
the cursor moves. This avoids the blank TkAgg/Canvas rendering on the repository's legacy macOS
Tk 8.5.9 runtime without changing the graphical plot. TkAgg redraws are requested with
`draw_idle()`; the legacy raster path updates only the cursor pixels. Earth rendering and trajectory
tails remain planned enhancements to this backend.

**VTK backend.** Scene built in `build`:

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

**Event loop integration.** The app owns exactly one loop (Tk). VTK is *pumped*, not run:

1. `vtkRenderWindowInteractor.Initialize()` is called, but never `Start()`.
2. The frame timer in `PlayerApp` calls `interactor.ProcessEvents()` and then `Render()` for each open VTK view, so mouse
   rotate/zoom works and the window is redrawn in lockstep with the clock.
3. The VTK window is its own top-level native window (not embedded in Tk). This avoids the unreliable
   `vtkTkRenderWindowInteractor` embedding on macOS/Cocoa; closing it is detected through the interactor's
   `ExitEvent`/`WindowIsCurrent` observer and unregisters the view, exactly like closing a Matplotlib window.

Embedding in a Tk frame (`vtkTkRenderWindowInteractor`) remains a possible opt-in on Linux/Windows but is not planned for v1.

**Testing.** The backend-neutral contract is tested on both backends: `build` + several `update` calls,
and marker position == cursor-state position (Matplotlib: artist data; VTK: `actor.GetPosition()`).
VTK tests are skipped via `pytest.importorskip("vtk")`.

### 4.4 Control window

The control window is the compact dashboard and remains useful independently of which plot
windows are open. Startup opens `overview` by default: the 3D orbit and combined speed/altitude
time-series view. `--plots` can replace that selection with individual views or named groups.
Users can open additional views at any time; the clock and readouts stay in the main window.

Tk `Toplevel`/root with:

```
[ ▶/⏸ ] [◀/▶] [speed ▼ 1 10 60 100 300 1000] ━━━●━━━━━━━━━━━  UTC …  elapsed …
Readout: r=(x,y,z) km   v=(vx,vy,vz) km/s   speed=… km/s   altitude=… km (WGS84)
Toolbar: [3D Orbit] [State] [Speed/Altitude] [RTN] [Angular] [Direction] [Distance]
Groups: [Overview] [State] [Motion diagnostics] [All]
Data: object … | frame … | center … | samples … | cursor: interpolated / sample / gap
Details ▸ (additional OEM metadata and diagnostics)
```

- Legacy Tk rendering must remain usable through a compatible fallback; the concrete version
  check and rendering strategy are specified in implementation-plan steps 6–8.
- Timeline seek control → `clock.seek`; clock updates move the control without feeding back
  into `seek`.
- Speed: log scale slider (10^0…10^3) plus 1x/10x/100x/1000x preset buttons, all bound to
  `clock.set_speed`.
- Direction: toggle button `◀ / ▶` (key `R`) bound to `clock.reverse`; label shows e.g. `−60x`.
- Time entry: text field accepting `1h30m` (elapsed) or a UTC epoch; Enter → `clock.seek`; invalid input is flagged without changing `t_now`.
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

### 4.5 `PlayerApp` and the frame loop

One Tk `after(1000/fps)` timer:

1. `dt = monotonic() - last`; `clock.tick(dt)`.
2. Update slider and readouts.
3. For each open view: `view.update(t_now)` then blit.

Only the Tk loop exists (no threads). Heavy precomputation (`compute_orbit_series`) happens once
before the window appears, with progress printed to stdout like `plot-oem`.

## 5. CLI flow (`__main__.py`)

1. Parse args (`PlayOemArgs`), parse duration/time-unit exactly as `plot-oem`.
2. Read and filter states, then compute the series.
3. Select `TkAgg`, create `PlayerApp`, open the requested `--plots` (default `overview`),
   apply `--start/--speed/--reverse/--autoplay` (reverse without `--start` begins at `t_end`;
   otherwise playback starts at `t_start`),
   `mainloop()`.
   Trailing tails in trajectory views are drawn on the side behind the direction of motion.
4. SIGINT closes all windows (reuse `plot-oem`'s handler, adapted to Tk `root.quit`).

## 6. Testing

- `clock.py`: pure unit tests (`tests/play_oem/test_clock.py`).
- Cursor lookup vs. interpolator on `tests/data/ISS_2026-05-20.OEM` and `JPSS-1.oem`.
- Data loading and series tests: compare behavior with `plot-oem` on representative OEM files.
- Views: with a non-interactive Matplotlib backend, `build` + several `update` calls without exceptions; cursor artist
  positions equal expected values.
- CLI parse and input-loading tests (`--duration`, `--time-unit`, speed bounds, `--start`, `--plots` validation).
- Manual: GUI smoke test on macOS; 1000x with all views on a large OEM, check fps.

## 7. Implementation plan

The dependency-ordered, demo-first implementation sequence is maintained separately in
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md).

## 8. Risks

- Blitting with 3D axes is unreliable → the Matplotlib 3D backend updates the marker and redraws at a reduced rate (e.g. 10 fps) without blitting; VTK avoids this.
- VTK alongside Tk: two GUI toolkits in one process. Mitigated by pumping VTK events from the Tk timer instead of running a second loop; verify on macOS, Linux (X11/Wayland) and Windows.
- VTK wheels may lag new Python versions; hence optional extra and automatic Matplotlib fallback.
- Multiple Matplotlib figures in one Tk loop on macOS: use `plt.figure` with TkAgg only, never mix backends.
- Tk absent on some Linux Pythons → report a clear GUI dependency error; core logic remains testable without a display.
