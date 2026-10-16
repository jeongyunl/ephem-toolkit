# `play-oem` — Concepts and Requirements

> Status: **planned** (not yet implemented). Design: [PLAY_OEM_DESIGN.md](./PLAY_OEM_DESIGN.md).

`play-oem` is the interactive, animated successor to [`plot-oem`](../tools/PLOT_OEM.md). Where `plot-oem` renders
static figures of a whole OEM history, `play-oem` replays the orbit through time: a
main control window drives a shared simulation clock, and every open plot window shows
the state at that clock.

## Name

`play-oem` (package `ephem_toolkit.play_oem`). Chosen to sit beside `plot-oem`, `slice-oem`,
`diff-oem`, etc. `plot-oem` is kept unchanged until `play-oem` reaches parity, after which
it may become an alias (see [Migration](#migration)).

## Concepts

| Concept | Meaning |
|---------|---------|
| **Timeline** | The OEM time span `[t_start, t_end]` (after `--duration` filtering). All times are shown as UTC and as elapsed time from `t_start`. |
| **Playback clock** | A single shared `t_now` in the timeline. Only the clock advances; views only read it. |
| **Playback speed** | Ratio of simulated seconds to wall-clock seconds (`|rate|` 1x … 1000x); the sign indicates direction. |
| **Cursor state** | The OEM state at `t_now`, interpolated from the OEM samples (using the OEM's `INTERPOLATION` metadata when present). |
| **View** | A plot window that renders a series or trajectory and a cursor/marker at `t_now`. |
| **View group** | A named collection of related views opened together (Overview, State, Motion diagnostics, All). |
| **Control window** | The main dashboard: time slider, play/pause, speed and direction controls, current-state readout, data context and view toolbar. Closing it quits the app. |

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
2. Play/Pause button (also `Space`). At either end of the timeline playback pauses
   (or wraps with `--loop`).
3. Speed control from `1x` up to `1000x` (log-scale slider and/or preset buttons
   1, 10, 60, 100, 300, 1000).
4. **Reverse playback**: a direction control (button, and `R` key) plays the timeline
   backward at the selected speed (`-1x` … `-1000x`). Reversing mid-play is seamless
   (no jump in `t_now`). Reaching `t_start` while reversed pauses (or wraps to `t_end` with `--loop`).
   Cursor state and views are identical whether a time was reached forward, backward, or by seeking.
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

**F2. Animated views**

1. All open views are synchronized to the single clock (never drift relative to each other).
2. Rendering must keep the UI responsive at 1000x: frame rate is capped (default 30 fps)
   and frames are dropped, not queued.
3. Seeking works while paused or playing.

**F3. CLI (very similar to `plot-oem`)**

```bash
play-oem <input_oem> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `<input_oem>` | Input CCSDS OEM path (same as `plot-oem`). |
| `-d`, `--duration <duration>` | Limit timeline to this duration from first state (same parser as `plot-oem`). |
| `--time-unit {m,minute,minutes,h,hour,hours}` | Elapsed-time axis unit; default `hours` (same as `plot-oem`). |
| `-o`, `--output <output_plot>` | Non-interactive: save static figures exactly like `plot-oem` (at `--at` time if given) and exit. Kept for compatibility. |
| `--speed <x>` | Initial speed multiplier (default `1`, range `-1000`…`1000`; negative plays in reverse, `0` is invalid). |
| `--reverse` | Start playing in reverse (equivalent to negating `--speed`). With no `--start`, begins at the end of the timeline. |
| `--start <t>` | Initial time: elapsed duration (`30m`) or UTC epoch (default: start; end when starting in reverse). |
| `--plots <list>` | Comma-separated view names or groups to open at launch (default: `overview`; groups: `overview`, `state`, `motion`, `all`). |
| `--autoplay` | Begin playing immediately. |
| `--loop` | Restart at the end. |
| `--fps <n>` | Max render rate (default 30). |
| `--3d-backend {auto,vtk,matplotlib}` | Renderer for 3D views (default `auto`: VTK if available, else Matplotlib). Explicit `vtk` fails with an install hint if VTK is missing. |
| `-h`, `--help` | Help. |

Differences from `plot-oem` are limited to the added playback options.

**F4. Data and computation reuse**

Data loading, duration filtering, series computation (RTN deltas, angular rates, distance,
WGS84 altitude), time units and output naming are reused from `plot-oem` (copied, then
modified only where needed—see design).

### Non-functional

- **N1 Performance**: at 1000x with all 7 views open, UI stays interactive (≥ 15 fps on a typical laptop, OEM of ≥ 100k samples).
- **N2 Portability**: macOS, Linux, Windows; Python version per `pyproject.toml`.
- **N3a 3D backends**: 3D views have two interchangeable implementations, Matplotlib/Tk (always available) and VTK
  (optional extra `vtk`, GPU-accelerated). Behavior and controls are identical; VTK is preferred when installed
  and selectable via `--3d-backend`.
- **N3 Dependencies**: prefer the existing optional `plotting` extra (Matplotlib). The GUI toolkit
  decision is in the design; any new dependency is added as an optional extra.
- **N4 Determinism**: the state at `t_now` depends only on `t_now`, not on how the clock got there.
- **N4a Data honesty**: indicate OEM segment boundaries and gaps; never imply continuous data or valid interpolation across a gap. Label reference frames, units, altitude reference and interpolated cursor values clearly.
- **N5 Quality**: follow [python_style_guide.md](../development/python_style_guide.md); pure logic
  (clock, series, interpolation lookup) unit-testable without a display.
- **N6 Headless**: `-o` mode and tests run without a display (Agg backend).

### Out of scope (initial version)

- Editing/modifying OEMs, multiple-OEM overlay (`plot-oem-diff` successor), ground tracks/maps,
  video export (possible follow-up: `--record movie.mp4`).

## Migration

1. Implement `play-oem` alongside `plot-oem`.
2. When static output parity is verified, make `plot-oem` a thin alias of `play-oem -o`.
3. Update [TODO.md](../development/TODO.md) and README tool lists.

## Open questions

- GUI toolkit (see design §3): Matplotlib widgets in-window vs. Tk/Qt control window.
- Whether to also provide a `play-oem-diff` later.
