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

## Attempt 6: stable post-initial constrained-layout lifecycle

Status: **ineffective; reverted**

Hypothesis:

- Prevent `_on_canvas_size` from re-enabling the constrained layout after the
  first draw has stabilized the embedded figure.
- Keep the layout engine disabled for subsequent resize and redraw work.

Short-scenario evidence:

| Metric | Attempt 5 | Attempt 6 | Change |
| --- | ---: | ---: | ---: |
| Instrumented total | 24.920 s | 27.141 s | 8.9% higher |
| Function calls | 16.939M | 20.671M | 22.1% higher |
| Matplotlib draw cumulative | 11.537 s | 12.867 s | 11.5% higher |
| `_set_text` cumulative | 5.406 s | 6.147 s | 13.7% higher |

The stable-layout change was not a net improvement and was reverted. It
does not establish that constrained layout is universally harmful; the
existing first-draw stabilization remains unchanged, and resize behavior
continues to use the prior layout-engine lifecycle.

## Attempt 7: exact station-access query cache

Status: **ineffective; reverted**

Hypothesis:

- Cache complete exact-range `StationAccessView` queries alongside the existing
  interval cache.
- Reuse the full store query for repeated identical snapshot/range/station
  requests while preserving interval clipping and partial-range semantics.

Short-scenario evidence:

| Metric | Attempt 5 | Attempt 7 | Change |
| --- | ---: | ---: | ---: |
| Instrumented total | 24.920 s | 26.314 s | 5.6% higher |
| Function calls | 16.939M | 18.789M | 10.9% higher |
| Matplotlib draw cumulative | 11.537 s | 11.956 s | 3.6% higher |

The exact full-query cache did not improve this range pan and introduced
cache/lookup overhead. It was reverted; the existing covering-range interval
cache remains the station-access reuse mechanism.

## Attempt 8: Sky View polar artist reuse

Status: **effective architecture; performance inconclusive**

Changed implementation:

- Replaced Sky View `axes.clear()` rebuilds with reusable mask, pass, marker,
  and playback `Line2D` bindings.
- The polar playback marker retains a stable artist and switches between an
  empty data array outside a pass and the live look-angle point inside a pass.
- Status text and legend presentation are retained or synchronized rather than
  recreating the full polar axes for each pass/range refresh.

Short-scenario evidence:

| Metric | Attempt 5 | Attempt 8 | Change |
| --- | ---: | ---: | ---: |
| Instrumented total | 24.920 s | 26.674 s | 7.0% higher |
| Function calls | 16.939M | 19.815M | 17.0% higher |
| Matplotlib draw cumulative | 11.537 s | 12.033 s | 4.3% higher |

The repeated short profile did not open Sky, so this result is not a
measured Sky performance gain. It is kept for architecture and test coverage:
it removes repeated polar axes and artist construction and introduces a stable
artist identity for pass/mask/playback content.

## Attempt 9: complete range-snapshot series cache

Status: **inconclusive; reverted**

Hypothesis:

- Reuse complete exact-range series query results across forward/reverse range
  pans through `StoreViewContext`.
- Preserve partial/incomplete-range queries without caching and bound the
  exact-range cache to 32 entries.

Short-scenario evidence:

| Run | Metric | Attempt 5 | Attempt 9 | Change |
| --- | --- | ---: | ---: | ---: |
| First | Instrumented total | 24.920 s | 25.137 s | 0.87% higher |
| First | Function calls | 16.939M | 16.975M | 0.21% higher |
| First | Matplotlib draw cumulative | 11.537 s | 10.565 s | 8.4% lower |
| Repeat | Instrumented total | 24.920 s | 25.763 s | 3.4% higher |
| Repeat | Function calls | 16.939M | 20.173M | 19.1% higher |
| Repeat | Matplotlib draw cumulative | 11.537 s | 11.318 s | 1.9% lower |

The cache introduced lookup/memory overhead and was not stable across
repeated runs. Its modest draw/text reduction did not produce a reliable
total/call improvement, so it was reverted.

## Attempt 10: Ground Station static-axis decoration

Status: **inconclusive; reverted**

Hypothesis:

- Move Ground Station xlabel, UTC formatter, ylabel, grid, and typography setup
  from every range `_draw()` call to panel build time.
- Preserve only limits/profile artist updates during range-only redraws.

Short-scenario evidence:

| Run | Instrumented total | Calls | Matplotlib draw | `set_text` |
| --- | ---: | ---: | ---: | ---: |
| Attempt 5 baseline | 24.920 s | 16.939M | 11.537 s | 5.406 s |
| Attempt 10 first | 26.296 s | 19.854M | 9.879 s | 4.311 s |
| Attempt 10 repeat | 26.610 s | 19.640M | 10.709 s | 4.814 s |

Both repeats lowered Matplotlib text/draw work, but total and call counts
were higher. That tradeoff was not stable enough to justify the change, so
the static-axis setup was reverted.

## Attempt 11: retained long-scenario retry

Status: **effective; stable on the longer scenario**

Captured the [retained recorded scenario](scenario-recorded.json) against the
current implementation, including the already-validated Ground Station
Profile and Sky artist reuse work.

Retained-scenario evidence:

| Metric | Baseline | Attempt 11 | Change |
| --- | ---: | ---: | ---: |
| Wall time | 128 s | not remeasured outside cProfile | — |
| Instrumented total | 125.492 s | 72.718 s | 42.0% lower |
| Function calls | 165.147M | 50.941M | 69.2% lower |
| Matplotlib draw cumulative | 33.544 s | 17.732 s | 47.1% lower |
| `_dispatch_time_range` cumulative | 33.901 s | 11.659 s | 65.6% lower |
| `_prepare_access`/station query cumulative | 11.756 s / 11.728 s | 7.207 s / 7.190 s | 38.7% / 38.7% lower |
| Axis tick update cumulative | 12.747 s | 5.467 s | 57.1% lower |

Comparison with Attempt 5:

| Metric | Attempt 5 | Attempt 11 | Change |
| --- | ---: | ---: | ---: |
| Instrumented total | 72.596 s | 72.718 s | 0.17% higher |
| Function calls | 51.519M | 50.941M | 1.1% lower |
| Matplotlib draw cumulative | 17.895 s | 17.732 s | 0.9% lower |
| `_dispatch_time_range` cumulative | 11.474 s | 11.659 s | 1.6% higher |

The longer retry is effectively stable relative to Attempt 5: no material
total, call, or draw regression. Remaining high-cost areas are constrained
layout/tight-bbox execution and repeated axis/tick/text work, but the latest
layout and static-axis hypotheses did not justify a change on repeated short
tests.

## Attempt 12: live-status text deduplication

Status: **inconclusive; reverted**

Hypothesis:

- Skip unchanged `_set_time_series_status()` writes across 5 Hz cursor/update
  ticks, keeping status label updates only on text changes.

Short-scenario evidence:

| Metric | Attempt 5 | Attempt 12 | Change |
| --- | ---: | ---: | ---: |
| Instrumented total | 24.920 s | 24.202 s | 2.9% lower |
| Function calls | 16.939M | 15.163M | 10.5% lower |
| Matplotlib draw cumulative | 11.537 s | 10.389 s | 10.0% lower |
| `_set_text` cumulative | 5.406 s | 4.999 s | 7.5% lower |

Full-scenario evidence:

| Metric | Attempt 11 | Attempt 12 | Change |
| --- | ---: | ---: | ---: |
| Instrumented total | 72.718 s | 73.473 s | 1.0% higher |
| Function calls | 50.941M | 52.228M | 2.5% higher |
| Matplotlib draw cumulative | 17.732 s | 18.330 s | 3.4% higher |

The short result was positive but not preserved in the retained longer
scenario. Status deduplication was therefore reverted after the full profile
showed no reliable end-to-end gain.

## Attempt 13: defer station preparation during active range drag

Status: **ineffective; reverted**

Hypothesis:

- Keep immediate axis/cursor feedback while range dragging.
- Defer `StationAccessBinding` preparation, station interval/profile queries,
  pass-row rebuilding, and profile/polar refresh until the settled range.

Short-scenario evidence:

| Metric | Attempt 12 | Attempt 13 | Change |
| --- | ---: | ---: | ---: |
| Instrumented total | 24.202 s | 27.201 s | 12.4% higher |
| Function calls | 15.163M | 22.131M | 45.9% higher |
| Matplotlib draw cumulative | 10.389 s | 10.205 s | 1.8% lower |
| `query_station_access` cumulative | 1.338 s | 7.488 s | 459.6% higher |
| `_prepare_access` cumulative | 1.340 s | 7.491 s | 459.0% higher |
| `_dispatch_time_range` cumulative | 5.338 s | 10.636 s | 99.2% higher |
| `_on_timer` cumulative | 5.701 s | 5.890 s | 3.3% higher |

The short run did not reduce station preparation in the settled range scenario;
it increased station and dispatch work substantially. The change was reverted.
No additional station drag-deferral behavior is retained.

## Attempt 14: retained full-scenario stability rerun

Status: **effective; stable**

Repeated the retained recorded scenario against the reverted implementation
with a physical wall-time measurement and cProfile capture.

| Metric | Attempt 11 | Attempt 14 | Change |
| --- | ---: | ---: | ---: |
| Wall time | not remeasured outside cProfile | 74.04 s | measured |
| Instrumented total | 72.718 s | 72.779 s | 0.08% higher |
| Function calls | 50.941M | 51.700M | 1.49% higher |
| Matplotlib draw cumulative | 17.732 s | 18.056 s | 1.83% higher |
| `_dispatch_time_range` cumulative | 11.659 s | 11.438 s | 1.90% lower |
| `_prepare_access`/station query cumulative | 7.207 s / 7.190 s | 7.201 s / 7.188 s | effectively unchanged |

The rerun confirms the retained implementation is stable across repeated full
runs, while remaining far below the 128-second baseline wall time and
125.492-second instrumented baseline. The remaining station, layout, axis/tick,
and draw costs are repeatable profile hotspots, but no new untested change has
a stable evidence-backed full-scenario gain. Further implementation attempts
should use a fresh short profile and full rerun before retention.

## Attempt 15: StoreViewContext-bound station query cache

Status: **ineffective; reverted**

Hypothesis:

- Reuse one exact-range complete `StationAccessView` query across elevation,
  azimuth, range, pass, and Sky views bound to the same context.
- Preserve snapshot/range/policy identity and bound the cache to 32 entries.

Short-scenario evidence:

| Metric | Attempt 5 short baseline | Attempt 15 | Change |
| --- | ---: | ---: | ---: |
| Instrumented total | 24.920 s | 27.083 s | 8.7% higher |
| Function calls | 16.939M | 19.615M | 15.8% higher |
| Matplotlib draw cumulative | 11.537 s | 13.352 s | 15.7% higher |
| `query_station_access` cumulative | 3.213 s | 2.571 s | 20.0% lower |
| `_prepare_access` cumulative | 3.215 s | 2.574 s | 19.9% lower |

The context-local cache increased rather than reduced station and dispatch
work. It was reverted, and no station exact-query cache is retained.

## Attempt 16: fixed-layout store time-series figures

Status: **effective; retained**

Changed implementation:

- Store-backed orbit time-series figures now disable constrained layout at
  construction and apply one fixed tight-layout pass after their axes exist.
- The shared orbit time-series presenter calls `configure_figure_layout`
  once before panel realization.
- The change covers Speed/Altitude, Geocentric Distance, state components,
  angular velocity, direction-change, and RTN views.

Short-scenario evidence:

| Run | Instrumented total | Function calls | Matplotlib draw | Constrained layout | Axis ticks |
| --- | ---: | ---: | ---: | ---: | ---: |
| Prior short run | 24.202 s | 15.163M | 10.389 s | 1.910 s | 1.870 s |
| Attempt 16 first | 22.140 s | 10.733M | 7.465 s | 0.155 s | 0.592 s |
| Attempt 16 repeat | 21.217 s | 9.640M | 5.596 s | 0.131 s | 0.514 s |
| Physical wall | 23.07 s first / 21.87 s repeat | — | — | — | — |

Retained-scenario evidence:

| Metric | Attempt 14 | Attempt 16 first | Attempt 16 repeat | Change first / repeat |
| --- | ---: | ---: | ---: | ---: |
| Wall time | 74.04 s | 64.74 s | 60.64 s | 12.6% / 18.1% lower |
| Instrumented total | 72.779 s | 63.576 s | 59.723 s | 12.6% / 17.9% lower |
| Function calls | 51.700M | 26.413M | 22.777M | 48.9% / 56.0% lower |
| Matplotlib draw cumulative | 18.056 s | 10.014 s | 8.235 s | 44.5% / 54.4% lower |
| Constrained layout cumulative | 5.837 s | 0.083 s | 0.072 s | 98.6% / 98.8% lower |
| Axis tick update cumulative | 5.591 s | 1.537 s | 1.254 s | 72.5% / 77.6% lower |
| `query_station_access` cumulative | 7.188 s | 7.438 s | 4.737 s | 3.5% higher / 34.1% lower |

The improvement is stable in two short runs and two full runs, including the
largest call-count and draw-time reductions in the optimization record. It
removes Matplotlib constrained-layout execution from the fixed orbit
time-series figures while retaining their one-time tight layout.

## Attempt 17: station layout interval cache

Status: **effective; retained**

Changed implementation:

- Cache assembled access intervals once per OEM segment layout, snapshot,
  policy revision, station identity, and elevation threshold.
- Reuse full-layout intervals for overlapping ranges by clipping them to the
  requested bounds.
- Preserve the existing range-bound station profile columns and exact/covering
  interval cache semantics.
- Clear layout interval entries with raw station-profile or policy invalidation.

Short-scenario evidence:

| Run | Instrumented total | Function calls | `query_station_access` | Profile events | `_intervals_for_segment` |
| --- | ---: | ---: | ---: | ---: | ---: |
| Attempt 16 repeat | 21.217 s | 9.640M | 5.983 s | 286,962 calls | 34 calls |
| Attempt 17 first | 21.453 s | 8.989M | 2.947 s | 187,357 calls | 24 calls |
| Attempt 17 repeat | 21.893 s | 9.971M | 5.370 s | 245,255 calls | 30 calls |

Full-scenario evidence:

| Metric | Attempt 16 repeat | Attempt 17 first | Attempt 17 repeat | Change repeat |
| --- | ---: | ---: | ---: | ---: |
| Wall time | 60.64 s | 62.82 s | 60.53 s | 0.2% lower |
| Instrumented total | 59.723 s | 61.758 s | 59.454 s | 0.45% lower |
| Function calls | 22.777M | 24.385M | 22.429M | 1.53% lower |
| Matplotlib draw cumulative | 8.235 s | 8.959 s | 8.010 s | 2.73% lower |
| `query_station_access` cumulative | 4.737 s | 5.113 s | 4.919 s | effectively neutral |
| Station profile event cumulative | 2.572 s | 2.199 s | 2.148 s | 16.5% lower |
| `_intervals_for_segment` cumulative | 2.926 s | 2.583 s | 2.496 s | 14.7% lower |

The repeated full run retained the fixed-layout win while reducing interval
assembly and total calls. The cache remains bounded and policy/snapshot-aware,
and it was accepted after the full suite and repeated profile.

## Attempt 18: reused Ground Station static-axis decoration

Status: **effective; retained**

Changed implementation:

- Cache the Ground Station profile xlabel, UTC formatter, ylabel, grid, and
  shared typography once per display-time-zone configuration.
- Reapply only range limits and dynamic profile/legend artists on range refresh.
- Invalidates the static configuration when the display time zone changes.

Short-scenario evidence:

| Run | Instrumented total | Function calls | Matplotlib draw | Set-text | Ground station prepare |
| --- | ---: | ---: | ---: | ---: | ---: |
| Attempt 17 repeat | 21.893 s | 9.971M | 8.203 s | 5.397 s | 5.372 s |
| Attempt 18 first | 21.708 s | 10.293M | 5.790 s | 3.080 s | 5.745 s |
| Attempt 18 repeat | 20.981 s | 8.667M | 7.522 s | 5.053 s | 0.989 s |

The repeated short run lowered total/call/draw work even though station timing
can vary significantly between runs. The display-time-zone invalidation test
preserves formatter identity until the zone changes.

Full-scenario evidence:

| Metric | Attempt 17 repeat | Attempt 18 first | Attempt 18 repeat | Change repeat |
| --- | ---: | ---: | ---: | ---: |
| Wall time | 60.53 s | 61.50 s | 60.19 s | 0.6% lower |
| Instrumented total | 59.454 s | 60.710 s | 59.153 s | 0.51% lower |
| Function calls | 22.429M | 22.157M | 21.622M | 3.60% lower |
| Matplotlib draw cumulative | 8.010 s | 8.626 s | 7.822 s | 2.35% lower |
| Set-text cumulative | 1.022 s | 1.264 s | 0.894 s | 12.5% lower |
| Axis tick update cumulative | 1.275 s | 1.283 s | 1.227 s | 3.76% lower |
| `_prepare_access` cumulative | 4.924 s | 4.939 s | 4.907 s | effectively unchanged |

The repeated full profile confirms the static-axis reuse is stable and
preserves station behavior while reducing text/draw work and primitive calls.

## Attempt 19: Pass/Sky short-scenario profile
Status: **inconclusive; no implementation**

Opened Pass List and Sky View in a temporary state copy for the short
scenario. Evidence:

| Metric | Static-axis short repeat | With Pass/Sky open | Change |
| --- | ---: | ---: | ---: |
| Wall time | 21.83 s | 22.92 s | 5.0% higher |
| Instrumented total | 20.981 s | 22.161 s | 5.6% higher |
| Function calls | 8.667M | 11.178M | 29.0% higher |
| `query_station_access` cumulative | 0.987 s | 6.454 s | run-dependent |
| Pass `_refresh_rows` cumulative | — | 0.162 s | measured only with panels open |
| Sky `_draw_sky_plot` cumulative | — | 0.082 s | measured only with panels open |

The direct Pass/Sky refresh/draw functions are small relative to the station
query and Matplotlib draw totals. No Pass/Sky code change was retained.

## Attempt 20: timer incremental/store idle fast paths
Status: **ineffective; reverted**

Hypothesis:

- Skip `_poll_incremental_load()` after incremental coverage is complete.
- Do not acquire `OemDataStore.snapshot()` in `_drain_store_notices()` when
  the store notice queue is empty.

Short-scenario evidence:

| Run | Instrumented total | Function calls | `_on_timer` cumulative |
| --- | ---: | ---: | ---: |
| Attempt 18 repeat | 20.981 s | 8.667M | 4.068 s |
| Attempt 20 first | 22.647 s | 11.618M | 6.021 s |
| Attempt 20 repeat | 21.366 s | 9.749M | 5.389 s |

The repeated run remained slower than Attempt 18 and increased primitive
work, so neither fast path was retained. The measurement did not establish a
stable timer or notice cost reduction independent of run-to-run station and
draw variation.

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

No implementation is currently justified by an independently stable hotspot:

- `_on_timer` is 3.180 s cumulative in the latest repeated full profile.
- `_refresh_store_data_views` is 2.767 s.
- `_update_time_display` is 0.554 s.
- `_apply_store_context` is 0.488 s.
- `_set_time_series_status` is 0.024 s.

Further work should require a new recorded scenario or a reproducible
cross-run gain in one of these areas rather than speculative cache changes.
