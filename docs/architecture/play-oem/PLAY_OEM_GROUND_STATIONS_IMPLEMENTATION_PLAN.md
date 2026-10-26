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
Implementation status and validation evidence are tracked below.

## How to use this plan

Implement one pending step at a time in dependency order. A step is done only when its checklist
and completion criteria pass. Update this document with status and evidence as implementation
proceeds. If implementation changes a design decision, update the software or GUI design first,
then keep this plan consistent with the revised decision.

### 1. Add the station model and configuration schema

Create the validated station record and add a `[ground_stations]` array-of-inline-tables
representation to `play-oem.toml`. Continue reading legacy station definitions from
`play-oem-state.toml` and migrate them when the new configuration section is absent. Keep
window, recent-file, and workspace state in the app-maintained state file.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Define the station record, stable ID generation, coordinate conventions, and validation.
- [x] Add configuration serialization and deserialization with finite/range checks.
- [x] Migrate legacy station records from saved state into user configuration.
- [x] Test empty, one-station, multiple-station, malformed, and legacy files.
- [x] Verify station updates preserve unrelated configuration and application state.

**Done when:** station definitions round-trip through `play-oem.toml`, invalid definitions are
reported through the established config policy, and legacy state files still load.
**Depends on:** None.

### 2. Implement geometry and access-window preparation

Implement station ECEF/ENU conversion and current-time access metrics without wxPython or
Matplotlib dependencies. Implement pass interval preparation over valid OEM segments, crossing
refinement, gap handling, caching, and invalidation.

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Convert validated WGS-84 geodetic station coordinates to ECEF.
- [x] Calculate azimuth, elevation, slant range, and mask-based access from ITRF spacecraft
  positions.
- [x] Resolve current state through `OemCursor` and reject unsupported centers/frames explicitly.
- [x] Detect and refine access crossings without bridging OEM segment gaps.
- [x] Handle clipped coverage endpoints and insufficient sample cadence explicitly.
- [x] Test known ENU cases, mask boundaries, frame conversion errors, gaps, and crossing tolerance.

**Done when:** calculations pass independent geometry checks and produce access windows with
documented timing accuracy without extrapolating outside OEM coverage.
**Depends on:** Step 1.

### 3. Build the Ground Stations manager

Add the Ground Stations Controls & Info page, expandable station list, empty state, inline
Add/Edit flow, and Remove action. Station management must work before an OEM is loaded.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Add the feature-rail page and keyboard-accessible station list.
- [x] Implement expandable rows with inline Add/Edit fields, validation, Save, and Cancel behavior.
- [x] Implement removal confirmation, unsaved-edit handling, and keyboard-accessible expansion.
- [x] Update app state and persist changes through the established state writer.
- [x] Test zero/one/multiple station UI states and CRUD validation.

**Done when:** station definitions can be safely managed and persisted without an OEM loaded.
**Depends on:** Step 1.

### 4. Implement and register the Ground Station Access view

Create a graph panel with a multi-station contact timeline, playback cursor, current metrics,
and selected-station pass details. Integrate with the existing graph-panel lifecycle and
registry. Include the view in `all`; leave `overview` unchanged.

- **Status:** Done.
- **Progress:** 6/6 checklist items.
- [x] Add `ground-station-access` to view labels, registry, factory, and controller.
- [x] Draw station access rows, pass intervals, coverage-edge states, and playback cursor.
- [x] Add selected-station current metrics and previous/next pass summary.
- [x] Implement empty-station, no-OEM, unsupported-OEM, and cursor-gap states.
- [x] Refresh on station edits and OEM replacement; avoid full pass recomputation per clock tick.
- [x] Test registry/launch behavior, live updates, seek behavior, and panel cleanup.

**Done when:** the access panel behaves like other graph views and stays synchronized with
playback and station/OEM changes.
**Depends on:** Steps 1, 2, and 3.

### 5. Document, profile, and validate the feature

Complete user-facing guidance, verify performance, and run focused and broader tests.

- **Status:** Done.
- **Progress:** 5/5 checklist items.
- [x] Add a user guide for station management, coordinate units, access metrics, and limitations.
- [x] Link the software design, GUI design, and implementation plan from the main `play-oem`
  architecture documents.
- [x] Profile pass preparation with a representative large OEM and multiple stations; record
  workload, timing, and the sampling/crossing accuracy.
- [x] Run all `play-oem` tests and the relevant repository test suite.
- [x] Verify missing/invalid data errors are visible and that existing Ground Track behavior is
  unchanged.

**Completion evidence:** the full `play-oem` suite passes (376 passed, 3 skipped). The full
repository suite passes (1,761 passed, 3 skipped, 3 deselected).
**Done when:** documentation matches tested behavior, performance is recorded, and acceptance
criteria in the software design are met.
**Depends on:** Steps 2, 3, and 4.
