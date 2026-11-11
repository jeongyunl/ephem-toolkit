# play-oem — Incremental Loader Return Contract Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior async lifecycle evidence:
[PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md](./PLAY_OEM_COMPLEXITY_4_LOAD_LIFECYCLE_PLAN.md).

## Goal

Determine whether `IncrementalLoader.start` should continue returning the full
`IncrementalLoadSession`, or whether the app-facing contract can be narrower
without making direct session users more complicated.

The goal is to reduce caller coupling only if there is a simpler, coherent
contract. Do not change event ordering, cancellation, replacement, or thread
ownership as part of this investigation.

## Evidence and hypothesis

`IncrementalLoader` owns its active session and provides loader-level
`generation`, `drain`, and `cancel` operations. The controller stores the
return value of `start` to read `session.generation`, then uses the loader for
event draining and cancellation. This leaves the controller coupled to the
session object for a value the loader already exposes.

However, direct loader tests use returned sessions for `drain`, `cancel`,
`finished`, and generation checks; some lifecycle tests also inspect private
session state. `iter_load_events` accepts an `IncrementalLoadSession`
directly. The session therefore serves real lower-level and non-GUI use cases;
the controller's usage alone is not enough evidence to remove its handle.

The relevant implementation is in
[incremental_loader.py](../../../../../src/ephem_toolkit/play_oem/incremental_loader.py),
the app caller is in
[controller.py](../../../../../src/ephem_toolkit/play_oem/app/controller.py),
and current direct-session tests are in
[test_incremental_loader.py](../../../../../tests/ephem_toolkit/play_oem/test_incremental_loader.py).

## Scope and invariants

- Inspect the return value and callers of `IncrementalLoader.start`, the
  `session` property, loader-level `drain`/`cancel`, and
  `iter_load_events`.
- Inspect the controller's use of the return value separately from direct
  session consumers and test helpers.
- Preserve the generation-tagged event contract and stale-generation filtering.
- Preserve the distinction between load generation and store epoch; they are
  not interchangeable tokens.
- Preserve replacement cancellation, bounded event queues, nonblocking
  cancellation, terminal event behavior, and GUI-thread draining limits.
- Do not change parser behavior, `OemDataStore` lifecycle, worker scheduling,
  wx event-loop ownership, or the direct session iterator.
- Do not introduce a handle, protocol, callback layer, or async framework unless
  evidence shows it reduces caller obligations overall.

## Alternatives to compare

1. **Keep the session return.** The app can read `loader.generation` after
   starting instead of using the returned session, while direct callers retain
   the session handle. This reduces the controller's coupling but does not
   shrink `start`'s return type.
2. **Return a generation value.** The loader could retain session ownership and
   return the generation token. Determine how direct callers would access
   `finished`, direct draining, and session cancellation without simply
   exposing the session through another property.
3. **Introduce a narrower handle.** Consider only if the caller inventory
   demonstrates a repeated stable subset of session operations. Account for
   the cost of a new type and the fact that non-GUI callers may need direct
   session operations.
4. **Retain the current contract.** If the alternatives move complexity to
   tests or direct clients, document the session return as intentional.

## Investigation procedure

1. Record the current revision and worktree state. Read Plan 4's lifecycle
   transition findings; do not repeat its concurrency trace.
2. Search the repository for `IncrementalLoader.start`, `session`,
   `iter_load_events`, and loader-level `drain`/`cancel` use. Classify each
   caller as GUI controller, direct session consumer, or test/helper.
3. Record exactly which public and private session attributes each direct
   caller needs. Treat private test access as test coupling to evaluate, not as
   an automatic reason to expand the production API.
4. Trace the controller's generation assignment and compare using
   `loader.generation` with the current returned-session path. Verify that
   replacement and cancellation still identify the intended generation.
5. Compare the alternatives above using caller steps, exposed state, type
   clarity, and whether a second access path to the session remains.
6. Select a source change only if one alternative removes a real caller
   obligation without moving equal or greater complexity elsewhere. Otherwise
   keep the contract and record why.
7. If changing the contract, update the loader implementation, controller,
   protocol/type declarations, tests, and docs together. Do not change direct
   session semantics as an incidental consequence.
8. Run the focused incremental-loader and app lifecycle tests, including
   replacement, cancellation during parsing, stale-event filtering, and
   shutdown while loading.
9. Record the keep/change decision and test results in this plan and the
   assessment.

## Decision criteria

- Prefer the current session return if direct callers materially need session
  operations and a generation-only return would require a second session
  access path or a new handle with equivalent surface.
- Prefer a generation-only return only if all legitimate callers can use the
  loader facade and direct session use remains explicit and coherent.
- The controller may use the loader's generation property without changing the
  return contract if that is the only proven coupling.
- Any change must preserve separate generation and epoch validation and all
  cancellation/backpressure guarantees.
- Reject an abstraction whose public operations substantially mirror
  `IncrementalLoadSession` without reducing required caller knowledge.

## Expected output

- A caller matrix showing which clients need generation, event draining,
  cancellation, completion state, or direct session access.
- A documented keep/change decision and the chosen return contract.
- If changed, a minimal API patch with focused lifecycle and app tests.
- No change to load state transitions or asynchronous behavior.

## Execution results

Baseline revision: `10524597`. Direct loader tests use the returned session for
draining, cancellation, completion, and generation checks; the non-GUI
`iter_load_events` helper also accepts a session. The controller used the
returned session only to obtain its generation, then used `IncrementalLoader`
for draining and cancellation.

Kept `IncrementalLoader.start` returning `IncrementalLoadSession` so direct
session clients retain one usable handle. Changed the controller to read
`IncrementalLoader.generation` after `start`, removing its unnecessary
dependence on the session object without adding another handle or changing the
loader's public return contract. Generation and store epoch remain separate.

The focused five-module regression run passed all 157 tests, including
incremental-load replacement, cancellation, app lifecycle, and view/panel
coverage. No event, queue, cancellation, or session behavior changed.

The contract review is complete. A future return-type change requires new
evidence that a narrower contract benefits direct session clients too.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 8/8.
- [x] Record revision, worktree state, and relevant lifecycle findings.
- [x] Inventory all start/session/iterator/drain/cancel callers.
- [x] Separate controller needs from direct session and test needs.
- [x] Compare the return-contract alternatives and caller burden.
- [x] Keep the session return; have the controller read the loader generation.
- [x] Preserve source and protocol signatures; no new handle was justified.
- [x] Run loader and app lifecycle regression tests.
- [x] Update the assessment and this plan with the outcome.
