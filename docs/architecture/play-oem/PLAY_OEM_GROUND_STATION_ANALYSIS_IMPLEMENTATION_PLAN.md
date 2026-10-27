# `play-oem` — Ground Station Analysis Implementation Plan

Requirements and panel behavior: [PLAY_OEM_GROUND_STATION_ANALYSIS_SOFTWARE_DESIGN.md](./PLAY_OEM_GROUND_STATION_ANALYSIS_SOFTWARE_DESIGN.md).
Workspace and visual behavior:
[PLAY_OEM_GROUND_STATION_ANALYSIS_GUI_DESIGN.md](./PLAY_OEM_GROUND_STATION_ANALYSIS_GUI_DESIGN.md).
The prior composite implementation is recorded in the archived
[implementation report](./old/PLAY_OEM_GROUND_STATION_ANALYSIS_IMPLEMENTATION_REPORT.md).

Ground Station Access and Ground Station Passes already provide the baseline station metrics,
access cache, elevation graph, pass table, and sky plot. This plan replaces those composite
surfaces with eight focused panels while preserving their established calculations and
user-facing semantics.

## Current implementation baseline

`station_access.py` prepares OEM-segment-bounded access intervals, elevation profiles, and
azimuth/elevation profiles in a reusable `StationAccessCache`. The existing Access graph and
Passes view consume this prepared history. The Passes view currently combines a table and Sky
View, owns local station/pass selection, and lays out both panels vertically. The view registry
still exposes the legacy `ground-station-access` and `ground-station-passes` selections.

Treat the existing interval refinement, sample limits, segment/gap handling, Plot Range overlap,
UTC formatting, mask behavior, and explicit Focus pass/Seek to peak actions as compatibility
requirements. Panel views must not independently prepare historical station metrics.

## How to use this plan

Work **one pending numbered step at a time, in order**. Do not begin a later pending step until
the current step's checklist and completion criteria pass. Each dependency field identifies its
prerequisite. Step 1 has no dependency.

When a step is complete, move its full entry to the `Completed steps` section at the end of this
document. Preserve its original number, status, progress, checklist, completion criteria, and
dependency so the implementation history remains auditable.

For a numbered step with substeps, keep completed substeps under the active parent until every
substep is done. Then move the entire parent entry, including all substep statuses and evidence,
to `Completed steps` as one unit.

If implementation cannot progress in the documented order, stop and reevaluate the plan before
starting work out of sequence. Update the step order, dependencies, completion criteria, and
status/progress fields here so the plan reflects the actual dependency order.

If implementation changes affect the proposed interfaces, data model, panel behavior, or
workspace semantics, update the relevant software or GUI design before proceeding with dependent
steps. Keep this plan, both designs, and the implementation consistent.

For every step, keep the status and progress fields current:

- `Not started` — no work begun.
- `In progress` — implementation or its checks are underway.
- `Blocked` — cannot proceed; record the blocker.
- `Done` — all checklist items and completion criteria pass.

Progress is the number of checklist items completed. Do not mark a step done based only on code
being written.

## Implementation guardrails

- Keep access history app-scoped and shared. Views project cached results; they do not resample
  OEM history or convert the same states independently.
- Keep each sampled profile within one valid OEM segment. Preserve non-finite gaps as plot breaks.
- Filter intervals by inclusive Plot Range overlap without changing their OEM-bounded metrics or
  presenting clipped/gap-limited duration as complete.
- Keep station and selected interval local to each workspace stack unless **Follow selection** is
  enabled. Use stable interval identity rather than a row index.
- Preserve the existing `overview` group and legacy plot selections. Add new optional presets
  without opening every Ground Station panel by default.
- Use the proposed compact side-by-side Pass Study when both panels fit at usable widths; stack
  Pass List above Sky View when they do not. Do not shrink axes or table columns below usable
  sizes to force the compact arrangement.

## Active implementation sequence

### 1. Extend shared station profiles for all panel data

Add sampled slant range to the per-segment station profile using the station metrics already
computed during access preparation. Preserve compatibility for the existing elevation and
Passes views, and do not add another OEM traversal or position conversion. Update the access
cache result as the single source for the new profiles.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Extend the profile model with slant range while preserving existing profile consumers.
- [x] Populate the new values from the same access-preparation samples and shared conversions.
- [x] Preserve segment boundaries, invalid-sample gaps, sample limits, and cache invalidation.
- [x] Add unit tests for range values, segment isolation, and invalid samples.
- [x] Verify existing access/pass profile tests and shared-cache behavior remain unchanged.

**Done when:** one cached station-access result supplies time, azimuth, elevation, and slant-range
samples per valid OEM segment, with no additional history pass.
**Depends on:** None.

### 2. Add per-stack station-analysis selection and refresh state

Introduce the small `StationAnalysisContext` described in the software design. Share station and
stable selected-interval identity only among views in the same stack. Keep Main Analysis and
Comparison independent by default. Define station edits, OEM replacement, and panel
close/unsubscribe behavior before building the linked panels; optional follow-selection is wired
with the workspace presets in Step 6.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Define and test stable interval identity and context selection/notification behavior.
- [x] Scope contexts to their owning graph stack; do not make Plot Range or playback stack-local.
- [x] Preserve independent station and interval selection between Main Analysis and Comparison.
- [x] Refresh or clear stale selection after station edits and OEM replacement.
- [x] Release view subscriptions when panels close.

**Done when:** station and pass selection propagate only to peer panels in the same stack, with
independent Main Analysis and Comparison contexts.
**Depends on:** None.

### 3. Implement Station Status, Pass Strip, and time-profile panels

Build the focused current-state and time-history panels on the existing wx graph-panel lifecycle.
Reuse current-state lookup for Station Status and cached intervals/profiles for Pass Strip and the
Elevation, Azimuth, and Range profiles. Retain the existing elevation graph behavior while
extracting shared rendering or range-update behavior where needed.

- **Status:** Done.
- **Progress:** 7/7 checklist items.
- [x] Implement Station Status with explicit unavailable, unsupported-OEM, and no-station states.
- [x] Implement Pass Strip over the shared Plot Range with boundary limitation markers.
- [x] Implement Elevation Profile with its fixed 0°–95° scale, mask, intervals, and playhead.
- [x] Implement Azimuth Profile with line breaks across north wrap and invalid data.
- [x] Implement Range Profile in kilometres from cached slant-range samples.
- [x] Test Plot Range updates, UTC labels, pass selection, gaps, and single shared preparation.
- [x] Register each of the five panels for independent opening and graph-panel selection.

**Done when:** all five panels open independently and update from shared cached/current-state
data without duplicating station-history preparation.
**Depends on:** Steps 1 and 2.

### 4. Implement Pass List, Sky View, and responsive Pass Study

Refactor the existing combined Passes view into the focused Pass List and Sky View panels.
Preserve full pass details, stable selection links, and explicit pass actions. In Pass Study,
place the compact list beside Sky View only when both meet usable minimum sizes; otherwise stack
the list above the larger sky plot.

- **Status:** Done.
- **Progress:** 7/7 checklist items.
- [x] Implement chronological Pass List rows for interval UTC, known duration, peak and its time,
  minimum range and its time, and coverage/gap status.
- [x] Show only intervals overlapping Plot Range while retaining OEM-bounded details.
- [x] Implement Sky View with clockwise azimuth, zenith at center, mask, path, and distinct
  interval/playback markers.
- [x] Link row selection to Sky View using the stable interval identity from Step 2.
- [x] Keep Focus pass and Seek to peak explicit and disabled when their required times are
  unavailable.
- [x] Implement compact side-by-side and stacked narrow-width layouts without unusable panel
  compression.
- [x] Test selection, range changes, coverage/gap-limited intervals, azimuth breaks, and both
  layout modes.

**Done when:** Pass List and Sky View work independently and together, preserve existing pass
semantics, and adapt between compact and stacked layouts without losing selection.
**Depends on:** Step 3.

### 5. Implement the pass-bounded Ground Track panel

Add the focused Pass Ground Track using the shared Earth-fixed position cache and selected
interval. Keep it clipped to that pass, retain OEM segment breaks, and distinguish the station
marker. Do not change the existing full-coverage Ground Track or imply radio visibility.

- **Status:** Done.
- **Progress:** 4/4 checklist items.
- [x] Reuse cached Earth-fixed positions; do not perform a second full state conversion.
- [x] Clip displayed coordinates to the selected interval and preserve OEM/gap breaks.
- [x] Highlight the selected station and provide the designed no-data/unavailable states.
- [x] Test interval changes, source refresh, and shared position-cache reuse.

**Done when:** Pass Ground Track displays only the selected pass using shared prepared positions
and does not alter existing Ground Track behavior.
**Depends on:** Step 2.

### 6. Register panel names, compatibility aliases, and workspace presets

Expose the eight focused panels through the view registry, selector, CLI selection, and workspace
panel lifecycle. Preserve legacy saved/CLI plot names by mapping Ground Station Access to
Elevation Profile and Ground Station Passes to Pass List. Add optional Access Overview and Pass
Study presets without changing `overview`.

- **Status:** Done.
- **Progress:** 7/7 checklist items.
- [x] Register concise names and labels for all eight focused views.
- [x] Map legacy Ground Station Access and Ground Station Passes selections to the specified
  focused views.
- [x] Implement Access Overview with Station Status, Pass Strip, and Elevation Profile.
- [x] Implement Pass Study with linked Pass List and Sky View; retain the compact responsive
  paired layout for the Ground Track **Open Passes** action.
- [x] Add explicit optional Comparison follow-selection and verify it stays off by default.
- [x] Keep presets optional and preserve the existing `overview` group and default view behavior.
- [x] Test registry expansion, CLI/saved-selection compatibility, panel opening, and no duplicates.

**Done when:** each focused panel is selectable independently, both presets open the intended
views, and existing saved selections and `overview` continue to work.
**Depends on:** Steps 4 and 5.

### 7. Complete failure states, accessibility, and visual behavior

Bring all new panels to the proposed empty/failure-state and accessibility contracts. Keep status
explicit for unsupported OEMs, missing stations, unavailable samples, OEM gaps, no access, and an
empty Plot Range. Verify keyboard interaction, accessible names, theme-aware styling, and
comparison selection rules.

- **Status:** In progress.
- **Progress:** 3/5 checklist items.
- [x] Verify documented empty, unsupported, unavailable, and limited-coverage states exercised
  by focused tests.
- [ ] Verify table selection, station controls, pass actions, and layout controls are keyboard
  accessible and have accessible names.
- [x] Verify mask and boundary states remain distinguishable without color alone.
- [ ] Verify light/dark theme contrast, labels, units, and UTC presentation.
- [x] Verify Comparison follows selection only when enabled and otherwise remains independent.

**Done when:** all panels provide explicit states and meet the GUI design's accessibility and
workspace interaction requirements.
**Depends on:** Step 6.

### 8. Run integration acceptance and publish Ground Station documentation

Validate the complete modular workflow and document the new panel catalog and presets. Update
the user-facing guide and relevant technical references only after behavior is verified.

- **Status:** In progress.
- **Progress:** 5/6 checklist items.
- [x] Run focused station-access, panel, registry, workspace, and app tests.
- [x] Run the complete repository test suite and resolve failures caused by this feature.
- [ ] Smoke-test individual panels, both presets, responsive Pass Study, and two-stack comparison.
- [x] Verify no panel triggers independent history preparation and Plot Range work remains
  restricted to the requested interval.
- [x] Update Ground Station user documentation, examples, and links to the new design.
- [x] Review the final design/implementation consistency and record accepted limitations.

**Done when:** focused and full tests pass, the integrated workflows satisfy the design contracts,
and user documentation reflects verified behavior.
**Depends on:** Step 7.

## Completed steps

Steps 1–6 are complete; the wx-backed visual acceptance items in Steps 7–8 still need an
interactive display environment. The compact paired Pass Study remains accessible through the
Ground Track **Open Passes** action; the named Pass Study preset opens independently selectable
Pass List and Sky View panels.
