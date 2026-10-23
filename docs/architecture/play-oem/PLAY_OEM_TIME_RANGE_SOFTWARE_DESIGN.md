# `play-oem` — Shared Time Range Software Design

> Status: **proposed**. Implementation and validation are pending.

This document defines independent playback bounds and shared plot filtering for `play-oem`.
It extends [PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md).
User interaction and five design alternatives are specified in
[PLAY_OEM_TIME_RANGE_GUI_DESIGN.md](./PLAY_OEM_TIME_RANGE_GUI_DESIGN.md).
Implementation sequencing and acceptance evidence belong in
[PLAY_OEM_TIME_RANGE_IMPLEMENTATION_PLAN.md](./PLAY_OEM_TIME_RANGE_IMPLEMENTATION_PLAN.md).
Where the existing architecture describes full-history plotting, this proposal adds optional
filtering; it does not claim that filtering already exists.

## 1. Purpose and user-facing contract

Let the user select one interval for every graph in Main Analysis and Comparison, including
time-series histories, the 3D orbit, and the ground track. Each plot endpoint independently
selects a fixed UTC timestamp or an offset from the shared playback time. Mixing endpoint
types defines one interval, not two disjoint intervals.

- Maintain `effective plot range ⊆ OEM coverage` and `playback range ⊆ OEM coverage`.
  Neither range must contain the other; they may overlap or be disjoint.
- Define playback bounds independently using fixed UTC endpoints, defaulting to OEM coverage.
  Plot filtering never changes playback bounds or seeks the clock.
- Default plot filtering to **All OEM data**, displaying data throughout OEM coverage.
- Include only samples inside the effective plot range, inclusively. Playback time may be
  outside that range; past-only and future-only windows are valid.
- Pause playback when either range is edited, apply valid edits live, and leave playback paused.
  Only playback-bound edits may clamp the current time.
- Follow effective plot bounds on time-series X axes while keeping full-data Y limits stable.
- Retain both settings only for the current dataset session. New and duplicated graphs inherit
  them; successful OEM replacement and application restart reset both.

This proposal changes neither `plot-oem` nor the CLI. It adds no dependencies, per-graph range
overrides, saved-state keys, disjoint interval overlays, or relative playback bounds.

## 2. OEM coverage, playback range, and plot range

All model timestamps are finite absolute TT seconds since J2000, matching the existing clock
and cursor. UTC input/output is converted through `core.time_utils`. Duration offsets are
finite seconds relative to the playback timestamp, not wall-clock time or OEM start.

| Symbol | Meaning |
|---|---|
| `D = [d0, d1]` | OEM coverage: first through last loaded sample epochs |
| `B = [b0, b1]` | Independent allowed playback range, with `d0 <= b0 <= b1 <= d1` |
| `t` | Current playback time, always in `B` |
| `S(t)` | Requested plot start: fixed epoch `a`, or `t + u` for any signed offset `u` |
| `E(t)` | Requested plot end: fixed epoch `b`, or `t + v` for any signed offset `v` |
| `Q(t)` | Requested plot interval; empty when `S(t) > E(t)` |
| `R(t)` | Effective plot range: `Q(t) ∩ D`, possibly empty |

Coverage is the loaded sample envelope, not a promise of continuous data. Existing segment
validity and interpolation gaps remain authoritative. Do not substitute metadata coverage or
usable-time fields for loaded sample bounds.

```text
B is selected independently of the plot rule and must be contained in D.
t = clamp(requested playback time, b0, b1)

When plot filtering is enabled:
    left  = max(d0, S(t))
    right = min(d1, E(t))
    R(t)  = [left, right] if left <= right, otherwise empty

When plot filtering is disabled (All OEM data):
    R(t) = D

Always: R(t) ⊆ D and B ⊆ D; no containment relationship is required between R(t) and B.
```

| Plot endpoint types | Effective plot range | Playback range |
|---|---|---|
| Fixed `a` → fixed `b` | `[a,b] ∩ D` | Unchanged `B` |
| Offset `u` → offset `v` | `[t+u,t+v] ∩ D` | Unchanged `B` |
| Fixed `a` → offset `v` | `[a,t+v] ∩ D`, or empty | Unchanged `B` |
| Offset `u` → fixed `b` | `[t+u,b] ∩ D`, or empty | Unchanged `B` |

Example: OEM coverage is `2026-10-23 08:00Z` through `20:00Z`; playback bounds are
`10:00Z` through `14:00Z`; current time is `12:00Z`. Offsets `-1h` and `+3h` request
`11:00Z` through `15:00Z`, and the effective plot range remains `11:00Z` through
`15:00Z`, including one hour after playback end. The `+3h` rule is retained. Plotting `15:00Z` through `17:00Z` is
also valid: it is disjoint from playback bounds but inside OEM coverage. A fixed plot
interval `11:00Z` through `13:00Z` does not prevent playback at `10:00Z` or `14:00Z`.

Offset signs are unrestricted: `+1h → +3h` and `-3h → -1h` are valid. Reject reversed
fixed/fixed endpoints and reversed offset/offset endpoints because they are always reversed.
Mixed endpoints may cross as playback advances; accept those rules and resolve to an empty
range while crossed. A requested interval wholly outside `D` is also a valid empty result.
An interval outside `B` but inside `D` is rendered normally, not treated as empty.
Neither state changes the playback clock or its bounds.

## 3. Proposed model and interfaces

Add `play_oem/time_range.py`, independent of wxPython, Matplotlib, VTK, and frame conversion.
Use immutable dataclasses:

| Type | Fields and contract |
|---|---|
| `PlaybackTimeRange` | `start_s: float`, `end_s: float`; finite, ordered, contained in OEM coverage |
| `TimeRangeEndpoint` | `mode: Literal["fixed", "offset"]`, `value_s: float`; epoch or signed duration |
| `PlotTimeRange` | `enabled: bool`, `start: TimeRangeEndpoint`, `end: TimeRangeEndpoint` |
| `ResolvedTimeRange` | `start_s: float`, `end_s: float`; inclusive, ordered effective bounds |

Provide pure operations `validate_playback_range(bounds, coverage)`,
`validate_plot_range(rule)`, and `resolve_plot_range(rule, coverage, t_s)`.
The resolver returns `ResolvedTimeRange | None`, with `None` meaning an empty intersection,
not disabled filtering. Disabled filtering returns OEM coverage. The resolver requires
a validated rule, finite ordered coverage, and `t_s` inside that coverage; invalid inputs
raise `ValueError`.
Map each endpoint’s Fixed time checkbox to its existing model mode: checked is `fixed`,
unchecked is `offset`. Toggling converts the value while preserving its requested instant
at the paused playback time. Reject an invalid conversion atomically and restore the prior
checkbox state. Keep parsing and formatted errors at the application/editor boundary. Do not derive playback
bounds from plot endpoints.

Extend `PlaybackClock` with read-only `playback_start`, `playback_end`, and
`set_playback_bounds(start_s, end_s)`. Keep `t_start`/`t_end` as immutable OEM limits so
elapsed-time origins, dataset labels, slider mapping, and sample timestamps remain stable.
Initial playback bounds equal coverage. A playback-bound update clamps `t_now`, clears
addition compensation, and notifies once with the final state, even if time did not move.
The setter preserves playing state; the editor pauses explicitly before calling it. Plot
edits never call this setter or `seek`; dispatch their range-only refresh explicitly.

All clock movement, including tick, seek, and sample/second stepping, uses `B`. Boundary
arrival pauses as today; existing optional loop behavior wraps inside `B`. Singleton playback
bounds cannot advance and pause on play/tick. A singleton plot range imposes no playback
limit or boundary pause after the user resumes from editing.
No new GUI loop control is introduced.

Extend the shared view interface:

```python
def set_time_range(
    self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
) -> None:
    """Select display data; None clears plots and uses OEM coverage for empty-state axes."""
```

Retain `build`, `update(t_s)`, and `close`. The empty graph provides a no-op setter. Retain
full source arrays for cursor lookup and derived calculations; filtering changes display
artists only. Views use OEM coverage for empty-state axis fallback, not extra samples.

## 4. Controller, navigation, and lifecycle

`PlayerApp` separately owns playback bounds and the applied plot rule. Initialize playback
bounds to OEM coverage and the plot rule disabled with fixed endpoints at those bounds.
The editor owns draft text and errors; focused actions belong in `app/time_range_actions.py`.
On first plot enable, use fixed endpoints at OEM coverage limits. On later
disable/re-enable cycles, retain the last applied plot endpoints instead.

For a plot edit:

1. Pause on the first editing interaction and reset elapsed timer bookkeeping.
2. Parse and validate the candidate without changing applied state. Empty resolved results
   are valid; malformed values and always-reversed same-mode endpoints are invalid.
3. Install the valid plot rule without changing playback bounds or `t_now`.
4. Explicitly dispatch one refresh at the unchanged clock time: resolve once, set every view's
   plot range/OEM coverage, update cursor visibility, and schedule redraws.
5. Synchronize effective labels, handles, and status without emitting recursive events.

For a playback-bound edit, pause, validate fixed bounds against `D`, then install them through
`set_playback_bounds`. Its notification resolves the existing plot rule against `D` and
the final clamped time.
Retain requested plot endpoint values, including offsets. Changing `B` leaves a fixed plot
range unchanged. A moving or mixed plot range changes only if the playback edit clamps `t`,
not because playback limits clip it. Restoring **Full OEM** changes only `B`.
**All OEM data** disables only plot filtering, sets `R = D`, and retains the last plot rule
for re-enabling.

Replace per-view clock subscriptions with one controller-owned dispatch. It resolves `R(t)`
once, supplies `R(t)` and `D` to all live views, then updates cursor/marker state and schedules
redraws. Adapt `_OpenView` cleanup so there is only one update path. On opening a panel,
call `build`, apply current bounds, and update overlays before its first visible draw.

Implement `TimeRangeSlider(wx.Slider)` in `workspace/time_range_slider.py`, preserving the
standard current-time thumb and integer slider API used by timeline synchronization. Add
four custom draggable handles in reserved upper space, all at the same vertical center.
Playback start/end use solid rounded grips; plot start/end use outlined diamonds. No text
is drawn on or beside grips; tooltips on hover/focus supply identity, values, and plot mode.
Map all five targets to the same full-OEM time domain. Keep model epochs at full precision;
pixel/integer conversion applies only at the widget boundary. Align custom grip coordinates
with the actual native track endpoints/thumb travel, not the outer control rectangle.

Playback-grip drags emit playback-bound edits; plot-grip drags emit plot edits; the standard
thumb/rail emits seeks. Capture and route each gesture to only one operation. Preserve
native seek events and API compatibility, preventing range drags from also propagating as
native seeks. Synchronize both input rows and handles without recursive edit events.
Fan colliding grips out horizontally while keeping identical heights, with leader lines
to true time positions; preserve drag offset to avoid a jump. Keep five independent keyboard
and accessible targets. Validate native painting, track alignment, DPI, resizing, and capture
behavior on supported wx backends before considering the widget complete.

All seek/step routes clamp to `B`, never to `R`. This includes fraction seeks, typed times,
plot clicks, sample/second stepping, and start/end buttons. Keep dataset-relative parsing and
full-coverage slider mapping. A valid timestamp outside `B` clamps with a status message;
malformed input reports a parsing error. Start/end target `B`; sample stepping across a
boundary lands on it even between samples. Playback at times outside `R` continues normally.

Edits preserve rate and direction. New/duplicated views inherit both settings. Successful
OEM replacement resets both before rebuilding panels; failed opens retain both. Close and
replace release range caches/artists; application shutdown removes dispatch and queued work.
Neither setting is persisted across application restarts.

## 5. Data selection and rendering

### 5.1 Time-series plots

Keep source arrays and derived quantities at full resolution. Filter each plotted series by
its own sample timestamps, then preserve contiguous valid segment runs and apply display
decimation to those runs. Do not filter only the previously decimated full-history curve:
that could omit extrema or all samples in a narrow range.

Use the existing elapsed-time origin and selected unit to convert effective absolute bounds
to axis coordinates. Ordinary series use `OrbitSeries.elapsed_time`; RTN deltas use
`rtn_elapsed_time` and `rtn_segment_ids`, not the ordinary N-sample timestamps. Derived values
retain their existing timestamp assignment and full-history computation; do not recompute
derivatives or RTN deltas at a newly selected boundary. Invalid segment IDs remain excluded.

For a nonempty effective range, set X limits without ordinary autoscale margins.
For an empty effective range, clear history artists, show OEM coverage on X, and label
the empty state; axis fallback does not admit any samples. Capture full-data
Y limits at build time and preserve them during range updates. User vertical zoom remains
local; Home restores full-data Y limits and the current effective X range. While filtering
is enabled, prevent toolbar X pan/zoom or stale navigation history from overriding the shared
range; do not disable ordinary navigation when filtering is off.

Retain source-index slices and existing line artists where practical. Use binary searches on
ordered timestamps, selecting both endpoints inclusively. A single eligible sample uses a
visible point marker so it is not lost as a zero-length line. Never include adjacent
out-of-range samples to extend a line to the range edge, and never interpolate new history
samples merely to fill that edge.

### 5.2 3D trajectories and ground track

Apply the same timestamp selection before path decimation in both Matplotlib and VTK 3D
backends. Keep separate contiguous OEM runs; preserve topology rather than connecting removed
samples. Intersect any existing direction-aware tail selection with the effective range.
An interpolated tail endpoint at the current cursor is allowed only when that timestamp is
inside the effective plot range and the existing cursor rules permit interpolation.
Keep Earth geometry, camera orientation, and spatial bounds unchanged during range updates.

Filter the ground track by its source timestamps before map-seam splitting and display
decimation. Preserve both OEM boundaries and crossings of the active map seam. Reuse cached
Earth-fixed coordinates; a time-range change must not repeat full-file frame conversion.
Keep projection, center longitude, background, map extent, and local navigation intact.

Current plot markers, time-series cursor lines, and ground footprints use the existing
full-resolution cursor and validity rules, and are visible only when `t` is inside the
effective plot range. A valid interpolated current state may be displayed without a selected
source sample if its timestamp is inside that range. Otherwise hide plot overlays and show
`Playback time outside plot range`. Global timeline/current-state readouts remain live even
when plots omit the current state. Never interpolate across an OEM gap.

### 5.3 Scheduling and cache invalidation

All UI and artist updates run on the existing wx thread. Reuse the workspace graph-redraw
queue and panel throttling; do not add a timer per view, rebuild figures on every edit, or
queue obsolete drag frames. For hidden panels, retain only the latest range and cursor
state and apply it before their next visible render.

Cache selected source indices by dataset, series timestamp array, effective bounds, and
display budget. Reuse unchanged slices/decimation when only the cursor moves; a moving X
range can still require an axes redraw. Invalidate display selections on bound changes,
source replacement, projection/seam changes where relevant, and panel closure. Keep cache
size bounded to the latest selection rather than accumulating playback frames.

## 6. Validation and exceptional states

| Condition | Required behavior |
|---|---|
| Playback bounds reversed, non-finite, or outside OEM coverage | Reject edit; retain prior bounds, clock time, and views |
| Plot value malformed/non-finite or same-mode endpoints always reversed | Reject edit; retain applied plot rule; never change playback bounds/time |
| Plot interval extends beyond OEM coverage | Intersect with `D`, retain requested values, label OEM clipping |
| Plot interval extends beyond or is disjoint from playback bounds | Render normally inside OEM coverage; leave playback limits and clock time unchanged |
| Plot interval wholly outside `D`, or mixed endpoints crossed | Accept; `R = None`, clear history/overlays, show `Plot range does not overlap OEM coverage` or `Plot start is after plot end` |
| Nonempty range contains no eligible samples | Clear history; show `No samples in selected range`; valid in-range current overlays may remain |
| Playback time outside a nonempty plot range | Continue playback; hide plot cursor/marker/footprints; keep global state readouts and slider thumb live |
| Current time lies in an OEM gap | Existing unavailable-state rules apply; never bridge the gap |
| Singleton plot range | Select only that instant; impose no playback limit or boundary pause |
| Singleton playback bounds | Clamp/pause the clock there; fixed plots may still span any interval in OEM coverage |
| No OEM loaded | Disable both range editors; retain the existing load prompt |

A singleton plot X extent receives one second of visual padding on either side, converted
to existing axis units. An empty plot uses `D` as its X extent, with the same padding if `D`
is a singleton. Visual padding may extend outside bounds; it admits no samples and changes
neither playback limits nor effective range labels. Empty history and an empty intersection
are distinct states. Never leave stale paths or out-of-range current overlays visible.

## 7. Verification strategy

Pure tests prove `R ⊆ D` and `B ⊆ D` for fixed, relative, and both mixed combinations across forward,
backward, and arbitrary seeks, including wholly outside requests and dynamic crossings.
Use narrowed playback bounds and plots extending beyond both ends of `B`, plus plots wholly
disjoint from `B`, to prove plot selection is independent. Test that changing `B` preserves
fixed plots and affects relative plots only when the clock time is clamped.
Test valid future-only/past-only windows and optional empty results. Clock/application tests
prove plot edits never call the bounds setter/seek and never change playback time; only
playback-bound edits clamp it. Cover independent resets, observers, and dataset lifecycle.

Agg renderer tests cover inclusive filtering before decimation, segment gaps, stable Y,
empty/singleton axes, and current-overlay visibility independent of global readouts. Exercise
both 3D backends and ground-track seam/camera behavior, recording unavailable backend checks.

Live wx checks cover shared-slider hit targets, both editors, keyboard/focus, resize/themes,
clipping, empty ranges, and playback while outside plots. Benchmark at least 100,000 samples,
all views, moving/fixed windows, both directions, and repeated dragging. Record platform,
backend, FPS, achieved rate, and latency against the existing architecture's performance
target; do not claim completion without evidence. See the implementation plan for gates.
