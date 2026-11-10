# `play-oem` — Unified OEM Data Store Implementation Report

**Status: Concluded.** The unified data-store migration is implemented. The plan is closed at the
user's direction; the JPSS-1 first-delivery acceptance gate remains unpassed and is not represented
as accepted.

## Summary

`OemDataStore` is the authoritative in-memory owner of raw OEM states and lazily requested
analysis/plotting products. Parsing writes directly into store-owned buffers, and loaded views
read snapshot-bound store data without retaining orbit-sized copies. The migration covers loading,
playback, views, range scheduling, lifecycle, and removal of superseded data owners.

## Delivered

- Added fixed-capacity raw storage, direct parser-to-store ingestion, committed-prefix snapshots,
  epoch-safe cancellation, and explicit load lifecycle states.
- Added lazy, range-bound series, Earth-fixed, interpolation, and station-access tiers, with
  shared memoization, prioritization, cancellation, and eviction.
- Migrated the active player and store-capable views to one store per load generation, including
  live playback timestamps, snapshot-bound read contexts, range hints, and store-backed station
  prefetch.
- Removed the prepared-batch path, duplicate derived-series owners, and legacy Ground Track,
  station-access, and footprint cache ownership.
- Verified zero-copy raw views and lazy derived preparation against ISS, JPSS-1, and
  multi-segment fixtures.

## Performance outcome

Five alternating fresh-process pairs compared the prepared-batch baseline with direct-store
loading:

| Fixture | First batch / raw append | Validated completion | Process peak RSS |
|---|---:|---:|---:|
| ISS | 13.706 → 12.686 ms (−7.4%) | 0.109261 → 0.043214 s (−60.5%) | 76.3 → 68.3 MiB (−10.5%) |
| JPSS-1 | 14.488 → 25.375 ms (+75.1%) | 0.759649 → 0.500905 s (−34.1%) | 90.7 → 87.1 MiB (−4.0%) |

The provisional gates require at least 10% lower JPSS-1 completion time, no more than 5%
first-batch regression on either fixture, and no more than 5% regression in comparable RSS.
Completion and RSS pass in these pairs; JPSS-1 first delivery fails. Automatic sizing added
10.899 ms median first-append time versus explicit 21,624-row capacity in a separate diagnostic.
That diagnostic is not acceptance evidence. GUI responsiveness was not measured.

## Repeat-open cache decision

A temporary, benchmark-only, same-process cache prototype measured validated hits at 0.072 ms
median for ISS (5 hits) and 0.076 ms for JPSS-1 (10 hits across two processes), including source
stat and snapshot creation. Hits returned the same store and raw buffer; a same-size modification
to a synthetic OEM invalidated the stat-keyed entry.

The approved direction is a bounded process-local memory-cache design, not a persistent disk
cache. The prototype was removed after measurement. Production implementation requires separate
approval; content-digest verification, retained-memory cost, derived-tier reuse, and application
lifecycle behavior remain unmeasured.

## Verification

- Full play-oem and core-interpolator regression suites: **688 passed, 4 skipped**.
- `compileall` and `git diff --check` passed during implementation.
- Five-pair loader measurements and repeat-open diagnostics are documented in the
  [software design](./PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md).
- Current dataflow is documented in [PLAY_OEM_DATAFLOW.md](../PLAY_OEM_DATAFLOW.md) and
  [PLAY_OEM_DATAFLOW.mmd](../PLAY_OEM_DATAFLOW.mmd).

## Deferred acceptance and follow-up

The implementation plan is concluded, but the first-delivery performance gate remains deferred
and unpassed. Do not treat faster completion or lower RSS as a substitute for meeting that gate.
The bounded cache design is approved; do not implement a production cache without separate
approval.

Implementation sources include [oem_data_store.py](../../../../src/ephem_toolkit/play_oem/oem_data_store.py),
[incremental_loader.py](../../../../src/ephem_toolkit/play_oem/incremental_loader.py), and
[streaming_oem.py](../../../../src/ephem_toolkit/play_oem/streaming_oem.py).

## Archived design materials

- [Unified OEM Data Store Software Design](./PLAY_OEM_DATA_STORE_SOFTWARE_DESIGN.md)
