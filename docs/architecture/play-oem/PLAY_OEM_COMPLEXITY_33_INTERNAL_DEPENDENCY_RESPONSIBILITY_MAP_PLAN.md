# play-oem — Internal Dependency and Responsibility Map Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Current evidence priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Deferred runtime study:
[PLAY_OEM_COMPLEXITY_32_REPRESENTATIVE_LOAD_MEASUREMENT_PLAN.md](./PLAY_OEM_COMPLEXITY_32_REPRESENTATIVE_LOAD_MEASUREMENT_PLAN.md).

## Goal

Build an evidence-based map of internal dependencies, state ownership,
responsibilities, callbacks, and dynamic registration across Play-OEM. Use it
to determine where a concrete change requires unnecessary coordination or
cross-component knowledge, and where existing boundaries already contain
complexity effectively.

This is an investigation plan, not a refactoring proposal. Make no production
changes. Reducing algorithmic time or space complexity is out of scope; the
goal is to understand and, only if evidence supports it, reduce implementation
complexity.

## Why this step

Plans 4–31 investigated and made bounded changes to selected lifecycle,
query, view, controller, and store concerns. They rejected broad extractions
where shared policy or a useful boundary was not established. The strategy
identifies an internal dependency and responsibility map as the next
architectural evidence gap.

The representative runtime and memory study in Plan 32 is deferred for later.
This plan does not depend on its latency or memory measurements. It should
reuse existing traces and plan evidence rather than repeat completed lifecycle
reviews.

## Scope and baseline

- Record the source revision, working-tree state, inspected package scope, and
  tools or scripts used. Keep conclusions tied to that snapshot.
- Focus on internal Python code under
  [`src/ephem_toolkit/play_oem`](../../../src/ephem_toolkit/play_oem) and the
  directly relevant tests. Use tests as behavior evidence, not as production
  dependencies. Do not infer external callers from repository-local references.
- Include loading and controller coordination, raw and derived store
  responsibilities, query and cache ownership, view bindings and range
  updates, workspace and panel lifecycle, representative station views, and
  both trajectory 3D backends.
- Reuse the call paths and invariants recorded in Plans 4–31. Extend a trace
  only when needed to resolve a newly discovered dependency or ownership
  question.
- Treat performance and memory properties as constraints that a maintainability
  change must preserve. Do not investigate or propose runtime, memory, or
  asymptotic time/space optimization in this plan.
- Exclude production refactoring, platform certification, and external API
  compatibility claims. Record these only if they emerge as unresolved
  dependencies relevant to a specific internal boundary.

## Evidence to collect

| Evidence | Record | Limitation |
| --- | --- | --- |
| Internal imports and module dependencies | Directed relationships, cycles, and notable dependency depth between package areas. | Imports miss callbacks, dynamic registration, and runtime dispatch. |
| Responsibility and state ownership | For each selected responsibility, identify the state/decision owner, coordinators, consumers, and the interface used. | A responsibility can be intentionally shared across layers; a single owner is not always appropriate. |
| Calls, events, callbacks, and registration | Registration site, invocation/dispatch site, state passed, thread or lifecycle boundary, and cleanup/unregistration where relevant. | Dynamic behavior may require a focused source trace; static search alone is not proof of runtime execution. |
| Representative change paths | Source and test locations that would change for a bounded behavior change, and the invariants each location protects. | A file count is context, not a complexity score or evidence that files should be merged. |
| Existing tests and prior plans | Tests that verify mapped contracts and links to completed investigations. | Test presence or count does not establish that a responsibility is well-factored. |

Build the responsibility matrix around concrete behaviors, including:

- incremental load, replacement, cancellation, and snapshot installation;
- derived query scheduling, cache validity, and view-held results;
- plot-range propagation and store-backed view refresh;
- view registration, panel opening/replacement/cleanup, and trajectory backend
  selection;
- station or pass analysis where it crosses store, controller, and view
  boundaries.

For each responsibility, use **owner**, **coordinator**, and **consumer**
labels where they clarify distinct roles. Cite source symbols and tests rather
than relying on module names alone.

## Procedure

1. Record the source revision and working-tree state. List the scope and
   exclude generated files, tests-as-production-dependencies, and external
   consumers from the internal dependency map.
2. Establish the module-level import graph for the selected package areas.
   Verify apparent cycles and significant paths in source; do not treat graph
   density, path length, or file size as a finding by itself.
3. Build the responsibility/state-owner matrix for the behaviors above.
   Distinguish state ownership from coordination and consumption, and record
   the interface or event that crosses each boundary.
4. Trace callback and dynamic-dispatch paths that imports cannot show,
   including view registration, event subscriptions, workspace redraw
   scheduling, loader events, and backend selection. Record registration,
   invocation, and teardown/invalidating actions where applicable.
5. Select a small number of bounded change scenarios, such as changing a
   derived-query validity rule, adjusting range propagation, or adding a
   registered view. Trace the files, state owners, tests, and invariants that
   each scenario would actually involve. Reuse earlier plan evidence where
   applicable.
6. Identify potential complexity findings only when evidence shows duplicated
   policy, unclear ownership, unnecessary caller obligations, hidden
   dependency, or repeated cross-component edits for the same rule. Record
   counter-evidence and necessary domain or lifecycle constraints.
7. For each candidate, state a possible boundary or responsibility change,
   expected reduction in reasoning/coordination, new concepts or indirection,
   behavior and performance constraints, and evidence that would reject the
   change. Do not implement it in this plan.
8. Update the assessment and subsystem research with the map's scope,
   evidence, limitations, and a decision to retain current boundaries, gather
   more evidence, or create one separate bounded implementation plan.

## Decision criteria

- Do not infer unnecessary complexity from line counts, AST scores, import
  counts, module size, or a dense dependency graph alone.
- Treat a boundary as a candidate only when a concrete change path demonstrates
  avoidable coordination, duplicated rules, unclear ownership, or caller
  obligations.
- Preserve useful separation, distinct domain semantics, lifecycle rollback,
  concurrency rules, compatibility behavior, and view-specific presentation.
- Do not introduce a shared abstraction merely because code looks similar;
  verify the policy and invariants are actually shared.
- The result need not recommend a refactor. A well-supported decision to keep
  current boundaries or defer judgment is a valid outcome.
- Algorithmic time/space complexity and performance or memory optimization
  remain out of scope. Any maintainability proposal must preserve required
  performance and memory behavior.

## Expected output

- A concise internal module-dependency map with verified cycles or notable
  paths and its coverage limitations.
- A responsibility/state-ownership matrix with source and test references.
- A callback and dynamic-registration map that complements the import graph.
- A few evidence-backed change-coordination traces, including counter-evidence
  and important invariants.
- A ranked set of concrete complexity findings, or an explicit conclusion that
  current evidence does not justify a boundary change.
- Updated assessment and subsystem research; no production code changes.

## Execution record — 2026-11-11

### Snapshot and method

- Source revision: `9a897f060fb19665b4956823b0fb31d4a69b6178`.
- At inspection start, the working tree contained documentation changes only;
  no production or test source files were modified for this map.
- Scope: all 63 Python modules under
  [`src/ephem_toolkit/play_oem`](../../../src/ephem_toolkit/play_oem), with
  focused inspection of app, store, view, workspace, and 3D backend paths.
- Methods: ad hoc Python AST import scan, source searches and reads, Pylance
  symbol usages, and review of existing focused tests. No runtime or performance
  measurements were performed; Plan 32 remains deferred.

### Dependency map

The AST scan found 238 direct module-to-module imports executed at module
import time and no strongly connected import components after excluding
function-local and `TYPE_CHECKING` imports. A broader scan that included those
deferred/type-only imports flagged two apparent cycles. Source inspection
showed that the `cursor`/`oem_data_store` relationship includes type-only and
local imports, while the `selection`/`vtk_backend` relationship uses local
imports to preserve optional, lazy VTK loading; neither is an eager import
cycle. The scan is a first-pass static graph, not a complete call graph or
proof about external imports.

The verified package-level direction is broadly:

| Area | Main dependencies and role |
| --- | --- |
| `app/` | Composition and coordination layer. `PlayerApp` combines view-factory, playback, range, and panel mixins; it connects store/load events, registered views, and workspace operations. `PlayerAppState` is the structural contract used by those mixins. |
| `views/` | Concrete view behavior depends on core data, range, and domain APIs. Store-backed views use `StoreViewContext` and view-specific tier subscriptions; they do not own the store scheduler. |
| `workspace/` and `graph_panel.py` | Own GUI layout, panel hosts, visibility, and redraw scheduling; the workspace does not import concrete view implementations in the scanned graph. |
| Package entry/config modules | CLI and saved configuration use the view registry and backend-choice declarations to validate persisted or command-line selections. This is a user-facing name contract, not an app-to-domain dependency. |
| `views/trajectory3d/` | Backend selection lazily loads the optional VTK implementation. The view factory handles fallback policy; panel management accepts either a Matplotlib `Figure` or native wx content. |

Shared high-fan-in modules include `time_range`, `time_unit`, `series`,
`views.base`, `oem_data_store`, and `views.plotting`. This identifies common
contracts and utilities, not a complexity ranking. The import graph shows
little strict layering by itself: the app is the composition root and callback
paths cross boundaries that imports cannot express.

### Responsibility and ownership matrix

| Concern | Owner | Coordinator and consumers | Evidence / boundary |
| --- | --- | --- | --- |
| OEM ingestion and visible playback state | `IncrementalLoadSession` owns its worker and bounded event queue; `IncrementalLoader` owns the current generation/session; `OemDataStore` owns committed raw rows and epochs; `PlayerApp` owns active/pending load and playback state. | `PlayerApp._poll_incremental_load` validates generation and notices, then routes first-prefix installation or later snapshot advancement to playback and views. | [`IncrementalLoader`](../../../src/ephem_toolkit/play_oem/incremental_loader.py#L211), [`PlayerApp._start_incremental_load`](../../../src/ephem_toolkit/play_oem/app/controller.py#L1200), [`PlayerApp._poll_incremental_load`](../../../src/ephem_toolkit/play_oem/app/controller.py#L1256), [`PlayerApp._install_store_snapshot`](../../../src/ephem_toolkit/play_oem/app/controller.py#L1385). |
| Derived queries, caches, and scheduling | `OemDataStore` owns query tiers, scheduler, range hints, caches, memory budget, and store notices. | `StoreViewContext` supplies snapshot-bound query operations and range/display state; `StoreViewBinding` owns view interest subscriptions and unsubscription. Views consume query results. | [`OemDataStore`](../../../src/ephem_toolkit/play_oem/oem_data_store.py#L752), [`StoreViewContext`](../../../src/ephem_toolkit/play_oem/views/base.py#L81), [`StoreViewBinding`](../../../src/ephem_toolkit/play_oem/views/base.py#L251). |
| Plot range and redraw | `PlayerApp` owns the plot rule and resolved range; `TimeRangeActionsMixin` validates and dispatches changes. | Visible views apply range and cursor updates; hidden panels keep pending range state. `Workspace` schedules visible redraws and `GraphPanelHost` coalesces redraw requests. | [`_dispatch_time_range`](../../../src/ephem_toolkit/play_oem/app/time_range_actions.py#L133), [`queue_graph_redraw`](../../../src/ephem_toolkit/play_oem/workspace/graph_stack.py#L359), [`GraphPanelHost.request_redraw`](../../../src/ephem_toolkit/play_oem/graph_panel.py#L437). |
| View selection and panel lifecycle | `ViewRegistry` owns view names, aliases, groups, and registered openers; `PlayerApp` wires those callbacks. `PanelManagementMixin` owns panel construction, replacement, rollback, and disposal. | `ViewFactoryMixin` constructs concrete views; `Workspace` owns panel placement; each view owns its presentation resources and `close` behavior. | [`ViewRegistry`](../../../src/ephem_toolkit/play_oem/views/registry.py#L55), [`open_panel_view`](../../../src/ephem_toolkit/play_oem/app/panel_management.py#L47), [`_open_view`](../../../src/ephem_toolkit/play_oem/app/panel_management.py#L184), [`_dispose_open_view`](../../../src/ephem_toolkit/play_oem/app/panel_management.py#L381). |
| Station/access analysis | Store query methods coordinate coverage, caching, and derived data; `station_access` owns domain interval calculations. | Station and pass views adapt query results and own selection/presentation rules. | [`OemDataStore.station_access`](../../../src/ephem_toolkit/play_oem/oem_data_store.py#L2176), [`_intervals_for_segment`](../../../src/ephem_toolkit/play_oem/station_access.py#L175), and the existing station-analysis view tests. |
| 3D backend | `PlayerApp` owns requested/selected backend state; the trajectory selector owns backend choices and lazy VTK loading; each backend owns its rendering resources. | `ViewFactoryMixin` chooses VTK or fallback policy; panel management embeds the returned native widget or Matplotlib figure. | [`open_trajectory_view`](../../../src/ephem_toolkit/play_oem/app/view_factory.py#L403), [`create_vtk_view`](../../../src/ephem_toolkit/play_oem/views/trajectory3d/selection.py#L78), and backend-specific tests. |

### Callback and change-path findings

- **Load events:** the session publishes generation-tagged events to a bounded
  queue; the controller drains at most 64 per wx tick and checks generation and
  store snapshot state before installation. This keeps worker parsing, store
  epoch validity, and GUI state distinct.
- **Store notices:** the controller's store callback only enqueues
  `(store, notice)`; the wx-thread drain rejects stale store/epoch notices,
  maps `TierNotice` to affected view names, coalesces panel refreshes, and
  updates a snapshot-bound context. Separately, each `StoreViewBinding`
  subscribes to store tier interest; closing/rebinding the view releases those
  subscriptions. See [`_subscribe_store_notices` and notice routing](../../../src/ephem_toolkit/play_oem/app/controller.py#L630),
  [`subscribe_tier`](../../../src/ephem_toolkit/play_oem/oem_data_store.py#L890),
  and [`StoreViewBinding.bind`](../../../src/ephem_toolkit/play_oem/views/base.py#L260).
- **View registration:** the controller registers fixed view names with bound
  openers, and the registry clears those callbacks at shutdown. Panel-instance
  routing separately maps names to openers that accept panel ID, stack, and
  replacement options. The distinct signatures explain why the two routes are
  not interchangeable, although a new view requires coordinated edits.
- **Redraws:** a panel marks its redraw request and calls the workspace
  scheduler; the scheduler filters to visible panels and services one queued
  panel at a time. This is an intentional callback cycle at runtime, not an
  import cycle.
- **Range change:** the app updates the shared store-view context, defers work
  during incremental refresh when required, applies ranges to visible views,
  retains pending state for hidden views, and asks the workspace to schedule
  drawing. This coordination preserves distinct view semantics and visibility
  behavior.

Three representative change paths were checked:

1. **Add a registered view:** the concrete view and factory opener, selectable
   name/label (and optional group/alias), controller callback registration,
   panel-instance dispatch, and focused tests have separate responsibilities.
   The route is multi-file, but the inspected contracts are distinct. There is
   no evidence that consolidating them would reduce complexity safely.
2. **Add a derived tier consumer:** the store query/notice, view's tier
   subscription, controller's tier-to-view refresh mapping, and tests for
   targeted refresh must agree. The explicit mapping is a coordination point;
   existing coverage in
   [`test_play_oem_app.py`](../../../tests/ephem_toolkit/play_oem/test_play_oem_app.py)
   and [`test_store_series_views.py`](../../../tests/ephem_toolkit/play_oem/test_store_series_views.py)
   checks important behavior. No repeated maintenance failure or unnecessary
   shared policy was established.
3. **Change a plot range or trajectory backend:** the range action, bound
   context/query, view-specific update, and workspace redraw form separate
   contracts; backend selection remains lazy and resource cleanup remains
   panel/view-specific. Existing coverage includes
   [`test_time_range_actions.py`](../../../tests/ephem_toolkit/play_oem/test_time_range_actions.py),
   [`test_graph_panel.py`](../../../tests/ephem_toolkit/play_oem/test_graph_panel.py),
   and [`test_vtk_trajectory3d.py`](../../../tests/ephem_toolkit/play_oem/test_vtk_trajectory3d.py).

### Decision

The map did not identify an eager import cycle, an unclear store/query owner, or
a repeated rule whose extraction is supported by evidence. Explicit view
registration and tier-to-view refresh mappings are the clearest coordination
points, but their responsibilities differ and no recurring avoidable cost was
demonstrated. Retain the current boundaries; do not create a production
refactor plan from this map alone. Plan 32 remains deferred, and algorithmic
time/space or performance/memory optimization remains out of scope.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 8/8 checklist items.
- [x] Record revision, working-tree state, scope, and inspection tools.
- [x] Map internal imports for the selected package areas and verify any
      apparent cycles or notable dependency paths.
- [x] Build the responsibility/state-owner matrix for the selected behaviors.
- [x] Trace callbacks, event subscriptions, dynamic registration, dispatch, and
      teardown paths that are not visible in imports.
- [x] Trace bounded change scenarios through source, state owners, and tests.
- [x] Record candidate boundaries, counter-evidence, invariants, and limits
      without treating counts as complexity scores.
- [x] Update the assessment and subsystem research with a keep, investigate,
      or separate-plan decision.
- [x] No separate implementation plan created; the map did not demonstrate a
      concrete, avoidable implementation-complexity cost.

**Done:** The map covers the selected responsibilities and meaningful dynamic
paths, conclusions cite concrete source and test evidence, and no refactor was
proposed without evidence of avoidable implementation complexity.
