# play-oem — Runtime Cursor Type Contract Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Current evidence priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior cursor inventory:
[PLAY_OEM_COMPLEXITY_10_CURSOR_BACKEND_COMPATIBILITY_PLAN.md](./PLAY_OEM_COMPLEXITY_10_CURSOR_BACKEND_COMPATIBILITY_PLAN.md).
Prior dependency map:
[PLAY_OEM_COMPLEXITY_33_INTERNAL_DEPENDENCY_RESPONSIBILITY_MAP_PLAN.md](./PLAY_OEM_COMPLEXITY_33_INTERNAL_DEPENDENCY_RESPONSIBILITY_MAP_PLAN.md).

## Goal

Verify that Play-OEM's type annotations accurately describe the cursor state
used by the application before and after the first incremental data batch.
If the current annotations obscure a real runtime variant or produce a
verified diagnostic, identify the smallest type-only clarification that makes
the contract easier to understand and check.

This is a bounded investigation with a possible annotation-only change, not a
cursor redesign. Preserve the existing `OemCursor` and `StoreCursor` behaviors
and their distinct storage lifetimes.

## Why this step

The source establishes a concrete type-contract question:

- [`PlaybackData.cursor`](../../../src/ephem_toolkit/play_oem/playback_data.py)
  and [`PlayerAppState.cursor`](../../../src/ephem_toolkit/play_oem/app/state.py)
  are annotated as `OemCursor`.
- [`PlayerApp.__init__`](../../../src/ephem_toolkit/play_oem/app/controller.py)
  accepts and initially stores an `OemCursor`.
- On the first usable incremental append, the controller assigns a
  `StoreCursor`; subsequent advancement narrows the value with an
  `isinstance` check before calling `refresh`.
- The app uses shared operations such as `lookup`, `set_interpolation`, and
  `timestamps_s`, while `append` and `refresh` belong to different cursor
  lifecycles.

Plan 10 recorded this as an unresolved typing question: Pylance diagnostics
timed out, and no static type-checker configuration was found in
`pyproject.toml`. These source facts do not by themselves prove a type error or
justify a `Protocol`. Verify the language-server evidence and actual call paths
before changing annotations.

Plan 32 remains deferred indefinitely, Plan 33 found no broad boundary change,
and the maintainer has said external compatibility is not a concern. This
investigation is internal and does not depend on workload measurements or
external consumer research.

## Scope and baseline

- Source revision observed during planning: `75fc3477d2e0855cadda5149946db24c06b85ad4`.
  The worktree contained documentation changes; no production source change
  was present.
- Inspect the cursor lifecycle from `empty_playback_data` through app
  construction, first incremental snapshot installation, later refresh, and
  shutdown.
- Trace only the actual cursor members read or called by the app and relevant
  views. Distinguish shared operations from `OemCursor`-only append behavior
  and `StoreCursor`-only refresh behavior.
- Include annotations at app state, constructor, playback data, and direct
  consumers only when those consumers receive either runtime type. Do not
  replace every `OemCursor` annotation mechanically; some APIs may remain
  intentionally owned-cursor-only or use `StoreViewContext` instead.
- Preserve `OemCursor`'s owned sample history and append semantics,
  `StoreCursor`'s snapshot-backed views and epoch checks, interpolation
  behavior, and query results.
- Make no runtime, algorithmic, performance, memory, or GUI behavior changes.
  Do not add a type checker solely to complete this investigation.

## Evidence to collect

| Evidence | Record | Limitation |
| --- | --- | --- |
| Pylance or configured checker diagnostics | Exact rule, message, file, and range for cursor declarations, assignments, and member use. | If the language-server request is unavailable, state that explicitly; do not infer a diagnostic from annotations alone. |
| Runtime lifecycle and assignments | Which concrete cursor is installed at each lifecycle stage and where the state is narrowed. | The known transition may be intentional and does not itself imply a defect. |
| Shared and type-specific members | App/view operations needed from each concrete cursor and operations that remain variant-specific. | Text search must be checked against actual call paths; names alone do not prove all consumers receive both types. |
| Existing tests | Cursor behavior, initial app construction, incremental replacement, and trajectory/view consumers. | Runtime tests do not establish static type correctness. |

## Investigation procedure

1. Record the current source revision and worktree state. Reuse the exact
   unresolved finding in Plan 10 rather than repeating cursor parity or backend
   behavior tests.
2. Request Pylance diagnostics and hover/type information for
   `PlaybackData.cursor`, `PlayerAppState.cursor`, the `PlayerApp` constructor,
   the first-batch `StoreCursor` assignment, and the guarded refresh path.
   Record exact diagnostics, including a clean result. If Pylance is
   unavailable, do not claim a type error; keep the outcome at the hypothesis
   stage.
3. Trace the concrete cursor at each application state and list the operations
   performed by the owner and direct consumers. Verify whether any
   `OemCursor`-annotated view or factory parameter can receive a `StoreCursor`
   at runtime, or whether store-backed paths use `StoreViewContext` instead.
4. Compare the smallest plausible models only after collecting evidence:
   - a union where application state intentionally switches between the two
     concrete cursors and variant-specific operations need narrowing; or
   - a narrow shared protocol only if several real consumers depend on a
     stable common interface.
   Keep constructor inputs that are genuinely `OemCursor`-only unchanged.
5. If a verified mismatch or diagnostic exists and one representation clearly
   improves local reasoning, update only the affected annotations and
   docstrings. Avoid `Any`, unchecked casts, runtime adapters, and broad
   signature changes.
6. Run the focused static diagnostics and tests. At minimum consider
   `test_play_oem_cursor.py`, `test_incremental_loader.py`,
   `test_play_oem_app.py`, `test_trajectory3d.py`, and
   `test_vtk_trajectory3d.py`; select the smallest set that covers the
   modified contract.
7. Update the assessment and subsystem research with the evidence and a
   keep/change decision. If no defect or meaningful clarity improvement is
   established, make no source change and close the plan with that result.

## Decision criteria

- Change annotations only when diagnostics or verified call paths show that
  the current declared type fails to express the actual internal contract.
- Prefer the simplest accurate type: keep the union if consumers need concrete
  narrowing; introduce a protocol only when multiple consumers truly rely on
  the same small behavior contract and the indirection improves clarity.
- Preserve the distinct `append` and `refresh` lifecycles; do not make the
  cursor implementations artificially interchangeable.
- If Pylance is unavailable and no configured checker can provide evidence,
  record the limitation and do not claim or patch a type error.
- Reject any proposal that adds equal or greater conceptual complexity without
  making the runtime state transition easier to understand.

## Expected output

- A short cursor-state/type matrix with exact diagnostics or explicit
  verification limits.
- A documented keep/change decision and, only if justified, a minimal
  annotation-only patch.
- Focused validation results and updates to the assessment and subsystem
  research.
- No runtime behavior or performance changes.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 7/7 checklist items.
- [x] Record revision, worktree state, and focused source scope.
- [x] Obtain exact Pylance or configured-checker evidence for cursor types and
      assignments.
- [x] Trace runtime cursor variants and actual shared/type-specific member use.
- [x] Choose the simplest accurate contract, or record why no change is needed.
- [x] If justified, make an annotation-only change without altering behavior.
- [x] Run focused diagnostics and tests for the changed contract.
- [x] Update the assessment and subsystem research with the decision.

## Execution record — 2026-11-11

The source revision was `01764eb1d56520ccc9c36972a65f37bd9393cd0e0`. The
worktree already contained edits to Plans 1–3 and this untracked plan; those
changes were preserved. No configured Pyright or mypy checker was found in the
project configuration files inspected.

| Surface | Verified runtime/type contract | Diagnostic evidence |
| --- | --- | --- |
| `PlaybackData.cursor` and `PlayerApp.__init__` input | Both start with an `OemCursor`; `empty_playback_data` constructs that concrete cursor. These annotations remain unchanged. | No Pylance diagnostics in `playback_data.py`. |
| `PlayerApp.cursor` and `PlayerAppState.cursor` | The app stores the initial cursor, installs `StoreCursor` on the first usable snapshot, and narrows to `StoreCursor` before `refresh`. The owner also calls shared `lookup`, `set_interpolation`, and `timestamps_s`. | No cursor-related Pylance diagnostics in `state.py` or `controller.py`; the controller had unrelated deprecation/unused-code warnings. Hover/type requests timed out. |
| Direct view consumers | `ViewFactoryMixin` passes the app's current cursor to Ground Station and 3D views, including views opened after snapshot installation. Their previous `OemCursor`-only annotations did not describe that call path. | The consumers were included in post-change diagnostic requests, but the Pylance server timed out. |
| Cursor-specific lifecycle | `OemCursor.append` remains owned-history-only; `StoreCursor.refresh` remains snapshot-only and is used behind an `isinstance` guard. | No behavior changes were made. |

The smallest useful clarification is the `PlaybackCursor` union alias. The app
attribute and state protocol, plus direct view-factory consumers, now use it;
the genuinely initial-only `PlaybackData` field and constructor parameter
remain `OemCursor`. No shared protocol was added because concrete narrowing is
already required for the distinct refresh lifecycle.

Focused validation:

- `python3 -m pytest tests/ephem_toolkit/play_oem/test_play_oem_cursor.py tests/ephem_toolkit/play_oem/test_incremental_loader.py tests/ephem_toolkit/play_oem/test_play_oem_app.py tests/ephem_toolkit/play_oem/test_trajectory3d.py tests/ephem_toolkit/play_oem/test_vtk_trajectory3d.py`
  — **130 passed**, with 14 dependency deprecation warnings.
- Pylance diagnostics succeeded before the edit for the state, playback-data,
  and controller files and reported no cursor-related issue. Post-edit
  diagnostics were requested for every touched source file, but timed out; no
  post-edit static-checker result is claimed.

**Done when:** The runtime cursor transition and its declared type contract
have been checked against source and diagnostics, and any change is minimal,
validated, and behavior-preserving—or the evidence supports leaving the code
unchanged.
