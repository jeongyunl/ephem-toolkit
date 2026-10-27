# play-oem OEM Dataflow and Computation Efficiency

## Summary

This document describes how OEM data flows through `play-oem` into its graphs, including
incremental loading, range-limited analysis, cache retention, and in-place panel refresh.
The dataflow diagram is [PLAY_OEM_DATAFLOW.mmd](./PLAY_OEM_DATAFLOW.mmd).

On `tests/data/JPSS-1.oem` (21,601 samples across 15 days), the latest three-run medians
were 1.318 s for parsing, 0.284 s for `compute_orbit_series`, and 1.642 s for full playback
preparation. Ground Track and station-access analyses are limited to the active plot range
plus their support margins. During incremental loading, compatible views update existing
artists instead of rebuilding their panels.

The default playback range is the first two days of the OEM, and the default plot range
follows playback. Saved settings override those defaults.

## Dataflow

1. **Read and prepare (loader thread).** The incremental loader reads OEM batches.
   `IncrementalPlaybackPreparer` appends each batch to `AppendablePlaybackData`, which updates:
   - `OrbitSeriesAccumulator`, deriving series for new rows and the batch boundary.
   - `OemCursor`, extending timestamps, states, segment IDs, and interpolation support.
   - `GroundTrackSource`, exposing the cursor's growing sample arrays for range analyses.

2. **Install (wx thread).** `_poll_incremental_load` installs prepared batches. Plot refreshes
   are throttled to at most once every five seconds while loading and forced at completion.
   Large preview series are downsampled for rendering. Ground Station Access and Passes panels
   are deferred during loading and their analyses are warmed off-thread at completion.

3. **Prepare visible graph data.**
   - **2D histories** receive the current (possibly downsampled) `OrbitSeries`. Their
     `SegmentedPlotHistory` instances select samples inside the plot bounds and decimate each
     displayed segment.
   - **3D trajectory** views select plot-range samples and decimate the displayed path in the
     Matplotlib or VTK backend.
   - **Ground Track** converts only source samples in the plot range plus a margin to
     Earth-fixed and WGS-84 coordinates.
   - **Ground Station Access and Passes** evaluate a 30-second grid over the plot range plus
     an analysis margin. Per-window Earth-fixed positions are shared across stations.

4. **Refresh existing panels.** Time-series views update their history arrays and retain line
   artists when their segment structure remains compatible. Both 3D backends update their
   path data in place. If data shape or view structure is incompatible, the controller falls
   back to replacing the view. Deferred station panels are refreshed after their analysis is
   ready.

5. **Retain caches across appends.** Ground Track Earth-fixed positions are retained when the
   new sample source is an unchanged prefix extension, with geometrically grown backing
   storage. Station-access results are retained only for analysis windows conservatively
   separated from the old coverage edge by an interpolation-support margin. Tail windows are
   recomputed; a changed source prefix or interpolation policy invalidates cached results.
   Ground Track plot coordinates are invalidated when an appended batch intersects the active
   plot range.

6. **Playback.** Each frame advances the clock and resolves the cursor state. Ground-station
   views derive the current station metrics from that state. This per-frame cursor and station
   calculation is distinct from the static range analyses above.

## Latest measurements

Three-run medians on Python 3.9.6 / macOS 26.7.1 arm64, unprofiled, using
`tests/data/JPSS-1.oem`:

| Stage | Baseline | Latest | Notes |
|---|---:|---:|---|
| OEM parsing | 1.715 s | 1.318 s | Fixed-format timestamp fast path |
| `compute_orbit_series` | 1.438 s | 0.284 s | Batched RTN direction calculations |
| Full playback preparation | 3.219 s | 1.642 s | 49% faster overall |
| One-day Ground Track conversion | 0.451 s | 0.453 s | Approximately unchanged |
| One-day Access, 1 station | 2.780 s | 2.759 s | Approximately unchanged |
| One-day Access, 3 stations | 6.938 s | 5.393 s | Shared position conversions |
| One-day Access, 10 stations | 21.440 s | 14.613 s | Station-specific metric work remains |

In the final visible wx probe, panel refreshes retained all 50 observed view and figure
identities across 25 refreshes; synchronous refreshes peaked at 12 ms. During loading, timer
gaps had a 33.6 ms median and a 757.5 ms maximum, with three gaps over 100 ms. Post-load timer
gaps peaked at 22.2 ms, with none over 100 ms. The probe does not isolate the cause of the
remaining loading-time delays.

See [PLAY_OEM_DATA_PATH_PERFORMANCE_REPORT.md](./old/PLAY_OEM_DATA_PATH_PERFORMANCE_REPORT.md)
for implementation and validation details, and
[PLAY_OEM_PERFORMANCE_REPORT.md](./PLAY_OEM_PERFORMANCE_REPORT.md) for playback render-rate
measurements.

## Remaining efficiency considerations

- Access analysis still scales with station count because topocentric metrics are station
  specific, even though Earth-fixed position conversions are shared.
- Rare timer delays remain during loading. Their cause has not been isolated; further
  scheduling changes should follow measurements of loader-thread CPU/GIL activity and
  per-tick batch installation.
- Ground Track and access results intentionally include support margins, so their analyzed
  data window can extend beyond the visible plot boundaries.

## Related documents

- [PLAY_OEM_DATA_PATH_PERFORMANCE_REPORT.md](./old/PLAY_OEM_DATA_PATH_PERFORMANCE_REPORT.md):
  completed data-path optimization report
- [PLAY_OEM_PERFORMANCE_REPORT.md](./PLAY_OEM_PERFORMANCE_REPORT.md): playback render-rate
  measurements
- [PLAY_OEM_INCREMENTAL_LOADING.md](./PLAY_OEM_INCREMENTAL_LOADING.md): incremental loading
  design
- [PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md): overall software design
