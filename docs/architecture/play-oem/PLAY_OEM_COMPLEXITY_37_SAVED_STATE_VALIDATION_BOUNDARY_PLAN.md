# play-oem — Saved-State Validation Boundary Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior investigation:
[PLAY_OEM_COMPLEXITY_8_SAVED_STATE_PARSING_VALIDATION_PLAN.md](./PLAY_OEM_COMPLEXITY_8_SAVED_STATE_PARSING_VALIDATION_PLAN.md).

## Goal

Reassess one narrow opportunity in `load_saved_state`: whether repeated
section-table and allowed-key checks can share a small validation boundary
without obscuring error order or adding a generic parsing framework.

This is not a request to split the loader into per-section functions. Plan 8
already evaluated that proposal and retained the section-by-section loader
because extraction added navigation and exception translation without removing
validation policy.

## Baseline and hypothesis

At source revision `c422b94c7ec3b938ff104e16fe5e35d8672e863d`,
`load_saved_state` is 268 lines with a decision score of 69 under the
assessment's AST indicator. The function repeats structural checks for section
tables and unknown keys, while delegating domain-specific range, plot, and
station validation to existing helpers.

**Hypothesis:** a narrowly scoped helper for required table shape and allowed
keys may remove repeated structural rules while preserving the loader's
document-wide fallback behavior. Reject the hypothesis if the helper merely
hides the same decisions behind parameters or changes which validation error
is reported first.

## Scope and constraints

- Inspect only `load_saved_state` and directly related structural validation.
- Preserve section order, exact accepted keys, error text, one-warning/default
  fallback, and atomic loading.
- Preserve version compatibility, defaults, ignored legacy `playback.fps`,
  station migration, and existing domain validators.
- Do not change serialized state, saving, config precedence, or UI behavior.
- Do not extract each section, add a schema framework, or refactor unrelated
  models.

## Procedure

1. Inventory each root/section table check and unknown-key check, including
   qualified error labels and the first-error ordering.
2. Compare the repeated structural rule with the sections' distinct validation
   and compatibility behavior.
3. Sketch at most one small helper and compare total branches, calls, arguments,
   and error translation with the current implementation.
4. Confirm existing tests cover unknown root/nested keys, malformed input,
   single-warning fallback, missing-file defaults, versions, and legacy
   station/FPS behavior. Add a characterization test only for a concrete gap
   affected by the proposed boundary.
5. Implement only if the helper makes the validation contract easier to follow
   without changing the prior Plan 8 decision about section ownership.
6. Run `test_saved_state.py` and the relevant CLI/config tests; retain no code
   change if the evidence does not show a net simplification.
7. Record the decision and test result in the assessment.

## Done when

The structural validation checks are either simpler under a small, tested
shared boundary or explicitly retained with evidence that their differences
and error ordering outweigh the duplication. No change is justified by the
AST score alone.

**Status:** Complete; no code change.

## Outcome

The shared-validation hypothesis was rejected. The loader has distinct
structural cases: the root table; six strict sections (`window`,
`recent_files`, `workspace`, `ground_track`, `ground_stations`, and `playback`);
the dynamic `recent_files.settings` table; and per-file settings tables that
are validated only for paths retained in the recent-file list. The latter
checks follow path validation and filtering, while each section's table and
allowed-key checks are interleaved with its domain validation.

A helper returning only the first unknown key would move that branch but leave
the section-specific error construction and fallback at each call site. A
helper that also validates table shape would need the table label, key prefix,
and allowed-key set as inputs, then still require caller-side error translation
to preserve the existing warning and first-error order. Neither sketch removes
a validation rule or caller obligation; it adds an abstraction and plumbing.
The existing section-by-section flow remains easier to trace, consistent with
Plan 8's no-extraction decision.

`test_saved_state.py` covers root and nested unknown keys, malformed TOML,
single-warning/default fallback, missing-file defaults, version compatibility,
legacy FPS handling, and station migration. No characterization test was
added because the rejected helper would not change behavior or address a
specific coverage gap. Validation passed:

```sh
python3 -m pytest \
  tests/ephem_toolkit/play_oem/test_saved_state.py \
  tests/ephem_toolkit/play_oem/test_play_oem_cli.py \
  tests/ephem_toolkit/play_oem/test_config.py
```

Result: 71 passed. The 14 warnings are third-party Matplotlib/Pyparsing
deprecation warnings. The CLI and config suites were included to check the
existing startup and station-migration surfaces; no saved-state/config
precedence or UI behavior was changed.
