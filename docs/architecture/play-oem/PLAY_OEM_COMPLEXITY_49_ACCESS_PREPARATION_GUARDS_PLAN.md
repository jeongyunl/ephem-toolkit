# play-oem — Access-Preparation Guards Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior Ground Station Access review:
[PLAY_OEM_COMPLEXITY_48_READOUT_STATUS_INITIALIZATION_PLAN.md](./PLAY_OEM_COMPLEXITY_48_READOUT_STATUS_INITIALIZATION_PLAN.md).

## Goal

Share the identical early-return bodies in `GroundStationAccessView._prepare_access`
for missing store context or unloaded OEM without changing query-cache reset or
range-specific preparation behavior.

## Evidence and hypothesis

`_prepare_access` is 22 lines with an AST decision score of 7. After clearing
`_store_queries`, it separately checks for a missing store context and an
unloaded OEM. Both branches clear `_access_results`, clear
`_preparation_error`, and return. The direct access-view tests do not currently
exercise `_prepare_access`'s guard behavior.

The loaded-context path is distinct: it clears the preparation error, may
create empty `StationAccess` results when a limited range has no prepared
bounds, or queries each station. In particular, do not treat an empty station
list as a new early-return condition.

The two equivalent guards were combined with
`self._store_context is None or not self._oem_loaded` can remove the duplicated
body without a helper. The decision score remains unchanged because one `if`
plus an `or` operand replaces two `if` nodes.

## Scope and invariants

- Inspect only `_prepare_access` and direct tests in
  `test_ground_station_access_view.py`.
- Preserve `_store_queries.clear()` before either guard.
- Preserve clearing access results and preparation errors for both missing
  context and unloaded OEM.
- Preserve the loaded-context path, including limited-range empty results and
  station query preparation.
- Preserve behavior for an empty station list; it is not one of the guards
  being combined.
- Do not change error handling, store ownership, interval computation, or
  other view responsibilities.

## Execution results

Added characterization for missing context, unloaded OEM, and a loaded context
with an unapplied limited range. The reset tests begin with stale cached queries,
results, and preparation errors. The two early-return branches have identical
outcomes; query caches are still cleared before the combined guard, and the
loaded limited-range case still creates one empty `StationAccess` result per
station.

`_prepare_access` decreased from 22 to 18 lines; its AST decision score remains
7. The focused characterization passed (3 tests), and the complete access-view
test file passed (17 tests). No helper or other behavior change was needed.

The guard consolidation is complete. Query lifecycle, empty-station handling,
and other view responsibilities remain out of scope.
