# play-oem Performance Analysis 2

## Source baseline

Analysis 2 starts from the retained behavior of analysis 1:

- 5 Hz drag-range feedback;
- Earth-fixed `CursorState` caching;
- shared redraw batching;
- batched station-profile row metric conversion;
- drag release dispatching the latest settled range.

The baseline source is the recorded user interaction:
[scenario-recorded.json](scenario-recorded.json). It contains 14 playback-range
states, measured pauses, and fractional bounds relative to OEM coverage.

Captured inputs:

- OEM: [ISS_2026-05-20.OEM](/Users/jeongyun/Projects/ephem-toolkit/tests/data/ISS_2026-05-20.OEM)
- Config: [play-oem.toml](play-oem.toml)
- State: [play-oem-state.toml](play-oem-state.toml)
- Recorded scenario: [scenario-recorded.json](scenario-recorded.json)
- Interpreter: `.venv/bin/python`, Python 3.9.6
- wxPython: 4.2.4
- wxWidgets: 3.2.8

## Baseline profile

- Profile: [play-oem-baseline.prof](play-oem-baseline.prof)
- Text summary: [play-oem-baseline.txt](play-oem-baseline.txt)
- Wall time: 128 seconds
- Instrumented total: 125.492 seconds
- Function calls: 165,146,787 total / 162,676,002 primitive

Dominant recorded hotspots:

- `_apply_playback_bounds`: 34.517 seconds cumulative
- Matplotlib drawing: 33.544 seconds cumulative
- `_dispatch_time_range`: 33.901 seconds cumulative
- `_apply_store_context`: 26.322 seconds cumulative
- `_on_timer`: 22.227 seconds cumulative
- `_refresh_store_data_views`: 21.924 seconds cumulative
- Ground Station draw: 13.227 seconds cumulative
- Ground Station prepare: 11.756 seconds cumulative

## Short validation baseline

The [new scenario](scenario-new.json) is a 10%-coverage playback-range pan:

- 30%-40% initial range;
- two 2% forward pan steps;
- two reverse pan steps;
- 1-second settled pauses.

It produces a faster repeatable regression/profile cycle:

- Profile: [play-oem-baseline-new.prof](play-oem-baseline-new.prof)
- Text summary: [play-oem-baseline-new.txt](play-oem-baseline-new.txt)
- Wall time: 72 seconds
- Instrumented total: 69.771 seconds
- Function calls: 55,778,400 total / 54,962,810 primitive

## Attempt 1: range refresh, artist reuse, and station cache

Status: **effective**

Changed implementation:

- Store refreshes now distinguish snapshot/range changes from cursor-only updates
  and avoid rebuilding unchanged visible panel state.
- Speed/Altitude reuses existing `Line2D` and `PathPatch` artists for retained
  range segments.
- Station interval cache entries support covering-range reuse and clip intervals
  to the requested bounds.
- Ground Station profile/pass preparation is keyed by snapshot, range, coverage,
  and station configuration to avoid identical re-query callbacks.

Short-scenario evidence:

| Metric | Baseline new | Attempt 1 | Change |
| --- | ---: | ---: | ---: |
| Wall time | 72 s | 33 s | 54.2% lower |
| Instrumented total | 69.771 s | 31.752 s | 54.5% lower |
| Function calls | 55.778M | 30.967M | 44.5% lower |
| `_on_timer` cumulative | 29.759 s | 7.946 s | 73.3% lower |
| `_refresh_store_data_views` cumulative | 29.595 s | 7.841 s | 73.5% lower |
| Matplotlib draw cumulative | 25.173 s | 12.698 s | 49.6% lower |
| `_apply_store_context` cumulative | 20.561 s | 6.059 s | 70.5% lower |
| `_prepare_access` cumulative | 9.852 s | 4.360 s | 55.8% lower |
| `query_station_access` cumulative | 9.841 s | 4.356 s | 55.7% lower |

Retained recorded-scenario evidence:

| Metric | Baseline | Attempt 1 | Change |
| --- | ---: | ---: | ---: |
| Wall time | 128 s | 102 s | 20.3% lower |
| Instrumented total | 125.492 s | 100.061 s | 20.3% lower |
| Function calls | 165.147M | 111.845M | 32.3% lower |
| `_on_timer` cumulative | 22.227 s | 9.470 s | 57.4% lower |
| `_refresh_store_data_views` cumulative | 21.924 s | not in top 35 | lower |
| Matplotlib draw cumulative | 33.544 s | 32.985 s | 1.7% lower |
| `_apply_store_context` cumulative | 26.322 s | not in top 35 | lower |
| `_prepare_access` calls | 516 | 490 | 5.0% lower |
| `station_access` calls | 1030 | 490 | 52.4% lower |

## Attempt 2: generalized Matplotlib store-artist binding

Status: **effective**

Shared implementation:

- [StoreArtistBinding](../../../../../src/ephem_toolkit/play_oem/views/plotting.py)
  now owns one-axis artist synchronization for store-derived series,
  raw-state components, and arbitrary point-pair views.
- Speed/Altitude, distance, state components, angular velocity, RTN, and
  direction-change views now use the same binding instead of view-local
  remove/rebuild helpers.
- The shared binding reuses compatible `Line2D` and `PathPatch` instances,
  updates transforms and paths in place, and removes excess artists.

Short-scenario evidence:

| Metric | Attempt 1 | Attempt 2 | Change |
| --- | ---: | ---: | ---: |
| Wall time | 33 s | 32 s | 3.0% lower |
| Instrumented total | 31.752 s | 31.040 s | 2.2% lower |
| Function calls | 30.967M | 30.009M | 3.1% lower |

Retained recorded-scenario evidence:

| Metric | Attempt 1 | Attempt 2 | Change |
| --- | ---: | ---: | ---: |
| Wall time | 102 s | 102 s | unchanged |
| Instrumented total | 100.061 s | 100.157 s | 0.1% higher |
| Function calls | 111.845M | 113.323M | 1.3% higher |

## Attempt 3: shared Ground Track and Ground Station bindings

Status: **effective architecture; performance inconclusive**

Changed implementation:

- Added `StoreLineSegmentBinding` for reusable projected `Line2D` segments.
- Ground Track now syncs projected track segments in place instead of removing
  and recreating every track line.
- Added `StationAccessBinding` for shared station/snapshot/range/policy
  preparation identity.
- Ground Station profile renderers and Pass/Sky views now reuse the same
  binding for store queries and adapted station results.

Short-scenario evidence:

| Metric | Attempt 2 | Attempt 3 | Change |
| --- | ---: | ---: | ---: |
| Wall time | 32 s | 34 s | 6.3% higher |
| Instrumented total | 31.040 s | 33.482 s | 7.9% higher |
| Function calls | 30.009M | 34.421M | 14.7% higher |

The wall-time and call-count change is inconclusive and includes run-to-run
variation. This attempt is kept for architectural simplification and reuse:
it reduces duplicate preparation code and view-local artist rebuild loops
without changing range, coverage, station, or pass semantics.

This baseline is retained for feature-preserving 5 Hz drag feedback. It is not
comparable with analysis-1 attempts that suppressed range redraws during drag.

## Attempt 4: Ground Station profile artist reuse

Status: **effective**

Changed implementation:

- Added `StationProfileArtistBinding` for reusable station profile `Line2D`
  artists, access-range `Polygon` artists, and mask `Line2D` artists.
- Ground Station profile renderers no longer call `Axes.clear()` during range
  or snapshot refreshes.
- The playback marker remains in place and is updated in place.
- Profile range/coverage changes now synchronize existing artists instead of
  rebuilding Matplotlib axes and patches.

Short-scenario evidence:

| Metric | Attempt 3 | Attempt 4 | Change |
| --- | ---: | ---: | ---: |
| Instrumented total | 33.482 s | 28.230 s | 15.7% lower |
| Function calls | 34.421M | 23.806M | 30.8% lower |
| Matplotlib draw cumulative | 16.407 s | 13.121 s | 20.0% lower |
| `_prepare_access` cumulative | 4.223 s | 2.842 s | 32.7% lower |
| Station `query_station_access` cumulative | 4.219 s | 2.842 s | 32.6% lower |

The retained-scenario rerun for the combined final implementation is now
captured below under Attempt 5. An Attempt 4-only full profile was not
captured separately, but the full Attempt 5 profile contains both the Ground
Station artist reuse and range-dispatch deduplication changes.

## Attempt 5: range-dispatch/store-refresh deduplication

Status: **effective**

Changed implementation:

- Range-only `_dispatch_time_range` updates no longer queue a full
  `_refresh_store_data_views` pass after updating the same visible views.
- Visible store-backed views receive their range setter directly.
- Hidden panels retain pending-range state and catch up when they become
  visible.
- Store snapshot/tier notices continue to use the separate refresh path.

Short-scenario evidence:

| Metric | Attempt 4 | Attempt 5 | Change |
| --- | ---: | ---: | ---: |
| Instrumented total | 28.230 s | 24.920 s | 11.7% lower |
| Function calls | 23.806M | 16.939M | 28.9% lower |
| Matplotlib draw cumulative | 13.121 s | 11.537 s | 12.1% lower |
| `_on_timer` cumulative | 9.232 s | 8.390 s | 9.1% lower |
| `_refresh_store_data_views` cumulative | 9.126 s | 8.287 s | 9.2% lower |
| Ground Station prepare cumulative | 2.844 s | 3.215 s | 13.0% higher |
| Station `query_station_access` cumulative | 2.842 s | 3.213 s | 13.1% higher |

The cProfile result is strong for overall time and call count, and it is
consistent with removing duplicate visible-view range rebuild work. Station
preparation and query totals increased in this run, so those values are not
claimed as an independent station gain. The full retained-scenario rerun
is now available below.

Retained recorded-scenario evidence:

| Metric | Baseline | Attempt 5 | Change |
| --- | ---: | ---: | ---: |
| Wall time | 128 s | not remeasured outside cProfile | — |
| Instrumented total | 125.492 s | 72.596 s | 42.2% lower |
| Function calls | 165.147M | 51.519M | 68.8% lower |
| Matplotlib draw cumulative | 33.544 s | 17.895 s | 46.6% lower |
| `_dispatch_time_range` cumulative | 33.901 s | 11.474 s | 66.2% lower |
| `_prepare_access`/station query cumulative | 11.756 s / 11.728 s | 8.916 s / 8.905 s | 24.2% / 24.1% lower |
| Ground Station profile range updates | 256 + 256 calls | 139 + 139 calls | 45.7% lower |

## Reproduce

```sh
docs/architecture/play-oem/performance/analysis-2/profile_play_oem_ui.sh \
  --scenario docs/architecture/play-oem/performance/analysis-2/scenario-recorded.json \
  --config docs/architecture/play-oem/performance/analysis-2/play-oem.toml \
  --state docs/architecture/play-oem/performance/analysis-2/play-oem-state.toml \
  --output docs/architecture/play-oem/performance/analysis-2/play-oem-attempt-X.prof
```

## Optimization protocol

Each attempt must:

1. Preserve 5 Hz drag feedback and the settled-range release dispatch.
2. Change only one hypothesis or one tightly coupled implementation step.
3. Use `.venv/bin/python`, the copied scenario, and the copied TOML snapshots.
4. Capture both `.prof` and `.txt` output in this directory.
5. Compare call counts and cumulative time against `play-oem-baseline.prof`.
6. Mark the result effective, ineffective, inconclusive, or reverted.
7. Revert ineffective work and document the evidence.

## Next hypotheses

1. Batch or coalesce Matplotlib artist replacement in `_apply_store_context`.
2. Apply similar in-place artist reuse to Ground Station Pass/Sky `_draw_sky_plot`
   and pass-table rebuilds where range/station refresh repeatedly recreates
   Matplotlib artists.
3. Cache or reuse visible data-view range snapshots within a 5 Hz dispatch.
4. Deduplicate station-access queries by exact settled/visible range lifecycle.
5. Bound and coalesce `_on_timer` redraw/store notice work.
6. Re-evaluate station interval reuse now that retained drag feedback restores
   repeated station queries.
