# `play-oem` Data-Path Performance Report

## Executive summary

This work improved OEM preparation and incremental graph refresh for `play-oem`. On the
15-day JPSS-1 sample file, median full playback preparation fell from 3.219 s to 1.642 s
(49% faster). Vectorized orbit-series computation, shared station-position conversions,
faster common-format timestamp parsing, and retained caches contributed to the data-path
improvements. Existing plots now update in place during incremental loading when their
structure permits.

The complete repository test suite passed: 1,836 passed, 4 skipped, and 3 deselected.
In the final visible GUI probe, all 50 observed view and figure identities were retained
through 25 incremental refreshes, and synchronous refresh duration peaked at 12.0 ms.
Occasional long wx timer gaps remained while loading; the probe does not establish their
cause.

This report covers OEM preparation, range caches, and loading-time view refresh. Rendering
rate and cursor-drawing work are documented separately in
[PLAY_OEM_PERFORMANCE_REPORT.md](../PLAY_OEM_PERFORMANCE_REPORT.md). The OEM-to-view dataflow
investigation is in [PLAY_OEM_DATAFLOW.md](../PLAY_OEM_DATAFLOW.md).

## Measurement conditions

Data measurements used `tests/data/JPSS-1.oem` (21,601 samples at 60-second spacing over
15 days), Python 3.9.6, macOS 26.7.1 arm64, unprofiled wall-clock timing, and three-run
medians. Ground Track and Access measurements used a one-day range. GUI responsiveness was
measured in a visible wx session using a 10 ms probe timer during incremental loading and
for two seconds after loading finished. The application used its Matplotlib fallback because
VTK did not complete its initial render in the final probe.

These are local measurements, not release benchmarks. GUI results are individual probe
runs and are sensitive to environment and workload.

## Results

| Measurement | Baseline | Final | Change |
|---|---:|---:|---:|
| OEM parsing | 1.715 s | 1.318 s | 23% faster |
| `compute_orbit_series` | 1.438 s | 0.284 s | 80% faster |
| Full playback preparation | 3.219 s | 1.642 s | 49% faster |
| One-day Ground Track conversion | 0.451 s | 0.453 s | Approximately unchanged |
| One-day Access, 1 station | 2.780 s | 2.759 s | Approximately unchanged |
| One-day Access, 3 stations | 6.938 s | 5.393 s | 22% faster |
| One-day Access, 10 stations | 21.440 s | 14.613 s | 32% faster |

Final GUI probe:

| Measure | During load | Post-load |
|---|---:|---:|
| Timer-gap samples | 41 | 202 |
| Median timer gap | 33.6 ms | 10.0 ms |
| Maximum timer gap | 757.5 ms | 22.2 ms |
| Gaps over 100 ms | 3 | 0 |

Across 25 measured panel refreshes, all 50 observed view identities and all 50 Matplotlib
figure identities were retained. The longest synchronous refresh took 12.0 ms. Thus panel
reconstruction was avoided, but occasional delays during loading were not eliminated.

## Implemented changes

### Shared Earth-fixed positions for station analysis

Station access calculations now share converted Earth-fixed positions for a common analysis
window. This removes repeated conversions across stations while keeping station-specific
topocentric metric calculations independent. Cache invalidation on source changes is covered
by regression tests. Multi-station analysis improved, although runtime still scales with
station count.

### Vectorized orbit-series direction calculations

RTN direction-vector derivation now uses batched cross-products, masked normalization, and
array operations instead of a per-sample Python loop. Tests compare results against the scalar
reference, including degenerate states and different streaming batch boundaries. The observed
maximum angle difference was approximately 2.2e-15 degrees; parity tests use a 1e-12-degree
absolute tolerance.

### Faster common timestamp parsing

The common fixed-format timestamp path now constructs datetimes directly from validated
calendar fields. The existing `strptime` path remains for formats outside the fast path,
including fractions beyond Python datetime's six-digit precision. Parser tests cover accepted
formats and existing error behavior.

### Cache retention across incremental appends

Earth-fixed position storage now retains computed positions when a new source is an unchanged
prefix extension and grows capacity geometrically. Station-access cache entries are retained
only when their analysis windows are conservatively separated from the previous coverage edge
by the interpolation-support margin. Tail windows are recomputed. The controller also
invalidates Ground Track plot coordinates when an appended batch intersects the active plot
range.

Regression tests cover prefix reuse, safe early-window reuse, and recomputation of a tail
window. This preserves reuse without assuming that interpolation results near the appended
boundary remain unchanged.

### In-place incremental view updates

Time-series views replace their history source arrays and reuse line artists when segment
structure remains compatible. Matplotlib and VTK trajectory views update their path data in
place. If data shape, time unit, segment structure, or view layout is incompatible, the
existing rebuild path remains available.

Tests verify updated samples, retained figures and artists, and the fallback for incompatible
structures. The GUI probe confirms that the refresh path kept existing panels and figures in
place for the observed workload.

## Validation

- Full repository test suite: **1,836 passed, 4 skipped, 3 deselected**.
- Python 3.9 compilation checks passed for the changed playback modules and benchmark.
- `git diff --check` passed.
- Pylance reported no diagnostics in the changed implementation files, apart from existing
  unused-parameter warnings in unrelated callbacks and unused `coverage` parameters in the
  trajectory range methods.

## Remaining observations

The final loading probe recorded three timer gaps over 100 ms and a maximum gap of 757.5 ms.
Post-load responsiveness was substantially steadier, and measured panel refreshes were short,
but the probe cannot attribute the loading-time gaps to worker-thread GIL contention, batch
installation, or another cause. No thread or batch-scheduling changes were made without that
evidence.

If investigating further, measure loader-thread CPU/GIL activity and per-tick OEM batch
installation on the same workload. Access analysis also remains the largest measured
multi-station cost; the final one-day medians were 2.759 s for one station and 14.613 s for
ten stations.

## Reproducing the measurements

Run the data benchmark from the repository root:

```text
python3 scripts/bench_play_oem.py --repeats 3 --range-days 1
```

Run the visible GUI timer and refresh probe:

```text
python3 scripts/bench_play_oem.py --gui-stall-probe --skip-data-benchmarks
```
