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

This baseline is retained for feature-preserving 5 Hz drag feedback. It is not
comparable with analysis-1 attempts that suppressed range redraws during drag.

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
2. Avoid repeated Ground Station patch/path construction during range refresh.
3. Cache or reuse visible data-view range snapshots within a 5 Hz dispatch.
4. Deduplicate station-access queries by exact settled/visible range lifecycle.
5. Bound and coalesce `_on_timer` redraw/store notice work.
6. Re-evaluate station interval reuse now that retained drag feedback restores
   repeated station queries.
