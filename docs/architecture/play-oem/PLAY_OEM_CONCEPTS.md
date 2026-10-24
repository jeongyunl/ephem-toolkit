# `play-oem` — Concepts and Requirements

> Status: **implemented**. Configuration behavior is documented in the
> [configuration implementation report](./old/PLAY_OEM_CONFIG_REPORT.md) and the
> [end-user guide](../../tools/PLAY_OEM_CONFIG.md). Software design:
> [PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md). Time-range implementation:
> [PLAY_OEM_TIME_RANGE_IMPLEMENTATION_REPORT.md](./PLAY_OEM_TIME_RANGE_IMPLEMENTATION_REPORT.md).
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
| **Timeline** | The full time span `[t_start, t_end]` from every state in the OEM. All times are shown as UTC and as elapsed time from `t_start`. |
| **Playback clock** | A single shared `t_now` in the timeline. Only the clock advances; views only read it. |
| **Playback speed** | Ratio of simulated seconds to wall-clock seconds (`|rate|` 1x … 9000x); the sign indicates direction. |
| **Cursor state** | The OEM state at `t_now`, interpolated from the OEM samples (using the OEM's `INTERPOLATION` metadata when present). |
| **View** | A plot window that renders a series or trajectory and a cursor/marker at `t_now`. |
| **View group** | A named collection of related views opened together (Overview, State, Motion diagnostics, All). |
| **Control window** | The Controls & Info pane: a render-rate control on Playback, current-state readouts on State, and OEM context. Playback controls and navigation live in the shared timeline. Closing the app window quits the app. |

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
   - Time slider: dragging updates all views live; clicking the trough jumps to that point.
   - Direct entry: type an elapsed time (`1h30m`) or a UTC epoch into a time field.
   - Click-to-seek: clicking on a time-series plot seeks to that time.
   - Step buttons/keys: ±1 sample, ±1 minute, jump to start/end.
   - Seeking works while playing, paused, or reversed, and never changes speed or direction.
2. Play/Pause button (also `Space`). Playback starts paused at the first OEM state and pauses at either timeline boundary.
3. Speed control from `1x` up to `9000x` (log-scale slider and preset buttons
   1, 10, 60, 100, 300, 1000).
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
   sample values from interpolated values.
7. **View toolbar**: buttons open individual views and groups: `Overview` (default), `State`,
   `Motion diagnostics`, and `All`. Opening an already open view raises it; closing a view does
   not affect the clock. `All` includes the 3D orbit, state components, speed/altitude, RTN
   deltas, angular velocity, direction change, and geocentric distance.
8. **Render rate**: an FPS slider in the Settings pane selects 1–30 frames per second (default
   30). Playback advances by whole selected frame periods. When rendering overruns, consume all
   elapsed frame periods in one clock update and redraw once, dropping intermediate frames.

**F2. Animated views**

1. All open views are synchronized to the single clock (never drift relative to each other).
2. Rendering must keep the UI responsive at speeds up to 9000x: the frame rate is capped at
   30 render-rate FPS and overdue frames are dropped, not queued. The playback clock catches up by advancing
   through all elapsed frame periods in one update.
3. Seeking works while paused or playing.

**F3. CLI (very similar to `plot-oem`)**

```bash
play-oem [<input_oem>] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `<input_oem>` | Input CCSDS OEM path (same as `plot-oem`). |
| `--plots <list>` | Comma-separated view names or groups to open at launch (default: `overview`; groups: `overview`, `state`, `motion`, `all`). |
| `--3d-backend {auto,vtk,matplotlib}` | Renderer for 3D views (default `auto`: VTK if available, else Matplotlib). Explicit `vtk` fails with an install hint if VTK is missing. |
| `-h`, `--help` | Help. |

The CLI accepts an optional OEM path plus view-selection options. It loads the entire OEM and
chooses minutes for timelines shorter than an hour, otherwise hours. Playback speed, direction,
seeking, and frame rate are controlled in the GUI. Use `plot-oem`
for saved diagnostic plots; `play-oem` is the interactive playback command.

**F4. Data and computation reuse**

Data loading, series computation (RTN deltas, angular rates, distance,
WGS84 altitude), and time-unit conversion utilities are reused from `plot-oem` (copied, then
modified only where needed—see design). `play-oem` selects minutes or hours from the OEM span.

### Non-functional

- **N1 Performance target**: at 1000x with all 7 views open, target an interactive UI
  (at least 15 playback updates/s on a typical laptop with an OEM of at least 100k samples).
  If a platform/backend benchmark falls below target, record the measured environment and
  workload and obtain explicit acceptance before deferring further optimization. The current
  macOS baseline is documented in the design; the user accepted it for now, with N1 retained
  as a future optimization target.
- **N2 Portability**: macOS, Linux, Windows; Python version per `pyproject.toml`.
- **N3a 3D backends**: 3D views have two interchangeable implementations, Matplotlib/WxAgg (always available) and VTK
  (optional extra `vtk`, GPU-accelerated). Behavior and controls are identical; VTK is preferred when installed
  and selectable via `--3d-backend`.
- **N3 Dependencies**: prefer the existing optional `plotting` extra (Matplotlib). The GUI toolkit
  decision is in the design; any new dependency is added as an optional extra.
- **N4 Determinism**: the state at `t_now` depends only on `t_now`, not on how the clock got there.
- **N4a Data honesty**: indicate OEM segment boundaries and gaps; never imply continuous data or valid interpolation across a gap. Label reference frames, units, altitude reference and interpolated cursor values clearly.
- **N5 Quality**: follow [python_style_guide.md](../../development/python_style_guide.md); pure logic
  (clock, series, interpolation lookup) unit-testable without a display.
- **N6 Testability**: playback logic, data processing and tests run without a display. Running
  the interactive player requires its GUI toolkit and display environment.

### Out of scope (initial version)

- Editing/modifying OEMs, multiple-OEM overlay (`plot-oem-diff` successor), ground tracks/maps,
  video export (possible follow-up: `--record movie.mp4`).

## Migration

1. Implement `play-oem` as a separate interactive application alongside `plot-oem`.
2. Keep `plot-oem` as the existing command for static diagnostic figures; do not alias it to
   `play-oem`.
3. Share numerical/data-processing code only when behavior remains compatible with both tools.
4. Update [TODO.md](../../development/TODO.md) and README tool lists.

## Open questions

- Whether to also provide a `play-oem-diff` later.
