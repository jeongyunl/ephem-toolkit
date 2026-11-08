# play-oem OEM Dataflow and Computation Efficiency

## Summary

This document describes how OEM data flows through `play-oem` into its graphs, including
incremental loading, range-limited analysis, cache retention, and in-place panel refresh.
The dataflow diagram is [PLAY_OEM_DATAFLOW.mmd](./PLAY_OEM_DATAFLOW.mmd).

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
   - **2D histories** (State Components, Speed / Altitude, RTN Deltas, Angular Velocity,
     Direction Change, and Geocentric Distance) receive the current (possibly downsampled)
     `OrbitSeries`. Their `SegmentedPlotHistory` instances select samples inside the plot bounds
     and decimate each displayed segment.
   - **3D Orbit** views select plot-range samples and decimate the displayed path in the
     Matplotlib or VTK backend.
   - **Ground Track** and **Pass Ground Track** use `prepare_ground_track` to convert bounded
     source samples to WGS-84 coordinates. Pass Ground Track limits the same preparation to the
     selected pass interval.
   - **Station Status, Pass Strip, Elevation / Azimuth / Range Profiles, Pass List, and Sky View**
     consume per-station access results. The profile views use the same sampled look-angle
     profiles (time, azimuth, elevation, and range); pass views use the access intervals derived
     from those samples.

Ground Track preparation and station analysis share the same `EarthFixedPositionCache` for
sample ITRF positions. Their downstream calculations are distinct: Ground Track converts those
positions to WGS-84 latitude/longitude, while station analysis transforms spacecraft-minus-station
ECEF vectors into local ENU and derives azimuth, elevation, and range. Current station status
uses the playback cursor state and station-metric calculation; it is not simply a lookup in a
precomputed profile. Footprints are Ground Track-specific results computed from the current
Earth-fixed position and elevation mask.

4. **Refresh existing panels.** Time-series views update their history arrays and retain line
   artists when their segment structure remains compatible. Both 3D backends update their
   path data in place. If data shape or view structure is incompatible, the controller falls
   back to replacing the view. Deferred station panels are refreshed after their analysis is
   ready.

5. **Retain caches across appends.** Ground Track Earth-fixed positions are retained when the
   new sample source is an unchanged prefix extension, with geometrically grown backing
   storage; the same position cache is used by station analysis and Pass Ground Track.
   Station-access results are retained only for analysis windows conservatively separated from
   the old coverage edge by an interpolation-support margin. Tail windows are recomputed; a
   changed source prefix or interpolation policy invalidates cached results. Ground Track plot
   coordinates are invalidated when an appended batch intersects the active plot range.

6. **Playback.** Each frame advances the clock and resolves the cursor state. Ground-station
   views derive the current station metrics from that state. This per-frame cursor and station
   calculation is distinct from the static range analyses above.

## Remaining efficiency considerations

- Access analysis still scales with station count because topocentric metrics are station
  specific, even though Earth-fixed position conversions are shared.
- Ground Track and access results intentionally include support margins, so their analyzed
  data window can extend beyond the visible plot boundaries.

## Related documents

- [PLAY_OEM_INCREMENTAL_LOADING.md](./PLAY_OEM_INCREMENTAL_LOADING.md): incremental loading
  design
- [PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md](./PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md): target
  unified-store architecture and performance evidence
- [PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md): overall software design
