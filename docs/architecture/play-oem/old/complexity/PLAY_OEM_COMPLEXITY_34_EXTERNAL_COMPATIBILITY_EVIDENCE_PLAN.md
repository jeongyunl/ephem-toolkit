# play-oem — External Compatibility Evidence Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Current evidence priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior cursor/backend inventory:
[PLAY_OEM_COMPLEXITY_10_CURSOR_BACKEND_COMPATIBILITY_PLAN.md](./PLAY_OEM_COMPLEXITY_10_CURSOR_BACKEND_COMPATIBILITY_PLAN.md).
Prior saved-state investigation:
[PLAY_OEM_COMPLEXITY_8_SAVED_STATE_PARSING_VALIDATION_PLAN.md](./PLAY_OEM_COMPLEXITY_8_SAVED_STATE_PARSING_VALIDATION_PLAN.md).

## Goal

Gather verifiable evidence about whether selected Play-OEM compatibility
surfaces are documented promises or used by downstream consumers. Focus on the
legacy `OemCursor` path, directly consumed store APIs, and saved-state formats
identified in prior investigations.

This is an evidence inventory, not an API audit or retirement proposal. Make no
code or compatibility changes. Do not infer that a surface is unused from the
absence of an in-repository caller or a search result.

## Closure — 2026-11-11

**Status:** Closed before completion by maintainer direction.

The project maintainer stated that the project is not being used by others yet
and that compatibility is not a concern. External-consumer evidence is
therefore not a gate for the current complexity work; the candidate evidence
matrix was not completed and this inventory is not scheduled. No compatibility
or source changes were made. Reopen only if the maintainer's scope decision
changes.

## Why this step

Plan 10 completed the internal cursor and 3D backend inventory and found no
behavioral mismatch requiring consolidation; it explicitly left external use
unknown. Plan 8 documented saved-state parsing and legacy-field behavior.
Plan 33 completed the dependency and responsibility map without identifying a
boundary change to implement. This document captured a possible follow-up to
resolve external-use uncertainty. The maintainer later determined that
compatibility is not a concern and closed this investigation before its
evidence matrix was completed.

The representative workload study in Plan 32 remains deferred indefinitely.
Native GTK/MSW and VTK lifecycle work remains conditional on suitable runners.
This plan is retained only as a record of the proposed scope and closure
decision; it is not an active task.

## Scope and baseline

- Record the source revision, worktree state, evidence sources, search dates,
  and access limitations. Tie conclusions to this snapshot.
- Reuse Plan 10's cursor, package-export, and CLI/config inventory and Plan 8's
  saved-state findings. Do not repeat their behavior or backend traces.
- Limit candidates to:
  - the legacy `OemCursor` path and relevant importable cursor surfaces;
  - directly exposed or documented `OemDataStore` APIs implicated by the
    existing compatibility assessment;
  - persisted saved-state versions and fields with compatibility handling.
- Inspect package metadata, documentation, examples, release records, and
  available downstream-consumer evidence only to answer whether those
  candidates are promised or used.
- Use only public or otherwise authorized consumer sources. Do not inspect
  private user data, infer use from telemetry that is not available, or contact
  consumers without authorization.
- Exclude backend behavior, native GUI certification, performance or memory
  measurement, production changes, and a broad public-API audit.

## Evidence to collect

| Evidence class | Record | Limitation |
| --- | --- | --- |
| Declared project surface | Package exports, importable modules, documented examples, CLI entry points, API docs, and explicit compatibility/deprecation policy. | An undocumented surface may still be relied upon; packaging alone does not establish a stable API commitment. |
| Release evidence | Published versions, release notes, and available distribution artifacts relevant to the candidate surface. | Distribution proves availability, not downstream use or a support promise. |
| Downstream references | Exact symbol, module, or saved-state references found in authorized public or owner-provided consumer sources; include source URL/revision and search scope. | Search coverage is incomplete. A missing result is not proof of no consumer. |
| Maintainer or consumer confirmation | Confirmed support expectations or known integrations, with date and scope. | No response or unavailable contact leaves the question unknown. |
| Aggregate package signals | Public dependency or download information, if readily available and relevant. | These signals do not identify use of a particular symbol or format and cannot settle a removal decision. |

For each claim, record its source, date, exact candidate surface, coverage,
confidence, and whether it is direct evidence or contextual signal. Keep
positive evidence and search limitations equally visible.

## Investigation procedure

1. Record the current revision and worktree state. Read the relevant conclusions
   from Plans 8 and 10 and copy their candidate surfaces into an evidence
   matrix; do not broaden the list without a concrete reason.
2. Verify each candidate's current package visibility and documented status
   from project metadata, exports, docs, examples, CLI/config documentation, and
   release notes. Distinguish an explicit stability promise from simple
   availability.
3. Check available published artifacts and version history for evidence that
   a candidate was intentionally exposed or changed. Record gaps in artifact
   or release coverage rather than assuming a complete history.
4. Search only authorized downstream sources for exact imports, calls, or
   persisted-format use. Save the search scope and date. Treat each positive
   match as evidence for that consumer; treat no match as unknown.
5. If public sources are insufficient and a maintainer or consumer decision is
   necessary, record the question and who must resolve it. Do not interpret
   silence as approval to remove compatibility.
6. Classify each candidate as **documented promise**, **confirmed use**,
   **no evidence found (still unknown)**, or **out of scope**. Separate
   confirmed facts from inference.
7. Update the assessment and subsystem research with the evidence, limitations,
   and decision. Propose a separate change plan only if a verified, avoidable
   implementation-complexity cost exists and the required compatibility policy
   has an explicit owner.

## Decision criteria

- A documented promise or confirmed consumer requires preserving the surface
  unless its owner approves a versioned compatibility or deprecation policy.
- No matching consumer evidence does not authorize removal; keep the path and
  record the uncertainty.
- Aggregate download/dependency signals may guide where to look but cannot
  resolve symbol-level compatibility.
- Do not consolidate or retire `OemCursor`, store APIs, or saved-state fields
  merely to reduce code volume. A later change must identify a concrete
  repeated rule or caller obligation and include compatibility-specific tests.
- Plan 32 remains deferred indefinitely. Do not add runtime, queue, GUI
  latency, or memory measurements to this work.

## Expected output

- A scoped candidate-to-evidence matrix with dates, sources, coverage, and
  confidence.
- An explicit list of unknowns and evidence limitations.
- A decision for each candidate: preserve as a documented/used contract,
  remain unchanged because evidence is inconclusive, or propose a separate
  bounded investigation with ownership approval.
- Updated assessment and subsystem research; no production code changes.

## Implementation checklist

- **Status:** Closed; investigation not required.
- **Progress:** 0/7 checklist items; closed by scope decision.
- **Note:** The closure decision above supersedes this proposed evidence
  procedure. Unchecked items are not pending work.
- [ ] Record revision, worktree state, candidate surfaces, and evidence scope.
- [ ] Reuse the relevant Plan 8 and Plan 10 findings without repeating their
      internal behavior inventories.
- [ ] Verify project-declared surfaces and available release artifacts.
- [ ] Search authorized downstream sources and record scope, date, and limits.
- [ ] Classify evidence and unresolved compatibility questions per candidate.
- [ ] Update the assessment and subsystem research with findings and decision.
- [ ] Create a separate implementation plan only if verified evidence and
      compatibility ownership justify one.

**Done when:** Each scoped compatibility candidate has a source-backed status
or is explicitly marked unknown, search limitations are clear, and no removal
or behavior change is inferred from absence of evidence.
