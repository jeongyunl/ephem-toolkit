# play-oem — Load Lifecycle Complexity Reduction Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Baseline and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context: [PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Current dataflow: [PLAY_OEM_DATAFLOW.md](./PLAY_OEM_DATAFLOW.md).

## Goal

Make incremental-load replacement easier to understand, change, and verify by
establishing its existing lifecycle contract, identifying avoidable distributed
state and caller obligations, and testing one bounded improvement if the
evidence supports it. Preserve observable behavior, concurrency guarantees,
and performance. The improvement may be a clarified contract rather than a
code refactor if no candidate demonstrably reduces overall complexity.

Apply the strategy in three stages: establish the as-built behavioral contract,
identify costly coordination, then evaluate a bounded experiment. Use both a
vertical behavior trace and a horizontal responsibility map. Assess local
reasoning, overall interactions, and code volume separately; a smaller file or
lower count alone is not evidence of improvement.

## Current implementation and initial evidence

The application uses incremental loading as its normal path. The controller
creates a pending `OemDataStore` and starts a generation-scoped loader session.
The loader allocates a store epoch, cancels the previous session, and publishes
metadata, append, completion, and failure events. The controller polls events
on the wx thread and installs a new store when it has a usable committed prefix.
Store epochs protect store operations; loader generations identify sessions.

The following is an initial orientation from static inspection, not the completed
transition contract. Verify ownership, cleanup, and corner cases against the
implementation and tests during the first checklist items.

| Trigger | Observed behavior | Points to verify |
| --- | --- | --- |
| Start replacement | A new pending store and loader session are created; the existing store stays installed initially. The prior session is cancelled. | Ownership and close timing for pending, active, and retired stores, including a replacement during a partial load. |
| Metadata | A generation-tagged segment event can contribute declared slider bounds before or after the first append. | Multiple segments, invalid declarations, and cancellation while metadata is queued. |
| First usable append | The controller checks notice epoch, revision, and sample count against a snapshot and installs the new store and playback state. | Exact installation order, old-store retirement, views, ranges, and failures during installation. |
| Later append | The controller validates and installs a newer snapshot; playback coverage and views are refreshed. | In-flight or coalesced refreshes, range dragging, and stale notices. |
| Completion | Final metadata is applied when a prefix exists; the controller clears loading state and triggers the final refresh. An empty OEM is handled separately. | Metadata validation, pending-store cleanup, and completion after an earlier installation error. |
| Failure | Before first append, the pending store is closed; after first append, a valid installed prefix can remain, and playback is paused. | Status and resources for each failure point, including replacement of a partial load. |
| Cancel or close | Loader cancellation invalidates the generation and requests cancellation of its session; frame close stops the timer and closes stores and view resources. | Late events, blocked publishers, pending redraws, and ordering during shutdown. |

Existing named tests include `test_incremental_replacement_keeps_old_oem_until_first_batch`,
`test_failed_incremental_replacement_leaves_current_oem_installed`, and
`test_controller_ignores_stale_incremental_events` in
[`test_play_oem_app.py`](../../../tests/ephem_toolkit/play_oem/test_play_oem_app.py),
plus cancellation, backpressure, stale append, replacement, and valid-prefix
cases in [`test_incremental_loader.py`](../../../tests/ephem_toolkit/play_oem/test_incremental_loader.py).
These references are starting evidence, not a claim that all transitions are
covered or that tests were run for this plan.

## Relevant assessment findings

The assessment ranks load lifecycle and event handling first because of its
cross-component impact and the consequences of lifecycle mistakes. This is a
preliminary judgment; change frequency and defect rates were not measured.
Its source baseline was commit `cf93496`, with no source modifications, on
2026-11-10. These measurements may be stale when the plan is executed.

| Assessed area | Baseline evidence | Implication for this plan |
| --- | --- | --- |
| Load event handling | Five event kinds; `PlayerApp._poll_incremental_load` spans 126 lines with a decision score of 32. | Map generation checks, event-specific transitions, snapshot validation, and refresh obligations; five event kinds are not five independent lifecycle states. |
| Snapshot installation | `PlayerApp._install_store_snapshot` spans 174 lines with a decision score of 32. | Trace first versus later append, store ownership transfer, playback state, and failure outcomes. |
| Controller initialization | `PlayerApp.__init__` spans 368 lines with a decision score of 34; `controller.py` contains 1,920 physical lines. | Inventory lifecycle state initialized alongside playback, configuration, and GUI state; do not infer that moving initialization reduces coupling. |
| Store boundary | `oem_data_store.py` contains 3,545 physical lines and combines raw storage with derived queries, scheduling, and eviction. | Account for epochs and store lifetime while retaining one raw-data owner; a full cache redesign is outside this plan. |

The assessment's decision score is a custom AST-based hotspot indicator, not
standard cyclomatic complexity or a count of independent execution paths. It
includes nested definitions in enclosing functions and omits some decision
forms; the assessment gives its exact method and reproduction command. Line
counts include comments and blank lines. Neither measure establishes avoidable
complexity, and neither is a reduction target by itself.

The assessment also identifies **caller-side protocol complexity** in two
relevant places. `_poll_incremental_load` checks generation and event kind,
validates and installs snapshots, updates state, and schedules refreshes. This
is one complex consumer, not evidence that multiple consumers duplicate it.
[`_StoreRowSink`](../../../src/ephem_toolkit/play_oem/streaming_oem.py) reserves
rows, tracks and commits batches, publishes notices, and discards an active
reservation during cleanup. The inspected production path already uses this
dedicated sink; repeated independent callers have not been established. Map
the obligations and failure paths before proposing a shared helper.

Refresh routing also crosses `_drain_store_notices`, `_views_for_tier_notice`,
`_refresh_store_views`, `_refresh_incremental_views`, range actions, and views.
Examine it where it affects this lifecycle, including targeted updates,
throttling, and dragging; a general refresh-policy redesign is a separate
work item unless the trace establishes a necessary bounded change.

The assessment did not measure runtime, memory, call-graph depth, dependency
cycles, change frequency, defect history, or external API use. It did not
quantify duplicated protocol steps or prove that an abstraction would help.
Its tests and GUI scenarios were not run. Establish the relevant gaps and a
current baseline during execution rather than presenting these observations as
validated results.

## Interactions with other subsystems

The subsystem research identifies the following boundaries that must be
included when they intersect a load transition. Its findings are based on
static inspection at `cf93496`; they are starting points to verify, not a
completed audit or evidence of a defect.

- **Derived work and view lifetime:** range queries can report partial coverage
  while computations are pending. Work may finish after a store epoch, range,
  policy, or subscription changes, while views can retain pinned data.
  `ChunkMemo` distinguishes absent, computing, tentative, and complete entries
  and shares in-flight computation. Trace how replacement, append, and close
  affect work publication and view references; preserve each tier's actual
  validity and eviction rules. Do not assume every tier depends on the
  interpolation policy. A complete per-tier cache audit is a separate effort.
- **Playback and ranges:** coverage, playback bounds, and plot rules are
  distinct. Appends can extend coverage without moving the cursor or resuming
  playback, while explicit or saved bounds remain meaningful. A plot rule can
  follow bounds, use an offset from playback time, or be fixed; an empty
  resolved range is different from partial or unloaded data. Trace a fixed/follow
  and a moving-offset case through append, seek, and range dragging where they
  affect the load lifecycle. Preserve reverse and loop behavior.
- **Point queries and interpolation:** `OemDataStore.state_at` checks snapshot
  epoch and interpolation-policy revision and distinguishes exact samples,
  interpolation, gaps, and unavailable or out-of-range states. Partial loading
  can change available support near a boundary. Verify that replacing or
  refreshing a store does not reuse an invalid snapshot or bridge a segment gap;
  do not remove a cursor compatibility path without a separate caller audit.
- **Panel and native resources:** replacing data and closing the application
  can overlap view updates and cleanup. Trace ownership of panel/view resources
  and subscriptions as far as the lifecycle requires, including rollback or
  shutdown while work is pending. A general panel-construction redesign is a
  separate work item.

Relevant starting tests include `test_chunk_memo.py` for in-flight work and
invalidation; `test_oem_data_store.py` for partial coverage, policy-dependent
prefetch, and pinned views; `test_play_oem_clock.py` and `test_time_range.py`
for playback and range behavior; and `test_stateless_interpolation.py` for
samples, segment edges, and gaps. Map specific cases to transitions before
claiming coverage, and run only the focused checks relevant to the proposed
change plus any justified broader checks.

## Required behavior and constraints

- Keep the current OEM visible until a replacement has a usable committed
  prefix. Preserve current failure behavior before and after first append,
  including a valid prefix when later parsing fails.
- Reject obsolete generation events and prevent stale epoch operations from
  publishing into a replacement. Do not equate generation with store epoch.
- Keep parsing off the wx thread and apply GUI changes on the wx thread. Do not
  introduce blocking cancellation or deadlocks when the event queue is full.
- Preserve snapshot and notice validation, progressive coverage, range and
  timeline behavior, saved settings, and coalesced view refresh. Close pending,
  active, retired, and view resources according to their actual ownership.
- Preserve derived-work validity and pinned-view lifetimes across replacement;
  preserve distinct coverage, playback, and plot ranges and the point-query
  epoch, policy, and segment-gap contracts.
- Preserve single-store ownership for each generation, zero-copy ingestion,
  numerical results, memory limits, and responsiveness. Do not introduce a
  separate non-incremental mode or require a file split as the outcome.

## Implementation checklist

Work in dependency order. Record actual findings rather than treating the
initial table as a complete specification. Update status and progress as work
and checks are completed; revise the plan if evidence changes its approach.
Keep the assessment as the authoritative baseline and priority list, and put
detailed lifecycle evidence in this plan or a linked investigation record.

- **Status:** Not started.
- **Progress:** 0/8 checklist items.
- [ ] Trace the startup, open/recent-file, replacement, and shutdown entry
      points through loader, stream, store, controller, and view refresh. Record
      threads, event queue and generation ownership, and active, pending, and
      retired store ownership, including close and cancellation paths. Compare
      each trace with the existing dataflow and record discrepancies separately
      from proposed changes.
- [ ] Produce an as-built transition table for start, metadata, first and later
      append, completion, empty input, failure before and after first append,
      replacement at each stage, cancellation, stale events, and close. For
      each row record preconditions, event/generation and epoch, state changes,
      visible data, resource ownership, and failure or cancellation outcomes.
      Include relevant pending derived work, view references, range state, and
      snapshot/policy validity when they affect each transition.
- [ ] Build a responsibility matrix for the loader, stream, store, controller,
      view context, and affected views. Mark who owns, coordinates, and consumes
      each lifecycle decision or state. Inventory invariants and caller
      obligations, including first-append, completion, failure, pending refresh,
      drag state, and notice/snapshot checks. Identify invalid or ambiguous
      combinations, useful existing separation, and repeated policy; distinguish
      inherent asynchronous work from avoidable distributed coordination.
- [ ] Map transition cases to existing loader, stream, store, controller, and
      GUI tests. Run relevant focused tests in the available environment; add
      meaningful missing coverage for the contract and record skipped GUI cases
      or environment limitations. Verify failure before and after first append,
      late events, cancellation under backpressure, and shutdown while loading.
      Include affected cache, range, and point-query tests where the trace or
      proposed change crosses those subsystem boundaries.
- [ ] Record a before baseline at a specific commit and working-tree state:
      representative traces and responsibility matrix, caller obligations,
      affected code and tests, and appropriate responsiveness/memory measures.
      Count components, thread handoffs, transitions, and relevant code volume as
      review aids, not targets. State commands, tool versions, scope, exclusions,
      inputs, and environment; reuse the assessment baseline where applicable.
      Compare performance only with representative inputs and the same conditions.
- [ ] Rank the observed issues by change frequency where evidence exists,
      difficulty of understanding and testing, and consequence of mistakes;
      record uncertainty rather than inventing a score. Select and document one
      bounded hypothesis with expected benefits, affected interfaces,
      invariants, alternatives, and explicit rejection criteria.
      Candidate: a cohesive lifecycle state or event-handling contract. If no
      change is justified, document that conclusion and skip code changes rather
      than introducing an abstraction solely to satisfy the plan.
- [ ] Evaluate the hypothesis with a sketch or small prototype; production
      implementation is a separate decision. If justified, implement the
      smallest change and run relevant focused tests and appropriate broader
      checks. Compare the same before/after trace, responsibility matrix, caller
      obligations, tests, local reasoning, overall interactions, code volume,
      and relevant performance. Account for added indirection and concepts;
      retain a change only if it improves overall reasoning and preserves the
      contract. Record any unverified GUI or platform behavior.
- [ ] Update the assessment with evidence, outcomes, and revised priorities;
      update dataflow or software design if behavior or architecture changes.
      Record the final decision, validation results, known limitations, and a
      recommendation for the next subsystem.

**Done when:** the transition table and ownership/invariant map are checked
against code and tests; gaps and validation limits are recorded; a bounded
candidate has been evaluated against the baseline or rejected with evidence;
and any accepted implementation preserves the required behavior and passes the
applicable checks. The result must explain the effect on local and overall
complexity and code volume, including any new indirection, not merely whether
code moved or a file became shorter. If no candidate is justified, document the
evidence and remaining uncertainty without claiming a reduction was achieved.

**Depends on:** the existing complexity strategy and assessment. This plan does
not supersede the main release-readiness plan.
