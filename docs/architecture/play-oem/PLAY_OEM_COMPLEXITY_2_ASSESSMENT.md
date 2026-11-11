# play-oem complexity assessment

This is a first, static assessment and work-item inventory. It applies the
framework in [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Priorities are preliminary judgments, not measured defect rates or commitments
to implement a particular design. Update this document as traces, experiments,
and measurements provide better evidence.

For an analysis of state, concurrency, and domain interactions, see
[logically complex subsystems](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).

## Baseline and method

Measured against source at Git commit `cf93496` on 2026-11-10, with no source
modifications in the working tree. Scope: Python files recursively under
`src/ephem_toolkit/play_oem`; tests, generated artifacts, documentation, and
assets are excluded. Counts are physical lines including blanks and comments.

| Measure | Result |
| --- | ---: |
| Python files | 63 |
| Physical lines | 25,577 |
| Function and method definitions, including nested functions | 1,097 |
| `oem_data_store.py` lines | 3,545 (13.9% of package) |
| `app/controller.py` lines | 1,920 (7.5%) |
| `app/panel_management.py` lines | 391 |
| `saved_state.py` lines | 551 |
| View files containing `StoreViewBinding(` | 10 |

The last count identifies files, not the number of duplicated sequences or the
number of callers with equivalent behavior. The two largest files together
contain 21.4% of package lines; concentration does not prove poor design.

The following **decision score** is a simple AST-based hotspot indicator, not
a standard cyclomatic-complexity implementation: for each function definition,
start at one, add one for each `if`, `for`, `async for`, `while`, exception
handler, conditional expression, and comprehension generator, and add one per
additional operand of a Boolean `and`/`or`. It traverses nested definitions as
part of the enclosing function and also reports them separately; it does not
count `match` cases or comprehension filter clauses individually. Therefore
scores are useful for ordering inspection within this baseline, not for strict
thresholds, comparisons with other tools, or claims about independent paths.
Function lengths include decorators only when included in the AST node's span;
the counts below are from `end_lineno - lineno + 1`.

| Function | Lines | Decision score | Initial interpretation |
| --- | ---: | ---: | --- |
| `saved_state.load_saved_state` | 268 | 69 | Many validation and migration branches; inspect repeated validation and error policy. |
| `oem_data_store._capacity_for_ascii_file` | 179 | 46 | Optimized scanner handles chunk, encoding, line-length, and cancellation cases; performance-sensitive. |
| `PanelManagementMixin._open_view` | 177 | 43 | Coordinates panel construction, view setup, replacement, and rollback. |
| `station_access._intervals_for_segment` | 166 | 42 | Domain interval computation; investigate branch meaning and boundary cases before simplifying. |
| `OemDataStore.station_access` | 244 | 38 | Station query, range coverage, and derived data lifecycle. |
| `PlayerApp.__init__` | 368 | 34 | Application initialization spans multiple responsibilities. |
| `PlayerApp._install_store_snapshot` | 174 | 32 | Incremental installation and UI/state coordination. |
| `PlayerApp._poll_incremental_load` | 126 | 32 | Generation checks and event-specific state transitions. |
| `Workspace.__init__` | 398 | 30 | Large GUI construction routine; much of the volume may be layout. |
| `OemDataStore.series` | 159 | 30 | Series query and derived-data handling. |
| `OemDataStore._evict_derived_buffers` | 162 | 25 | Cache accounting and eviction; preserve memory and lifetime invariants. |

Reproduce the counts from the repository root with Python's standard library:

```sh
python - <<'PY'
import ast
from pathlib import Path

files = list(Path('src/ephem_toolkit/play_oem').rglob('*.py'))
functions = []
for path in files:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nodes = list(ast.walk(node))
            score = 1 + sum(isinstance(n, (ast.If, ast.For, ast.AsyncFor,
                ast.While, ast.ExceptHandler, ast.IfExp, ast.comprehension))
                for n in nodes)
            score += sum(len(n.values) - 1 for n in nodes if isinstance(n, ast.BoolOp))
            functions.append((score, node.end_lineno - node.lineno + 1,
                              str(path), node.lineno, node.name))
print('files', len(files), 'lines', sum(len(p.read_text().splitlines()) for p in files),
      'functions', len(functions))
for item in sorted(functions, reverse=True)[:25]:
    print(*item)
PY
```

## Cross-component and caller-side findings

- **Loading:** the event enum defines five kinds. The controller polls them,
  rejects stale generations, verifies append notices against a snapshot, and
  coordinates first installation, completion, failure, and view refresh.
  Replacement, cancellation, and valid-prefix behavior are separate cases.
  Tests explicitly cover stale events, replacement, and failed replacement in
  `test_play_oem_app.py`, and cancellation and generation behavior in
  `test_incremental_loader.py`. A full transition count and thread audit remain
  open; five event kinds are not five independent states.
- **Queries and view lifecycle:** ten view files instantiate `StoreViewBinding`.
  The binding already centralizes subscription switching and cleanup. Callers
  still bind contexts, query data, update view-specific output, and close the
  binding. Some views interpret partial coverage. The amount of genuinely
  repeated policy has not been measured, and rendering work is not automatically
  duplication.
- **Panel construction:** `_open_view` has 177 lines and score 43, including
  creation, range setup, Matplotlib/native content, replacement, and exception
  rollback. This is one orchestration site; complexity here does not establish
  repeated independent callers. `test_play_oem_app.py` includes a failed view
  change that restores the original panel.
- **Store ownership:** one module combines raw storage, derived queries,
  scheduling, and eviction. Its size and individual scores show concentrated
  code, while the existing single-owner design also limits overall complexity.
  Lock, epoch, and cache dependencies have not yet been mapped, so the cost of
  separating responsibilities is unknown.

## Candidate inventory

A line count of Python files under `src/ephem_toolkit/play_oem` gives roughly
25,600 lines, including 3,545 in
[`oem_data_store.py`](../../../src/ephem_toolkit/play_oem/oem_data_store.py)
and 1,920 in
[`app/controller.py`](../../../src/ephem_toolkit/play_oem/app/controller.py).
These counts include comments and blank lines and will change as the code
changes. They identify places to inspect; they do not measure complexity or
establish that a file should be divided.

The following inventory contains *candidates*, not a claim that each has
avoidable complexity. The work-item order below is the priority order. Validate
the relevant callers, invariants, and
tests before changing an interface or removing a path.

1. **Load lifecycle and replacement.**
   [`IncrementalLoader`](../../../src/ephem_toolkit/play_oem/incremental_loader.py)
   owns generation-scoped sessions, while `PlayerApp._start_incremental_load`,
   `_poll_incremental_load`, `_install_store_snapshot`, and
   `_finish_incremental_metadata` coordinate generation, installation, and
   UI state. Trace the state and event transitions and try grouping related
   lifecycle state behind an explicit contract. The opportunity is to reduce
   cross-method reasoning; preserve late-event rejection, valid-prefix behavior,
   replacement, cancellation, and shutdown. Incremental loading is the normal
   application path, not a CLI-selectable mode to remove as an unused variant.
2. **Store scheduling and cache lifecycle.** Detailed investigation plan:
   [PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md](./PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md).
   `OemDataStore.prefetch`,
   `_drain_scheduler_queue`, `_run_prefetch`, and `_evict_derived_buffers`
   coexist with raw storage and query methods in
   [`oem_data_store.py`](../../../src/ephem_toolkit/play_oem/oem_data_store.py).
   Map shared locks, epochs, pinning, and ownership, then investigate whether
   scheduling or eviction can have a narrower internal interface. Preserve one
   raw-data owner, snapshot validity, bounded memory, cancellation, and query
   performance; moving methods alone is not a reduction in coupling.
3. **Derived store queries.** Detailed investigation plan:
   [PLAY_OEM_COMPLEXITY_6_DERIVED_STORE_QUERIES_PLAN.md](./PLAY_OEM_COMPLEXITY_6_DERIVED_STORE_QUERIES_PLAN.md).
   The store's `series`,
   `earth_fixed_positions`, `ground_track`, and `station_access` methods each
   manage range-oriented derived data. Compare their coverage, chunk, and
   invalidation handling for repeated policy, then test a small shared internal
   operation only where invariants truly match. Preserve partial coverage,
   interpolation support, station-specific behavior, and cache semantics.
4. **View refresh coordination.** Detailed investigation plan:
   [PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md](./PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md).
   `PlayerApp._drain_store_notices`,
   `_views_for_tier_notice`, `_refresh_store_views`, and
   `_refresh_incremental_views` route and defer updates; range actions and views
   also participate. Trace which event refreshes which panels and consider a
   single explicit refresh policy if rules overlap. Preserve targeted updates,
   refresh throttling, dragging behavior, and wx-thread ownership.
5. **Controller initialization and shared state.**
   `PlayerApp.__init__` initializes loading, playback, configuration, and GUI
   state, while its panel, playback, and range mixins use shared app state.
   Inventory attributes and dependencies by responsibility; prototype a
   cohesive state owner or setup boundary where it reduces the knowledge
   required for a change. Do not simply move initialization or add another
   forwarding layer. Preserve initialization order and cleanup.
6. **Panel and view lifecycle.**
   [`PanelManagementMixin._open_view`](../../../src/ephem_toolkit/play_oem/app/panel_management.py)
   and its disposal methods coordinate view creation and resources;
   [`StoreViewBinding`](../../../src/ephem_toolkit/play_oem/views/base.py)
   already centralizes tier subscription lifetime. Compare a history view,
   Ground Track, a station view, and a 3D backend for duplicated lifecycle
   policy before extending shared machinery. Preserve panel identity, observer
   cleanup, and backend-specific native resource release.
   Detailed investigation plan:
   [PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md).
7. **Large GUI view responsibilities.**
   [`GroundTrackView`](../../../src/ephem_toolkit/play_oem/views/ground_track.py)
   combines panel construction, map drawing and navigation, station controls,
   and playback updates; `GroundStationPassesView` combines table and sky-view
   behavior. Identify a concrete change that crosses these concerns and test a
   cohesive boundary, such as navigation state or artist management. Preserve
   selection, map limits, event behavior, and rendering performance.
   Detailed investigation plan:
   [PLAY_OEM_COMPLEXITY_11_LARGE_GUI_VIEW_RESPONSIBILITIES_PLAN.md](./PLAY_OEM_COMPLEXITY_11_LARGE_GUI_VIEW_RESPONSIBILITIES_PLAN.md).
8. **Parallel paths and variants.**
   [`cursor.py`](../../../src/ephem_toolkit/play_oem/cursor.py) contains
   `OemCursor` and `StoreCursor`; the 3D view has Matplotlib and VTK backends.
   Inventory production, test, documented, and potential external callers and
   measure the maintenance cost of each path. Consolidate or retire a path only
   if its support obligations and behavioral differences permit it; backend
   differences and compatibility may justify the code volume.

These targets include local control flow, overall coordination, and potential
volume reduction. Their value depends on evidence from the planned investigations;
none should be implemented solely to reduce a line count.

## Caller-side protocol complexity

Use **caller-side protocol complexity** for the effort an API imposes on its
callers to prepare inputs, follow operations in the right order, interpret
results, and perform cleanup. When the same sequence is repeated, it is also
**duplicated orchestration** or **caller boilerplate**. The required ordering
is often called **temporal coupling**; when implementation details escape the
interface, **leaky abstraction** may also apply. These terms describe different
aspects, not proof that a particular API is poorly designed.

The distinction matters: some preparation and cleanup enforce real resource,
concurrency, or rendering requirements. The opportunity is to make a common
safe operation easier for its callers without hiding decisions they need or
weakening the underlying guarantees. Initial examples to investigate:

1. **Store-backed view binding and refresh.**
   [`SpeedAltitudeView`](../../../src/ephem_toolkit/play_oem/views/speed_altitude.py),
   [`RtnView`](../../../src/ephem_toolkit/play_oem/views/rtn.py),
   [`GroundTrackView`](../../../src/ephem_toolkit/play_oem/views/ground_track.py),
   and `GroundStationPassesView` use `StoreViewBinding` around context changes
   and close it during teardown. Callers also retain or update context, perform
   queries, and update artists or controls. `StoreViewBinding` already handles
   subscription switching; compare the remaining sequences and their differences
   before considering a common lifecycle helper. Preserve tier subscriptions,
   context/range updates, and view-specific rendering and cleanup.
2. **Range query preparation and result handling.** The store's range-query
   methods require a snapshot and bounds and return a `StoreQuery` with values
   and coverage. `StoreViewContext` already captures the snapshot, resolves
   bounds, and handles empty ranges. Ground Track and station-pass views still
   interpret values and incomplete coverage to decide what to display. Compare
   these callers for repeated *policy*, rather than treating distinct messages or
   rendering as duplication. Any shared result handling must retain partial
   coverage and the distinction between pending, empty, and out-of-range data.
3. **Opening and disposing a panel.**
   [`PanelManagementMixin._open_view`](../../../src/ephem_toolkit/play_oem/app/panel_management.py)
   selects a host, creates a view, resolves its range, chooses a build path,
   applies range and current time, and sets up GUI resources and callbacks; its
   disposal methods handle the corresponding lifecycle. Investigate whether an
   explicit panel/view lifecycle contract can simplify setup and failure cleanup.
   The different content and backend types may require genuine special handling;
   preserve replacement, subscriptions, and native resource release.
4. **Raw ingestion reservation protocol.**
   [`_StoreRowSink`](../../../src/ephem_toolkit/play_oem/streaming_oem.py)
   reserves rows, tracks a count, commits batches, publishes notices, and
   discards an active reservation on close. This is an example of substantial
   caller protocol, but the inspected production path uses a dedicated sink;
   repeated independent callers have not been established. Check all callers
   and failure paths before considering a scoped reservation helper. Preserve
   zero-copy writes, epoch checks, cancellation, and commit atomicity.
5. **Load event consumption.**
   [`PlayerApp._poll_incremental_load`](../../../src/ephem_toolkit/play_oem/app/controller.py)
   checks generations, handles event kinds, installs snapshots, updates loading
   state, and schedules refreshes. Investigate whether a more explicit event
   contract or lifecycle state can make the consumer's obligations easier to
   understand and test. This is a complex consumer, not yet evidence of
   duplicated consumers; preserve wx-thread updates and late-event handling.

For each candidate, inventory actual callers and list the required preconditions,
operation order, result interpretation, and cleanup, including failure paths.
Separate repeated policy from necessary caller-specific work. A promising change
should remove or centralize a demonstrably repeated obligation and reduce the
number of rules callers must remember; compare before/after call sites and
tests as well as the additional abstraction and its performance cost.

## Prioritized work items

This is the authoritative work-item order; the candidate inventory above records
the underlying leads and does not establish a separate priority list.

Order reflects the likely breadth of impact, complexity evidence, and risk of a
mistake. It is a research and experiment order, not a claim about measured change
frequency. Each item requires an evidence review before production refactoring.

1. **Model incremental-load state and event handling.** Trace normal load,
   replacement before and after first append, failure, cancellation, stale events,
   and close. Inventory state fields and their owners across loader, store, and
   controller; identify illegal combinations and test gaps. Then prototype a
   smaller explicit lifecycle contract if it reduces rules spread across callers.
   Success: one understandable transition table, traceable tests, and fewer
   independently coordinated state changes without changing prefix, generation,
   responsiveness, or wx-thread behavior. Incremental loading is the normal
   path, not an optional CLI mode.
2. **Simplify panel creation and rollback.** Map resources acquired at each
   stage of `_open_view` and cleanup on each failure. Evaluate a scoped owner or
   clearer lifecycle boundary against the existing implementation. Success:
   fewer caller-managed intermediate resources and explicit ownership transfer,
   with replacement restoration, subscriptions, and VTK/Matplotlib cleanup
   preserved. Start with existing failed-view tests and add only missing failure
   scenarios needed for a proposed change.
3. **Map store scheduling, query, and eviction invariants.** Document the lock,
   epoch, pinning, snapshot, and memory-accounting relationships around
   `prefetch`, derived queries, and eviction; compare `series` and
   `station_access` for repeated policy. Prototype a narrow internal boundary or
   common operation only if it simplifies those relationships. Success: fewer
   responsibilities or repeated rules per caller without a second raw-data
   owner, numerical changes, weaker memory bounds, or a performance regression.
4. **Reduce repeated view protocol where equivalent.** Detailed investigation
   plan:
   [PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md](./PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md).
   Compare the ten binding
   users, including history, Ground Track, and station views, and enumerate
   bind/query/refresh/close obligations and coverage behavior. Test a small
   helper only for truly shared policy. Success: fewer repeated lifecycle rules
   without obscuring tier subscriptions, partial results, or backend-specific
   rendering; report the number of affected callers before and after.
5. **Review saved-state parsing and validation.** `load_saved_state` has the
   highest measured decision score, with validation and version-dependent
   behavior. Group branches by independent state section and inspect repeated
   error handling. Try section-level parsing only if it makes the validation
   contract clearer. Preserve version migrations, rejection behavior, error
   messages where relied upon, and fallback-to-default startup; use the existing
   saved-state tests to assess compatibility. Detailed investigation plan:
   [PLAY_OEM_COMPLEXITY_8_SAVED_STATE_PARSING_VALIDATION_PLAN.md](./PLAY_OEM_COMPLEXITY_8_SAVED_STATE_PARSING_VALIDATION_PLAN.md).
6. **Investigate domain and performance hotspots separately.** Examine
   `_intervals_for_segment`, `_capacity_for_ascii_file`, and the large workspace
   constructor for distinct opportunities. Their high scores may represent
   necessary boundary handling, optimized scanning, or GUI layout. Require
   boundary-case tests and relevant benchmarks before changing numerical or
   scanning logic; do not prioritize a rewrite based on a score alone. Detailed
   investigation plan:
   [PLAY_OEM_COMPLEXITY_9_DOMAIN_PERFORMANCE_HOTSPOTS_PLAN.md](./PLAY_OEM_COMPLEXITY_9_DOMAIN_PERFORMANCE_HOTSPOTS_PLAN.md).
7. **Inventory compatibility and backend variants.** Identify callers and
   documented support for both cursor implementations and both 3D backends,
   including possible external users. Estimate their maintenance cost and
   behavioral differences before proposing consolidation or retirement. Treat
   supported behavior as a constraint until its owner decides otherwise.
   Detailed investigation plan:
   [PLAY_OEM_COMPLEXITY_10_CURSOR_BACKEND_COMPATIBILITY_PLAN.md](./PLAY_OEM_COMPLEXITY_10_CURSOR_BACKEND_COMPATIBILITY_PLAN.md).

## Evidence gaps and completion criteria

The baseline does not measure runtime, memory, call-graph depth, dependency
cycles, change frequency, defect history, or external API usage. It does not
establish how many protocol steps are duplicated or whether a proposed
abstraction will reduce total complexity. Static inspection and counts were
performed; tests and GUI scenarios were not run for this assessment.

For each chosen work item, record the relevant before/after behavior trace,
caller obligations, local scores and volume, tests, and performance where
applicable. Accept a change when it makes the relevant responsibilities and
invariants easier to understand and verify without moving equal or greater
complexity into another layer or changing required behavior. Reassess the
priority order after the first lifecycle trace and caller inventory.

## Lifecycle work-item update — 2026-11-10

The detailed trace, transition table, responsibility matrix, and test mapping
are recorded in
[PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md).
At commit `629cb280b3f31bca3979aa8d79a96d82e6ae97f6`, the worktree was clean
before implementation changes. Focused loader, stream, controller, cache,
store, clock, range, and point-query validation passed (267 tests). Deterministic
controller tests now cover closing during a blocked parse and the exact
per-tick event-drain limit.

The lifecycle remains the first investigation priority because mistakes can
discard valid data or cross generation/epoch boundaries; however, no duplicated
event consumer or row-sink protocol was found, and a single enum would conflate
the current load with the installed store's completeness. A production
abstraction was therefore not justified by this evidence. The controller's
unbounded event drain was a separate, concrete responsiveness risk; it now
handles at most 64 events per timer tick and leaves the rest for later ticks.
The test verifies this work bound. Change frequency, defect history, and native
GUI latency remain unknown. Store scheduling/query/eviction became the next
investigation; see the subsequent work-item update.

## Store scheduling and cache lifecycle update — 2026-11-10

The verified trace, tier matrix, lock notes, test mapping, and evaluation are
recorded in
[PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md](./PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md).
The investigation found identical tier-specific support-range expansion in
`_priority_for_request` and `_request_rows`; the shared
`_expanded_request_bounds` helper now owns that policy. The store/memo and
controller integration suites passed (163 tests). Targeted method volume fell
by 11 lines net, while the module gained one helper; this is a small local
clarity and policy-consistency improvement, not a broad store simplification.

The derived-memory budget covers selected chunk and Ground Track buffers, not
process RSS or every bounded cache. Pinned/active chunks can remain resident
over budget, and chunk eviction depends on platform memory advice. No RSS,
native GUI latency, change-frequency, or defect-history evidence was gathered.
The next work item is the derived-query slice of priority 3; avoid a scheduler
extraction or module split absent stronger evidence.

## Derived store query update — 2026-11-10

The verified tier contracts, test map, before/after comparison, and decision
are recorded in
[PLAY_OEM_COMPLEXITY_6_DERIVED_STORE_QUERIES_PLAN.md](./PLAY_OEM_COMPLEXITY_6_DERIVED_STORE_QUERIES_PLAN.md).
The query comparison found that `_coverage_for_rows` already centralizes the
common series/Earth-fixed span-to-coverage conversion; their span selection is
intentionally different, while Ground Track delegates to Earth-fixed coverage
and station access has sample-grid coverage. No broader query abstraction was
justified.

The narrow repeated invariant was Earth-centered metadata validation across
the three range queries and the station-metric and footprint point queries.
`_earth_centered_frame_name` now owns string-presence, loading-versus-complete,
and Earth-center checks while callers retain their distinct incomplete results
and error messages. The source module fell from 3,536 to 3,505 physical lines;
focused store/view validation passed (155 passed, 3 skipped). This is local
deduplication, not evidence of lower whole-store coupling or improved runtime.
Dataflow and store design did not change. Priority 3 is complete; the next
authoritative work item was priority 4, view refresh coordination.

## View refresh coordination update — 2026-11-10

The verified event-to-view routing, binding inventory, benchmark limits,
test results, and decision are recorded in
[PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md](./PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md).
The focused controller/binding/range/history/Ground Track/station/graph-panel
suite passed (217 passed, 3 skipped). Eight deterministic routing cases were
added, including duplicate-notice coalescing and stale-epoch rejection
coverage. No production refresh or binding code changed.

The current map is explicit and station-status demonstrates why scheduler
binding interest and stale-view routing are not interchangeable. The synthetic
notice-drain stress test scaled linearly, but did not establish realistic
backlog frequency or rendering impact; a queue cap could break coalescing or
starve refreshes. Retain the current architecture and revisit batching only if
representative queue-depth or timer-latency evidence justifies it. The status
bar reports panel update failures, but pending IDs are cleared and there is no
automatic retry; this remains an unresolved recovery-policy question, not a
verified defect.

No dataflow or store-design document change is warranted because runtime
ownership and behavior are unchanged. Priority 4 is complete. The next
authoritative work item is priority 5, saved-state parsing and validation
(`saved_state.load_saved_state`).

## Saved-state parsing and validation update — 2026-11-10

The verified section/version behavior, fallback contract, tests, and decision
are recorded in
[PLAY_OEM_COMPLEXITY_8_SAVED_STATE_PARSING_VALIDATION_PLAN.md](./PLAY_OEM_COMPLEXITY_8_SAVED_STATE_PARSING_VALIDATION_PLAN.md).
The saved-state and CLI regression suite passed (48 passed). Tests now cover
missing-file defaults, malformed TOML, unsupported versions, unknown root and
nested keys, one-warning fallback, and document-wide fallback after a later
section is invalid.

No production parser refactor was justified: the existing code is already
organized into contiguous sections, reuses shared domain validators, and
enforces one consistent first-error/default policy. Extracting those blocks
would add indirection without reducing validation rules or changing recovery
behavior. Statement coverage in the targeted run increased from 74% to 76%;
remaining uncovered paths are not treated as proof of defects.

The persisted format, serializer, and startup ownership are unchanged, so no
dataflow or format documentation update is warranted. Priority 5 is complete.
The next authoritative work item is priority 6, investigating domain and
performance hotspots separately.

## Domain and performance hotspots update — 2026-11-10

The three independent investigations, measurements, tests, and decisions are
recorded in
[PLAY_OEM_COMPLEXITY_9_DOMAIN_PERFORMANCE_HOTSPOTS_PLAN.md](./PLAY_OEM_COMPLEXITY_9_DOMAIN_PERFORMANCE_HOTSPOTS_PLAN.md).
The store/interval test run passed (80 passed); the direct wx Workspace test
was skipped because this environment has no display.

Station interval logic remains unchanged; two focused tests now cover the
non-finite-metric split/reset behavior and coverage/gap endpoint flags. The
capacity scanner's synthetic 1-64 MiB runs measured scan latency separately
from parsing, but did not establish a production bottleneck. The scan occurs
on the loader worker before parsing begins, not on the wx thread. Workspace
construction remains explicit GUI composition; no extraction boundary or
performance need was demonstrated, and native layout validation was
unavailable.

No production source or subsystem ownership changed. Priority 6 is complete.
The next authoritative work item is priority 7, inventorying cursor and 3D
backend compatibility variants.

## Cursor and 3D backend compatibility update — 2026-11-10

The verified lifecycle, compatibility matrix, backend-selection trace,
validation, and unresolved typing question are recorded in
[PLAY_OEM_COMPLEXITY_10_CURSOR_BACKEND_COMPATIBILITY_PLAN.md](./PLAY_OEM_COMPLEXITY_10_CURSOR_BACKEND_COMPATIBILITY_PLAN.md).
The focused cursor/store, Matplotlib/VTK, config/CLI, and app backend-selection
tests passed (174 passed, no skips).

`OemCursor` remains the owned-history and append path; `StoreCursor` is the
snapshot-backed incremental path. Common point-query results matched across
exact, interpolated, gap, out-of-range, and configured-interpolation cases.
The app transitions to `StoreCursor` on the first usable append, while
store-backed views use `StoreViewContext`. Matplotlib remains the exported
default implementation; optional VTK retains separate native-widget,
render-context, and cleanup behavior. CLI/config choices, lazy imports,
fallback behavior, and explicit VTK errors are covered by focused tests.

No production change or consolidation was justified. The source annotations
still describe some runtime cursor fields as `OemCursor`; Pylance diagnostics
timed out, so this is recorded as an unverified typing question rather than a
confirmed type error. VTK unit tests use a fake widget for render-context
behavior, so native desktop integration remains unverified. External consumer
usage is unknown. Priority 7 is complete; the remaining assessment candidate
is large GUI view responsibilities; see
[PLAY_OEM_COMPLEXITY_11_LARGE_GUI_VIEW_RESPONSIBILITIES_PLAN.md](./PLAY_OEM_COMPLEXITY_11_LARGE_GUI_VIEW_RESPONSIBILITIES_PLAN.md)
for the bounded investigation and candidate-ranking procedure.

## Large GUI view responsibilities update — 2026-11-10

The state/resource maps, candidate comparison, bounded change, and test
results are recorded in
[PLAY_OEM_COMPLEXITY_11_LARGE_GUI_VIEW_RESPONSIBILITIES_PLAN.md](./PLAY_OEM_COMPLEXITY_11_LARGE_GUI_VIEW_RESPONSIBILITIES_PLAN.md).
The Ground Track and pass-view suites passed (41 passed, 3 display-gated
skips); selected app lifecycle tests passed (9); store-backed view tests
passed (3).

No whole-view extraction was justified. The Ground Station Passes view already
uses `StationAnalysisContext` for shared station/interval selection, and its
responsive presentation and lifecycle have focused tests. Ground Track
navigation remains tied to projection and axes operations, but its horizontal
and vertical scrollbar conversions duplicated a small inverse-mapping policy
with no direct headless coverage. That mapping is now centralized in private
pure helpers and tested for direction, quantization, clamping, full-world
disablement, and both-axis integration. The wx view retains ownership of
controls, projection, axes, and redraw.

Native wx layout tests were skipped without a display; no subsystem or
dataflow ownership changed. This candidate is complete. Re-rank the remaining
assessment candidates before defining the next authoritative work item. The
next selected candidate is panel and view lifecycle: transactional rollback and
heterogeneous resource release have concrete, testable consequences, while
controller initialization remains a broader follow-on without a specific
runtime mismatch. See
[PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md).

## Panel and view lifecycle update

The lifecycle trace, bounded change, and test results are recorded in
[PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md).
The complete app lifecycle suite passed (88 passed); representative store
binding, history, Ground Track, station, speed/altitude, and VTK suites passed
(70 passed, 3 skipped). The skipped cases require a display. VTK cleanup tests
use a fake widget, so native desktop integration remains unverified.

Setup rollback and normal resource release shared the same low-level
callback-disconnect, unsubscribe, and `view.close()` sequence. That sequence
is now centralized in `_release_view_resources`, with exactly-once assertions
for failed construction, successful replacement, ordinary close, and frame
shutdown. Transaction-specific panel restoration, registry updates, and
destruction remain separate. Existing resource owners and runtime behavior are
unchanged; no subsystem or dataflow documentation update is warranted.

Priority 8, panel and view lifecycle, is complete. The remaining assessment
candidate is controller initialization and shared state. It is broader and
currently lacks a specific runtime mismatch, so first define a bounded
investigation and verify state ownership and initialization ordering before
proposing a refactor. The bounded investigation is planned in
[PLAY_OEM_COMPLEXITY_13_CONTROLLER_INITIALIZATION_SHARED_STATE_PLAN.md](./PLAY_OEM_COMPLEXITY_13_CONTROLLER_INITIALIZATION_SHARED_STATE_PLAN.md).

## Controller initialization and shared state update — 2026-11-11

The state map, ordering findings, bounded changes, and validation are recorded
in
[PLAY_OEM_COMPLEXITY_13_CONTROLLER_INITIALIZATION_SHARED_STATE_PLAN.md](./PLAY_OEM_COMPLEXITY_13_CONTROLLER_INITIALIZATION_SHARED_STATE_PLAN.md).
An AST inventory found 80 unique attributes assigned by `PlayerApp.__init__`;
all 48 data attributes in `PlayerAppState` are initialized there. No separate
state owner or stale protocol member was identified, so a constructor
extraction or state container is not justified.

Two concrete initialization-order issues were fixed. Invalid render-rate
input previously mutated the supplied clock and cursor before raising; its
validation now precedes those side effects. A failure during the last workspace
setup call previously left a clock observer registered to the incomplete app;
the subscription now occurs after workspace setup succeeds. The app, CLI, and
control-window tests passed (119 passed).

No subsystem or dataflow ownership changed. Native wx event dispatch and
cleanup after failure during frame/workspace/control-window construction
remain unverified. Priority 9, controller initialization and shared state, is
complete.

## Partial GUI startup cleanup selection — 2026-11-11

Re-ranking the remaining leads selects cleanup after partial GUI construction
as the next investigation. It is the clearest unverified failure boundary from
the controller initialization trace: a frame, workspace, control window, or
timer may already exist when a later constructor step fails, but normal cleanup
requires a successfully constructed `PlayerApp`. The bounded investigation is
planned in
[PLAY_OEM_COMPLEXITY_14_PARTIAL_GUI_STARTUP_CLEANUP_PLAN.md](./PLAY_OEM_COMPLEXITY_14_PARTIAL_GUI_STARTUP_CLEANUP_PLAN.md).

The raw-ingestion reservation lead remains deferred because the lifecycle
investigation found one production sink and no repeated independent protocol.
Load-event consumption also remains deferred: the event consumer was traced,
no duplicate consumer was found, and its per-tick drain is already bounded.

## Partial GUI startup cleanup findings — 2026-11-11

Failure injection confirmed that frame/workspace/control-window construction
could fail after acquiring GUI resources without running normal close cleanup.
`PlayerApp` now rolls back acquired resources independently and preserves the
original construction exception. It keeps both newly created and reused
`wx.App` instances intact; cleanup failures are logged and do not prevent
remaining releases. The implementation and evidence are recorded in
[PLAY_OEM_COMPLEXITY_14_PARTIAL_GUI_STARTUP_CLEANUP_PLAN.md](./PLAY_OEM_COMPLEXITY_14_PARTIAL_GUI_STARTUP_CLEANUP_PLAN.md).

The app, CLI, and control-window regression suites passed (**125 passed**).
These tests use fakes and do not verify native wx teardown. No dataflow
ownership changed. Re-rank remaining candidates before selecting the next
investigation; no next implementation item is preselected.

## Store-backed view result-state selection — 2026-11-11

The next investigation is how store-backed views interpret query coverage,
committed-prefix values, and load state when rendering data and selecting
status. `StoreViewContext` already binds queries to snapshots and ranges, while
Ground Track, Ground Station Passes, Ground Station Analysis, and Speed/
Altitude apply distinct result and presentation rules. This is a candidate for
cross-caller clarification, not evidence that the rules are inconsistent or
should be unified.

The bounded investigation will compare the state precedence and test coverage
without repeating the store-query, refresh-coordination, or panel-lifecycle
work. Its plan is
[PLAY_OEM_COMPLEXITY_15_STORE_VIEW_RESULT_STATE_PLAN.md](./PLAY_OEM_COMPLEXITY_15_STORE_VIEW_RESULT_STATE_PLAN.md).
The raw-ingestion reservation and load-event-consumption leads remain deferred
absent a concrete protocol gap or transition mismatch. Native wx teardown
requires display-capable integration evidence and is deferred separately.

## Store-backed view result-state findings — 2026-11-11

The comparison and test map are recorded in
[PLAY_OEM_COMPLEXITY_15_STORE_VIEW_RESULT_STATE_PLAN.md](./PLAY_OEM_COMPLEXITY_15_STORE_VIEW_RESULT_STATE_PLAN.md).
`StoreViewContext` preserves snapshot/range semantics, and
`store_load_status_message()` already centralizes the shared failed/cancelled
store-state wording. Ground Track, station views, and Speed/Altitude have
different result and presentation requirements; no common result classifier
or production change was justified.

Ground Track status tests now distinguish incomplete empty data, complete
empty data, and no effective range. The focused Ground Track, Ground Station
Passes, Station Analysis, Speed/Altitude, and shared series-view suites passed
(80 passed, 3 skipped). The skipped tests require a wx display. Raw-ingestion
reservation and load-event-consumption leads remain deferred; native wx
teardown remains unverified. No next implementation candidate is selected;
re-rank remaining candidates before defining another plan.

## Native wx cleanup verification selection — 2026-11-11

Re-ranking the residual leads selects native validation of partial GUI startup
cleanup. Plan 14 established the Python-level rollback contract, but its fakes
cannot verify native child ownership, deferred deletion, or timer behavior.
Existing display-backed tests skip without a usable wx display and identify
`xvfb-run` as a possible test path. The bounded feasibility and integration
plan is
[PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md](./PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md).

This is a validation plan, not a new production refactor. Raw-ingestion
reservation and load-event consumption remain deferred because their concrete
failure and event paths have already been mapped without revealing a current
gap. Plan 16 must report a native environment blocker if no display-backed run
is feasible; fake-widget results must not be presented as native verification.

## Native wx cleanup verification findings — 2026-11-11

The display-backed test and evidence are recorded in
[PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md](./PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md).
Although `DISPLAY` was unset and `xvfb-run` unavailable, wxPython 4.2.4 on
macOS reported a usable `osx-cocoa` display. A real `PlayerApp` failure after
workspace/control-window/timer construction closed the workspace, left the
timer stopped, preserved the wx app, propagated the injected exception, and
removed the frame from wx's top-level windows after event processing; its
wrapper then rejected native access.

The complete app lifecycle suite passed (**97 passed**), including this native
integration test. No production change was needed. Native teardown is verified
only for macOS Cocoa; GTK, MSW, and other wxPython versions remain unverified.
The test's display-free skip branch was reviewed but not executed because this
environment reports a native display. Raw-ingestion and load-event leads
remain deferred; no next implementation candidate is selected.

## Cross-platform wx cleanup verification — 2026-11-11

Plan 17 completed the runner-feasibility check. The current host is macOS;
there is no Linux/GTK or Windows/MSW host, no `xvfb-run` or local container
runtime, and no `.github/workflows` configuration. Linux and Windows runs are
therefore **blocked**, not passed or skipped. The known macOS Cocoa result
remains limited to the 97-pass app lifecycle suite recorded above.

No CI infrastructure or production change was added: cross-platform teardown
behavior and backend-specific assertion reliability remain unverified. The
next actionable step requires access to a Linux runner with wxGTK and Xvfb and
a desktop-capable Windows runner. The feasibility evidence and explicit
limitations are recorded in
[PLAY_OEM_COMPLEXITY_17_CROSS_PLATFORM_WX_CLEANUP_PLAN.md](./PLAY_OEM_COMPLEXITY_17_CROSS_PLATFORM_WX_CLEANUP_PLAN.md).

## Native wx runner enablement selection — 2026-11-11

Because plan 17 could not execute outside macOS, the next step is a separate,
bounded feasibility and implementation plan for hosted Ubuntu/wxGTK and
Windows/wxMSW test jobs. The work must first prove Linux dependency installation
and virtual-display behavior, and Windows native GUI availability; it must not
assume those capabilities or introduce self-hosted runners. If both hosted
paths are viable, add only the narrow CI coverage needed for the real cleanup
test and focused app lifecycle suite. If not, record the blocker and stop
before adding infrastructure. Scope and gates are in
[PLAY_OEM_COMPLEXITY_18_WX_CI_RUNNER_ENABLEMENT_PLAN.md](./PLAY_OEM_COMPLEXITY_18_WX_CI_RUNNER_ENABLEMENT_PLAN.md).

Plan 18 found no configured GitHub Actions workflows and could not test hosted
runner policy, Linux wxGTK installation, or Windows desktop availability from
this session. It added no speculative infrastructure; GTK and MSW remain
blocked and unverified. Continuing requires authorization and a mechanism to
run a minimal hosted workflow, or independently provided platform runners.

## Hosted wx test pilot selection — 2026-11-11

Plan 19 proposed a manually triggered GitHub Actions run on one Ubuntu and one
Windows hosted runner. Execution is deferred: the available environment is
macOS only, with no access to Ubuntu or Windows. No workflow was added or
triggered; GTK and MSW remain blocked until non-macOS runner access becomes
available. See
[PLAY_OEM_COMPLEXITY_19_HOSTED_WX_TEST_PILOT_PLAN.md](./PLAY_OEM_COMPLEXITY_19_HOSTED_WX_TEST_PILOT_PLAN.md).

## Active-load shutdown investigation selection — 2026-11-11

With cross-platform execution deferred, the next locally executable step is
to verify app shutdown while an incremental OEM load is active. Shutdown is a
stated invariant of the load lifecycle, but the available findings do not
establish that a focused test covers late loader events after teardown. Plan 20
will first check existing tests and add coverage only if a real gap remains;
it will not presume a production defect.
[PLAY_OEM_COMPLEXITY_20_ACTIVE_LOAD_SHUTDOWN_PLAN.md](./PLAY_OEM_COMPLEXITY_20_ACTIVE_LOAD_SHUTDOWN_PLAN.md)
records the bounded procedure.

Plan 20 found existing deterministic coverage for closing during a blocked
parse: cancellation and store closure are asserted, and releasing the parser
does not append a sample. The loader suite plus this focused app test passed
(11 passed) on macOS; no duplicate test or production change was needed.
GTK/MSW remain deferred.

## Native active-load shutdown selection — 2026-11-11

Plan 20's active-load shutdown test uses the app test doubles, while plan 16's
native wx integration verifies partial-construction rollback. The next
macOS-only step is to verify the intersection: closing real wx resources while
the loader is blocked at a deterministic parser boundary. Add a display-gated
test only if the combined setup is safe and reliable; keep GTK/MSW deferred.
Scope is in
[PLAY_OEM_COMPLEXITY_21_NATIVE_WX_ACTIVE_LOAD_SHUTDOWN_PLAN.md](./PLAY_OEM_COMPLEXITY_21_NATIVE_WX_ACTIVE_LOAD_SHUTDOWN_PLAN.md).

Plan 21 verified the intersection on macOS Cocoa: the real wx app closed during
a blocked parse, cancelling the session, stopping the timer, closing the store
and workspace, preserving `wx.App`, and preventing late append. The focused
native test passed and the full app lifecycle suite passed (98 passed) with
wxPython 4.2.4 / wxWidgets 3.2.8. No production change was needed; GTK/MSW
remain deferred.

## Candidate re-ranking selection — 2026-11-11

The next step is a decision checkpoint, not another adjacent lifecycle test.
Reconcile remaining candidates against completed work, require an observable
complexity hypothesis and feasible before/after validation, and select at most
one new candidate. If none meets those criteria, pause the sequence until new
evidence or platform access becomes available. Plan 22 records this bounded
re-ranking procedure:
[PLAY_OEM_COMPLEXITY_22_CANDIDATE_RERANKING_PLAN.md](./PLAY_OEM_COMPLEXITY_22_CANDIDATE_RERANKING_PLAN.md).

## Snapshot-installation reduction selection — 2026-11-11

The reranking conclusion is reopened by a focused source comparison of
`PlayerApp._install_store_snapshot`: first and later appends contain the same
pending-playback-bounds decision, while later append has a separate
follow-coverage case. Plan 23 tests whether consolidating only the duplicated
decision reduces local complexity without flags or indirection. This is the
next code-directed experiment; retain the change only if the behavior remains
clearer and the relevant tests pass:
[PLAY_OEM_COMPLEXITY_23_SNAPSHOT_INSTALLATION_DEDUPLICATION_PLAN.md](./PLAY_OEM_COMPLEXITY_23_SNAPSHOT_INSTALLATION_DEDUPLICATION_PLAN.md).

Plan 23 completed the experiment. `_apply_pending_playback_bounds` now owns
the duplicated pending-range application decision; first-append cursor
anchoring and later-append follow-coverage behavior remain separate. Existing
pending-range tests cover initial and subsequent append behavior, so no test
was added. The app, clock, and time-range suites passed (162 passed) on macOS.
This is a bounded local reduction in duplicated policy, not a broader
controller or load-lifecycle redesign.

Plan 22 is complete. The ranked candidates have been investigated, and the
remaining leads lack either a concrete complexity defect/change hypothesis or
an available validation path. No new implementation plan is selected. Reopen
the ranking when evidence emerges—such as duplicated protocol callers,
representative refresh latency, a reproducible state mismatch, or non-macOS
runner access—rather than continuing with adjacent test-only extensions.
