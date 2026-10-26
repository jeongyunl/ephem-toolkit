# `play-oem` — Ground Stations Implementation Plan

Requirements: [PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md). Shared software architecture:
[PLAY_OEM_SOFTWARE_DESIGN.md](./PLAY_OEM_SOFTWARE_DESIGN.md). Ground Stations software design:
[PLAY_OEM_GROUND_STATIONS_SOFTWARE_DESIGN.md](./PLAY_OEM_GROUND_STATIONS_SOFTWARE_DESIGN.md).
GUI design:
[PLAY_OEM_GROUND_STATIONS_GUI_DESIGN.md](./PLAY_OEM_GROUND_STATIONS_GUI_DESIGN.md).
Visual mockups are
[the manager](./mockup-ground-stations-manager.svg),
[the inline expanded station details](./mockup-ground-station-editor.svg), and
[the access panel](./mockup-ground-station-access.svg).
This plan is a proposal; all steps are **Not started**.

## How to use this plan

Implement one pending step at a time in dependency order. A step is done only when its checklist
and completion criteria pass. Update this document with status and evidence as implementation
proceeds. If implementation changes a design decision, update the software or GUI design first,
then keep this plan consistent with the revised decision.

### 1. Add the station model and saved-state schema

Create the validated station record and station collection in `SavedAppState`. Add a
`[ground_stations]` array-of-inline-tables representation to the app state file and bump the
state version. Continue accepting every currently supported prior state version, defaulting
stations to an empty collection. Preserve atomic writes and unrelated state.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Define the station record, stable ID generation, coordinate conventions, and validation.
- [ ] Add collection serialization and deserialization with finite/range checks.
- [ ] Add migration behavior for current and older state versions.
- [ ] Test empty, one-station, multiple-station, malformed, and prior-version files.
- [ ] Verify station updates preserve window, recent-file, and workspace state.

**Done when:** the station collection round-trips correctly, invalid definitions are reported
through the established state policy, and old state files still load.
**Depends on:** None.

### 2. Implement geometry and access-window preparation

Implement station ECEF/ENU conversion and current-time access metrics without wxPython or
Matplotlib dependencies. Implement pass interval preparation over valid OEM segments, crossing
refinement, gap handling, caching, and invalidation.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Convert validated WGS-84 geodetic station coordinates to ECEF.
- [ ] Calculate azimuth, elevation, slant range, and mask-based access from ITRF spacecraft
  positions.
- [ ] Resolve current state through `OemCursor` and reject unsupported centers/frames explicitly.
- [ ] Detect and refine access crossings without bridging OEM segment gaps.
- [ ] Handle clipped coverage endpoints and insufficient sample cadence explicitly.
- [ ] Test known ENU cases, mask boundaries, frame conversion errors, gaps, and crossing tolerance.

**Done when:** calculations pass independent geometry checks and produce access windows with
documented timing accuracy without extrapolating outside OEM coverage.
**Depends on:** Step 1.

### 3. Build the Ground Stations manager

Add the Ground Stations Controls & Info page, expandable station list, empty state, inline
Add/Edit flow, and Remove action. Station management must work before an OEM is loaded.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Add the feature-rail page and keyboard-accessible station list.
- [ ] Implement expandable rows with inline Add/Edit fields, validation, Save, and Cancel behavior.
- [ ] Implement removal confirmation, unsaved-edit handling, and keyboard-accessible expansion.
- [ ] Update app state and persist changes through the established state writer.
- [ ] Test zero/one/multiple station UI states and CRUD validation.

**Done when:** station definitions can be safely managed and persisted without an OEM loaded.
**Depends on:** Step 1.

### 4. Implement and register the Ground Station Access view

Create a graph panel with a multi-station contact timeline, playback cursor, current metrics,
and selected-station pass details. Integrate with the existing graph-panel lifecycle and
registry. Include the view in `all`; leave `overview` unchanged.

- **Status:** Not started.
- **Progress:** 0/6 checklist items.
- [ ] Add `ground-station-access` to view labels, registry, factory, and controller.
- [ ] Draw station access rows, pass intervals, coverage-edge states, and playback cursor.
- [ ] Add selected-station current metrics and previous/next pass summary.
- [ ] Implement empty-station, no-OEM, unsupported-OEM, and cursor-gap states.
- [ ] Refresh on station edits and OEM replacement; avoid full pass recomputation per clock tick.
- [ ] Test registry/launch behavior, live updates, seek behavior, and panel cleanup.

**Done when:** the access panel behaves like other graph views and stays synchronized with
playback and station/OEM changes.
**Depends on:** Steps 1, 2, and 3.

### 5. Document, profile, and validate the feature

Complete user-facing guidance, verify performance, and run focused and broader tests.

- **Status:** Not started.
- **Progress:** 0/5 checklist items.
- [ ] Add a user guide for station management, coordinate units, access metrics, and limitations.
- [ ] Link the software design, GUI design, and implementation plan from the main `play-oem`
  architecture documents.
- [ ] Profile pass preparation with a representative large OEM and multiple stations; record
  workload, timing, and the sampling/crossing accuracy.
- [ ] Run all `play-oem` tests and the relevant repository test suite.
- [ ] Verify missing/invalid data errors are visible and that existing Ground Track behavior is
  unchanged.

**Done when:** documentation matches tested behavior, performance is recorded, and acceptance
criteria in the software design are met.
**Depends on:** Steps 2, 3, and 4.
