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

The incremental reader publishes generation-tagged segment metadata, raw appends, parser
progress, and completion events. The controller combines valid UTC metadata bounds with observed
sample bounds for the slider domain, while playback remains bounded by committed playable
coverage. The `TimeRangeSlider` keeps the domain, loaded coverage, playback bounds, plot
endpoints, and current time distinct; it marks the unread remainder and reports unloaded time in
its hover text.

The playback, plot-range, and current-time grips report drag lifecycle, including mouse-capture
loss. While loading, the controller defers and coalesces plot-view updates and redraw requests
during a drag, then refreshes from the latest range, cursor, and store snapshot when the drag
ends. Seeking into unloaded time follows the clock's existing loaded-coverage clamping behavior;
the timeline tooltip identifies the requested time as not loaded.

## Interaction and loading rules

- The slider domain is the union of valid OEM-declared bounds and observed sample bounds. Missing,
  malformed, or reversed declared bounds fall back to observed bounds. `play-oem` supports only
  `TIME_SYSTEM = UTC` for now; convert declared bounds with the same UTC-to-TT path as sample
  epochs and report other time systems as unsupported.
- Keep the declared slider domain separate from committed sample coverage and the playback clock's
  valid interval. Expanding the display domain must not make unloaded time playable or change
  clock bounds. Seeking into unloaded time continues to follow the clock's existing committed-
  coverage clamping behavior; give the user feedback that the requested time is not loaded, and
  do not apply a queued seek later without a new user action.
- Determine the unread region from parser progress, not merely the minimum/maximum observed sample
  epochs. Once the parser has passed a declared interval, do not depict a real OEM gap or a
  metadata-to-first-sample interval as unread data.
- During loading, visually distinguish the unread remainder from the loaded/playable interval,
  with a legend or accessible text that explains the color. On successful completion, remove the
  loading indication; on failure or cancellation, stop presenting the remainder as actively
  loading and retain the existing error/status behavior.
- Handle positions and time labels must be calculated from one consistent timeline state:
  slider domain, committed coverage, playback bounds, plot-range rule, and current time.
- During a pointer drag while loading, keep the timeline handles and readouts responsive, but
  defer plot-view updates and redraws. Coalesce handle changes and incoming store updates. On
  release or mouse-capture loss, refresh visible plots once from the latest range, cursor, and
  store snapshot. Apply equivalent behavior to keyboard-driven changes: discrete nudges may flush
  once per command, while a repeated adjustment must not redraw for each repeat event. Preserve
  the existing redraw behavior when not loading. Ignore old-generation metadata, appends, or
  pending redraws after file replacement, and clear drag state during cancellation or shutdown.

## Implementation checklist

The checklist is in dependency order: establish metadata semantics, expose loader state, model
the timeline, synchronize and render the control, add interaction lifecycle, defer plot work, then
validate and document. Complete each item before starting the next; later UI and redraw work
depends on the preceding metadata and state contracts.

- **Status:** Complete.
- **Progress:** 9/9 checklist items.
- [x] Confirm how the parser exposes `START_TIME`, `STOP_TIME`, `TIME_SYSTEM`, and segment-local
      metadata. Define the file-wide bounds and ordering rules; cover inconsistent or reversed
      declarations. Limit `play-oem` to UTC and leave other core parser consumers unchanged.
- [x] Publish generation-tagged metadata as soon as the background parser reaches it, before
      raw-row streaming completes. Validate UTC before publishing or appending that segment.
      Include committed parser-progress watermarks with append events. Keep parsing off the GUI
      thread and avoid a second whole-file scan.
- [x] Build normalized timeline state with declared bounds, observed sample bounds, parser
      progress, and load status kept separately. Use the union of valid declared and observed
      bounds for the slider domain; fall back to observed bounds for absent or invalid metadata.
      Do not change playback-clock bounds merely to expand the display domain.
- [x] Apply slider domain, committed coverage, playback bounds, plot-range rule, and current time
      to the timeline control as one state update so all handles, labels, and the time marker
      move to their correct positions together. Preserve saved and pending range settings.
- [x] Paint the not-yet-loaded part of the domain with a visually distinct, accessible treatment
      and add a legend or accessible text. Base it on parser progress, not sample min/max; do not
      depict OEM gaps or already-processed intervals as unread. Clear the loading treatment on
      success and stop presenting it as active loading on failure or cancel. Explain seeks into
      unloaded time while preserving the clock's current clamping behavior.
- [x] Track seek-grip drag start/end and capture loss as well as playback- and plot-range drags.
      Keep timeline handles and readouts responsive while dragging; cover keyboard adjustments
      with equivalent discrete or repeated-input behavior.
- [x] While loading and any timeline handle is being dragged, defer plot-view updates and redraw
      requests, coalescing playback, plot-range, cursor, and arriving store changes. Flush the
      latest state once when the drag ends; do not defer normal redraws when not loading. Clear
      drag state and discard stale deferred work on completion, failure, cancellation, file
      replacement, or app shutdown.
- [x] Add loader, slider, and wx interaction tests for metadata timing, invalid metadata,
      `TIME_SYSTEM` conversion, multi-segment bounds, parser progress versus OEM gaps,
      handle alignment/collision, zero-span and one-sample inputs, loading-color progression and
      accessibility, seek feedback in unloaded time, failed/cancelled/replaced loads, keyboard
      adjustment, and one redraw after drag completion using the latest snapshot and range.
      Verify non-loading interaction remains unchanged.
- [x] Update the active concepts and software-design documentation to describe the full timeline
      domain, loading indicator, and drag behavior.

**Done when:** correctly normalized OEM bounds define the slider domain before EOF; loaded and
not-yet-loaded time are distinguishable without confusing OEM gaps with pending data; all
timeline handles and the current-time marker align after the same update; an unloaded-time seek
is clearly communicated without claiming the clock reached it; and a loading-time drag causes no
plot updates/redraws until completion of the interaction, followed by one refresh of the latest
state with no stale work from an old load generation.
**Depends on:** Step 27.
