# play-oem — Controller Initialization and Shared State Investigation Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Panel and view lifecycle findings:
[PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_12_PANEL_VIEW_LIFECYCLE_PLAN.md).

## Goal

Investigate the next selected assessment candidate, **controller initialization
and shared state**. Trace how `PlayerApp.__init__` establishes state consumed
by its behavior mixins, how initialization order relates to callbacks and
external resources, and whether state ownership or initialization invariants
are genuinely duplicated or difficult to maintain.

The assessment's historical baseline identifies `PlayerApp.__init__` as a
large routine spanning loading, playback, configuration, and GUI setup. That
is a reason to map its contract, not evidence that the constructor should be
split or that a runtime defect exists. Make no production change unless the
investigation identifies a concrete, testable improvement.

## Scope and ranking

This is the remaining broad assessment candidate after the panel/view lifecycle
investigation. Keep this pass bounded to:

- initialization state and invariants owned by `PlayerApp`;
- the structural state expected by `PlayerAppState` and consumed by mixins;
- ordering of validation, external-object mutation, subscriptions, GUI
  construction, and callback registration;
- startup paths and tests needed to substantiate those contracts.

Do not repeat the panel replacement/resource audit. Follow panel/view behavior
only where it establishes when startup state is consumed. Do not redesign
incremental loading, saved-state parsing, workspace layout, or the mixin
architecture as independent work items.

## Planning baseline and initial evidence

The assessment's source baseline records `PlayerApp.__init__` at 368 lines
with a decision score of 34. These are historical hotspot indicators, not
current thresholds or measures of avoidable complexity.

The constructor currently performs several ordered groups of work:

1. Validates some constructor options, initializes the clock reference and
   playback/loading bounds, and applies playback bounds to the supplied clock.
2. Assigns data, display, interpolation, configuration, and metadata state;
   may update the supplied cursor's interpolation; and derives render-rate FPS.
3. Initializes incremental-loader/store state, station-selection contexts,
   recent-file and saved-range state, and backend selection.
4. Creates the view registry and expands the initial plot selection.
5. Reuses or creates the wx application, builds the frame, menu, status bar,
   workspace, and control window, then initializes timer, lifecycle, panel,
   and observer state.

The constructor also passes bound methods into GUI components and installs
subscriptions around domain and GUI objects. This makes initialization order
and partial-construction behavior worth checking, but does not by itself
establish that a callback fires too early or that a resource leaks.

`PlayerApp` combines `ViewFactoryMixin`, `PlaybackActionsMixin`,
`TimeRangeActionsMixin`, and `PanelManagementMixin`. The `PlayerAppState`
protocol declares the shared attributes and operations those mixins rely on.
The investigation must distinguish canonical state from derived or transient
fields and verify actual consumers rather than infer ownership from naming.

## State and initialization matrix to verify

| Area | Initial evidence | Questions to answer |
| --- | --- | --- |
| Constructor inputs and validation | Tick interval and backend are validated early; display time zone and render rate have separate checks | Which invalid inputs can mutate the supplied clock or cursor before rejection? Are those semantics intended and tested? |
| Playback and time-range state | Slider bounds, playback handles, pending bounds, plot range, and clock values are initialized in stages | Which values are canonical, derived, or pending? Which cross-field invariants must always hold? |
| Incremental loading and store state | Loader, current/pending/retired stores, notices, generations, and coverage flags are initialized together | Which fields are owned by the controller versus loader/store, and what combinations represent valid startup states? |
| Saved state and configuration | Recent files, initial file, saved ranges, stations, and dirty flags are initialized before GUI construction | Which values are copied versus shared or mutated? How do loaded and unloaded startup paths differ? |
| Mixins and shared protocol | Several mixins consume a structural `PlayerAppState` with a broad set of attributes | Are protocol members missing, stale, or duplicating ownership? Which attributes have a single authoritative writer? |
| GUI and callback setup | The constructor creates/reuses wx resources and passes bound methods to workspace/control components | Can any construction or binding invoke a callback before all fields it reads are initialized? What is cleaned up if later construction fails? |
| Startup and shutdown | Timer, panel registries, start/closed flags, and clock observer state are initialized near the end | When are callbacks and initial views activated relative to construction? Are startup and shutdown transitions covered without display access? |

## Investigation procedure

1. Inventory constructor assignments in execution order. Group them by
   ownership domain and mark values that are input copies, canonical state,
   derived state, transition state, or acquired resources.
2. Trace the relevant reads and writes in `PlayerAppState` and each behavior
   mixin. Record authoritative writers, mutation paths, and invariants spanning
   more than one field; verify call sites rather than relying on field names.
3. Trace validation and side effects involving caller-owned objects, including
   clock bounds and cursor interpolation. Determine whether failures can occur
   after mutation or resource acquisition and whether that behavior is
   intentional and covered.
4. Compare the loaded/unloaded OEM paths, saved-state and initial-file paths,
   render-rate defaults, backend selection, and existing-wx-app reuse. Record
   only behavior differences that affect initialization contracts.
5. Trace when bound callbacks, subscriptions, timers, and initial plot requests
   become active. Check whether any constructor or binding can invoke a
   callback before its required state is ready; distinguish a theoretical
   concern from observed execution or a reproducible test case.
6. Map existing app, control-window, CLI, saved-state, and incremental-load
   tests to the verified initialization paths. Add a focused test only for a
   concrete uncovered invariant or failure path.
7. Evaluate at most one narrow experiment if evidence shows repeated
   initialization policy, ambiguous ownership, or a testable ordering defect.
   Compare the resulting state contract and call sites; do not extract helpers
   solely to shorten `__init__` or wrap related fields in a new container
   without a demonstrated improvement.
8. Run the focused tests for any experiment and update the assessment with the
   state map, decision, test results, limitations, and next candidate. Update
   subsystem documentation only if verified ownership or transitions change.

## Required behavior and constraints

- Preserve the public `PlayerApp` constructor and CLI-to-app behavior unless a
  concrete incompatibility is demonstrated and explicitly addressed.
- Preserve initial values and ordering for playback bounds, interpolation,
  saved-state restoration, backend fallback, and initial view selection.
- Preserve wx-thread affinity and ensure callbacks cannot observe partially
  initialized state.
- Preserve subscription and timer ownership, including cleanup if construction
  fails after a resource has been acquired.
- Preserve the loaded and unloaded OEM startup paths and incremental loading's
  normal application behavior.
- Do not infer a defect from constructor length, a broad protocol, or
  initialization order alone.
- Do not change adjacent view, store, saved-state, or workspace behavior unless
  required to fix a verified initialization contract.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 8/8 checklist items.
- [x] Inventory constructor assignments by ownership and initialization phase.
- [x] Trace shared state consumers and authoritative writers across
      `PlayerAppState` and its behavior mixins.
- [x] Verify cross-field invariants and identify canonical versus derived or
      transient state.
- [x] Trace validation, external-object mutations, subscriptions, and GUI
      resource acquisition in execution order.
- [x] Verify loaded/unloaded startup, saved-state, backend, and existing-wx-app
      paths against current tests.
- [x] Check callback readiness and partial-construction cleanup; distinguish
      observed gaps from hypotheses.
- [x] Select at most one evidence-backed experiment, or record why no
      production change is justified; run focused tests if changed.
- [x] Update the assessment with findings, decision, validation, limitations,
      and the next candidate. Update subsystem documentation only if ownership
      or transitions change.

**Done when:** shared state ownership and initialization ordering are mapped
against real consumers and startup tests; any production change is supported
by a concrete invariant or failure case, or a no-change decision is recorded.

## Execution record — 2026-11-11

### State ownership and startup ordering

An AST inventory found 85 direct `self` assignments in `PlayerApp.__init__`,
covering 80 unique attributes. All 48 data attributes declared by
`PlayerAppState` are assigned directly by the constructor. The repeated writes
to recent-file and playback-handle state are staged normalization/restoration,
not independent owners. State falls into input/domain references, playback and
range state, incremental-load/store transitions, saved/configuration state,
station-selection contexts, and GUI/lifecycle resources. The mixins mutate
this shared application state through their structural protocol; no second
state owner or stale protocol member was identified.

`start()` runs after construction. It marks the app started, shows the frame,
opens loaded or pending plots, then starts the timer. Workspace and control
callbacks are passed as bound methods during construction; no direct callback
invocation was found in the constructor path. The headless tests use wx fakes,
so native event dispatch during real desktop construction remains unverified.

### Bounded change

The `render_rate_fps` check previously occurred after
`clock.set_playback_bounds()` and `cursor.set_interpolation()`. A regression
test reproduced a rejected render rate resetting a caller-owned clock's
narrower playback range, notifying its observers, and invoking cursor setup.
The validation now occurs with the other early option checks, before those
external mutations.

The clock observer was also registered before the final
`workspace.set_oem_loaded()` and status-message calls. Failure injection at
workspace setup demonstrated that the external clock retained a bound method
from the partially constructed `PlayerApp`. Registration now occurs after
those final setup calls, and the failure test verifies that no observer is
left registered.

No broad constructor split or new state container was justified. The change
preserves valid-path initialization values and ordering; only rejected
construction avoids side effects, and the observer is acquired after remaining
fallible workspace setup. Arbitrary native wx resource cleanup if frame,
workspace, or control-window construction itself fails remains unverified;
the failure test covers observer retention, not desktop teardown.

### Validation and next selection

The app, CLI, and control-window regression suites passed: **119 passed**.
The test environment uses fakes for wx construction; no native desktop
integration was exercised. The Pylance syntax-check request timed out, while
the Python test run imported and exercised the edited controller successfully.
No dataflow or subsystem ownership changed.

This completes the currently selected assessment candidates. No next
implementation candidate is preselected; re-rank the remaining unprioritized
leads before defining another investigation plan.
