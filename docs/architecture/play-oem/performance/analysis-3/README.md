# play-oem Performance Analysis 3

## Source baseline

Analysis 3 evaluates internal data access and data structure efficiency. It
does not treat Matplotlib drawing, wx artist creation, timer dispatch, or panel
refreshing as the primary optimization target.

The source baseline is the current repository implementation after the retained
behavior and optimizations from analysis 1 and analysis 2:

- 5 Hz drag-range feedback;
- Earth-fixed `CursorState` caching;
- shared redraw batching;
- batched station-profile row metric conversion;
- store-owned lazy raw and derived data;
- covering station interval reuse;
- in-place store-backed view refresh where structure permits.

The baseline workload is the recorded playback-range interaction copied from
`analysis-1`:
[scenario-recorded.json](scenario-recorded.json). It contains the recorded
playback-range states and fractional bounds relative to OEM coverage.

Captured inputs:

- OEM: [ISS_2026-05-20.OEM](/Users/jeongyun/Projects/ephem-toolkit/tests/data/ISS_2026-05-20.OEM)
- Config: [play-oem.toml](play-oem.toml)
- State: [play-oem-state.toml](play-oem-state.toml)
- Recorded scenario: [scenario-recorded.json](scenario-recorded.json)
- Profiler: [profile_play_oem_ui.py](profile_play_oem_ui.py)
- Launcher: [profile_play_oem_ui.sh](profile_play_oem_ui.sh)
- Interpreter: `.venv/bin/python`
- wxPython: 4.2.4
- wxWidgets: 3.2.8

No optimization change is presumed effective until it is compared against a
captured analysis-3 baseline and checked for data, cache, and coverage parity.

## Measurement scope

This study follows data as it moves through the internal store:

- snapshot epoch and policy validation;
- raw sample and segment lookup;
- state exact/interpolation lookup;
- Earth-fixed conversion and cursor-state caching;
- derived chunk readiness and memo behavior;
- station profile storage and row conversion;
- peak and access-crossing refinement;
- interval and layout cache lookup;
- covering-range cache scans;
- ground-track, footprint, and prefetch/scheduler structures.

Excluded as optimization targets:

- Matplotlib figure drawing;
- wx paint and bitmap conversion;
- panel artist creation and reuse;
- timer cadence and range-event dispatch;
- general UI layout and rendering policy.

The existing UI profiler remains useful for repeatable scenario replay, but
analysis-3 additions should call store APIs directly or add store instrumentation
so internal cost is isolated from GUI rendering.

## Reproduce the source baseline

Run the copied repeatable launcher from the repository root:

```sh
docs/architecture/play-oem/performance/analysis-3/profile_play_oem_ui.sh \
  --scenario docs/architecture/play-oem/performance/analysis-3/scenario-recorded.json \
  --config docs/architecture/play-oem/performance/analysis-3/play-oem.toml \
  --state docs/architecture/play-oem/performance/analysis-3/play-oem-state.toml \
  --output docs/architecture/play-oem/performance/analysis-3/play-oem-baseline.prof
```

The launcher copies the TOML snapshots to temporary files and always executes
the profiler with `.venv/bin/python`. The profile and text summary are written as:

- `play-oem-baseline.prof`
- `play-oem-baseline.txt`

This baseline currently provides UI replay evidence. It is not yet the store-only
baseline required for analysis-3 and should not be used as proof of an internal
data-path improvement.

## Store-only baseline

The next baseline artifact should be a store-only profiler that:

- loads the existing OEM fixture through `OemDataStore`;
- replays the recorded range sequence without creating a wx application;
- optionally loads a station list from one to ten stations;
- measures settled ranges, overlapping ranges, adjacent ranges, repeated ranges,
  and cursor-only exact timestamp lookups;
- reports wall-clock median and cProfile totals separately.

Required output names:

- `profile_oem_data_paths.py`
- `profile_oem_data_paths.sh`
- `play-oem-data-baseline.prof`
- `play-oem-data-baseline.txt`

The store-only baseline should capture at least:

- wall time and cProfile primitive-call count;
- exact and interpolated `state_at` counts;
- Earth-fixed state lookups and cache hit/miss counts;
- Earth-fixed source-state conversions;
- `station_access` and `query_station_access` counts;
- `_station_profile_events`, `_intervals_for_segment`, and `_refine_peak` counts;
- `_row_spans` and `compute_missing_chunk_ranges` counts;
- derived chunk memo hits and misses;
- exact and layout station interval cache hits;
- covering-range cache scans and evictions;
- derived-buffer resident bytes and eviction behavior.

No cache or chunk counter should be inferred from cProfile alone. Add or reuse
observable store counters before interpreting lookup behavior.

## Workloads

The recorded range replay is the real-workload regression:

| Workload | Purpose |
|---|---|
| Recorded ranges, 1 station | Retained behavior and cache reuse |
| Recorded ranges, 3 stations | Shared state and cross-station scaling |
| Recorded ranges, 10 stations | Per-station key/layout scaling |
| One-day range | Fast profile assembly and interval reuse |
| Full coverage range | Large ready-mask and layout coverage |
| Repeated exact range | Cache hit and covering-range lookup |
| Adjacent/overlapping ranges | Range-index and interval clipping behavior |
| Cursor-only timestamps | Exact and interpolated state lookup |

Use unprofiled wall-clock medians for keep/revert decisions. Use cProfile totals
to identify call paths and primitive-call multiplication. cProfile overhead must
not be presented as wall-clock ground truth.

## Internal analysis plan

### Snapshot and raw-array access

Inspect:

- `StoreSnapshot.raw` slicing and identity;
- `np.searchsorted(times, query_time)`;
- repeated `np.searchsorted(snapshot.segment_ids, ...)`;
- frame-name and policy validation;
- repeated epoch/policy lock checks.

Candidate structure:

- store-owned exact timestamp and segment indexes;
- immutable segment-boundary arrays;
- separate exact lookup from interpolation-window lookup;
- no raw-history copy unless mutation isolation requires it.

Preserve snapshot epoch, policy revision, segment, and out-of-range semantics.

### Chunk metadata and derived-range access

Inspect:

- `_row_spans`;
- `ChunkMemo`;
- `_chunk_ranges`;
- ready masks;
- chunk touch and pin/release behavior;
- derived-buffer evictions.

Candidate structure:

- chunk-first missing-range detection;
- chunk-aligned memo and range conversion;
- bounded requested-range pinning;
- removal of redundant mask-transition work if measured.

Preserve loading-time tentative data, epoch invalidation, and cancellation behavior.

### Cache keys and lookup efficiency

Measure:

- `_earth_fixed_cursor_cache`;
- `_earth_fixed_state_cache`;
- `_ground_track_cache`;
- `_station_interval_cache`;
- `_station_interval_layout_cache`;
- `_footprint_cache`;
- `_find_covering_station_intervals`.

Candidate structure:

- bounded range index or bucketed covering-range lookup;
- separate hot exact-state lookup from interval range scans;
- stable normalized cache keys;
- explicit epoch, policy, station, threshold, and layout identity.

A cache index must not become stale or become a second source of truth. Exact
and layout cache fallback behavior remains mandatory.

### Earth-fixed state conversion

Measure:

- exact timestamp hit/miss;
- interpolation-window hit/miss;
- source sample conversion count;
- `np.stack` allocations;
- frame-conversion overhead;
- cache lock hold time.

Candidate structure:

- batch adjacent Earth-fixed timestamp conversions;
- cache immutable interpolation windows or source rows;
- finer-grained converted-source caching;
- integer or quantized timestamp keys only if result identity is preserved.

Cache invalidation and float-timestamp parity are correctness gates.

### Station profile and interval assembly

Measure:

- profile-row metric conversion;
- local peak candidate evaluation;
- `_refine_peak`;
- interval layout assembly;
- layout cache hits;
- threshold and elevation access behavior.

Candidate structure:

- one batched metric conversion per profile;
- no duplicate refinement brackets;
- layout intervals keyed by layout identity and threshold;
- array/binary-search fast paths only with crossing parity evidence;
- immutable profile arrays with range-local views.

Preserve interval gap flags, coverage, access thresholds, and the 0.5-second
crossing tolerance.

### Prefetch and scheduler structures

Measure:

- `_scheduled_work`;
- `_work_queue`;
- `_active_work`;
- range hints and tier interest;
- one-worker scheduler lock/queue behavior.

Candidate structure:

- overlap and latest-range coalescing;
- priority separation for current-range versus speculative work;
- stale-work pruning only after epoch and cancellation evidence.

Do not make derived availability less predictable or schedule stale epochs.

## Optimization-attempt protocol

Run candidate attempts in increasing risk and reversibility:

1. Add observable cache, chunk, and station counters.
2. Index station interval covering-range lookup.
3. Coalesce station layout/profile requests.
4. Optimize Earth-fixed exact/interpolation keys.
5. Use chunk-first derived range computation.
6. Add station profile/interval fast paths.
7. Coalesce prefetch/scheduler work.

Each attempt should contain at most one primary implementation change.
Combined changes must be isolated so they can be reverted independently.

For each attempt add a README section containing:

- Hypothesis;
- Changed files;
- Baseline and attempt wall-clock metrics;
- cProfile total and primitive-call metrics;
- cache, chunk, and memory effects;
- focused correctness evidence;
- status: `effective`, `ineffective`, `inconclusive`, or `reverted`;
- reason for retaining or reverting the change.

Only compare against the captured analysis-3 source baseline or the immediately
preceding retained implementation. Do not substitute analysis-1 or analysis-2
profiles for the internal baseline.

## Baseline profiles

### UI replay baseline

- Profile: [play-oem-baseline.prof](play-oem-baseline.prof)
- Text summary: [play-oem-baseline.txt](play-oem-baseline.txt)
- Instrumented total: 60.368 seconds
- Primitive calls: 22,502,971
- Total function calls: 22,888,691
- Captured wall/process result: 60.980 seconds

Dominant recorded hotspots:

| Function/path | Calls | Cumulative |
|---|---:|---:|
| Matplotlib `MainLoop` | 1 | 59.752 s |
| `Matplotlib`/wx `backend_wxagg.draw` | 414 | 8.507 s |
| `_dispatch_time_range` | 91 | 7.578 s |
| `_apply_playback_bounds` | 274 | 7.062 s |
| Ground Station `set_time_range` | 84 | 6.832 s |
| `_prepare_access` | 90 | 5.030 s |
| `query_station_access` | 172 | 5.014 s |
| `_intervals_for_segment` | 166 | 2.552 s |
| `_refresh_store_data_views` | 86 | 3.046 s |
| `_poll_incremental_load` | 1363 | 2.808 s |

The replay baseline still includes wx and Matplotlib work. It establishes a
repeatable source-behavior baseline and isolates the internal data path for
later store-only attempts.

### Store-only baseline

- Profile: [play-oem-data-baseline.prof](play-oem-data-baseline.prof)
- Text summary: [play-oem-data-baseline.txt](play-oem-data-baseline.txt)
- Instrumented total: 13.588 seconds
- Primitive calls: 33,771,251
- Total function calls: 33,812,265
- State lookup median: 0.000090 s

Recorded range sweep wall-clock medians (warm-up excluded):

| Stations | Station queries | Median |
|---:|---:|---:|
| 1 | 14 | 0.011251 s |
| 3 | 42 | 0.018652 s |
| 10 | 140 | 2.564496 s |

Dominant store-only call paths:

| Function/path | Calls | Cumulative |
|---|---:|---:|
| `query_station_access` | 588 | 13.451 s |
| `_intervals_for_segment` | 462 | 8.657 s |
| `station_profile_events` | 1,387,419 | 7.607 s |
| `earth_fixed_state_at` | 296,430 | 6.386 s |
| `state_at` | 296,433 | 6.297 s |
| `_compute_station_profile_ranges` | 588 | 4.550 s |
| `_refine_peak` | 13,466 | 4.135 s |
| `station_metrics_from_ecef` | 296,427 | 2.921 s |
| `station_metrics`/profile conversion | 177,503 | 1.808 s |
| `interpolate_view` | 47,747 | 0.437 s |

The dominant retained cost is repeated station-profile and refined-state work,
not raw ingestion or snapshot construction. The 10-station repeated sweep
accounts for most of the store-only wall-clock cost.

## Attempt 1: bounded covering station-cache index

Status: **ineffective; reverted**

Hypothesis:

- Replace linear `_station_interval_cache` scans in
  `_find_covering_station_intervals` with a bounded prefix/range index.
- Preserve exact cache, layout cache, threshold, epoch, revision, and policy keys.

Changed implementation:

- Added a station-interval covering index and maintenance on cache insert/eviction.
- Routed covering-range lookup through the index instead of iterating every exact entry.

Profile comparison against the store-only baseline:

| Metric | Baseline | Index attempt |
|---|---:|---:|
| Instrumented total | 13.588 s | 13.675 s |
| Primitive calls | 33,771,251 | 33,769,405 |
| 10-station median | 2.564496 s | 2.573032 s |
| `query_station_access` | 13.451 s | 13.607 s |
| `_intervals_for_segment` | 8.657 s | 8.777 s |

Correctness evidence:

- 23 focused station/interval/cache tests passed.
- The implementation was fully reverted after the run showed no wall-clock or
  call-count benefit.

Profile artifacts:

- [play-oem-attempt-1-covering-index.prof](play-oem-attempt-1-covering-index.prof)
- [play-oem-attempt-1-covering-index.txt](play-oem-attempt-1-covering-index.txt)

## Attempt 2: store-owned station metrics cache

Status: **ineffective; reverted**

Hypothesis:

- Cache exact station-relative metrics for refined peak/crossing timestamps.
- Reuse topocentric metric conversion across repeated station ranges and stations.

Changed implementation:

- Added a bounded store-owned `(epoch, policy, station, timestamp)` metric cache.
- Routed `_refine_peak` and `_refine_crossing` through the cache-aware cursor.
- Cleared station metrics on epoch/policy invalidation.

Profile comparison against the store-only baseline:

| Metric | Baseline | Metrics-cache attempt |
|---|---:|---:|
| Instrumented total | 13.588 s | 13.308 s |
| Primitive calls | 33,771,251 | 31,351,577 |
| 10-station median | 2.564496 s | 2.603065 s |
| `earth_fixed_state_at` calls | 296,430 | 157,453 |
| `station_metrics_from_ecef` | 296,427 calls | 157,450 calls |

Correctness evidence:

- 4 focused Earth-fixed/cache tests passed.
- 13 station-analysis tests passed.
- The implementation was reverted because the cProfile call reduction did not
  translate into a lower 10-station wall-clock median and added cache/lifecycle
  machinery that did not meet the success threshold.

Profile artifacts:

- [play-oem-attempt-2-metrics-cache.prof](play-oem-attempt-2-metrics-cache.prof)
- [play-oem-attempt-2-metrics-cache.txt](play-oem-attempt-2-metrics-cache.txt)

## Correctness gates

Before an attempt is marked effective:

- store snapshot tests pass;
- chunk memo and derived-buffer lifecycle tests pass;
- Earth-fixed state and interpolation tests pass;
- Ground Track and footprint tests pass;
- station profile, interval, gap, threshold, and coverage tests pass;
- focused `play-oem` test modules pass;
- the broader affected test suite has no regression;
- `git diff --check` passes;
- stale epoch, policy revision, station threshold, layout, and coverage cases
  remain covered.

Use `.venv/bin/python -m pytest` for affected tests. Start with the smallest
focused modules, then broaden to the affected store and `play-oem` suite.

## Success criteria

Retain an implementation only if it:

1. reduces measured internal data-path cost or primitive-call work;
2. preserves snapshot, interpolation, coverage, station, cache, and loading semantics;
3. passes focused and broader affected tests;
4. does not cause uncontrolled memory growth or stale-data behavior;
5. is smaller and clearer than a repeated view/workaround it replaces.

No fixed percentage improvement is assumed before measurement. Run-to-run noise
and cProfile overhead must be reported rather than hidden.
