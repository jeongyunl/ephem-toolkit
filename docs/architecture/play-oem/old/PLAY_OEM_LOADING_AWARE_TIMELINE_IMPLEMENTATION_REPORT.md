# `play-oem` — Loading-Aware Timeline Implementation Report

> **Status: Implemented.** The metadata-aware timeline, loaded-progress display, scrubber state,
> loading-time drag deferral, and range-ready initial graph handoff are present. The generic loader
> pause/resume API is available to app code and takes effect at a committed batch boundary.

Requirements and current user-facing behavior are described in
[PLAY_OEM_CONCEPTS.md](../PLAY_OEM_CONCEPTS.md). Current architecture is in
[PLAY_OEM_SOFTWARE_DESIGN.md](../PLAY_OEM_SOFTWARE_DESIGN.md) and
[PLAY_OEM_DATAFLOW.md](../PLAY_OEM_DATAFLOW.md). The parent implementation sequence is
[PLAY_OEM_IMPLEMENTATION_PLAN.md](../PLAY_OEM_IMPLEMENTATION_PLAN.md), Step 28.

## Implemented behavior

- The reader publishes segment metadata, raw append notices, parser progress, and completion
  events tagged with the load generation. Valid UTC `START_TIME` and `STOP_TIME` bounds are
  combined with observed sample bounds for the slider domain. Playback remains bounded by
  committed sample coverage.
- The timeline keeps the declared domain, loaded coverage, playback bounds, plot endpoints, and
  current time as separate values. It marks the unread suffix using parser progress and explains
  unloaded time in the timeline tooltip. Seeking into unloaded time retains the clock's loaded-
  coverage clamping behavior.
- Playback, plot-range, and seek grips report drag lifecycle, including mouse-capture loss. While
  loading and a timeline drag is active, plot refreshes are deferred and coalesced. Ending the drag
  refreshes from the latest range, cursor, and store snapshot.
- `IncrementalLoader` and its active `IncrementalLoadSession` expose generic `pause()` and
  `resume()` methods. Requests are non-blocking; a pause takes effect after the next raw-append
  event at a committed batch boundary. The session reports `paused` after the worker acknowledges
  that boundary. The same load generation can resume, and committed data remains available.
  These methods are producer controls and are separate from cancellation.
- The app starts loading normally and withholds initial plot creation and refreshes until loaded
  coverage includes the requested playback and plot range. It requests a pause as soon as an
  append event shows the range is covered, waits for the worker's batch-boundary acknowledgment,
  draws the initial graphs from that prefix, and resumes the same load. The queue is bounded, so
  batches already in flight may be committed before the worker acknowledges the pause.

## Implementation outcome

The timeline presentation, loading-time interaction, and range-ready graph handoff are implemented
in the loader, app controller, and timeline widget. The app no longer resumes after an insufficient
first batch; it continues loading until the requested interval is covered, then pauses, draws, and
resumes.

## Current limitations

- The generic pause/resume API is not exposed as a user-facing control in the GUI; the app uses it
  for its initial range-ready graph handoff.
- Timeline metadata support is UTC-only. Native GUI behavior across operating systems and live
  display-backed acceptance are not established here.
- Previously reported user observations of long loads, UI freezing, a post-draw quit, and Ground
  Track flicker were not reproduced or ruled out by these focused tests.

## Validation evidence

Focused application and loader tests passed: **21 passed, 100 deselected** across the incremental
loader and app test selection. This includes a multi-batch saved-range test that verifies initial
graphs draw while the worker acknowledges its pause, before EOF, and that loading continues after
the app resumes it. `compileall` and `git diff --check` also passed. No live GUI run was performed.

## Follow-up

Perform a live GUI acceptance run with a large OEM to check responsiveness, initial graph rendering,
and visible Ground Track behavior while the remainder continues loading.
