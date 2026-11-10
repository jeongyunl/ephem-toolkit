# `play-oem` — Incremental OEM Loading Implementation Report

> **Status: Complete.** The application loads OEM rows progressively through a single
> direct-to-store path. The earlier prepared-batch design and plan are retained in
> [the archived design](./PLAY_OEM_INCREMENTAL_LOADING.md); current runtime architecture is
> described in the [dataflow](../PLAY_OEM_DATAFLOW.md).

## Delivered behavior

- The application creates its workspace immediately and loads the selected OEM on a worker
  thread. The worker streams parsed rows into a generation-scoped `OemDataStore`; it does not
  retain whole-file state, covariance, or comment collections in the playback path.
- When capacity is not provided, the loader scans the input for a safe raw-store capacity before
  allocating. It commits bounded raw-row batches and emits generation-tagged append events.
- The wx thread drains loader events, installs committed snapshots, and refreshes open views using
  `StoreViewContext`. Derived data is requested lazily from the store rather than sent as prepared
  series batches.
- Playback and seeking are bounded by observed, loaded samples. The UI distinguishes partial
  coverage from a validated complete file; metadata is published at successful EOF.
- Replacement, cancellation, stale-event rejection, parser failures, and failures after a usable
  prefix are handled without allowing an obsolete load to mutate the active generation. A valid
  prefix remains inspectable after a later parse failure and is not presented as complete.

## Implementation outcome

The original staged prototype used `PlaybackBatch` events and an appendable playback-data owner.
That path was removed. The shipped path is `IncrementalLoader` →
`read_oem_into_store()` → `OemDataStore`, with the application controller installing snapshots
and routing refreshes. The store remains the owner of raw data and lazily computed derived tiers.

## Validation

Focused parser, loader, and application tests passed:

```text
PYTHONPATH=src python3 -m pytest -q \
  tests/ephem_toolkit/play_oem/test_streaming_oem.py \
  tests/ephem_toolkit/play_oem/test_incremental_loader.py \
  tests/ephem_toolkit/play_oem/test_play_oem_app.py
104 passed
```

The tests cover direct-store equivalence, bounded commits, generation tagging, cancellation,
failure handling, replacement behavior, progressive coverage, and saved-range restoration.

## Remaining performance work

Functional implementation and focused validation are complete. Performance characterization is
not: the automatic-capacity first-delivery gate remains deferred, and visible-window startup,
first-plot, memory, and UI-responsiveness measurements have not been established for the shipped
direct-to-store path. The earlier batch-path measurements in the archived plan do not certify the
current implementation.
