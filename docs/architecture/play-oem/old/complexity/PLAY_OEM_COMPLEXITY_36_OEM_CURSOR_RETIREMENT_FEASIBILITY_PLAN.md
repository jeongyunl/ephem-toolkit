# play-oem — OemCursor Retirement Feasibility and Implementation Record

> The initial feasibility review below chose to retain both cursors. That
> decision was superseded by a follow-up implementation after the maintainer
> directed retirement; the current design and validation are recorded at the
> end of this document.

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Current evidence priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior cursor inventory:
[PLAY_OEM_COMPLEXITY_10_CURSOR_BACKEND_COMPATIBILITY_PLAN.md](./PLAY_OEM_COMPLEXITY_10_CURSOR_BACKEND_COMPATIBILITY_PLAN.md).
Runtime type contract:
[PLAY_OEM_COMPLEXITY_35_CURSOR_TYPE_CONTRACT_PLAN.md](./PLAY_OEM_COMPLEXITY_35_CURSOR_TYPE_CONTRACT_PLAN.md).

## Goal

Determine whether `OemCursor` still serves a necessary production role or
whether all of its production paths can move to the store-backed cursor model
without making lifecycle, data ownership, or caller behavior harder to
understand. This is a feasibility investigation, not a decision to remove
`OemCursor`.

The acceptable outcomes are:

1. Retain `OemCursor` and document the distinct owned-history path that needs
   it.
2. Propose a small, staged migration if evidence shows the owned-history path
   is no longer needed and `StoreCursor` can cover the remaining behavior.
3. Identify an unresolved contract or lifecycle constraint and defer retirement
   until that evidence is available.

## Why this step

Plan 10 found that `OemCursor` owns and appends its sample history, while
`StoreCursor` views committed store snapshots and refreshes within one store
epoch. Playback initially receives an `OemCursor` and the controller installs a
`StoreCursor` after the first usable incremental batch. Plan 35 clarified the
union type for app state and direct consumers; it did not consolidate either
implementation.

The relevant question is therefore not whether the two classes have similar
lookup methods. It is whether the owned-history lifecycle is still required by
any production construction path, and whether starting or operating those paths
through a store would reduce complexity without introducing a broader store
lifecycle obligation.

Planning baseline: commit
`ba9bcafb908d500579e16f2c3519b91051265a75`; worktree was clean.

## Scope and baseline

- Inventory production constructors, assignments, imports, and direct calls
  involving both cursor types. Separate app-owned, view, standalone, and
  test-only paths.
- Trace startup and full-file loading, first incremental batch, subsequent
  refresh, replacement, failure, and shutdown. Confirm whether each path
  actually needs an owned cursor or a store snapshot.
- Compare `OemCursor`-only operations and guarantees with store-backed
  equivalents, including append ordering, interpolation metadata, exact and
  interpolated results, gaps, unavailable/out-of-range states, and seek
  behavior.
- Inspect package exports, CLI/application construction, architecture docs,
  and tests for a separately supported cursor API. External compatibility is
  not a current gate by maintainer direction, but the inspected API surface
  must still be recorded.
- If retirement appears feasible, propose the smallest migration boundary and
  its regression criteria. Do not implement that migration as part of this
  plan.

Preserve `StoreCursor` epoch checks, prefix refresh, snapshot-backed read-only
views, and store interpolation policy. Preserve `OemCursor` owned-history
semantics unless evidence supports removing the path that requires them. Do
not add a protocol or adapter merely to make the types interchangeable. Make
no runtime, algorithmic, performance, memory, or GUI behavior changes during
the investigation.

## Evidence to collect

| Evidence | Record | Limitation |
| --- | --- | --- |
| Production construction and assignment sites | Concrete cursor type, owner, and lifecycle stage at each site. | Type annotations and text matches alone do not prove runtime reachability. |
| Owner-specific operations | Calls to `OemCursor.append`, store snapshot creation, `StoreCursor.refresh`, and interpolation-policy changes. | Shared method names do not prove interchangeable ownership or lifetime. |
| Direct consumers | Required members and whether they receive either cursor in the legacy or store-backed path. | A view's `StoreViewContext` query path may differ from its legacy cursor path. |
| Lookup and lifecycle tests | Existing coverage for append/refresh, interpolation, gaps, replacement, failure, and startup; identify only concrete gaps. | Runtime tests do not establish typing correctness or external use. |
| Pylance or configured-checker evidence | Exact diagnostics for any proposed migration; record unavailable requests explicitly. | Do not claim a type defect from the prior timeout or annotations alone. |

## Investigation procedure

1. Record the current revision, worktree state, and focused source scope.
2. Search production code, tests, exports, and documentation for cursor
   construction and use; classify each occurrence by runtime path rather than
   count alone.
3. Trace the app from initial playback data through fully loaded and
   incremental paths, including replacement/failure and close. Record which
   object owns each history or snapshot and when it is released.
4. For every production `OemCursor` path, list the operations it needs and
   decide whether it is genuinely store-independent. For every proposed
   `StoreCursor` path, verify the store exists for the required lifetime and
   that empty/startup behavior remains defined.
5. Compare the smallest outcomes: retain both with explicit roles, or propose
   a bounded migration. Reject a design that keeps `OemCursor` only as an
   adapter around a store or duplicates store-sized data.
6. If a concrete migration is justified, describe it as a separate
   implementation task with focused tests for the affected lifecycle and
   cursor behavior. Do not add a type checker solely for this investigation.

## Decision criteria

- Retire `OemCursor` only if no required production path still depends on
  owned-history construction, append, or store-independent lookup.
- Do not infer that it is removable because the incremental app path already
  uses `StoreCursor`.
- Prefer retaining both when the owned cursor supports a distinct, simpler
  use case and replacing it would require a store lifecycle solely to satisfy
  cursor construction.
- If the app's initial cursor is the only remaining production use, evaluate
  that path explicitly, including the no-file/empty state and failure before
  the first usable batch.
- Preserve query statuses, interpolation semantics, segment boundaries,
  random/reverse seeks, and failure behavior in any future migration.
- If evidence does not establish a meaningful reduction in rules or
  interactions, close with a keep decision and no source change.

## Expected output

- A construction/consumer matrix with concrete runtime types and owner-specific
  operations.
- A keep, migrate, or defer decision with evidence and explicit limitations.
- If migration is justified, a separate bounded implementation proposal and
  regression criteria; otherwise no source patch.
- Focused test and diagnostic results, with no runtime or performance claims
  beyond what was measured.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 6/6 checklist items.
- [x] Record revision, worktree state, and focused source scope.
- [x] Inventory production cursor construction, assignment, and consumer paths.
- [x] Trace owned-history and store-snapshot lifecycles through startup, load,
      replacement, failure, and shutdown.
- [x] Verify owner-specific operations and behavior coverage; note only
      evidence-based gaps.
- [x] Choose keep, migrate, or defer using the decision criteria.
- [x] Record the decision in the assessment and subsystem research; separate
      any justified code migration into its own task.

## Execution record — 2026-11-11

The source revision was `ba9bcafb908d500579e16f2c3519b91051265a75`. The
worktree already contained the untracked Plan 36 and edits to the assessment
and subsystem research; these documentation changes were preserved. No
production source changes were made.

| Surface | Verified path and role | Evidence |
| --- | --- | --- |
| Empty app startup | `play_oem.__main__` calls `empty_playback_data`, passes its one-sample `OemCursor` to `PlayerApp`, and starts with `oem_loaded=False`. | `playback_data.py`, `__main__.py`, and `test_play_oem_cli.py` verify this startup shape. |
| Incremental load | The first usable batch replaces the initial cursor with `StoreCursor`; later batches refresh it after an `isinstance` guard. | `PlayerApp._install_first_store_snapshot` and `_advance_store_snapshot`; app tests cover first installation, subsequent append, and replacement. |
| Store-backed consumers | These query through `StoreViewContext` and use the store cursor after snapshot installation. | Plan 10 and the current view-factory/store-view paths; no owned-history append is used by the incremental path. |
| Legacy 3D view | The `Trajectory3DView` exported by `views.trajectory3d` supports building from `OrbitSeries` plus a cursor. Its legacy builder uses cursor bounds and lookup; the data-update test appends to `OemCursor`. | `trajectory3d/__init__.py`, `mpl_backend.py`, and `test_trajectory3d.py`. |
| Store startup requirements | A new `OemDataStore` has no active raw epoch; `snapshot()` rejects that state. `StoreCursor` also rejects empty bounds, while the store owns a scheduler executor that must be closed. | `OemDataStore.__init__`, `snapshot`, `close`, and `StoreCursor` bounds/constructor. |
| Package surface | `OemCursor` is not re-exported from the `play_oem` package root, but the trajectory view is exported and retains a tested non-store construction path. | `play_oem/__init__.py` and `views/trajectory3d/__init__.py`. |

No production source call to `OemCursor.append` was found. That operation is
exercised by the legacy trajectory-view data-update tests, while the production
app's incremental path uses store reservations and `StoreCursor.refresh`.
Replacing the empty-state cursor with `StoreCursor` would require activating a
nonempty store epoch and taking ownership of its scheduler lifecycle, or adding
another empty-state abstraction. Neither is simpler than the existing
one-sample owned cursor. Removing `OemCursor` would also require redesigning or
dropping the tested non-store trajectory construction path.

**Initial decision: keep both cursor implementations (superseded).**
`OemCursor` was then considered the simple standalone/legacy owned-history
cursor and empty-app seed; `StoreCursor` was the incremental snapshot cursor.
That conclusion treated the empty startup state and trajectory-view tests as
reasons to retain two implementations. The follow-up below replaces those
requirements with a single cursor type and an explicit empty state.

Focused validation:

- `python3 -m pytest tests/ephem_toolkit/play_oem/test_play_oem_cursor.py tests/ephem_toolkit/play_oem/test_play_oem_cli.py tests/ephem_toolkit/play_oem/test_play_oem_app.py`
  — **133 passed**, with 14 dependency deprecation warnings.
- No Pylance request was needed because the investigation found no justified
  source or annotation change. Previous Plan 35 post-change Pylance requests
  had timed out; no new static-checker result is claimed.

**Done when:** The need for `OemCursor` is decided from verified production
paths and lifecycle evidence, with a bounded migration proposal only if it
reduces complexity without weakening behavior—or with a clear keep/defer
decision and no source change.

## Follow-up implementation — 2026-11-11

The maintainer directed that `OemCursor` be retired. The migration removes the
second cursor rather than adapting it around a store:

- `StoreCursor.empty()` represents pre-load startup without creating an
  `OemDataStore`, taking a snapshot, or acquiring a scheduler resource. It has
  empty read-only sample views, zero bounds, and returns `UNAVAILABLE` for
  lookup. Refresh and interpolation changes require replacing it with a
  store-bound cursor.
- The app state and view consumers now use `StoreCursor` directly. The
  controller verifies that a cursor is bound to the active store before
  refreshing it; the first usable batch replaces the inert cursor with a
  snapshot-bound cursor.
- The exported trajectory view's data-update path now uses the same
  store-backed cursor and commits appended rows through `OemDataStore` before
  refreshing the cursor. No owned-history append path remains.
- Tests that need cursor fixtures use committed store samples. Interpolation
  parity uses the core interpolator as an independent reference rather than a
  second cursor implementation.

This intentionally removes the `OemCursor` class from
`ephem_toolkit.play_oem.cursor`; external compatibility was not a release gate
by maintainer direction. A repository search found no remaining
`OemCursor`/`PlaybackCursor` references in production source or tests.

Focused validation:

- Ten cursor, app, CLI, data, store, interpolation, and view test modules:
  **266 passed**, with 14 dependency deprecation warnings.
- No Pylance result is claimed; focused runtime tests were used to validate
  the migration.

**Current outcome:** `StoreCursor` is the sole playback cursor and supports
both inert pre-load startup and snapshot-backed playback. This follow-up
supersedes the initial keep decision above.
