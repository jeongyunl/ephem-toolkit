# play-oem Performance Report

## Summary

Playback render rate is limited by Matplotlib figure drawing on the GUI thread. The per-tick data work is small by comparison. Two changes to the data path (vectorized decimation and skipping unchanged updates) gave large microbenchmark gains but no significant live-app gain. A cursor-only blit for the state-components view cut the measured per-frame draw time from about 60 ms to about 17 ms in wx, about 3.5×, and was kept.

The configured 30 fps is not reached with 2 or 8 panels open, and reloading an OEM file does not change the steady-state rate. The resource-hardening check (Phase 4) has not started.

| Phase | Change | Status | Outcome |
|---|---|---|---|
| 1 | Vectorize decimation | Kept | Microbenchmark gain; no significant live gain |
| 2 | Skip unchanged updates | Kept | Microbenchmark gain; no significant live gain |
| 3 | Measure in live app | Done | Target not met; draw cost identified as the bottleneck |
| 5 | Cursor-only blit (state view) | Kept | About 3.5× faster per frame (wx, measured) |
| 4 | Resource hardening and leak check | Not started | Open |

## Problem

Playback render rate drops after loading a different OEM file, and the cost grows with the number of open plots.

## Background and initial finding

Every clock tick, `PlayerApp._dispatch_time_range` calls `set_time_range` on each visible view. Each call runs `SegmentedPlotHistory.update` (`src/ephem_toolkit/play_oem/views/plotting.py`), which recomputes the visible selection and decimates every segment run longer than `MAX_DISPLAY_POINTS_PER_SEGMENT` (2000) with `decimate_indices`. This repeats on every tick, even when the visible range has not changed.

`decimate_indices` loops over display buckets in Python, so its cost is roughly constant per run regardless of how many samples the run contains.

Synthetic benchmark (Python 3.9.6, macOS, Matplotlib Agg; 200,000 samples over 48 h in 10 segments of 20,000 samples, one value column):

| Operation | Time |
|---|---|
| `decimate_indices`, 7,200 × 1 → 2,000 | 3.5 ms |
| `decimate_indices`, 200,000 × 1 → 2,000 | 3.6 ms |
| `SegmentedPlotHistory.update`, 1 h visible window | 3.8 ms |
| `SegmentedPlotHistory.update`, full range | 36 ms |

The full-range figure is about 10 × 3.5 ms, which matches one decimation per segment run. Decimation accounts for almost all of the update cost. Each open panel with a long visible range therefore costs about 4–36 ms per tick. At 30 fps the frame budget is about 33 ms, so a few full-range panels can exceed it.

## Phase 1: Vectorize decimation

**Change.** The per-bucket Python loop in `decimate_indices` was replaced with NumPy `reduceat` operations that compute per-bucket minimum and maximum for each column. The selected indices are unchanged: the first and last sample, plus bucket extrema, returned sorted and unique.

**Results** (same benchmark, old and new measured in one process):

| Operation | Before | After |
|---|---|---|
| `SegmentedPlotHistory.update`, 1 h visible window | 2.1 ms | 0.21 ms |
| `SegmentedPlotHistory.update`, full range | 20.6 ms | 2.2 ms |
| `decimate_indices`, 200,000 × 1 → 2,000 | 2.1 ms | 1.2 ms |
| `decimate_indices`, 200,000 × 3 → 2,000 | 2.9 ms | 3.4 ms |

The three-column case is about 15% slower. Multi-column callers (Ground Track and the 3D views) were not timed in the live app.

**Validation.** `test_decimation_matches_reference_for_ties_nans_and_columns` compares the output with the original loop on seeded random inputs, including ties, NaNs, and one to three columns.

**Decision:** kept.

## Phase 2: Skip unchanged updates

**Change.** `SegmentedPlotHistory.update` stores the last bounds (as floats) and the empty-range flag. When the next call has the same key, it returns the cached result without decimating. The check lives in the history, not the app layer. An earlier app-level cache was reverted at the user's request.

**Results** (same benchmark, one process):

| Case | Before | After |
|---|---|---|
| Fixed full range, unchanged each tick | 2.2 ms | ~0.00 ms |
| Fixed 1 h window, unchanged each tick | 0.21 ms | ~0.002 ms |
| Alternating full / 1 h (forces recompute) | n/a | 1.2 ms (same as before) |
| Follow 1 h window, moves each tick | 0.21 ms | 0.20 ms |

The skip removes the full-range cost for fixed windows. Follow mode is unchanged and still depends on Phase 1.

**Validation.** `test_history_skips_decimation_when_range_is_unchanged` counts decimation calls.

**Decision:** kept.

## Phase 3: Live-app measurement

**Method.** A temporary harness outside the repo (no source edits) ran the real GUI on `tests/data/JPSS-1.oem` (21,601 states). It reloaded `ISS_2026-05-20.OEM` and `JPSS-1.oem` through the normal `_load_oem_file` path, and played 10 s per phase at default settings (configured 30 fps). Runtime wrappers recorded `PlayerApp._on_timer`, `PlayerApp._dispatch_time_range` (inside timer ticks only), and `Figure.draw`.

**Results** (Phases 1–2 applied):

| Panels | Phase | Rendered frames/s (configured 30) | Dispatch per frame | Figure draw |
|---|---|---|---|---|
| overview (2) | initial | 17.2 | 8.6 ms mean | ~53 ms per draw |
| overview (2) | after reload ISS | 17.4 | 5.1 ms | ~50 ms |
| overview (2) | after reload JPSS | 17.1 | 9.1 ms | ~53 ms |
| all (8) | initial | 11.4 | 8.3 ms | ~107 ms per draw, 6.1 draws/s |
| all (8) | after reload ISS | 11.2 | 6.8 ms | ~110 ms |
| all (8) | after reload JPSS | 11.5 | 8.5 ms | ~107 ms |

Reload cost (load and replace, excluding the first file): ISS 1.0 s and JPSS 4.5 s with 2 panels; 3.5 s and 10.0 s with 8 panels.

**Before/after Phases 1–2** (`plotting.py` stashed, same `all` run):

| Phase | Frames/s before | Frames/s now | Dispatch before | Dispatch now |
|---|---|---|---|---|
| initial | 11.9 | 11.4 | 9.4 ms | 8.3 ms |
| after reload ISS | 11.3 | 11.2 | 6.5 ms | 6.8 ms |
| after reload JPSS | 11.6 | 11.5 | 10.1 ms | 8.5 ms |

**Findings.**
- The target was not met. The configured 30 fps is not reached with 2 or 8 panels, and reload does not change it.
- The bottleneck is Matplotlib drawing, not per-tick dispatch. The 8-panel `Position | Velocity` figure (6 axes) takes about 107 ms per draw. Draws run on the GUI thread and block the wx timer, so timer calls fall to about 12/s and the draw budget allows about 6/s.
- Dispatch is about 8 ms per frame before and after Phases 1–2. The differences are within run-to-run noise.
- Phase 4 (leak check) is not supported as the cause of the slow rate. Reload does not change the steady-state rate.

## Phase 5: Cursor-only blit for the state-components view

**Goal.** Reduce render time per frame: the GUI-thread wall time for one playback tick's draw. Frame rate is a derived result, not the target.

**Scope decision.** The user chose the `state_first` option: the cursor-only path covers the state-components view, and all other views keep full draws.

**Design.**
- Default plot range endpoints are `follow`, which resolves to the playback bounds. The default range is disabled, which resolves to the constant coverage. In either case the bounds are constant during playback, so only the cursor moves each tick.
- Enabled `offset` endpoints move the range every tick, so those frames still need a full draw.
- `TimeRangeSupport.animated_cursor_updates` is `False` by default. `StateComponentsView` opts in and builds its cursors with `animated=True`.
- `consume_cursor_only_update()` reports whether the range stayed the same since the last dispatch. A True result means only cursors moved.
- `GraphPanelHost` keeps a `_CursorBlitter`. On each full draw, a `draw_event` handler caches the figure background before the animated cursors are drawn, then draws the cursors. A cursor-only refresh restores that background, redraws the cursors, and blits.
- The blitter falls back to a full draw if the figure bbox or any axis limits changed since the capture, which covers resize, toolbar zoom, and pan.
- Pending requests are tracked as cursor-only or full. A full request, or a full draw already scheduled, takes priority.

**Validation.**
- Agg pixel test: the blit output equals a fresh full draw; a limit change forces the fallback.
- Flush-decision unit test: covers cursor-only, full-pending, scheduled-full, and blit-failure cases.
- Range-change test: `consume_cursor_only_update()` is False after a range change and True after a cursor-only update.
- Play-oem suite: 352 passed, 11 failed. The 11 failures are the pre-existing ones listed under Open items.

**Measurement** (wx, `FigureCanvasWxAgg`, 6-axis state view, 2280×1776 px, 60 frames; temporary script outside the repo, since deleted):

| Path | Median | p90 |
|---|---|---|
| Full draw (`canvas.draw()`, includes bitmap conversion) | 59.9 ms | 61.0 ms |
| Cursor-only blit (`_CursorBlitter.redraw()`) | 17.0 ms | 19.2 ms |

The blit saves about 43 ms per frame, about 3.5×. Most of the remaining 17 ms is Matplotlib's Agg-to-wx bitmap conversion inside `FigureCanvasWxAgg.blit`, which converts the full RGBA buffer. That conversion sets the floor on this canvas size.

**Decision:** kept.

**Not yet measured.** The live app with the real timer and the 8-panel workspace, and the VTK 3D panels. The synthetic full-draw median (59.9 ms at this size) is lower than the live 107 ms for the 6-axis figure in Phase 3. The live figure size and DPI were not matched in the benchmark, so the absolute numbers should not be compared directly.

## Phase 4: Resource hardening and leak check (not started)

- Disconnect `GroundTrackView` Matplotlib callbacks (`mpl_connect` and `xlim_changed`) explicitly in `close()`. This is hardening, not a confirmed leak.
- Measure memory and live wx window counts across repeated playback and unload/reload cycles, using `tracemalloc` or object-count snapshots.

**Target:** memory and window counts return to baseline after each reload.

## Ground Station Access preparation

**Change.** Access preparation evaluates each valid OEM segment on a uniform grid with a maximum
30-second step, rather than evaluating every source sample. The active `OemCursor` interpolates
states at grid epochs; sampled local elevation maxima are refined and access crossings are bisected
to within 0.5 seconds. This preserves the documented time tolerances while avoiding work that
scales with dense source cadence.

**Synthetic benchmark** (Python 3.9, macOS; Earth-centered ITRF circular-orbit OEM; 200,000 samples
over 48 hours; three stations):

| Measurement | Result |
|---|---|
| Uniform-grid evaluations across all stations | 17,283, plus refined extrema and crossings |
| Access preparation wall time | 0.748 s |
| Intervals found per station | 33, 0, 0 |
| Prediction limitations | None |

The prior source-sample-based loop took 21.110 seconds on the same workload. The uniform grid
reduces the initial evaluation count from 600,000 source-sample/station pairs to 17,283 while
retaining local-maximum refinement and 0.5-second crossing refinement. This synthetic result is
not a guarantee for frame-conversion-heavy OEMs or unusually complex interpolation policies.

**Validation.** Ground Station Access and interval tests pass, including sub-step maxima,
crossings, source-gap limitations, and segment-boundary behavior. The complete `play-oem` suite
passes: 376 passed, 3 skipped.

## Out of scope

- Changing the decimation algorithm's output or the display point cap.
- Changes to the clock or the render-rate setting.

## Open items

1. Approve Phase 3 live-app timing (done) and decide whether Phase 4 proceeds.
2. Decide whether Phase 4's Ground Track cleanup belongs in this report's scope.
3. Decide whether to fix the 11 pre-existing test failures:
   - 10 tests in `test_play_oem_cli.py` fail. The earlier diagnosis was a stale `args.speed` expectation; each test was not re-checked individually.
   - 1 test in `test_workspace.py` (`test_feature_rail_supports_click_and_vertical_keyboard_navigation`) expects a "Playback" title that is now "Settings".
4. Measure the live app with the Phase 5 path enabled (real timer, 8-panel workspace) to confirm the wx gain outside the benchmark.
