# play-oem OEM Dataflow and Computation Efficiency

## Summary

The default `play-oem` load path streams parsed OEM rows directly into an `OemDataStore`.
The store owns the raw samples and lazily computes the range-limited data requested by the
open views. The controller binds those views to one snapshot and range through
`StoreViewContext`; the diagram in [PLAY_OEM_DATAFLOW.mmd](./PLAY_OEM_DATAFLOW.mmd)
describes this shipped path.

An earlier prepared-batch prototype and its duplicate data owners were removed. The default
application has a single direct-to-store loading path.

The default playback range is the first two days of the OEM, and the default plot range
follows playback. Saved settings override those defaults.

## Dataflow

1. **Read and commit (loader thread).** `IncrementalLoader` starts a generation with a new
   `OemDataStore`. `read_oem_into_store` parses OEM rows into reserved raw buffers and commits
   each validated batch directly to the store. If capacity was not supplied, the worker scans
   the file for a safe capacity before allocating. Raw-append events identify committed
   prefixes without constructing prepared orbit-series batches.

2. **Install snapshots (wx thread).** The controller drains at most 64
   generation-tagged load events per timer tick, keeping a continuously
   refilled queue from monopolizing one GUI tick. Remaining events are handled
   on subsequent ticks. On the first usable append, it installs a `StoreCursor`,
   connects the playback clock to the store's live sample-time view, and captures a
   `StoreViewContext`. Each append refreshes the context to the latest committed
   snapshot. Completion publishes validated metadata to the store and refreshes
   the context; replacement, cancellation, and failure remain scoped to their
   load generation.

3. **Query only data needed by open views.** `StoreViewContext` binds a stable snapshot,
   resolved plot range, coverage, and time unit. Views request:
   - **2D histories** through named lazy series groups, such as kinematics, RTN, and
     direction-rate groups.
   - **3D Orbit** through read-only raw position/time/segment views for the bounded display
     path, and `state_at` for the moving marker and tail.
   - **Ground Track** through range- and margin-bounded Earth-fixed positions, converted to WGS-84 coordinates.
   - **Station Status, Pass Strip, profiles, Pass List, and Sky View** through shared
     per-station profile and access-interval tiers.
   - **Pass Ground Track** through the selected pass interval and the shared Ground Track
     tier. Footprints and current station metrics are point queries at playback time.

   Queries can return partial coverage while loading. The store memoizes requested derived
   chunks and ranges, applies its bounded eviction policy, and recomputes evicted data when
   requested again. Ground Track history uses its Earth-fixed position tier. Point consumers use
   `earth_fixed_state_at()` when they need Earth-fixed values: the store converts exact support
   samples at their OEM epochs, caches converted six-component states, and applies the active
   interpolation policy in that frame. Station profiles and access refinement use this path;
   they do not derive their states from the range-based position tier.

4. **Refresh affected views.** Raw append, reset, and derived-tier notices are drained by the
   controller and routed to relevant panels. Range hints prioritize work for the playback and
   plot ranges. Views retain artists or actors when their structure remains compatible and
   rebuild only when required by a data or view-structure change.

5. **Playback.** The clock advances over the store's sample-time view. Source-frame consumers
   resolve states through `state_at()` and Earth-fixed consumers use `earth_fixed_state_at()`.
   Both use the snapshot's interpolation policy and segment boundaries. Current station metrics
   and footprints are derived at the playback time; they are not lookups into range-profile results.

For the policy lifecycle, stateless point evaluator, gap rules, and every playback/derived
consumer, see [PLAY_OEM_INTERPOLATION.md](./PLAY_OEM_INTERPOLATION.md).

## Ownership and performance boundaries

All registered views use store-bound query builders. The application does not retain
`GroundTrackSource`, `EarthFixedPositionCache`, or `StationAccessCache` owners, and Ground Track
and station views do not have non-store data fallbacks. Each load generation owns one
`OemDataStore`; a replacement store is installed only after it has usable rows.

## Remaining efficiency considerations

- Station-access analysis remains station-specific. Its point-state conversion cache is separate
  from the Ground Track range-based Earth-fixed position tier.
- Range queries may include interpolation-support margins beyond the visible plot boundaries.
- Rendering may create bounded display paths or downsampled indices; these are not additional
  full-history owners in the default store path.
- Automatic-capacity scanning adds a pre-load file pass when no safe capacity is supplied; first-
  delivery latency for that path has not been established.

## Related documents

- [PLAY_OEM_INTERPOLATION.md](./PLAY_OEM_INTERPOLATION.md): interpolation policy, lookup rules,
  consumers, and gap behavior
- [PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md): shipped behavior and requirements
- [PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md): component and lifecycle design
- [PLAY_OEM_LOADING_AWARE_TIMELINE_IMPLEMENTATION_PLAN.md](./PLAY_OEM_LOADING_AWARE_TIMELINE_IMPLEMENTATION_PLAN.md):
  timeline loading and interaction behavior
- [PLAY_OEM_PERFORMANCE_REPORT.md](./PLAY_OEM_PERFORMANCE_REPORT.md): measured performance and
  deferred work
