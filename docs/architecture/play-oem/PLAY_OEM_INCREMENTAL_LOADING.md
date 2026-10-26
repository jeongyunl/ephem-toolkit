# `play-oem` — Incremental OEM Loading Design

## Goal

Show the `play-oem` workspace and useful orbit data before a large OEM has been fully parsed and
processed. Continue loading in the background, adding valid samples to the timeline and views until
the file is complete. Keep existing full-resolution cursor behavior, segment boundaries, gap
semantics, and numerical results.

This design targets startup latency. It does not by itself reduce the memory required to retain a
complete OEM history. It also does not promise a complete overview plot at first paint: views are
progressively populated while loading.

## Current bottleneck

`play_oem.__main__.main()` calls `load_playback_data()` before constructing `PlayerApp`. That calls
`CcsdsOem.from_file()`, which reads and retains all states, then `compute_orbit_series()` derives
all plot histories, `OemCursor` prepares interpolation data, and `GroundTrackSource` retains the
source samples. The wx app cannot appear until this work completes. Opening a different file uses
the same synchronous callback from `PlayerApp._load_oem_file()` and blocks the GUI thread.

The parser is a whole-file interface today. `_read_oem_impl()` handles header and metadata records,
segment transitions, state rows, and covariance blocks in one pass, but returns only after EOF.
Incremental loading therefore needs an explicit streaming API and a GUI-thread handoff; wrapping
the current method in a thread alone would make the window responsive during a reload but would
still defer first startup until the entire file is parsed.

## User-visible behavior

1. Construct the wx app and workspace immediately, with a file-loading status and disabled
   playback controls. The workspace may open without an OEM, as it already does today.
2. A loader worker opens the selected file, parses its header and first metadata segment, then
   reads a bounded initial batch of state rows. As soon as the first usable batch is ready, install
   it and show the first orbit samples, metadata, cursor, and plots.
3. Continue parsing and deriving bounded batches on the worker. Post prepared results to the wx
   event loop; the GUI thread only installs the latest series/cursor snapshot and advances its
   loaded timeline. Do not rebuild full plot histories for every batch. Keep the first visible
   plots responsive during loading, then refresh them once after EOF validation.
4. Show progress as loaded samples and, only when trustworthy, a byte-based estimate. Mark the
   loaded timeline and status as partial until the worker reaches EOF and validates the complete
   file. Whole-history analyses stay unavailable during this period.
5. At EOF, mark coverage complete, publish final sample count and bounds, and enable all features
   that require complete coverage. A parse error after partial display leaves the valid prefix
   visible, marks loading failed, and prevents the UI from claiming complete coverage.

For **Open File...**, keep the previous OEM usable until the replacement file produces its first
valid batch. Then atomically switch the active generation to the new file. This avoids both a long
frozen window and an empty workspace during parsing. A failed file before its first batch leaves
the previous OEM unchanged.

## Architecture

### Streaming reader

Add a playback-oriented streaming reader rather than changing the contract of
`CcsdsOem.from_file()` for every command. It owns the file handle and parser state and yields:

- a start event after header and first segment metadata are validated;
- ordered batches containing timestamps, SI state vectors, segment IDs, and any batch-local
  covariance records;
- a completion event after EOF checks and ODM context validation; or
- a failure event with the source location and parser error.

The parser should factor `_read_oem_impl()`'s line-state logic into reusable stateful parsing
primitives so ordinary `CcsdsOem.read()` retains exactly its current behavior. State batches must
not split the data needed to interpret metadata: a new `META_START` closes the prior segment and
the next state uses the new segment ID. Covariance data must remain associated with its epoch and
must be finalized and validated even when its rows cross a batch boundary. Do not materialize
whole-file `states`, covariance, or comment lists in the streaming playback path.

Use a worker thread for file I/O, parsing, and numerical batch preparation. Bound work by a target
state count and a maximum batch latency so sparse files still report progress. The initial batch
should be small enough for a quick first paint; subsequent batches can be larger to amortize
dispatch costs. These are configuration constants to tune from measurements, not user-facing
options initially.

### Playback data and append contract

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

Distinguish **loaded coverage** from **complete OEM coverage**. The slider's displayed time scale
uses declared OEM `START_TIME`/`STOP_TIME` when valid, so the track represents the file's intended
interval from the first batch. Loaded coverage and playable bounds still use observed samples and
grow as batches arrive. A slider seek into an unread part of the declared interval clamps to loaded
coverage; metadata does not prove that data exists there. Likewise, `START_TIME`/`STOP_TIME` do not
replace the observed first and last samples for playback or analysis.

Playback can run through loaded samples. Reaching the loaded end while loading pauses at that
boundary and presents a “Loading more data” state; it must not look like end-of-file. When a new
batch arrives, extend loaded coverage without moving the cursor unexpectedly. Do not automatically
resume playback: the user can press play again. Reverse playback and seeking are limited to loaded
coverage until complete. Restore saved playback and plot handle positions as soon as the first batch
is installed, even when the saved playback interval extends beyond loaded coverage. Keep the active
playback clock within loaded samples and apply the saved playback interval once its endpoints are
covered. On completion, the final endpoint becomes the real playback end.

Every batch updates the visible timeline/range labels and playback coverage, but it does not rebuild
the full history in each open plot. This keeps the wx event thread responsive while the sample
count grows. Open plots refresh to the complete history after successful EOF validation. Histories
draw each segment independently, with no line or derived value across gaps. Views that need the
entire OEM for accurate global results (notably ground-station access/pass prediction and full-span
statistics) stay unavailable or show an explicit “available when loading completes” state until
EOF. Ground Track may show the currently loaded prefix, clearly marked partial. Opening a new
full-history analysis before completion follows the same availability rule.

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

Proposed modules (names may be adjusted to match implementation conventions):

```
play_oem/
  streaming_oem.py       # reader events and bounded state batches
  incremental_loader.py  # worker/session, generation, cancellation, progress
  playback_data.py       # appendable playback store and batch derivation
  app/controller.py     # GUI-thread install/append and status updates
```

Keep the streaming parser playback-specific initially. A general public incremental API in
`core/ccsds/oem.py` should follow only after its event and covariance semantics are proven and a
clear non-GUI caller exists. Existing `read_oem_states()` and `load_playback_data()` can remain as
synchronous convenience APIs, implemented by consuming the streaming interface to completion, if
their signatures and tests stay stable.

## Delivery sequence

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
