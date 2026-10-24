# `play-oem` — Shared Time Range Implementation Report

> Status: **implemented; GUI acceptance is incomplete**. The playback-linked plot range model,
> playback limits, shared filtering, plot controls, and range grips are present. Automated
> checks cover the model and rendering behavior. Native wx interaction and display-backed
> acceptance have not been completed.

The archived design specifications and visual studies are in [`old/`](./old/):
[software design](./old/PLAY_OEM_TIME_RANGE_SOFTWARE_DESIGN.md) and
[GUI design](./old/PLAY_OEM_TIME_RANGE_GUI_DESIGN.md). The current application architecture
is in [PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md).

## Implemented behavior

- OEM coverage, playback bounds, and effective plot bounds are distinct. Each plot endpoint
  independently follows its corresponding playback handle, uses an offset from current playback
  time, or stays at a fixed UTC timepoint. Both endpoints follow playback by default.
- Playback clock movement, seek, stepping, start/end navigation, and loop behavior use the
  playback bounds. Following plot endpoints track playback-bound edits independently; offset
  endpoints track playback time, and fixed endpoints remain unchanged.
- Plot range controls use only the two timeline handles. Right-clicking either plot handle opens
  a compact Follow/Offset/Fixed mode menu. Plot handles use a triangle for Follow, a diamond for
  Offset, and a square for Fixed. Changing modes preserves the handle's current position where
  possible; choosing Follow snaps it to the matching playback bound. Follow handles are not
  draggable or keyboard-nudgable. Offset and Fixed handle positions are changed by dragging.
- Resolution clips to OEM coverage; valid empty and singleton selections are supported. Plot
  edits do not change playback bounds or seek the clock.
- Time-series views select inclusive samples before decimation, retain segment gaps and full
  source arrays, use the shared plot X limits, and preserve full-data Y baselines. RTN uses its
  own timestamps and segment IDs.
- Matplotlib and VTK orbit paths and ground tracks apply the same timestamp filter. Spatial
  navigation is retained; current markers, footprints, and tails are restricted to the
  effective plot range.
- A controller-owned dispatch resolves the shared range and updates visible views. Hidden views
  receive the latest state when shown. A loaded file restores its saved playback bounds when they
  remain valid for its coverage and restores that file's saved plot range; files without a saved
  plot range follow playback bounds by default. Plot-range customizations persist per OEM file.
- The timeline no longer has a separate plot-range editor row, value inputs, enable checkbox, or
  All OEM data button. Plot filtering remains enabled and is managed through the timeline handles.
  `TimeRangeSlider` uses a custom-painted track and seek thumb, colors the playable interval
  separately from seek progress, and uses four sibling grip controls with tooltips, pointer
  dragging, capture-loss handling, collision fan-out, and keyboard nudging. The playback footer
  stacks dedicated time-readout, timeline, and playback-control row panels vertically, with
  compact padding and small gaps between rows.

## Current limitations and acceptance gaps

- Plot endpoint timestamps and offsets are no longer editable as text; users adjust them by
  dragging the corresponding handle. The All OEM data toggle is also unavailable in the timeline.
- The slider's plot and playback grips occupy separate rows. Its keyboard nudge distance is
  based on OEM span (one thousandth of the span, or one second for a zero span), rather than a
  fixed one-second/minute scheme.
- Automated coverage does not establish custom track alignment, live painting, pointer capture,
  focus traversal, high-DPI/theme behavior, or cross-platform wx behavior. These need a live GUI
  session. VTK display/context-dependent checks are skipped in the recorded run.
- A workspace test fixture lacks `FakeSplitter.GetDefaultSashSize`; display-backed native wx
  acceptance also requires a live GUI session.

## Verification evidence

- Range model, playback actions, plotting, editor, clock, RTN, ground-track, 3D trajectory, and
  VTK test selection: **88 passed, 7 skipped**.
- `python -m compileall -q src/ephem_toolkit/play_oem` passed.
- `git diff --check` passed at the time of the recorded implementation work.
- Additional recorded coverage: model 23 passed; playback clock/action/application/control
  selection 123 passed; time-series selection 129 passed; spatial selection 27 passed, 7 skipped.

The automated runs above were recorded during implementation; they were not rerun as part of
this report edit. Live GUI acceptance, complete event-routing coverage, performance benchmarks,
and supported-platform coverage remain unverified.
