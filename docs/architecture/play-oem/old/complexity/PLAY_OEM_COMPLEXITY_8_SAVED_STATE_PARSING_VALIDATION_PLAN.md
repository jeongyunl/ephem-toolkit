# play-oem — Saved-State Parsing and Validation Complexity Reduction Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Baseline and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior investigation:
[PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md](./PLAY_OEM_COMPLEXITY_7_VIEW_REFRESH_COORDINATION_PLAN.md).
Current dataflow: [PLAY_OEM_DATAFLOW.md](./PLAY_OEM_DATAFLOW.md).

## Goal

Execute authoritative assessment priority 5, **Review saved-state parsing and
validation**. Trace `load_saved_state` from the state file through root and
section validation, compatibility handling, warning/fallback behavior, and
startup consumers. Determine whether grouping parsing by independent state
sections makes the validation contract clearer and easier to test.

Preserve accepted legacy state, current schema rejection rules, diagnostic
warnings, and the guarantee that missing or invalid saved state does not prevent
application startup. A decision to keep the current parser is acceptable. Do
not rewrite the serializer, saved-state model, user-config parser, or startup
ownership as a proxy for reducing parser complexity.

## Current implementation and initial evidence

The assessment's static baseline measured `saved_state.py` at 551 physical
lines and `load_saved_state` at 268 lines with decision score 69. These are
inspection signals, not evidence that the parser is defective or that splitting
it will improve comprehension. At planning time, the worktree is clean at
commit `0a97dab09fd591503810d7e504b4c677e2fb7152`; the assessment's original
line/score measurements were made at `cf93496` and have not been recomputed at
this planning commit.

`load_saved_state` reads TOML, returns defaults without a warning when the file
is missing, and warns and returns a fresh `SavedAppState` for I/O, decoding,
TOML syntax, schema, and semantic validation errors. The parser validates a
root version from 1 through `STATE_VERSION` (currently 8), rejects unknown
root/section keys, and constructs the result only after all sections validate.
There is no explicit per-version branch in the current loader; compatibility
also comes from section defaults and legacy fields.

The parser already delegates some shared validation: `_is_int`,
`_validated_playback_range`, `_validated_plot_range`,
`parse_plot_selection`, `validate_plot_range`, and
`parse_ground_station_records`. Reuse these policies rather than duplicating
them or changing domain validation while extracting section structure.

## Initial state-section map

| Section | Current responsibility | Compatibility and validation points |
| --- | --- | --- |
| Root | Validate TOML table, allowed keys, and `state_version` in 1..8 | Unknown keys or invalid/missing version reject the whole document. |
| `window` | Width, height, maximized flag, optional position | Defaults are used for omitted fields; dimensions and coordinates are bounded; booleans are not accepted as integers. |
| `recent_files` | Absolute paths, uniqueness/normalization, 15-item limit, per-path settings | Settings for paths outside the retained recent-path set are skipped; playback and plot ranges use dedicated validators. |
| `workspace` | Parse `open_plots` through the plot-selection parser | Missing selection defaults to empty; malformed types or selection reject the whole document. |
| `ground_track` | Elevation threshold, projection/background, longitude, and optional extents | Defaults represent current preferences; keep the existing boundary and conversion behavior unless a separate verified defect is in scope. |
| `ground_stations` | Read station records retained in legacy state files | Uses the shared station-record parser; startup can migrate these records to user config; the state serializer does not write them. |
| `playback` | Accept the legacy `fps` key | The value is intentionally ignored because render rate belongs to user config; unknown playback keys still reject the file. |

This is an initial map from source, not a complete version-by-version contract.
Verify which state versions introduced or retired each field from repository
history, tests, and caller behavior before proposing a migration change.

## Startup and compatibility interactions

`__main__` loads user config and saved state separately. Configured user
ground stations take precedence; if config has no station setting and legacy
state contains stations, startup writes them to user config and clears the
in-memory legacy field. Treat this as a compatibility boundary when tracing
state parsing, but do not change config ownership in this work item.

The parser's current failure policy is document-wide: a single invalid field
returns a fresh default state rather than a partially populated state. Any
section-level helper experiment must retain that atomic outcome unless the
existing contract and callers provide explicit evidence that partial recovery
is intended. A helper boundary is organizational, not permission to silently
skip invalid sections, accept unknown keys, or emit multiple warnings.

`serialize_saved_state` writes the current version and supported state fields;
`save_saved_state` writes atomically. They are comparison surfaces for
round-trip and migration tests, not automatic refactoring targets. Preserve
serialization determinism, legacy-field omission, and atomic replacement.

## Existing tests and evidence to collect

`tests/ephem_toolkit/play_oem/test_saved_state.py` covers current round trips,
invalid window/ground-track/recent-file/station inputs, versions 1, 6, and 7,
legacy FPS handling, legacy station reads, and station validation. Map every
loader branch and each supported field to tests before editing. In particular,
verify actual coverage for missing files, malformed TOML/encoding, invalid or
unsupported versions, unknown keys at root and nested sections, all section
defaults, path normalization/retention, and current-version round trips;
add tests only for meaningful uncovered contract behavior.

Record a before baseline with the exact focused test command and result. Run
adjacent startup/config tests where the trace shows the legacy station handoff
or precedence is implicated. Keep any change scoped to saved-state parsing and
its directly related tests unless an observed integration dependency requires
more.

## Candidate experiment

The bounded candidate is to organize parsing around independent sections while
keeping one document-level validation boundary. First compare the current
function's section-by-section flow and failure exits. If repetition or
interleaving genuinely hinders understanding, prototype the smallest extraction
that returns validated section values (or raises a clearly scoped validation
error) and assembles `SavedAppState` only after every section succeeds.

Compare before/after:

- The single warning and default-state result for every invalid document.
- Version acceptance and legacy field behavior.
- Existing error wording where tests or callers rely on it.
- The number of branches and validation rules callers must understand.
- Test coverage by section and compatibility behavior.
- The total code and navigation burden, not just the length of
  `load_saved_state`.

Do not introduce a generic schema framework, coercive parser, per-section
fallback, or broader validation policy without demonstrated need. Keep the
experiment only if the resulting contract is clearer without increasing
indirection or weakening compatibility.

## Required behavior and constraints

- Missing state remains a silent default; malformed, unreadable, unsupported,
  or semantically invalid state remains a warned default.
- Validate the root version and unknown-key policy before constructing state.
- Preserve all currently accepted fields, defaults, limits, normalization,
  ignored legacy `playback.fps`, and legacy ground-station handoff.
- Preserve all-or-nothing loading; do not expose partially validated state.
- Reuse existing domain validators and retain their distinct meanings.
- Preserve serialized schema/version, deterministic output, and atomic saves.
- Keep user-config precedence and saved-state responsibilities separate.
- Avoid unrelated parser, model, UI, and configuration refactors.

## Implementation checklist

- **Status:** Complete.
- **Progress:** 8/8 checklist items.
- [x] Trace `load_saved_state` call sites and startup consumers, including the
      legacy station migration and user-config precedence. Record actual
      state ownership and which errors are intentionally swallowed or warned.
- [x] Build a root/section schema and compatibility matrix for versions 1
      through 8 from source, tests, history, and callers. Distinguish explicit
      version handling from default-based compatibility.
- [x] Map every validation branch to its accepted and rejected input shape,
      error message, warning behavior, and fallback result. Identify only
      concrete gaps that affect contract confidence.
- [x] Record the before baseline: current commit/worktree, focused and relevant
      integration tests, branch/section coverage, and a behavior map. Keep
      source-line counts as context only.
- [x] Evaluate one bounded section-parsing experiment only if the trace shows
      that section ownership or failure handling is hard to follow. Preserve
      atomic document-level fallback and compare the total protocol.
- [x] Add or adjust deterministic tests for demonstrated gaps or behavior
      touched by the experiment, including version/legacy and error-policy
      guards where relevant.
- [x] Run saved-state tests and the smallest related config/startup test
      selection. Compare results and inspect any failure against the baseline.
- [x] Update the assessment with the evidence, decision, test result, remaining
      uncertainty, and next priority. Update other documentation only if the
      persisted format, ownership, or runtime behavior changes.

## Execution record — 2026-11-10

### Verified behavior and callers

The loader validates the document in a fixed order: root/version, window,
recent files, workspace, Ground Track, legacy ground stations, then legacy
playback. The first invalid condition emits one `RuntimeWarning` and returns a
fresh default `SavedAppState`; a missing file returns defaults silently.
Malformed TOML and read/decode errors use the same warned-default path.
Unknown keys are rejected at the root and within each section. `playback.fps`
is the sole explicitly accepted ignored legacy value.

`state_version` is checked as an integer in the inclusive range 1 through 8;
there are no explicit per-version branches in the loader. Compatibility is
provided by defaults for omitted fields and the retained legacy fields.
Existing tests exercise versions 1 through 7 through their fixtures and
version 8 through current serialization round trips. The CLI loads user config
and saved state independently; configured user stations win, while stations
read from old state are migrated into user config when config has no station
setting. `test_play_oem_cli.py` covers that handoff.

The parser already follows contiguous, named section blocks, and its genuinely
shared policies are delegated to typed/domain validators for plot selection,
plot ranges, playback ranges, and station records. Splitting the blocks into
more functions would keep the same validation branches and first-error order,
while adding helper navigation and an exception-to-warning translation
boundary. No specific section was interleaved with another or shown to have a
distinct recovery policy, so the proposed extraction did not demonstrate a
net reduction in protocol complexity. No production code change was made.

### Baseline, tests, and decision

Planning/execution baseline: commit
`0a97dab09fd591503810d7e504b4c677e2fb7152`. At the start of this slice,
`saved_state.py` and `test_saved_state.py` had no local modifications. The
baseline `python3 -m pytest tests/ephem_toolkit/play_oem/test_saved_state.py`
passed 18 tests. A combined saved-state/CLI coverage run passed 43 tests and
reported 74% statement coverage for `saved_state.py` (306 statements, 80
missed); coverage helped identify missing fallback-policy checks, not a
production defect or a coverage target.

Added tests for silent defaults when the file is absent; malformed TOML;
unsupported versions; unknown root and nested keys; exactly one warning and a
default state for invalid schemas; and document-wide atomic fallback when a
later invalid Ground Track field follows a valid non-default window value.
The final command was:

```sh
python3 -m pytest --cov=ephem_toolkit.play_oem.saved_state --cov-report=term-missing \
  tests/ephem_toolkit/play_oem/test_saved_state.py \
  tests/ephem_toolkit/play_oem/test_play_oem_cli.py
```

Result: 48 passed, 14 existing Matplotlib/Pyparsing deprecation warnings;
statement coverage for `saved_state.py` rose to 76% (306 statements, 72
missed). This targeted increase covers the identified default/error behaviors;
uncovered branches remain and were not claimed as exhaustively tested.

**Decision:** retain the current section-by-section loader. Its validation
ownership is already clear, its strict document-wide fallback is consistent,
and extracting the blocks would add indirection without removing policy or
changing testability enough to justify the extra boundary. Keep the new
contract tests. The saved-state format, serializer, and startup ownership did
not change, so no dataflow or format documentation update is needed. The next
authoritative work item is priority 6, domain and performance hotspots.

**Done when:** section and version behavior are verified; fallback and warning
semantics are tested; the result is either a smaller, clearer parsing contract
with preserved compatibility or an evidence-based decision to retain the
current implementation; and the assessment reflects the outcome.
