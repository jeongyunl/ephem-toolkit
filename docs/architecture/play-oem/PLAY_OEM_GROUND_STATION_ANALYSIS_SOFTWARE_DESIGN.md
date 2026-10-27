# `play-oem` — Modular Ground Station Analysis Software Design

**Status: Proposed.** This design decomposes the existing Ground Station Access and Ground
Station Passes composites into small graph-panel views that share one station-access data source.

The previous implementation is recorded in the archived
[implementation report](./old/PLAY_OEM_GROUND_STATION_ANALYSIS_IMPLEMENTATION_REPORT.md).
The interface and workspace configurations for this proposal are in the
[GUI design](./PLAY_OEM_GROUND_STATION_ANALYSIS_GUI_DESIGN.md).

## Goals

- Replace the two composite station views with focused panels that each answer one question.
- Let users combine a small number of panels in the existing Main Analysis and Comparison stacks.
- Reuse access intervals, sampled station metrics, Plot Range, and exact-sample ECEF conversions.
- Preserve current playback, coverage, gap, and minimum-elevation semantics.
- Keep every panel useful on its own; selection links between panels are explicit.

## Proposed panel catalog

The proposal defines eight focused panel types. They are options for a workspace, not a default
request to open eight panels at once.

| Panel | Question | Primary content |
|---|---|---|
| Station Status | What is happening at this station now? | Current access state, azimuth, elevation, slant range, and mask |
| Pass Strip | When are access intervals in the selected Plot Range? | Compact chronological interval bands with coverage boundaries |
| Elevation Profile | How does elevation change over time? | Elevation against UTC with mask, pass bands, and playback marker |
| Azimuth Profile | Which direction is the station looking over time? | Azimuth against UTC, with north-wrap discontinuities |
| Range Profile | How does slant range change over time? | Station-to-spacecraft range against UTC |
| Pass List | Which passes overlap the selected range? | Chronological rows with interval times, peak, closest range, and limits |
| Sky View | Where does the selected pass appear in the local sky? | Azimuth/elevation polar path and its mask |
| Pass Ground Track | Where does the spacecraft travel during this pass? | Pass-bounded subpoint path and the selected station marker |

Station Status and Pass List are compact information panels rather than plots. Keeping them as
panels lets users arrange them beside the plots without putting a large table or status header
inside every graph.

## Data and cache architecture

Continue to use the app-scoped `StationAccessCache` and `EarthFixedPositionCache`. A view must
never prepare historical OEM samples independently. Playback updates may resolve current metrics
through the existing current-state path; they must not regenerate access history.

The current sampled look-angle profiles contain time, azimuth, and elevation, while access
intervals retain peak and minimum-range values. Add sampled slant range to the per-segment profile
so Range Profile and Pass Ground Track can consume the same prepared history:

```text
StationAccessProfile
  times_s
  azimuths_deg
  elevations_deg
  slant_ranges_km
```

Keep each profile confined to one valid OEM segment. Invalid samples remain non-finite and must
break plotted paths. Retain the existing interval-boundary azimuth/elevation values and
coverage/gap flags. Migrate the current `LookAngleProfile` shape without breaking its consumers:
either extend it compatibly or introduce `StationAccessProfile` with a compatibility accessor for
the existing elevation graph.

Range values are already computed as part of station metrics during access preparation. Retaining
them at those same epochs should not add cursor lookups, frame conversions, or another history
pass. Preserve the 30-second maximum access sample step, crossing and peak refinement, sample
limits, segment isolation, and sparse-data limitations.

`StationAccess` continues to hold the authoritative access intervals and per-segment profiles.
The panels are projections of this shared result:

- Station Status uses `current_station_metrics` and the shared exact-sample position cache.
- Pass Strip, Elevation Profile, and Pass List use cached intervals and profiles.
- Azimuth Profile and Range Profile use cached per-segment samples.
- Sky View uses cached azimuth/elevation samples and refined interval endpoints.
- Pass Ground Track uses the shared Earth-fixed position cache and clips displayed coordinates to
  the selected interval; it does not prepare station access again.

## Optional pass-comparison plots

The eight-panel catalog covers the core workflow. For users comparing pass quality, three
additional plots are simpler and cheaper than adding more sampled time histories:

| Candidate | Plot | Data already available |
|---|---|---|
| Peak Elevation per Pass | Pass peak time (or AOS) vs. peak elevation | `AccessInterval.peak_time_s`, `peak_elevation_deg` |
| Closest Range per Pass | Pass minimum-range time (or AOS) vs. minimum slant range | `minimum_range_time_s`, `minimum_range_km` |
| Pass Duration | AOS vs. duration bar | Interval start/end; duration only when both boundaries are complete |

Recommend Peak Elevation and Closest Range as the first optional additions if users need
pass-to-pass comparison. They expose useful existing interval metrics without extending profile
sampling. Pass Duration is less reliable for intervals clipped at OEM boundaries or limited by
gaps; omit or visibly mark those bars rather than presenting a partial duration as complete.
These are optional alternatives, not part of the initial eight-panel count. Prefer them over
adding more derived graphs until the core panels are evaluated with users.

An inclusive Plot Range overlap filter remains:

```text
interval.start_s <= plot_range.end_s
and interval.end_s >= plot_range.start_s
```

The range selects which passes are shown; it does not clip interval metrics or cause new access
preparation. Preserve the full OEM-bounded interval and mark coverage- or gap-limited boundaries
as uncertain.

## Panel responsibilities and interaction contracts

### Station Status

Show only values at the current playback epoch: station name and mask, access/no-access state,
azimuth, elevation, and slant range. Clearly state when the current OEM state is unavailable or
the OEM is unsupported. Do not repeat previous/next-pass summaries here; interval discovery
belongs in Pass Strip and Pass List.

### Pass Strip and profile plots

Pass Strip displays intervals over the shared Plot Range and distinguishes complete, coverage-
limited, and gap-limited boundaries. Selecting a band selects an interval but does not seek.
Elevation Profile retains the fixed 0°–95° vertical scale and shows the station mask and access
bands. Each Elevation, Azimuth, and Range Profile has an independent **Show only above minimum
elevation** checkbox, checked by default. When enabled, plot only samples whose elevation meets or
exceeds the station's mask; omit below-mask values as non-finite plot breaks so lines do not imply
usable geometry through those intervals. When disabled, show all samples. Azimuth Profile also
splits lines across the 0°/360° wrap rather than drawing a misleading vertical jump. Range Profile
labels slant range in kilometres. All time axes use UTC labeling and the shared Plot Range.

Clicking a time on a profile may seek playback, matching the existing Ground Station Access
interaction. Selecting a pass band is selection only; it must not move the clock or Plot Range.

### Pass List

Show only intervals overlapping Plot Range, in chronological order. Keep full OEM-bounded
details in the rows:

- Start and end UTC.
- Duration only when both boundaries are known.
- Peak elevation and its time.
- Minimum slant range and its time.
- Coverage/gap boundary status.

Focus pass updates shared Plot Range. Seek to peak changes playback only. Both actions are
explicit and disabled when their required time is unknown.

### Sky View and Pass Ground Track

Sky View displays one selected pass, azimuth clockwise from north, horizon at the outer radius,
zenith at the center, the station mask ring, and distinct start/peak/end/playback markers. It
does not contain a pass table. The textual summary identifies the station, pass, mask, peak, and
playback relation.

Pass Ground Track displays the selected pass interval on the existing geographic projection,
with the station marker highlighted. It does not draw a station-centered footprint or imply
radio visibility. Existing Ground Track remains the full-coverage map; this is a focused
pass-bounded view.

## Selection and workspace state

Keep station and interval selection local to each stack by default. This preserves the ability to
compare different stations in Main Analysis and Comparison. Views in the same stack may share a
small `StationAnalysisContext` containing:

```text
station_id
selected_interval_key  # stable interval identity, not a row index
```

The context carries selection only; Plot Range and playback remain app-wide. A Pass List selection
updates peer Pass Strip, Sky View, and Pass Ground Track panels in that stack. A Comparison stack
can optionally follow Main Analysis selection; it remains independent unless the user links it.
Opening a view from a pass row seeds its station and interval identity.

Station edits retain a selected station when its ID remains configured, clear stale interval
selection when the station's access result changes, and refresh already-open views. OEM
replacement invalidates station history and refreshes each panel. Closing a panel releases its
context subscription.

## Registry and compatibility

Register each panel as an ordinary graph view with a concise label. Keep the `overview` group
unchanged. Provide two explicit station-analysis presets:

- **Access Overview:** Station Status, Pass Strip, and Elevation Profile.
- **Pass Study:** Pass List and Sky View, with Pass Ground Track optional.

Azimuth Profile and Range Profile are available for users who need additional geometry. Do not
make a preset open every panel type. Keep the existing view names as aliases during migration:
`ground-station-access` opens Elevation Profile and `ground-station-passes` opens Pass List. Show
the new concise labels in the selector while preserving saved configurations and CLI selections.

## Failure and empty states

- No configured stations: explain how to add one; do not create a synthetic station.
- No OEM or unsupported center/frame: identify the required Earth-centered OEM.
- Current sample unavailable or in a segment gap: show unavailable state, not zero-valued metrics.
- No access in OEM coverage: distinguish it from no intervals in the current Plot Range.
- No intervals in Plot Range: display the UTC range and suggest widening it.
- Coverage- or gap-limited pass: retain known samples and identify the uncertain boundary.

## Validation

- Verify each panel uses the shared cache and does not trigger another history calculation.
- Test interval overlap, gap/coverage limitations, selection identity, and station/OEM refresh.
- Test azimuth wrapping, slant-range units, mask behavior, and profile gaps.
- Verify all eight panels can be opened individually and in both workspace stacks.
- Verify both presets use the expected views, preserve current `overview`, and do not open all
  panels by default.
- Check narrow, standard, and wide layouts, keyboard/accessibility names, and light/dark themes.
- Confirm aliases for the existing Ground Station Access and Ground Station Passes names.
