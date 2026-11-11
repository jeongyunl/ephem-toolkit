# play-oem — Incremental Interpolation Metadata Complexity Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and candidate priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Load lifecycle:
[PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md).
Snapshot installation phases:
[PLAY_OEM_COMPLEXITY_25_SNAPSHOT_INSTALLATION_PHASES_PLAN.md](./PLAY_OEM_COMPLEXITY_25_SNAPSHOT_INSTALLATION_PHASES_PLAN.md).

## Goal

Evaluate whether repeated interpretation of OEM interpolation metadata during
snapshot installation and validated load completion can be expressed once,
reducing duplicated conversion policy without combining the distinct
provisional and final metadata lifecycles.

This is a small code-level reduction candidate. Keep it only if centralizing
the conversion prevents policy drift and leaves the timing and ownership of
each metadata update clear.

## Evidence and hypothesis

`_install_store_snapshot` and `_finish_incremental_metadata` both interpret
`INTERPOLATION` as a non-empty string or `None`, and `INTERPOLATION_DEGREE` as
an integer or `None`. The first path applies snapshot metadata as progressive
data arrives; the second applies completion metadata after full-file
validation. Other metadata processing, validation, UI updates, and completion
state differ and must remain separate.

**Hypothesis:** one small helper for these two field conversions can remove a
duplicate policy while the two callers retain their distinct timing. Reject
the helper if it introduces mutable side effects, broadens the metadata
protocol, or is less clear than the few repeated lines.

## Procedure

1. Verify the two assignments and inspect the metadata types and test
   expectations at both call sites.
2. Locate tests for interpolation selection on initial snapshot, later
   metadata/completion, and absent or invalid degree values.
3. Compare a pure conversion helper returning the normalized pair with a
   state-mutating helper. Prefer the least complex option; do not merge
   provisional and validated metadata handling.
4. Implement only if the shared conversion is clearer and does not add
   unnecessary result plumbing.
5. Run the focused app lifecycle, loader, and interpolation/store tests.
6. Record whether the central policy improves maintainability; revert if the
   helper is merely indirection for trivial assignments.
7. Update the assessment and subsystem overview with the result.

## Required behavior

- Preserve provisional snapshot updates and final validated metadata timing.
- Preserve `None` for missing/empty interpolation names and degrees.
- Preserve integer conversion and current errors for invalid degree values.
- Do not change cursor policy, store interpolation revision, or view refresh.

## Implementation checklist

- **Status:** Complete — helper rejected as needless indirection.
- **Progress:** 7/7 checklist items.
- [x] Verify duplicated conversion and its input types.
- [x] Map tests for snapshot and completion metadata.
- [x] Compare pure and mutating helper shapes before editing.
- [x] Reject centralization because the repeated conversion is two direct,
      straightforward assignments at distinct lifecycle points.
- [x] Run app, loader, and relevant interpolation/store tests.
- [x] Reject based on maintainability, not lines removed.
- [x] Update the assessment and subsystem overview.

**Done when:** The two load phases share one clear interpolation-metadata
conversion policy without conflating their distinct lifecycle behavior, or the
helper is rejected as needless indirection.

## Execution record — 2026-11-11

Both call sites perform the same simple normalization: one non-empty string
conversion and one optional integer conversion. A helper returning the pair
would add a definition, call, and tuple unpacking to two already explicit
assignments; a state-mutating helper would hide the timing of the updates.
Because the values are applied once during progressive snapshot installation
and again after full-file validation, keeping the assignments at their
respective lifecycle points is clearer than centralizing four lines.

No code or test changes were made. The focused app, loader, store, and
stateless-interpolation suites passed (**206 passed**) on macOS with Python
3.9.6. No conclusion about cross-platform behavior is implied.
