# play-oem complexity assessment

This assessment records the initial static baseline, completed targeted
investigations, and current evidence priorities. It applies the framework in
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
The current ranking is a judgment about what evidence to collect next, not a
measured defect rate or commitment to implement a particular design. Update it
when traces, experiments, and measurements provide better evidence.

## Scope boundary

This assessment concerns implementation complexity, not algorithmic
efficiency. Reducing asymptotic time complexity or space complexity (Big-O
runtime or memory) is out of scope. Runtime, latency, queue, and RSS
measurements are guardrails for understanding the operating envelope and
checking that maintainability changes preserve required behavior; improving
those measurements is not an objective. Track any separate performance or
memory optimization independently.

For an analysis of state, concurrency, and domain interactions, see
[logically complex subsystems](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).

## Initial baseline and method

Initially measured against source at Git commit `cf93496` on 2026-11-10, with
no source modifications in the working tree. Scope: Python files recursively under
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
The current source baseline, measured with the same method, is recorded at the
end of this document.

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

- **Loading:** Plan 4 mapped generation, epoch, replacement, valid-prefix, and
  thread ownership; Plans 20–21 verified active-load shutdown on macOS. No
  lifecycle enum was justified. Cross-platform event-loop behavior and
  sustained-load responsiveness remain open.
- **Queries and view lifecycle:** Plans 5–7, 12, and 15 mapped tier/query
  validity, refresh routing, binding ownership, and presentation differences.
  `StoreViewBinding` centralizes subscription switching; no common result or
  rendering policy was found.
- **Panel construction:** `_open_view` is 172 lines with score 39 in the current
  baseline. Plan 12 centralized low-level release while preserving
  transaction-specific rollback. GTK/MSW and native VTK lifecycle remain
  unverified.
- **Store ownership:** Plans 5–6 mapped locks, epochs, tier validity, and shared
  query policy; Plan 30 clarified the eviction-candidate record. Broad module
  separation remains unjustified; Plan 33 found no boundary cost, and Plan 32
  is deferred indefinitely.
- **Internal dependencies and responsibility map:** Plan 33 inspected 63
  modules and found no eager import cycle in its first-pass AST graph. It
  traced load/store ownership, derived-query subscriptions, range and redraw
  callbacks, view/panel lifecycle, and backend selection. View registration and
  tier-to-view refresh are explicit coordination points, but the roles differ
  and no repeated avoidable cost was established. Retain the current
  boundaries; the scan is not an exhaustive runtime call graph or external
  caller audit. See the [Plan 33 execution record](./PLAY_OEM_COMPLEXITY_33_INTERNAL_DEPENDENCY_RESPONSIBILITY_MAP_PLAN.md).
- **Cursor type contract:** Plan 10 documented that playback starts with an
  `OemCursor` and the controller replaces it with a `StoreCursor` on the first
  usable append, while several declarations still named `OemCursor`. Plan 35
  confirmed that the app and views opened after installation can receive
  either concrete cursor. It added a `PlaybackCursor` union to those runtime
  surfaces while preserving `OemCursor`-only initialization and
  `StoreCursor`-only refresh narrowing. Focused tests passed; post-change
  Pylance diagnostics timed out.

## Historical code-directed candidates

The original hotspot list was a discovery backlog, not an implementation plan.
Plans 4–30 have investigated its load lifecycle, store scheduling and queries,
view refresh and lifecycle, controller state, saved-state parsing, domain
performance, cursor/backend variants, station access, interpolation metadata,
and snapshot installation. The detailed decisions and links are retained in
the compressed execution record below. No broad extraction or split was
justified by those reviews. Do not revive the old candidates from their
baseline scores; current work is limited to the evidence priorities below.

## Caller-side protocol complexity — investigated leads

Use **caller-side protocol complexity** for the effort an API imposes on its
callers to prepare inputs, follow operations in the right order, interpret
results, and perform cleanup. When the same sequence is repeated, it is also
**duplicated orchestration** or **caller boilerplate**. The required ordering
is often called **temporal coupling**; when implementation details escape the
interface, **leaky abstraction** may also apply. These terms describe different
aspects, not proof that a particular API is poorly designed. The initial leads
below have been investigated; detailed outcomes are summarized in the execution
record and documented in their individual plans.

The distinction matters: some preparation and cleanup enforce real resource,
concurrency, or rendering requirements. The opportunity is to make a common
safe operation easier for its callers without hiding decisions they need or
weakening the underlying guarantees. Reviewed leads and remaining evaluation:

| Historical lead | Decision from completed review | Less-evaluated follow-up |
| --- | --- | --- |
| Store-backed view binding and refresh | Plan 7 found no shared refresh policy beyond existing subscription ownership. | Measure real queue depth and GUI latency before revisiting batching. |
| Range query preparation and result handling | Plans 6 and 15 found shared snapshot preparation but distinct coverage and presentation semantics. | Exercise range changes while derived work is pending on representative data. |
| Panel creation and disposal | Plan 12 centralized low-level release; Plan 14 established partial-startup rollback; Plans 16 and 20–21 verified Cocoa cleanup. | GTK/MSW and native VTK resource behavior remain unavailable or fake-widget tested. |
| Raw-ingestion reservation | One production `_StoreRowSink` owns the protocol; no duplicate consumer was found. | Reopen only if a second caller or concrete lifecycle failure appears. |
| Load event consumption | Plans 4, 20, 21, and 26 verified bounded draining, stale-event handling, and shutdown; extraction was rejected. | Representative sustained-load responsiveness and non-macOS event-loop behavior remain unmeasured. |

These are not active refactoring tasks. Consider a shared helper only when new
evidence shows the same safe operation is independently repeated and the
abstraction reduces caller obligations without hiding necessary policy.

## Current evidence priorities

Plans 4–30 investigated the initial code-directed candidates. Plan 31 found
that the available Git history spans only 27 days and does not support
long-term frequency conclusions. Use the following evidence-first sequence;
do not revive completed refactors based on old baseline scores.

| Priority | Evidence task | Scope and decision rule |
| --- | --- | --- |
| 1 — complete | [Internal dependency and responsibility map](./PLAY_OEM_COMPLEXITY_33_INTERNAL_DEPENDENCY_RESPONSIBILITY_MAP_PLAN.md) | Completed the first-pass import, ownership, callback, dynamic-registration, and representative change-path map. No eager import cycle or avoidable boundary cost was established. Retain current boundaries; revisit view registration or tier-to-view refresh only if future changes demonstrate repeated coordination failures. |
| 2 — deferred indefinitely | [Representative runtime and memory](./PLAY_OEM_COMPLEXITY_32_REPRESENTATIVE_LOAD_MEASUREMENT_PLAN.md) | No execution is scheduled. Resume only after explicit reprioritization. If reinstated, measure the combined workload as written and treat latency, queue depth, and memory as operating constraints—not optimization targets. |
| 3 — complete | [Cursor runtime/type contract](./PLAY_OEM_COMPLEXITY_35_CURSOR_TYPE_CONTRACT_PLAN.md) | Added a `PlaybackCursor` union for the app's switched state and direct consumers; retained the initial `OemCursor` input and concrete refresh narrowing. Five focused suites passed (130 tests); post-change Pylance requests timed out. |
| 4 — conditional | Native cross-platform GUI behavior | Real wx cleanup was verified on macOS Cocoa; GTK/MSW and native VTK widget lifecycle remain unverified. Resume when suitable Linux/Windows runners are available; do not infer native behavior from fake widgets or add speculative CI. |
| 5 — deferred | Longer-term maintenance trends | Play-OEM source history begins 2026-10-15. Revisit change frequency after several months of ordinary maintenance; the current feature and migration bursts are not representative. |

Plan 33 is complete; it did not identify a boundary change to implement. The
representative runtime and memory study is deferred indefinitely and is not an
active task. The project maintainer has said that there are not yet external
users and compatibility is not a concern; Plan 34 was closed before its
evidence matrix was completed and compatibility evidence is not a gate for
current changes. Native GUI work depends on runner availability, and
longer-term maintenance review depends on additional ordinary history. Plan 35
is complete with a bounded annotation-only clarification and no runtime
refactor.

## Evidence gaps and completion criteria

The current static baseline and 27-day change-history sample do not measure
representative runtime, peak memory, sustained GUI latency, external API use,
or long-term maintenance patterns. Plan 33 records a package-local dependency
and responsibility map and selected callback paths, but it is not an
exhaustive runtime call graph or external-caller audit. GTK/MSW native behavior
is blocked by runner availability. Existing tests and traces cover many
lifecycle cases, but they do not substitute for production-like workload
measurements.

Accept a future change only when it reduces the rules, caller obligations, or
interactions needed to understand a concrete behavior without moving equal or
greater complexity elsewhere. Record the same before/after trace, relevant
tests, code volume, and performance data where applicable. Otherwise retain the
current design and document the limitation.

## Compressed execution record — Plans 4–31

Detailed traces, implementation decisions, and test commands remain in the
linked plan documents. This summary retains outcomes and limits without
repeating the chronological selection notes.

| Scope | Durable outcome | Record |
| --- | --- | --- |
| Load lifecycle and store scheduling (4–5) | Bounded event draining to 64 per tick and centralized repeated request-bound policy. No lifecycle enum or scheduler extraction. | [Plan 4](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md), [plan 5](./PLAY_OEM_COMPLEXITY_5_STORE_SCHEDULING_CACHE_PLAN.md) |
| Queries and refresh (6–7) | Centralized Earth-center validation; retained distinct query coverage and refresh-routing rules. Focused routing tests added; no refresh policy abstraction. | [Plan 6](./PLAY_OEM_COMPLEXITY_6_DERIVED_STORE_QUERIES_PLAN.md), [plan 7](./PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md) |
| Saved state, domain logic, and variants (8–10) | Parser and cursor/backend consolidation rejected; synthetic capacity scan showed no wx-thread bottleneck; scrollbar conversion helper retained. Plan 35 later clarified the runtime cursor union without changing behavior. | [Plan 8](./PLAY_OEM_COMPLEXITY_8_SAVED_STATE_PARSING_VALIDATION_PLAN.md), [plan 9](./PLAY_OEM_COMPLEXITY_9_DOMAIN_PERFORMANCE_HOTSPOTS_PLAN.md), [plan 10](./PLAY_OEM_COMPLEXITY_10_CURSOR_BACKEND_COMPATIBILITY_PLAN.md), [plan 35](./PLAY_OEM_COMPLEXITY_35_CURSOR_TYPE_CONTRACT_PLAN.md) |
| Views, panels, and controller state (11–13) | Added a scrollbar mapping helper and shared resource-release path; fixed two initialization-order defects. No broad view split or new state owner. | [Plans 11](./PLAY_OEM_COMPLEXITY_11_LARGE_GUI_VIEW_RESPONSIBILITIES_PLAN.md), [12](./PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md), [13](./PLAY_OEM_COMPLEXITY_13_CONTROLLER_INITIALIZATION_SHARED_STATE_PLAN.md) |
| Startup and native wx cleanup (14–21) | Partial-startup rollback and active-load shutdown verified on macOS Cocoa. GTK/MSW execution and hosted runner feasibility remain blocked; no speculative CI was added. | [Plan 14](./PLAY_OEM_COMPLEXITY_14_PARTIAL_GUI_STARTUP_CLEANUP_PLAN.md), [15](./PLAY_OEM_COMPLEXITY_15_STORE_VIEW_RESULT_STATE_PLAN.md), [16](./PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md), [17](./PLAY_OEM_COMPLEXITY_17_CROSS_PLATFORM_WX_CLEANUP_PLAN.md), [18](./PLAY_OEM_COMPLEXITY_18_WX_CI_RUNNER_ENABLEMENT_PLAN.md), [19](./PLAY_OEM_COMPLEXITY_19_HOSTED_WX_TEST_PILOT_PLAN.md), [20](./PLAY_OEM_COMPLEXITY_20_ACTIVE_LOAD_SHUTDOWN_PLAN.md), [21](./PLAY_OEM_COMPLEXITY_21_NATIVE_WX_ACTIVE_LOAD_SHUTDOWN_PLAN.md) |
| Snapshot installation (22–25) | Re-ranking selected three local reductions: pending bounds, exception-safe batch scope, and first-versus-later append phases. | [Plan 22](./PLAY_OEM_COMPLEXITY_22_CANDIDATE_RERANKING_PLAN.md), [23](./PLAY_OEM_COMPLEXITY_23_SNAPSHOT_INSTALLATION_DEDUPLICATION_PLAN.md), [24](./PLAY_OEM_COMPLEXITY_24_BATCH_INSTALL_GUARD_PLAN.md), [25](./PLAY_OEM_COMPLEXITY_25_SNAPSHOT_INSTALLATION_PHASES_PLAN.md) |
| Event routing and station access (26–29) | Rejected per-event and query-phase helpers; grouped active interval metrics in `_ActiveAccessInterval`; rejected metadata conversion extraction. | [Plan 26](./PLAY_OEM_COMPLEXITY_26_INCREMENTAL_EVENT_ROUTING_PLAN.md), [27](./PLAY_OEM_COMPLEXITY_27_STATION_INTERVAL_STATE_PLAN.md), [28](./PLAY_OEM_COMPLEXITY_28_INTERPOLATION_METADATA_PLAN.md), [29](./PLAY_OEM_COMPLEXITY_29_STATION_QUERY_PHASES_PLAN.md) |
| Eviction and history re-ranking (30–31) | Named the eviction-candidate record; method shrank 9 lines while the module grew 5 and decision score stayed 25. Available Git history spans only 27 days and yielded no new refactor candidate. | [Plan 30](./PLAY_OEM_COMPLEXITY_30_EVICTION_CANDIDATE_SHAPE_PLAN.md), [plan 31](./PLAY_OEM_COMPLEXITY_31_CHANGE_HISTORY_RERANKING_PLAN.md) |

## Current focus

Plan 33's dependency and responsibility map is complete and supports retaining
the current boundaries. Plan 32's representative load/query/range-change
measurement is deferred indefinitely. Plan 35 completed the cursor type
contract clarification; compatibility evidence is not a current gate by
maintainer direction. Platform and longer-term maintenance questions remain
conditional or deferred as ranked above.

## Current baseline refresh — 2026-11-11

Measured at commit `34a405bcecef47d7ba94110609f47658491db589`, with a clean
worktree, on macOS using Python 3.9.6. Scope and AST decision-score method are
unchanged from the initial baseline above; the reproduction script there emits
the current counts when run at this commit.

| Measure | Current result |
| --- | ---: |
| Python files | 63 |
| Physical lines | 25,602 |
| Function and method definitions, including nested definitions | 1,111 |
| `oem_data_store.py` lines | 3,510 (13.7% of package) |
| `app/controller.py` lines | 1,954 (7.6%) |
| `app/panel_management.py` lines | 402 |
| `saved_state.py` lines | 551 |
| View files containing `StoreViewBinding(` | 10 |

Current high-scoring functions by the same custom AST indicator:

| Function | Lines | Decision score |
| --- | ---: | ---: |
| `saved_state.load_saved_state` | 268 | 69 |
| `oem_data_store._capacity_for_ascii_file` | 179 | 46 |
| `PanelManagementMixin._open_view` | 172 | 39 |
| `OemDataStore.station_access` | 234 | 35 |
| `PlayerApp._poll_incremental_load` | 128 | 32 |
| `Workspace.__init__` | 398 | 30 |
| `OemDataStore.series` | 159 | 30 |
| `PlayerApp.__init__` | 265 | 28 |
| `views/ground_station_passes._draw_sky_plot` | 172 | 27 |
| `views/ground_station_access._draw_elevation_graph` | 122 | 26 |
| `views/trajectory3d/mpl_backend._refresh_store_trajectory` | 116 | 26 |
| `views/ground_track.update` | 107 | 26 |
| `OemDataStore.ground_track` | 176 | 25 |
| `OemDataStore._evict_derived_buffers` | 153 | 25 |

This refresh is a reproducible current reference, not evidence that line or
decision-score changes alone represent complexity reduction. Representative
runtime/memory profiles, GUI latency, defect history, external API usage, and
long-term change frequency remain unmeasured; GTK/MSW behavior remains
unverified without non-macOS runners.

Plan 31 analyzed all available non-merge history in the requested one-year
window. The Play-OEM source history begins on 2026-10-15, so the actual sample
covers only 27 days and is dominated by initial feature development, module
splits, and the store migration. The most common co-changes pair application
layers and match expected feature integration; excluding broad migration
commits did not expose a distinct duplicated policy. No further implementation
candidate is selected. Change frequency beyond the available 27-day period
remains unknown:
[PLAY_OEM_COMPLEXITY_31_CHANGE_HISTORY_RERANKING_PLAN.md](./PLAY_OEM_COMPLEXITY_31_CHANGE_HISTORY_RERANKING_PLAN.md).
