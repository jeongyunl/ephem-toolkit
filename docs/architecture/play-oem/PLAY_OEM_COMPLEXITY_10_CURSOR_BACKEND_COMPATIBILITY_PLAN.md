# play-oem — Cursor and 3D Backend Compatibility Inventory Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Baseline and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Current dataflow: [PLAY_OEM_DATAFLOW.md](./PLAY_OEM_DATAFLOW.md).
Prior hotspot findings:
[PLAY_OEM_COMPLEXITY_9_DOMAIN_PERFORMANCE_HOTSPOTS_PLAN.md](./PLAY_OEM_COMPLEXITY_9_DOMAIN_PERFORMANCE_HOTSPOTS_PLAN.md).

## Goal

Execute authoritative assessment priority 7, **Inventory compatibility and
backend variants**. Map the supported `OemCursor` and `StoreCursor` behavior,
then map Matplotlib and optional VTK 3D trajectory behavior, selection,
fallback, tests, and documented support. Determine whether the variants share
a stable contract and what maintenance obligations each adds.

This is an inventory before any consolidation or retirement proposal. Treat
documented support as required behavior unless its owner explicitly changes
that policy. Do not equate implementation similarity with safe interchange,
or infer that a path is unused from the absence of an in-repository caller.

## Planning baseline and initial evidence

At planning time, the worktree is clean at commit
`bea5196ee610912656d0df417c9beefea89696d1`.

### Cursor implementations

`OemCursor` owns copies of an ordered sample history, validates its dimensions,
timestamps, state finiteness, and segment IDs, and provides append and
interpolation support. `StoreCursor` is bound to an `OemDataStore` snapshot,
exposes read-only views over its arrays, refreshes to a later prefix in the
same epoch, and delegates point lookup to the store's configured interpolation
policy. Both expose point lookup and time bounds, but their lifecycle and
storage ownership differ.

The software design explicitly describes `StoreCursor` as the default
incremental path and `OemCursor` as retained for compatibility and non-store
use. `PlaybackData` starts with an `OemCursor`; the controller installs a
`StoreCursor` at the first usable append. Record all consumers that observe
that replacement and the operations they require. Several annotations currently
name `OemCursor`; distinguish intentional legacy-only fields from runtime
surfaces that accept either implementation and verify type-check evidence
before proposing a typing change.

### 3D trajectory backends

The `trajectory3d` package exports the Matplotlib view as
`Trajectory3DView`. The VTK implementation is loaded lazily through backend
selection and is an optional dependency. CLI and config choices are
`auto`, `vtk`, and `matplotlib`. The documented policy is: `auto` may fall back
to Matplotlib when VTK integration or render-context initialization is
unavailable; explicit `vtk` reports an actionable failure; explicit
`matplotlib` must not load VTK.

Both backend implementations support legacy orbit-series construction and
store-backed construction, but the rendering and resource models differ:
Matplotlib uses a figure/canvas and throttled redraws; VTK owns a native render
widget and actors and validates initial rendering. Inventory only the behavior
actually implemented and tested; documentation of future enhancements is not
evidence that they are supported.

No evidence about downstream package consumers is available from the
worktree. Inspect package exports, repository documentation, CLI/config
surfaces, and in-repository callers, but do not claim that external users do
not exist.

## Compatibility matrix to verify

| Surface | Required behavior to inventory | Initial test/doc sources |
| --- | --- | --- |
| `OemCursor` | Owned history, append, interpolation metadata, order-independent lookup, exact/interpolated/gap/out-of-range states | `test_play_oem_cursor.py`, stateless interpolation tests, playback data path |
| `StoreCursor` | Snapshot-backed read-only views, point-query parity, same-epoch prefix refresh, replacement rejection, store interpolation policy | `test_play_oem_cursor.py`, `test_oem_data_store.py`, app incremental-load tests |
| Matplotlib 3D | Legacy and store build/update, inclusive range filtering, segmented paths, cursor visibility, artist/resource lifecycle, no VTK import | `test_trajectory3d.py`, `test_store_raw_views.py`, app backend tests |
| VTK 3D | Optional import, native widget/render-context handling, segmented/range-bounded paths, cursor/tail updates, cleanup, explicit failure | `test_vtk_trajectory3d.py`, app backend-selection tests |
| Selection/config | CLI/config precedence, `auto` fallback, explicit VTK failure, Matplotlib isolation from VTK | `test_config.py`, `test_play_oem_cli.py`, `test_play_oem_app.py` |

This matrix is a starting point. Verify exact calls and test coverage; do not
assume tests exercise a real native VTK context simply because the view logic
is covered with a fake widget.

## Investigation procedure

1. Trace cursor construction and replacement from empty playback data through
   first append, progressive refresh, completion, and close. Record consumers,
   concrete runtime type, shared lookup contract, owned/copied versus
   snapshot-backed data, and refresh/policy lifecycle.
2. Compare the public behavior of both cursors on the same samples: exact,
   interpolated, segment-gap, out-of-range, interpolation-policy, and
   same-epoch append/refresh cases. Record differences as intentional,
   accidental, or unverified.
3. Trace 3D selection from CLI/config through view factory and panel creation.
   Record import boundaries, backend selection lifetime, fallback/error
   behavior, and whether view creation passes through legacy or store-backed
   construction.
4. Compare the two backend contracts: range filtering, segment preservation,
   cursor state, tail direction/rate, data updates, redraw/render scheduling,
   native resource ownership, failure cleanup, and test environment.
5. Inventory package exports, docs, config/CLI support, test coverage, and
   observable in-repository callers. List possible external API uncertainty
   separately; do not treat lack of a discovered caller as permission to remove
   a variant.
6. Only if the verified map exposes a concrete contract mismatch or duplicated
   policy, propose a bounded change with explicit compatibility and regression
   criteria. Otherwise retain both variants and record the reason.

## Required behavior and constraints

- Preserve the `CursorState` status and segment semantics for exact samples,
  interpolation, gaps, unavailable states, and out-of-range queries.
- Keep snapshot epoch and prefix-refresh behavior distinct from owned-history
  append behavior; do not copy store-sized histories to make the APIs look
  identical.
- Preserve configured/OEM interpolation policy and random/reverse seek
  behavior.
- Preserve backend CLI/config choices, lazy VTK imports, `auto` fallback
  boundaries, explicit VTK errors, and Matplotlib's no-VTK path.
- Preserve range filtering before display decimation, segment boundaries,
  cursor/tail semantics, rendering limits, and backend-specific cleanup.
- Keep native GUI/context claims separate from fake-widget/unit-test results;
  run display-dependent tests only when the environment supports them.
- Do not remove a cursor or backend based on in-repository call counts alone.
  Record external compatibility as unknown unless verified with its owner.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 8/8 checklist items.
- [x] Trace runtime cursor creation, replacement, and all relevant consumers.
      Record concrete type transitions and lifecycle differences.
- [x] Compare cursor lookup behavior on common samples and map existing tests
      to the contract; identify any mismatch or meaningful test gap.
- [x] Trace 3D backend selection from config/CLI to panel construction,
      including lazy import, fallback, and explicit-error paths.
- [x] Compare Matplotlib and VTK data, range, cursor, tail, rendering, update,
      and cleanup contracts; distinguish fake from native GUI evidence.
- [x] Inventory package exports, docs, config/CLI surfaces, and in-repository
      callers; state clearly what remains unknown about external consumers.
- [x] Rank only evidence-backed contract gaps or repeated policies. Do not
      propose retirement or consolidation without explicit ownership approval.
- [x] Run focused cursor, backend, config/CLI, and app selection tests; record
      optional dependency or display skips.
- [x] Update the assessment with verified support, behavioral differences,
      unresolved compatibility questions, validation, and the next priority.

**Done when:** both cursor implementations and both 3D backends have a
caller/contract/test inventory; selection and failure behavior are traced;
external-use uncertainty is explicit; and any change is either narrowly
justified with compatibility tests or explicitly deferred.

## Execution record — 2026-11-10

### Cursor lifecycle and lookup contract

`empty_playback_data` creates a one-sample `OemCursor`, which is passed into
`PlayerApp`. On the first usable append, the controller replaces it with a
`StoreCursor`; subsequent batches refresh that cursor with snapshots from the
same store epoch. Interpolation-policy changes are supported by both cursor
types. The owned cursor copies and appends its history, while the store cursor
exposes read-only snapshot-backed views and rejects a replaced epoch or a
snapshot that moves backward.

The app's state protocol and several view-factory/backend annotations name
`OemCursor`, although the controller's cursor becomes a `StoreCursor` at
runtime. Store-backed views are built or rebuilt from `StoreViewContext` and
query that context for playback state; the legacy construction path uses the
cursor lookup. This keeps the runtime paths distinct, but leaves a typing
question: the Pylance diagnostic requests for the controller and app state
timed out, and no static type-checker configuration was found in
`pyproject.toml`. No type change was made without a verified diagnostic.

`test_state_at_matches_cursor_without_copying_sample_history` compares
`OemCursor` lookup with the store's point-query result over exact, interpolated,
gap, and out-of-range times and the supported interpolation policies.
`test_play_oem_cursor.py` separately covers direction-independent lookup,
segment gaps, read-only store views, prefix refresh, and epoch replacement.
No point-query mismatch was found. The remaining limitation is that this
parity test compares the store query directly rather than exercising every
case through `StoreCursor.lookup`.

### 3D selection and backend contracts

The CLI's explicit `--3d-backend` value overrides config; otherwise the config
value is used. Choices remain `auto`, `vtk`, and `matplotlib`, and `vtk` is an
optional package extra. The trajectory package publicly exports the
Matplotlib `Trajectory3DView`; selection lazily imports VTK only when creating
that backend. Both backends support legacy series construction and
`StoreViewContext` construction, range filtering, and segment boundaries. VTK
uses the shared range/segment selector and additionally renders a
direction-aware tail; both update the playback cursor. Their rendering and
resource lifecycles remain intentionally different: Matplotlib owns a figure
and artists, while VTK owns a native widget, render window, and actors.

`auto` falls back to Matplotlib for the recognized VTK load or render-context
failure and reports the reason. Explicit `vtk` surfaces an actionable failure;
explicit `matplotlib` bypasses VTK. The app tests cover these routes and panel
cleanup with fakes. The VTK tests also verify OpenGL factory registration and
VTK array-sharing behavior; the widget/render-context tests use a fake widget,
so they do not establish native desktop rendering reliability.

### Validation and decision

Focused validation passed with no skips:

- Cursor/store contracts: 109 passed.
- Matplotlib and VTK trajectory tests: 12 passed.
- Config and CLI: 48 passed.
- App backend selection: 5 passed, 83 deselected.

No runtime contract mismatch or repeated backend policy requiring a new
abstraction was demonstrated. Keep both cursor and backend variants; do not
retire either based on local caller counts. No production code or subsystem
ownership changed. External package consumers remain unknown, and the cursor
typing question remains unverified. The next assessment candidate is the
large-GUI-view-responsibilities investigation; rank it against the remaining
candidates before selecting a concrete boundary.
