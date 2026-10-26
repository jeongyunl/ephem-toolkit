# `play-oem` — Incremental OEM Loading Implementation Plan

Requirements and architecture: [PLAY_OEM_INCREMENTAL_LOADING.md](./PLAY_OEM_INCREMENTAL_LOADING.md).
Current application plan and completed implementation history:
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md).

## Current runtime behavior

`play-oem` currently calls `load_playback_data()` before creating `PlayerApp`. The synchronous
loader parses the whole OEM, derives all orbit series, prepares cursor lookup, and builds the
ground-track source before the first window can appear. The Open File workflow runs the same load
and preparation synchronously from the GUI event handler. Loading therefore blocks both initial
startup and file replacement.

This plan implements the separate
[incremental loading design](./PLAY_OEM_INCREMENTAL_LOADING.md). It targets time to first
interactive data; it does not claim to reduce the memory needed for a complete history.

## How to use this plan

Work **one pending numbered step at a time, in order**. Do not begin a later pending step until the
current step's checklist and completion criteria pass. Keep status and progress current. If an
implementation choice changes the parser, batch, clock, view, or loading-session contracts, update
the incremental loading design before proceeding with dependent work. If user-visible behavior
changes, update [PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md) as well.

- **Not started** — no work begun.
- **In progress** — implementation or its checks are underway.
- **Blocked** — cannot proceed; record the blocker.
- **Done** — all checklist items and completion criteria pass.

For every numbered step, retain its original number, checklist, completion criteria, and dependency
when moving it to `Completed steps` below. Keep completed substeps under their active parent until
every substep and the parent completion criteria pass.

## Implementation sequence

### 6. Validate completion, errors, and startup performance

Exercise the complete lifecycle and measure whether incremental loading meets its startup goal.
Record results for representative real and synthetic files and document platform/backend limits.

- **Status:** In progress.
- **Progress:** 5/6 checklist items (the full GUI performance matrix remains unmeasured).
- [x] On EOF, validate the full file, mark coverage complete, publish final bounds/count, and enable
      full-history features.
- [x] Verify a parse failure before first data leaves the current OEM unchanged and a failure after
      first data preserves the valid prefix while marking it incomplete and paused.
- [x] Verify replacement cancellation, app close during loading, stale-event rejection, reverse
      playback, and seek/play at a growing loaded boundary.
- [x] Compare final one-shot and incremental numerical results and segment/gap behavior.
- [ ] Measure time to window, time to first sample/plot, total completion time, peak memory, and UI
      responsiveness on a small OEM, a 100k-sample OEM, and a multi-segment OEM.
- [x] Update the architecture/performance records and user documentation with measured results and
      any accepted limitations.

**Evidence:** Focused parser, data, clock, loader, application, and CLI checks passed (242 tests).
Profiling the supplied `LEO3_ICRF_2026-10-26-121849.oem` (120,961 states, 12 MiB) showed 237 batches;
parsing and batch derivation took 24.3 s, with derivation taking 20.4 s total and up to 139 ms for
one batch. Batch derivation now runs on the loader worker, and open plots are no longer rebuilt for
each incoming batch. Replaying this file through the prepared loader path produced the first batch
in 0.134 s and completed in 26.0 s; a main-thread queue drain took at most 0.1 ms in the polling
benchmark. This isolates the measured preparation cost from GUI installation, but a visible-window
responsiveness benchmark remains unavailable without a working display.
Synthetic parser measurements on this environment: 1k states, 0.015 s to first batch and 0.026 s
total; 100k states in a 3.9 MiB single-segment file, 0.021 s to first batch and 2.473 s total;
100k states across four segments, 0.013 s to first batch and 2.442 s total. A parser-only 100k run
reported 72,552 KiB peak RSS. Parsing plus incremental series derivation for the 100k single-segment
file took 17.696 s to EOF, with the first batch prepared in 0.082 s and peak RSS of 160,872 KiB.
These are synthetic measurements on this environment; no representative real OEM was available.
A real wx window/plot benchmark could not run: `xvfb-run -a xdpyinfo` could not open its display,
so time-to-window, first visible plot, and UI responsiveness remain unmeasured. The package-wide
playback suite collected with 35 failures in existing tests whose fakes/assertions do not match
the current display-time-zone and workspace APIs (388 passed, 9 skipped); the focused incremental
suite passes (242 passed).

**Done when:** lifecycle and equivalence checks pass, performance measurements are recorded, and
the user-facing docs accurately describe progressive loading and incomplete-file behavior.
**Depends on:** Step 5.

## Completed steps

### 1. Establish streaming parser equivalence

Factor the existing OEM line-processing state so playback can consume bounded state batches before
EOF while the established `CcsdsOem.read()` and `from_file()` APIs preserve their behavior. Keep
header/metadata validation, segment IDs, data comments, state ordering, and covariance association
and validation consistent across batch boundaries.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Define stream events for validated header/metadata, state batches, completion, and failure.
- [x] Preserve parser state across calls and batch boundaries, including segment and covariance
      blocks.
- [x] Share parser logic with the existing whole-file API without changing its return shape or
      error behavior.
- [x] Compare whole-file results and errors against the current parser for representative
      single- and multi-segment files, covariance records, and malformed inputs.
- [x] Confirm the streaming reader does not retain whole-file states, covariance records, or
      comments in its playback path.

**Evidence:** `_read_oem_impl()` now supports bounded state callbacks and clears emitted state
batches when used in non-retaining mode; existing whole-file calls keep the same return behavior.
`play_oem.streaming_oem.iter_oem_events()` parses on a daemon worker, applies queue back-pressure,
and yields state batches followed by a completion event only after EOF and ODM context validation.
Parser, segment, covariance, streaming-equivalence, cancellation, and late-error checks passed:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src pytest -q
tests/ephem_toolkit/core/ccsds/test_oem.py
tests/ephem_toolkit/core/ccsds/test_oem_extended.py
tests/ephem_toolkit/play_oem/test_streaming_oem.py` (85 passed).

**Done when:** the streaming reader yields bounded batches before EOF and consuming it to completion
produces the same OEM content and validation outcomes as the existing reader.
**Depends on:** None.

### 2. Derive and append playback batches

Introduce an appendable playback data store that accepts ordered batches and keeps source samples,
derived series, cursor lookup, and ground-track inputs aligned. Derive each incoming batch once;
do not recompute the accumulated prefix for each append. Preserve segment-local interpolation and
adjacent-sample calculations at batch boundaries.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Define an immutable batch contract for timestamps, SI states, segment IDs, and covariance
      data needed by playback.
- [x] Add batch preparation and append operations without breaking the synchronous
      `load_playback_data()` API.
- [x] Carry the prior terminal sample into adjacent-sample derivation and suppress calculations
      across segment boundaries.
- [x] Verify final series, cursor results, segment IDs, ground-track samples, and metadata match
      one-shot loading for multiple batch sizes and split locations.
- [x] Reject invalid timestamp order consistently with the clock, cursor, and series assumptions.

**Evidence:** `AppendablePlaybackData` appends ordered OEM batches, prepares only the incoming
batch plus the previous terminal state for adjacent-sample quantities, updates per-segment cursor
interpolators, and maintains Ground Track source arrays. When observed coverage crosses one hour,
elapsed axes switch from minutes to hours and retain the same origin. One-shot equivalence passed
for batch sizes 1, 2, 3, and 100, including a segment boundary; Hermite cursor interpolation,
single-sample prefixes, unit transition, and invalid append checks passed:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src pytest -q
tests/ephem_toolkit/play_oem/test_streaming_oem.py
tests/ephem_toolkit/play_oem/test_play_oem_cursor.py
tests/ephem_toolkit/play_oem/test_play_oem_data.py` (30 passed).

**Done when:** any valid file produces equivalent final playback data regardless of batch size or
batch boundaries, while append work processes only new samples and the required boundary context.
**Depends on:** Step 1.

### 3. Add a cancellable background loading session

Add a session that owns file parsing, batch derivation, progress, cancellation, and completion/error
state. Give each selected file a generation ID. Workers publish immutable events; only the wx event
thread installs data and updates application or view state.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Add a loader/session abstraction with bounded state-count batches, a 100 ms batch interval,
      and a bounded event queue.
- [x] Publish start, batch/progress, completion, and failure events tagged with a generation ID.
- [x] Provide a nonblocking drain API so the wx event thread can install data and update views.
- [x] Cancel the prior session on replacement; the loader exposes only current-generation events
      and tags queued events so scheduled stale deliveries can be rejected by the app.
- [x] Verify cancellation releases queue back-pressure and the worker exits without blocking the
      caller; parsing owns its file context and closes it as the worker unwinds.

**Evidence:** `IncrementalLoadSession` runs parsing and batch callbacks on one daemon worker and
publishes bounded, generation-tagged events through a nonblocking `drain()` interface.
`IncrementalLoader` cancels and replaces the active generation and filters drained messages to the
current generation. The parser flushes on a 512-state default or 100 ms interval; queues apply
back-pressure and cancellation is cooperative at batch boundaries. Session ordering, progress
counts, late parser errors, replacement generations, cancellation under back-pressure, and stream
equivalence passed:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src pytest -q
tests/ephem_toolkit/core/ccsds/test_oem.py
tests/ephem_toolkit/play_oem/test_incremental_loader.py
tests/ephem_toolkit/play_oem/test_streaming_oem.py` (50 passed).

**Done when:** a worker can parse and prepare a file incrementally, the UI remains responsive, and
stale or canceled sessions cannot mutate active playback data.
**Depends on:** Steps 1 and 2.

### 4. Show first data before EOF

Construct the app and workspace before full parsing finishes. Install the first valid batch as the
active OEM, update the dashboard and plots, and continue loading in the background. Preserve the
currently active OEM until a replacement file has produced a valid initial batch.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Create the initial `PlayerApp` before the selected OEM is completely parsed and prepared.
- [x] Show loading state with controls disabled until the first batch establishes usable coverage.
- [x] Install first-batch metadata, orbit, cursor, timeline, and plots on the GUI thread.
- [x] Make replacement loading transactional: keep the old OEM until the new first batch is ready;
      leave it active if the replacement fails before then.
- [x] Update recent-file state only after the new file's initial batch has been accepted.

**Evidence:** The CLI now starts from `empty_playback_data()` and passes the selected path to
`PlayerApp`, which shows the frame before starting `IncrementalLoader`. The wx timer drains loader
events on the UI thread; the first batch builds `PlaybackData` and replaces the placeholder, while
later batches append to its incremental store. The current OEM remains installed until that first
batch, and recent-file state is updated only after installation. Missing paths still fail quickly
with a file check before wx initialization. App and CLI behavior passed:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src pytest -q
tests/ephem_toolkit/play_oem/test_play_oem_app.py
tests/ephem_toolkit/play_oem/test_play_oem_cli.py` (92 passed).

**Done when:** the window is interactive before EOF, the first valid orbit batch appears without
waiting for full-file parsing, and a failed pre-display replacement leaves the previous OEM intact.
**Depends on:** Step 3.

### 5. Grow loaded coverage and gate full-history features

Extend the timeline as batches arrive. Distinguish the current loaded boundary from EOF, update
existing views in place, and keep analyses that require full coverage unavailable until loading
completes.

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- **Previous step:** Step 4 is complete; see [Completed steps](#completed-steps).
- [x] Add a clock/data contract for growing loaded coverage without unexpected cursor movement.
- [x] Pause at the loaded end with a loading indication rather than signaling end-of-file; do not
      auto-resume when another batch arrives.
- [x] Keep loaded-range controls current on each batch and defer expensive full-history plot
      refreshes until EOF; preserve segment and gap boundaries in the final redraw.
- [x] Mark progressive Ground Track output and timeline coverage as partial until completion.
- [x] Disable or clearly defer ground-station access/pass analysis and other full-history features
      until EOF validation succeeds.
- [x] Treat metadata `START_TIME` and `STOP_TIME` as declared values only, not proof of observed
      coverage or permission to seek into unread data.

**Done when:** users can distinguish loaded coverage from complete coverage, playback and seeking
respect the loaded boundary, and no full-history feature presents a partial result as complete.
**Depends on:** Step 4.

**Evidence:** The clock grows coverage only from ordered observed sample timestamps, keeps the
current cursor and paused state as batches extend, and grows playback bounds only when the upper
bound follows observed coverage. The app exposes the growing sample count/time span, stops at the
loaded edge with “Loading more data…”, keeps full-history plot redraws off the batch path, marks a
failed prefix as incomplete, and withholds ground-station access/pass analyses until successful EOF.
The slider scale uses valid metadata `START_TIME`/`STOP_TIME` bounds from the first batch, while
clock and playback coverage remain limited to observed loaded samples. Seeking into the declared
but unread interval clamps to loaded coverage. Saved playback and plot handle positions are shown
from the first batch; the clock applies a saved playback range when that interval is covered.
Clock and app checks for endpoint pause/extension, saved handle restoration, transactionally
retained replacements, partial failure, dashboard/view updates, and analysis gating passed in the
focused suite.
