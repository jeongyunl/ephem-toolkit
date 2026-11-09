# play-oem OEM Dataflow and Computation Efficiency

## Summary

The default `play-oem` load path streams parsed OEM rows directly into an `OemDataStore`.
The store owns the raw samples and lazily computes the range-limited data requested by the
open views. The controller binds those views to one snapshot and range through
`StoreViewContext`; the diagram in [PLAY_OEM_DATAFLOW.mmd](./PLAY_OEM_DATAFLOW.mmd)
describes this shipped path.

The prepared-batch loader and its duplicate data owners remain as compatibility code, but
they are not used by the default application load path. Step 8 tracks their removal.

The default playback range is the first two days of the OEM, and the default plot range
follows playback. Saved settings override those defaults.

## Dataflow

1. **Read and commit (loader thread).** `IncrementalLoader` starts a generation with a new
   `OemDataStore`. `read_oem_into_store` parses OEM rows into reserved raw buffers and commits
   each validated batch directly to the store. If capacity was not supplied, the worker scans
   the file for a safe capacity before allocating. Raw-append events identify committed
   prefixes without constructing prepared orbit-series batches.

2. **Install snapshots (wx thread).** The controller drains generation-tagged load events.
   On the first usable append, it installs a `StoreCursor`, connects the playback clock to the
   store's live sample-time view, and captures a `StoreViewContext`. Each append refreshes the
   context to the latest committed snapshot. Completion publishes validated metadata to the
   store and refreshes the context; replacement, cancellation, and failure remain scoped to
   their load generation.

3. **Query only data needed by open views.** `StoreViewContext` binds a stable snapshot,
   resolved plot range, coverage, and time unit. Views request:
   - **2D histories** through named lazy series groups, such as kinematics, RTN, and
     direction-rate groups.
   - **3D Orbit** through read-only raw position/time/segment views for the bounded display
     path, and `state_at` for the moving marker and tail.
   - **Ground Track** through range- and margin-bounded Earth-fixed and WGS-84 tiers.
   - **Station Status, Pass Strip, profiles, Pass List, and Sky View** through shared
     per-station profile and access-interval tiers.
   - **Pass Ground Track** through the selected pass interval and the shared Ground Track
     tier. Footprints and current station metrics are point queries at playback time.

   Queries can return partial coverage while loading. The store memoizes requested derived
   chunks and ranges, applies its bounded eviction policy, and recomputes evicted data when
   requested again. Ground Track uses the store's Earth-fixed tier. Station-access profile rows
   currently evaluate point states and station metrics independently; they do not consume that
   Earth-fixed tier.

4. **Refresh affected views.** Raw append, reset, and derived-tier notices are drained by the
   controller and routed to relevant panels. Range hints prioritize work for the playback and
   plot ranges. Views retain artists or actors when their structure remains compatible and
   rebuild only when required by a data or view-structure change.

5. **Playback.** The clock advances over the store's sample-time view. `StoreCursor` resolves
   point states from the same raw snapshot and interpolation policy used by range queries.
   Current station metrics and footprints are derived at the playback time; they are not
   lookups into the range-profile results.

## Compatibility path

`IncrementalLoader` still supports prepared-batch callbacks. That path uses
`IncrementalPlaybackPreparer`, `AppendablePlaybackData`, `OrbitSeriesAccumulator`,
`OemCursor`, `GroundTrackSource`, and the legacy station-access caches. Some views retain
fallback support for these objects. This path is not represented as the default flow and
remains scheduled for removal in Step 8.

## Remaining efficiency considerations

- Station-access analysis remains station-specific and currently evaluates its profile-row point
  states independently from the Ground Track Earth-fixed tier.
- Range queries may include interpolation-support margins beyond the visible plot boundaries.
- Rendering may create bounded display paths or downsampled indices; these are not additional
  full-history owners in the default store path.
- The Step 7 automatic-capacity first-delivery performance gate remains deferred and unpassed.

## Related documents

- [PLAY_OEM_INCREMENTAL_LOADING.md](./PLAY_OEM_INCREMENTAL_LOADING.md): incremental loading
  design
- [PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md](./PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md): unified
  store architecture and performance evidence
- [PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md): overall software design
