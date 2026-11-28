# play-oem Performance Analysis 1

## Restart baseline

Previous interactive baselines and optimization attempts are intentionally excluded
from this restart. They are not used for comparison.

The new source of truth is the recording of the user's playback-range interactions:
[scenario-recorded.json](scenario-recorded.json). It includes:

- absolute capture time for each range event;
- playback-range start/end as fractions of the OEM coverage;
- measured pause after each prior range change.

Capture environment:

- Commit: `1f22a75c8acc8bdb88c4b53db83570d75daebfa4`
- Interpreter: Python 3.9.6 from `.venv`
- wxPython: 4.2.4
- wxWidgets: 3.2.8
- OEM input: [ISS_2026-05-20.OEM](/Users/jeongyun/Projects/ephem-toolkit/tests/data/ISS_2026-05-20.OEM)
- Config snapshot: [play-oem.toml](play-oem.toml)
- State snapshot: [play-oem-state.toml](play-oem-state.toml)

## Reproduce the first baseline

```sh
docs/architecture/play-oem/performance/analysis-1/profile_play_oem_ui.sh \
  --scenario docs/architecture/play-oem/performance/analysis-1/scenario-recorded.json \
  --output docs/architecture/play-oem/performance/analysis-1/play-oem-restart.prof
```

The launcher loads the captured TOML snapshots from temporary copies, replays the
recorded ranges, and preserves the recorded pauses. The profile and text summary
will be named `play-oem-restart.prof` and `play-oem-restart.txt`.

No optimization change is presumed effective until it is compared against this
new baseline under the recorded scenario.

## Baseline profiles

- Restart profile 2:
  [play-oem-restart-2.prof](play-oem-restart-2.prof),
  [play-oem-restart-2.txt](play-oem-restart-2.txt).
- Restart profile 2 summary: 250,465,229 calls in 353.685 seconds of instrumented
  execution. `query_station_access` ran 1,046 times with 173.299 seconds cumulative
  and 3.757 seconds self-time; `_intervals_for_segment` ran 520 times with
  168.910 seconds cumulative. `station_profile_events` ran 1,549,366 times with
  124.829 seconds cumulative, and `_refine_peak` ran 6,019 times with
  101.496 seconds cumulative.

## Restart profile 2 analysis

### Dominant cost

The new recorded scenario is dominated by station-access range refresh:

- `query_station_access`: 1,046 calls, 173.299 seconds cumulative.
- `_intervals_for_segment`: 520 calls, 168.910 seconds cumulative.
- `station_profile_events`: 1,549,366 calls, 124.829 seconds cumulative.
- `_refine_peak`: 6,019 calls, 101.496 seconds cumulative.
- `earth_fixed_state_at` / `state_at`: 103,470 / 104,036 calls, approximately
  143.326 / 143.584 seconds cumulative.
- `interpolate_view`: 103,998 calls, 81.710 seconds cumulative, including
  33.275 seconds self-time.
- `station_metrics_from_profile_row`: 4,644,458 calls, 18.777 seconds cumulative,
  including 7.602 seconds self-time.

These functions are not independent hotspots. `_intervals_for_segment` invokes
`station_profile_events`; peak refinement invokes `_refine_peak`; peak crossing
refinement repeatedly invokes Earth-fixed state lookup and interpolation. The
station-access chain therefore accounts for most of the measured range-drag cost.

### Range refresh multiplicity

The launcher applied playback bounds 274 times. The application then performed:

- 378 `_dispatch_time_range` calls;
- 260 Ground Station `set_time_range` calls;
- 524 `_prepare_access` calls;
- 1,046 `station_access` queries;
- 262 store data-view refresh calls.

The 274-to-378-to-1046 ratios show that a range update fans out to multiple
station queries and that many intermediate drag states are processed. Incremental
dragging should coalesce updates so only settled or visibly needed ranges are
computed, while playback cursor-only updates continue to avoid station recomputation.

### Timer and event-loop cost

The wx MainLoop accumulated 357.388 seconds in the instrumented run, with
31.182 seconds of MainLoop self-time. `_on_timer` accumulated 46.792 seconds over
1,124 calls, and `_refresh_store_data_views` accumulated 46.407 seconds over
262 calls. `_poll_incremental_load` was comparatively small at 6.654 seconds,
suggesting that incremental loading was not the dominant post-load drag cost.

### Profile limits

The 353.685-second instrumented result is not wall-clock ground truth. `cProfile`
adds substantial overhead and does not distinguish native draw and SPICE work
as cleanly as sampling or tracing. Cumulative time is useful for call-path
comparison, while self-time and call counts identify likely optimization targets.

## Prioritized restart hypotheses

1. **Coalesce drag-range station work.**
   `_apply_playback_bounds` and `_dispatch_time_range` currently fan out during
   drag states. Debounce station queries until drag settle or a bounded frame
   cadence, and retain the latest range for cursor-only updates.

2. **Cache complete station profiles and intervals.**
   520 interval assembly calls and 1,549,366 profile-event calls indicate repeated
   processing of overlapping ranges. Reuse immutable station-profile intervals
   for exact/covering snapshot, station, threshold, bounds, and policy keys; clip
   only at range boundaries. Do not reuse crossed-coverage or policy-invalid data.

3. **Deduplicate Earth-fixed state lookup and interpolation.**
   104,036 state lookups and 103,998 interpolation calls occur across station
   profile and peak refinement. Share exact samples and prepared interpolation
   windows for overlapping queries and range views.

4. **Optimize or bound peak refinement.**
   `_refine_peak` cost 101.496 seconds cumulatively across 6,019 calls. Preserve
   crossing accuracy, but cache refined peaks for identical profile/sample
   brackets and avoid repeated refinement within overlapping range queries.

5. **Vectorize station row metrics.**
   `station_metrics_from_profile_row` ran 4,644,458 times. Its scalar finite,
   elevation, range, azimuth, and access conversion should be batched from profile
   arrays and only scalar objects should be retained at interval-event boundaries.

6. **Batch redraw work.**
   262 store refreshes produced 46.407 seconds of cumulative refresh cost.
   Coalesce one redraw batch per timer tick and avoid range refresh/artist-limit
   recomputation for cursor-only updates.

## Optimization-attempt protocol

For each future attempt:

1. Record the hypothesis and changed files.
2. Reproduce the same recorded scenario with the same `.venv` and snapshots.
3. Capture profile and focused correctness evidence.
4. Mark the result effective, ineffective, inconclusive, or reverted.
5. Document evidence without comparing against discarded prior attempts.

## Attempt 1: coalesce drag-range dispatch

Status: **effective**

Changed behavior:

- A real playback-range drag now suppresses clock-observer range dispatches while
  `_range_dragging` remains set.
- `_apply_playback_bounds` updates the clock and range hint, but does not fan out
  plot/store refreshes for intermediate drag states.
- Drag release dispatches the latest resolved range once.
- The repeatable launcher marks each gradual replay transition as dragging and
  releases it after the final drag step.

Evidence against restart profile 2:

| Metric | Restart baseline | Coalesced attempt | Change |
| --- | ---: | ---: | ---: |
| Instrumented total time | 353.685 s | 62.034 s | 82.5% lower |
| Primitive calls | 250,465,229 | 19,513,395 | 92.2% lower |
| `_dispatch_time_range` calls | 378 | 20 | 94.7% lower |
| `query_station_access` calls | 1,046 | 62 | 94.1% lower |
| `_intervals_for_segment` calls | 520 | 32 | 93.8% lower |
| `station_profile_events` calls | 1,549,366 | 85,264 | 94.5% lower |
| `_refine_peak` calls | 6,019 | 333 | 94.5% lower |
| `earth_fixed_state_at` calls | 103,470 | 5,664 | 94.5% lower |
| `interpolate_view` calls | 103,998 | 6,223 | 94.0% lower |
| `_refresh_store_data_views` calls | 262 | 18 | 93.1% lower |

The attempt kept all intermediate playback bounds in the clock and store range
hint. Only view/data-range fan-out was deferred until drag release, so the latest
settled range remains authoritative.

Correctness evidence:

- `tests/ephem_toolkit/play_oem/test_time_range_actions.py`: 12 passed.
- Range/drag filtering across the app tests: 21 passed.

Profile artifacts:

- [play-oem-attempt-1-coalesce.prof](play-oem-attempt-1-coalesce.prof)
- [play-oem-attempt-1-coalesce.txt](play-oem-attempt-1-coalesce.txt)

## Attempt 2: reuse intervals from covering station-cache windows

Status: **ineffective; reverted**

Added a lookup of containing exact station interval-cache windows and clipped
cached `AccessInterval` objects to the requested settled range.

Profile comparison against Attempt 1:

| Metric | Coalesced attempt | Covering-cache attempt | Change |
| --- | ---: | ---: | ---: |
| Instrumented total time | 62.034 s | 63.175 s | 1.141 s higher |
| Primitive calls | 19,513,395 | 19,132,325 | 381,070 lower |
| `_intervals_for_segment` calls | 32 | 32 | unchanged |
| `station_profile_events` calls | 85,264 | 85,266 | unchanged |
| `_refine_peak` calls | 333 | 333 | unchanged |

The covering lookup did not reduce interval assembly in the recorded scenario,
and it added cost while producing slightly worse instrumented total time.
The implementation was reverted.

Profile artifacts:

- [play-oem-attempt-2-covering-cache.prof](play-oem-attempt-2-covering-cache.prof)
- [play-oem-attempt-2-covering-cache.txt](play-oem-attempt-2-covering-cache.txt)

## Attempt 3: cache profile-row metric conversion within each assembly

Status: **inconclusive; reverted**

Cached `station_metrics_from_profile_row` results by row index while iterating
one station profile, avoiding repeated conversion of the same previous/current/
following row in local peak detection.

Profile comparison against Attempt 1:

| Metric | Coalesced attempt | Row-cache attempt | Change |
| --- | ---: | ---: | ---: |
| Instrumented total time | 62.034 s | 62.566 s | 0.532 s higher |
| Primitive calls | 19,513,395 | 18,494,635 | 1,018,760 lower |
| `station_metrics_from_profile_row` calls | 255,568 | 88,234 | 65.5% lower |
| `station_metrics_from_profile_row` cumulative | 0.904 s | 0.388 s | 57.1% lower |
| `query_station_access` cumulative | 14.959 s | 16.237 s | 1.278 s higher |

The local conversion cache reduced the target function substantially but did not
lower the end-to-end profile and correlated with higher query cost in this run,
so it was not retained.

Profile artifacts:

- [play-oem-attempt-3-profile-row-cache.prof](play-oem-attempt-3-profile-row-cache.prof)
- [play-oem-attempt-3-profile-row-cache.txt](play-oem-attempt-3-profile-row-cache.txt)

## Attempt 4: cache exact peak-refinement brackets

Status: **ineffective; reverted**

Added a bounded bracket cache to snapshot-bound station cursors for exact
`(station, low_s, high_s)` peak refinement calls.

Profile comparison against Attempt 1:

| Metric | Coalesced attempt | Peak-cache attempt | Change |
| --- | ---: | ---: | ---: |
| Instrumented total time | 62.034 s | 62.729 s | 0.695 s higher |
| `_refine_peak` calls | 333 | 333 | unchanged |
| `_refine_peak` cumulative | 5.284 s | 5.286 s | unchanged |
| `_intervals_for_segment` calls | 32 | 32 | unchanged |

The bracket cache found no repeated exact refinements in this recorded scenario;
it did not reduce `_refine_peak` work or end-to-end time. The implementation was
reverted.

Profile artifacts:

- [play-oem-attempt-4-peak-cache.prof](play-oem-attempt-4-peak-cache.prof)
- [play-oem-attempt-4-peak-cache.txt](play-oem-attempt-4-peak-cache.txt)

## Attempt 5: cache Earth-fixed cursor-state results

Status: **effective**

Added a bounded store-owned cache for exact Earth-fixed `CursorState` results,
keyed by snapshot epoch, policy revision, interpolation method/degree, and
timestamp. Cached entries are invalidated across OEM resets and remain separated
by interpolation policy.

Profile comparison against Attempt 1:

| Metric | Coalesced attempt | Earth-state-cache attempt | Change |
| --- | ---: | ---: | ---: |
| Instrumented total time | 62.034 s | 51.935 s | 16.3% lower |
| Primitive calls | 19,513,395 | 14,860,382 | 23.8% lower |
| `earth_fixed_state_at` cumulative | 8.979 s | 1.697 s | 81.1% lower |
| `state_at` cumulative | 9.320 s | 2.041 s | 78.1% lower |
| `interpolate_view` calls | 6,223 | 781 | 87.5% lower |
| `query_station_access` cumulative | 14.959 s | 2.932 s | 80.4% lower |
| `_intervals_for_segment` calls | 32 | 28 | 12.5% lower |
| `_refine_peak` calls | 333 | 282 | 15.3% lower |

The cache converts repeated exact Earth-fixed timestamp lookups from repeated
interpolation and frame work into direct store hits. It is bounded to 8192 entries
and is cleared on raw OEM epoch reset.

Correctness evidence:

- Store, station, and range test modules: 94 passed.
- Repeated Earth-fixed lookup test verifies object reuse and cache population.

Profile artifacts:

- [play-oem-attempt-5-earth-state-cache.prof](play-oem-attempt-5-earth-state-cache.prof)
- [play-oem-attempt-5-earth-state-cache.txt](play-oem-attempt-5-earth-state-cache.txt)

## Attempt 6: route store refresh redraws through the shared queue

Status: **effective**

Changed `_refresh_store_data_views` so updated panels mark and queue redraw work
through `_queue_time_range_redraw` instead of calling `canvas.draw_idle()` or
`panel.request_redraw()` immediately per panel.

Profile comparison against Attempt 5:

| Metric | Earth-state-cache attempt | Redraw-batch attempt | Change |
| --- | ---: | ---: | ---: |
| Instrumented total time | 51.935 s | 51.834 s | 0.101 s lower |
| Primitive calls | 14,860,382 | 14,736,355 | 124,027 lower |
| Immediate `request_redraw` calls | 49 | 5 | 89.8% lower |
| `query_station_access` cumulative | 2.932 s | 1.801 s | 38.6% lower |
| `earth_fixed_state_at` cumulative | 1.697 s | 1.477 s | 13.0% lower |
| `interpolate_view` calls | 781 | 661 | 15.4% lower |

The change also removes immediate Matplotlib redraw bypasses from store refresh
and relies on the workspace's existing deduplicating redraw queue.

Correctness evidence:

- Store, station, range, and app test modules: 208 passed.
- The focused store-refresh/range-drag set passed separately.

Profile artifacts:

- [play-oem-attempt-6-redraw-batch.prof](play-oem-attempt-6-redraw-batch.prof)
- [play-oem-attempt-6-redraw-batch.txt](play-oem-attempt-6-redraw-batch.txt)

## Attempt 7: vectorize station profile-row metric conversion

Status: **effective**

Added batch conversion for all profile rows before `station_profile_events`
iterates local samples. Finite rows are converted to `StationMetrics` in one
NumPy pass; invalid rows become `None`.

Profile comparison against Attempt 6:

| Metric | Redraw-batch attempt | Vectorized-profile attempt | Change |
| --- | ---: | ---: | ---: |
| Instrumented total time | 51.834 s | 51.109 s | 1.4% lower |
| Primitive calls | 14,736,355 | 13,830,474 | 6.1% lower |
| `station_metrics_from_profile_row` calls | 210,558 | 28 | 99.99% lower |
| `station_metrics_from_profile_rows` cumulative | N/A | 0.332 s | Batched converter |
| `station_profile_events` cumulative | 1.107 s | 0.823 s | 25.7% lower |
| `_intervals_for_segment` cumulative | 1.250 s | 0.968 s | 22.6% lower |

The batched converter also removed repeated `np.isfinite(row).all()` calls for
each scalar sample, while preserving the existing scalar API for direct callers.

Correctness evidence:

- Store, station, range, and app test modules: 209 passed.
- Added a finite/invalid/elevation-access threshold batch-conversion test.

Profile artifacts:

- [play-oem-attempt-7-profile-vectorization.prof](play-oem-attempt-7-profile-vectorization.prof)
- [play-oem-attempt-7-profile-vectorization.txt](play-oem-attempt-7-profile-vectorization.txt)

## Attempt 8: coalesce incremental initial-plot calls

Status: **ineffective; reverted**

Removed the `_advance_initial_plot()` call from each raw-append event, relying
only on the post-event-batch call in `_poll_incremental_load`.

Profile comparison against Attempt 7:

| Metric | Vectorized-profile attempt | Incremental-coalesce attempt | Change |
| --- | ---: | ---: | ---: |
| Instrumented total time | 51.109 s | 51.392 s | 0.283 s higher |
| `_advance_initial_plot` calls | 1022 | 1012 | 10 lower |
| `_poll_incremental_load` cumulative | 4.472 s | 4.295 s | 0.177 s lower |
| `_refresh_incremental_data_views` cumulative | 4.088 s | 3.909 s | 0.179 s lower |
| `query_station_access` cumulative | 3.831 s | 6.175 s | 2.344 s higher |

The duplicate-call removal did not improve the end-to-end recorded run and
correlated with a higher station-query cumulative cost. The implementation was
reverted.

Profile artifacts:

- [play-oem-attempt-8-incremental-coalesce.prof](play-oem-attempt-8-incremental-coalesce.prof)
- [play-oem-attempt-8-incremental-coalesce.txt](play-oem-attempt-8-incremental-coalesce.txt)

## Drag feedback behavior: 5 Hz range dispatch

Status: **feature-preserving behavior retained**

Playback-range drags no longer suppress all data-view range updates. The app now:

- dispatches the first changed playback range immediately;
- dispatches intermediate drag ranges at 5 Hz (200 ms cadence);
- dispatches the latest settled range once on drag release.

Profile comparison against the no-drag-feedback vectorized build:

| Metric | No-feedback vectorized build | 5 Hz drag-feedback build | Change |
| --- | ---: | ---: | ---: |
| Instrumented total time | 51.109 s | 172.922 s | 121.813 s higher |
| `_dispatch_time_range` calls | 18 | 278 | 15.4x |
| `query_station_access` calls | 60 | 1,046 | 17.4x |
| `_intervals_for_segment` calls | 28 | 520 | 18.6x |
| `_refresh_store_data_views` calls | 16 | 262 | 16.4x |

This confirms that preserving visible data-view feedback during a drag costs
station-access work. The retained cadence is a deliberate 5 Hz bound rather than
an unbounded dispatch on every pointer event.

Correctness evidence:

- Store, station, range, and app test modules: 209 passed.
- Added a monotonic-cadence test for immediate, throttled, and settled ranges.

Profile artifacts:

- [play-oem-attempt-9-drag-feedback-5hz.prof](play-oem-attempt-9-drag-feedback-5hz.prof)
- [play-oem-attempt-9-drag-feedback-5hz.txt](play-oem-attempt-9-drag-feedback-5hz.txt)

## Restart baseline versus retained current build

The direct current comparison uses the retained 5 Hz drag-feedback build:
`play-oem-attempt-9-drag-feedback-5hz.prof`. Earlier optimized builds are not
substituted for it because they suppressed drag data-view feedback.

| Metric | Restart profile 2 | Retained 5 Hz build | Change |
| --- | ---: | ---: | ---: |
| Instrumented total time | 353.685 s | 172.922 s | 51.1% lower |
| Primitive calls | 250,465,229 | 163,448,948 | 34.8% lower |
| `_dispatch_time_range` calls | 378 | 278 | 26.5% lower |
| `query_station_access` calls | 1,046 | 1,046 | unchanged |
| `_intervals_for_segment` calls | 520 | 520 | unchanged |
| `station_profile_events` calls | 1,549,366 | 1,549,366 | unchanged |
| `_refresh_store_data_views` calls | 262 | 262 | unchanged |

The retained 5 Hz build is faster than restart profile 2, but it restores the
intermediate station/range dispatch fan-out that the earlier no-feedback build
removed. The no-feedback `Attempt 7` vectorized build is the lower-cost
optimization comparison at 51.109 instrumented seconds, but it is not the retained
current behavior because it did not redraw data views during dragging.
