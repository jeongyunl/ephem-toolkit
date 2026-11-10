# play-oem — Loading-Aware Timeline Implementation Plan

Requirements: [PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md). As-built architecture:
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md). Parent work sequence:
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md), Step 28.

## Goal

Make the shared timeline represent the full OEM-declared time span while data streams in,
distinguish committed data from the unread portion, and keep every timeline handle aligned.
While a pointer is dragging a timeline handle during loading, update the timeline and readouts
without updating or drawing plot views. Apply the latest state once the drag ends.

## Current implementation

The incremental reader delivers raw append and completion events through
[`incremental_loader.py`](../../../src/ephem_toolkit/play_oem/incremental_loader.py). The
controller uses observed coverage during loading and applies parsed OEM `START_TIME` and
`STOP_TIME` bounds when final metadata is received. The
[`TimeRangeSlider`](../../../src/ephem_toolkit/play_oem/workspace/time_range_slider.py) already
keeps the slider domain, playback interval, plot endpoints, and current time as separate values,
but it does not draw the not-yet-loaded portion as a distinct region. Its `set_ranges()` call
updates the slider and handle positions together.

Playback- and plot-range grips report drag state, which the controller publishes as a store
`RangeHint`; that hint prioritizes derived work but does not suppress plot-view updates or redraw
requests. The current-time seek grip does not report drag lifecycle. The controller's
[`_dispatch_time_range`](../../../src/ephem_toolkit/play_oem/app/time_range_actions.py) path
updates visible views and queues redraws as ranges change.

## Interaction and loading rules

- The slider domain is the union of valid OEM-declared bounds and observed sample bounds. Missing,
  malformed, or reversed declared bounds fall back to observed bounds.
- Keep the declared slider domain separate from committed sample coverage and the playback clock's
  valid interval. Expanding the display domain must not make unloaded time playable or change
  clock bounds. Seeking into unloaded time continues to follow the clock's existing committed-
  coverage clamping behavior.
- During loading, visually distinguish the unread remainder from the loaded/playable interval.
  Do not depict OEM data gaps as unread data. On successful completion, remove the loading
  indication; on failure or cancellation, stop presenting the remainder as actively loading and
  retain the existing error/status behavior.
- Handle positions and time labels must be calculated from one consistent timeline state:
  slider domain, committed coverage, playback bounds, plot-range rule, and current time.
- During a pointer drag while loading, keep the timeline handles and readouts responsive, but
  defer plot-view updates and redraws. Coalesce handle changes and incoming store updates. On
  release or mouse-capture loss, refresh visible plots once from the latest range, cursor, and
  store snapshot. Preserve the existing redraw behavior when not loading.

## Implementation checklist

- **Status:** Not started.
- **Progress:** 0/9 checklist items.
- [ ] Publish generation-tagged declared time bounds from the background reader as soon as its
      parser reaches OEM metadata, before raw-row streaming completes. Keep parsing off the GUI
      thread and avoid a second whole-file scan.
- [ ] Initialize and expand the slider domain from valid declared bounds plus observed sample
      bounds. Fall back to observed bounds for absent, malformed, or reversed metadata, and do
      not change playback-clock bounds merely to expand the display domain.
- [ ] Track declared bounds, committed loading coverage, and load status separately. Advance
      committed coverage with each append and distinguish it from actual OEM gaps.
- [ ] Paint the not-yet-loaded part of the domain with a visually distinct, accessible treatment;
      clear it on successful completion and retain a non-loading/error state on failure or cancel.
- [ ] Apply slider domain, committed coverage, playback bounds, plot-range rule, and current time
      to the timeline control as one state update so all handles, labels, and the time marker
      move to their correct positions together. Preserve saved and pending range settings.
- [ ] Track seek-grip drag start/end and capture loss as well as playback- and plot-range drags.
      Keep timeline handles and readouts responsive while dragging.
- [ ] While loading and any timeline handle is being dragged, defer plot-view updates and redraw
      requests, coalescing playback, plot-range, cursor, and arriving store changes. Flush the
      latest state once when the drag ends; do not defer normal redraws when not loading.
- [ ] Add loader, slider, and wx interaction tests for metadata timing, invalid metadata,
      handle alignment, loading-color progression, failed/cancelled loads, and one redraw after
      drag completion using the latest loaded snapshot and range. Verify non-loading interaction
      remains unchanged.
- [ ] Update the active concepts and software-design documentation to describe the full timeline
      domain, loading indicator, and drag behavior.

**Done when:** declared OEM bounds define the slider domain before EOF; loaded and not-yet-loaded
time are distinguishable without confusing OEM gaps with pending data; all timeline handles and
the current-time marker align after the same update; and a loading-time drag causes no plot
updates/redraws until completion of the drag, followed by one refresh of the latest state.
**Depends on:** Step 27.
