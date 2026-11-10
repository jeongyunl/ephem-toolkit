# `play-oem` — Concepts and Requirements

> Status: **implemented**. Configuration behavior is documented in the
> [configuration implementation report](./old/PLAY_OEM_CONFIG_REPORT.md) and the
> [end-user guide](../../tools/PLAY_OEM_CONFIG.md). Software design:
> [PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md). Time-range implementation:
> [PLAY_OEM_TIME_RANGE_IMPLEMENTATION_REPORT.md](./old/PLAY_OEM_TIME_RANGE_IMPLEMENTATION_REPORT.md).
> Earlier time-range design specifications and diagrams are archived under `old/`.

`play-oem` is the interactive, animated successor to [`plot-oem`](../../tools/PLOT_OEM.md). Where `plot-oem` renders
static figures of a whole OEM history, `play-oem` replays the orbit through time: a
main control window drives a shared simulation clock, and every open plot window shows
the state at that clock.

## Name

`play-oem` (package `ephem_toolkit.play_oem`). Chosen to sit beside `plot-oem`, `slice-oem`,
`diff-oem`, etc. `plot-oem` remains a separate command for static diagnostic plots; `play-oem`
is the interactive playback application.

## Concepts

| Concept | Meaning |
|---------|---------|
| **Timeline** | The slider domain is the union of valid UTC `START_TIME`/`STOP_TIME` metadata and observed state times. Playback coverage remains bounded by loaded states; during loading, the unread suffix is marked separately. All times are shown as UTC and as elapsed time from `t_start`. |
| **Playback clock** | A single shared `t_now` in the timeline. Only the clock advances; views only read it. |
| **Playback speed** | Ratio of simulated seconds to wall-clock seconds (`|rate|` 1x … 9000x); the sign indicates direction. |
| **Cursor state** | The OEM state at `t_now`, interpolated from the OEM samples (using the OEM's `INTERPOLATION` metadata when present). |
| **View** | A plot window that renders a series or trajectory and a cursor/marker at `t_now`. |
| **View group** | A named collection of related views opened together (Overview, State, Motion, Access Overview, Pass Study, All). |
| **Control window** | The Controls & Info pane: a render-rate control on Settings, current-state readouts on State, OEM context, and Ground Stations. Playback controls and navigation live in the shared timeline. Closing the app window quits the app. |

Two kinds of views:

- **Time-series views** (velocity magnitude, altitude, RTN deltas, …): the full series is
  drawn statically; a vertical cursor line moves with `t_now`. Optionally the visible x-window
  follows the cursor.
- **Trajectory views** (3D state vectors / orbit path): the full or trailing path is drawn;
  a marker for the satellite moves with `t_now`, with optional trailing tail.

The default experience is a compact **Overview** dashboard, not every plot at once: it opens
the 3D orbit and speed/altitude view. Users can open individual views or a larger group from
the toolbar. The dashboard keeps the current state and data context visible regardless of
which views are open.

## Requirements

### Functional

**F1. Control window**

1. **Random seek**: any instant of the OEM timeline can be reached in constant time,
   independent of the current position and of playback direction or speed.
   - Time slider: dragging updates the time marker immediately; while data is loading, plot
     updates are coalesced until dragging stops. Hovering over unread time explains that it is not
     loaded yet; seeking there retains the clock's existing loaded-coverage clamping behavior.
     Clicking the trough jumps to that point.
   - Direct entry: type an elapsed time (`1h30m`) or a UTC epoch into a time field.
   - Click-to-seek: clicking on a time-series plot seeks to that time.
   - Step buttons/keys: ±1 sample, ±1 minute, jump to start/end.
   - Seeking works while playing, paused, or reversed, and never changes speed or direction.
2. Play/Pause button (also `Space`). Playback starts paused at the first OEM state and pauses at either timeline boundary.
3. Direction-specific speed preset buttons control playback from `1x` up to `9000x`; repeated
   clicks on a selected preset increase its speed by decades as described below.
4. **Reverse playback**: a direction control (button, and `R` key) plays the timeline
   backward at the selected speed (`-1x` … `-9000x`). Reversing mid-play is seamless
   (no jump in `t_now`). Reaching `t_start` while reversed pauses.
   Cursor state and views are identical whether a time was reached forward, backward, or by seeking.
   The shared controller above the time slider provides `<<<` / `<<` / `<` reverse speeds, a
   dedicated 1x Reverse Play/Pause button, a separate 1x Forward Play/Pause button, and `>` / `>>`
   / `>>>` forward speeds for 10x, 100x, and 1000x. Each play button starts playback in its
   direction at 1x when paused, pauses playback in that direction, or switches a running
   playback to its direction at 1x. A speed button selects its direction and base speed; clicking
   it again at exactly that speed advances by one decade up to 9000x, while clicking it at a
   higher same-direction speed resets to its base speed.
5. **Dashboard readout**: current UTC epoch, elapsed time, signed speed/direction, position
   and velocity components, speed, and altitude when valid. Keep the default readout concise;
   expose less-used values in a details panel.
6. **Data context**: show object name, reference frame, center, timeline, sample count and
   whether the cursor is in a gap or outside a valid interpolation segment. Clearly distinguish
   sample values from interpolated values. Play-OEM currently accepts `TIME_SYSTEM = UTC` only;
   unsupported time systems are reported before their state rows are loaded.
7. **View selection**: the graph-panel selector opens individual views; workspace presets open
   `Access Overview` and `Pass Study`. The `--plots` groups also include `Overview` (default),
   `State`, `Motion`, and `All`. Opening an already open view raises it; closing a view does not
   affect the clock. `All` opens every registered view, including the 3D orbit, state and motion
   plots, Ground Track, and the Ground Station panels.
8. **Render rate**: an FPS slider in the Settings pane selects 1–30 frames per second (default
   30). Playback advances by whole selected frame periods. When rendering overruns, consume all
   elapsed frame periods in one clock update and redraw once, dropping intermediate frames.

**F2. Animated views**

1. All open views are synchronized to the single clock (never drift relative to each other).
2. Rendering targets a responsive UI at speeds up to 9000x: the selected render-rate cap is
   1–30 FPS and overdue frames are dropped, not queued. The playback clock catches up by advancing
   through all elapsed frame periods in one update. The measured macOS rate remains below the N1
   target; see the [performance report](./PLAY_OEM_PERFORMANCE_REPORT.md).
3. Seeking works while paused or playing.

**F3. CLI (very similar to `plot-oem`)**

```bash
play-oem [<input_oem>] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `<input_oem>` | Input CCSDS OEM path (same as `plot-oem`). |
| `--plots <list>` | Comma-separated view names or groups to open at launch (default: `overview`; groups: `overview`, `state`, `motion`, `access-overview`, `pass-study`, `all`; compatibility alias: `state-vectors`). |
| `--3d-backend {auto,vtk,matplotlib}` | Renderer for 3D views (default `auto`: VTK when its wx integration is available, otherwise Matplotlib). Explicit `vtk` reports an actionable error if unavailable. |
| `--config <path>` | Load user defaults from the specified TOML file instead of the default configuration location. |
| `-h`, `--help` | Help. |

The CLI accepts an optional OEM path plus view-selection options. The window opens before parsing
finishes; playback starts with the first validated state batch and the loaded timeline grows as
additional batches arrive. Loading status distinguishes partial coverage from EOF validation.
When present and valid, the slider scale uses the OEM metadata start and stop times; seeking remains
limited to samples already loaded. Saved playback and plot range handles appear at their saved
positions as soon as the first batch is installed, even if those playback bounds are not playable
yet.
Playback speed, direction, seeking, and frame rate are controlled in the GUI. Use `plot-oem`
for saved diagnostic plots; `play-oem` is the interactive playback command.

**F4. Data and computation reuse**

The loader streams raw OEM rows into the application-owned `OemDataStore`. The store lazily
computes requested range-limited series, Earth-fixed positions, Ground Track data, and station
access tiers, calculating only missing rows within the queried interval rather than whole cache
chunks. Necessary raw support samples and the station pass-boundary margin are the exceptions.
Views query a shared snapshot/range context rather than retaining duplicate full-history data.
Station-access queries may show partial coverage while loading; their coverage is complete only
after EOF validation. The time-axis unit follows the loaded OEM span and settles to the full-file
span when loading completes.

### Non-functional

- **N1 Performance target**: at 1000x with the seven core orbit/diagnostic views used in the original benchmark, target an interactive UI
  (at least 15 playback updates/s on a typical laptop with an OEM of at least 100k samples).
  The current macOS benchmark is below this target and was accepted as a deferred optimization;
  Ground Track and Ground Station views add workloads not covered by that benchmark.
- **N2 Portability**: macOS, Linux, and Windows are targets; Linux/Windows GUI installations and
  rendering remain unverified in the current repository environment.
- **N3a 3D backends**: 3D views have interchangeable Matplotlib/WxAgg and optional VTK backends.
  VTK uses OpenGL, but hardware acceleration depends on the platform and graphics context; it is
  not guaranteed. `auto` selects VTK only when its wx integration initializes successfully.
- **N3 Dependencies**: wxPython, Matplotlib, and pyproj are provided by the optional `playback`
  extra; VTK is a separate optional `vtk` extra. The base install does not require the GUI stack.
- **N4 Determinism**: the state at `t_now` depends only on `t_now`, not on how the clock got there.
- **N4a Data honesty**: indicate OEM segment boundaries and gaps; never imply continuous data or valid interpolation across a gap. Label reference frames, units, altitude reference and interpolated cursor values clearly.
- **N5 Quality**: follow [python_style_guide.md](../../development/python_style_guide.md); pure logic
  (clock, series, interpolation lookup) unit-testable without a display.
- **N6 Testability**: playback logic, data processing and tests run without a display. Running
  the interactive player requires its GUI toolkit and display environment.

### Out of scope

- Editing/modifying OEMs, multiple-OEM overlay (`plot-oem-diff` successor), and video export
  (possible follow-up: `--record movie.mp4`). Ground Track and Ground Station analysis are
  implemented features, not current scope exclusions.

## Migration

1. Implement `play-oem` as a separate interactive application alongside `plot-oem`.
2. Keep `plot-oem` as the existing command for static diagnostic figures; do not alias it to
   `play-oem`.
3. Share numerical/data-processing code only when behavior remains compatible with both tools.
4. Update [TODO.md](../../development/TODO.md) and README tool lists.

## Open questions

- Whether to also provide a `play-oem-diff` later.
