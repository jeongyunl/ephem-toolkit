# `play-oem` — Incremental OEM Loading Design

> **Archived design.** Incremental loading is implemented. This document preserves the
> original design history; the shipped direct-to-store behavior is documented in the
> [dataflow](../PLAY_OEM_DATAFLOW.md) and
> [implementation report](./PLAY_OEM_INCREMENTAL_LOADING_IMPLEMENTATION_REPORT.md).

## Goal

Show the `play-oem` workspace and useful orbit data before a large OEM has been fully parsed and
processed. Continue loading in the background, adding valid samples to the timeline and views until
the file is complete. Keep existing full-resolution cursor behavior, segment boundaries, gap
semantics, and numerical results.

This design targets startup latency. It does not by itself reduce the memory required to retain a
complete OEM history. It also does not promise a complete overview plot at first paint: views are
progressively populated while loading.

## Shipped loading path

The original synchronous `load_playback_data()` startup path has been removed. `__main__.main()`
constructs the workspace with inert initial state; when an OEM is selected,
`PlayerApp._start_incremental_load()` creates an `OemDataStore` and starts
`IncrementalLoader` in direct-store mode. Its worker scans for capacity when needed and streams
parsed rows into reserved store buffers. The wx thread installs committed snapshots and refreshes
views through `StoreViewContext`.

The earlier whole-file loader derived an `OrbitSeries`, prepared an `OemCursor`, and built a
`GroundTrackSource` before showing useful data. The prepared-batch prototype was removed in
Step 8; the loader now exposes only direct-to-store raw appends.

## User-visible behavior

1. Construct the wx app and workspace immediately, with a file-loading status and disabled
   playback controls. The workspace may open without an OEM, as it already does today.
2. A loader worker parses and commits raw state rows to the store. As soon as the first usable
   prefix is committed, install it and show the available orbit samples and plots. Validated OEM
   metadata is published when the worker reaches EOF.
3. Continue parsing on the worker and compute derived products lazily as views request them. The
   wx thread installs the latest store snapshot and advances loaded coverage; it does not receive
   prepared full-history series for each batch.
4. Show progress as loaded samples. Mark the timeline and status as partial until the worker
   reaches EOF and validates the complete file. Queries outside committed coverage remain
   incomplete.
5. At EOF, mark coverage complete, publish final metadata and bounds, and enable features that
   require complete coverage. A parse error after partial display leaves the valid prefix visible,
   marks loading failed, and prevents the UI from claiming complete coverage.

For **Open File...**, keep the previous OEM usable until the replacement file produces its first
valid batch. Then atomically switch the active generation to the new file. This avoids both a long
frozen window and an empty workspace during parsing. A failed file before its first batch leaves
the previous OEM unchanged.

## Architecture

### Streaming reader

The default path uses `read_oem_into_store()` rather than whole-file state retention or prepared
playback batches. It writes parsed rows into store reservations, commits bounded prefixes, and
emits generation-tagged raw-append, completion, and failure events. EOF validation publishes
header and metadata to the store. It does not construct an intermediate `OemStateBatch` stream.

The reader currently uses `_read_oem_impl()`'s row sink so ordinary `CcsdsOem.read()` behavior
remains unchanged. Segment transitions and covariance validation continue to be handled by the
shared parser. The direct store path does not materialize whole-file `states`, covariance, or
comment lists.

The loader worker performs file I/O, capacity scanning when needed, parsing, and raw commits.
Derived work is scheduled lazily by the store for requested tiers and ranges.

### Removed prepared-batch design (historical)

The following describes the earlier prototype only. Its `PlaybackBatch` events, appendable
playback owner, and batch callback have been removed; the default and only loader path writes raw
rows directly to `OemDataStore`.

Introduce a loader/session object that owns the worker, cancellation token, generation ID, current
coverage, metadata, and completion/error state. It emits immutable `PlaybackBatch` values. The GUI
thread alone mutates app state and wx objects.

Batch append must update these structures together, preserving alignment and order:

- source timestamps, state vectors, and segment IDs;
- derived `OrbitSeries` arrays, including adjacent-sample quantities;
- cursor/interpolator lookup data;
- `GroundTrackSource` inputs;
- clock sample times and currently playable coverage.

Keep at least the prior terminal sample when deriving adjacent-sample values so the first delta in
the appended batch matches a one-shot `compute_orbit_series()` result. Never calculate a delta or
interpolation window across a segment boundary. Reject or fail a source if timestamps violate the
ordering assumptions required by the existing clock, series, and cursor.

Initially implement append by deriving each incoming batch once and concatenating arrays. Avoid
recomputing the accumulated prefix on every append. If measurements show concatenation itself is a
material cost, store chunked arrays behind a read-only series interface in a later optimization;
do not make every view understand loader internals in the first implementation.

### Clock, timeline, and view behavior

Distinguish **loaded coverage** from **complete OEM coverage**. During direct store loading, the
clock and playable bounds use observed samples and grow as raw prefixes are committed. Validated
declared `START_TIME`/`STOP_TIME` metadata is applied when loading completes; it does not prove
that data exists outside observed coverage or replace observed samples for playback and analysis.

Playback can run through loaded samples. Reaching the loaded end while loading pauses at that
boundary and presents a “Loading more data” state; it must not look like end-of-file. When a new
batch arrives, extend loaded coverage without moving the cursor unexpectedly. Do not automatically
resume playback: the user can press play again. Reverse playback and seeking are limited to loaded
coverage until complete. Restore saved playback and plot handle positions as soon as the first batch
is installed, even when the saved playback interval extends beyond loaded coverage. Keep the active
playback clock within loaded samples and apply the saved playback interval once its endpoints are
covered. On completion, the final endpoint becomes the real playback end.

Every append updates coverage and refreshes affected store-backed views without rebuilding complete
series histories on the wx thread. Histories draw each segment independently, with no line or
derived value across gaps. Queries may show partial results while loading; features that require
complete metadata or coverage remain incomplete until EOF. Ground Track and station range queries
use the store's reported coverage rather than treating the committed prefix as complete.

### Threading, cancellation, and errors

All wx calls and app/view updates run on the wx event thread. Workers communicate through
`wx.CallAfter` or a thread-safe queue drained by a wx timer; they never call view methods directly.
Tag all events with a monotonically increasing load generation. On a new selection or close,
cancel the prior session and ignore late events whose generation is no longer active. Close file
handles promptly and ensure worker shutdown does not block the UI.

Report initial open errors through the existing status/error path. If parsing fails after a valid
prefix was installed, keep that prefix available for inspection, pause playback, mark the file
incomplete, and show the error. Do not add the path to recent files until the initial valid batch
has been accepted; update recent-file state at the same point as the active-file swap.

## Data structures and module boundaries

Module ownership in the shipped path:

```
play_oem/
  streaming_oem.py       # parser row sink and direct raw-store ingestion
  incremental_loader.py  # worker/session, generation, cancellation, progress
  playback_data.py       # inert startup state and playback-window data model
  app/controller.py     # GUI-thread install/append and status updates
```

Keep the streaming parser playback-specific initially. A general public incremental API in
`core/ccsds/oem.py` should follow only after its event and covariance semantics are proven and a
clear non-GUI caller exists. `read_oem_states()` remains available for non-GUI analysis and reference tests. The one-shot
`load_playback_data()` helper and prepared-batch `playback_data_from_batch()` path have both been
removed.

## Original delivery sequence (historical)

1. **Parser equivalence:** factor parser state and implement a stream that can emit batches while
   retaining metadata, segment IDs, comments, and covariance validation semantics. Compare its
   complete output and errors with `CcsdsOem.from_file()` on single- and multi-segment fixtures.
2. **Batch derivation:** implement appendable playback data and prove that final series, cursor
   samples, segment boundaries, ground track, and sample counts equal one-shot loading regardless
   of batch size or boundaries.
3. **Responsive initial startup:** create the app before full loading; install the first batch and
   show progressive status. Keep Open File replacement transactional and cancellation-safe.
4. **Progressive views and clock:** grow loaded bounds and refresh open panels. Add the loading-end
   pause behavior and gate full-history analyses until completion.
5. **Performance and failure validation:** measure time to app window, first sample/plot, full
   completion, peak memory, and UI responsiveness across representative small, 100k-sample, and
   multi-segment files. Include malformed files that fail before and after first paint, cancellation
   during reload, reverse playback, and seek at a growing boundary.

## Acceptance criteria

- The window becomes interactive before parsing and derived-series work reaches EOF.
- First valid orbit data is visible after the first bounded batch; GUI input remains responsive
  during initial and replacement loads.
- Final results are numerically and structurally equivalent to current one-shot loading,
  independent of batch size, including segment/gap behavior and cursor lookup.
- No stale batch from a canceled/replaced load can modify the active OEM.
- Playback and UI clearly distinguish the loaded boundary from complete EOF coverage.
- Whole-history-only analyses do not present partial answers as complete.
- Report startup-to-window, startup-to-first-plot, completion, and peak-memory measurements.

## Deferred choices

- Whether the reader should later become a general `core.ccsds.oem` public streaming API.
- Whether large completed histories should remain resident, spill chunks to disk, or support an
  explicit reduced-memory mode. Incremental loading alone does not answer this.
- The exact initial/subsequent batch sizes, progress indicator, and whether percentage progress is
  shown. Percentage requires a stable byte denominator and is secondary to an accurate loaded
  sample/time range.
