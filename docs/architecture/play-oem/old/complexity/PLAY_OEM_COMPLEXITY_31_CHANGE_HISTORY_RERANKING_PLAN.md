# play-oem — Change-History Evidence and Candidate Re-ranking Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Current baseline and candidate inventory:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Current source baseline:
[`oem_data_store.py`](../../../src/ephem_toolkit/play_oem/oem_data_store.py).

## Goal

Use repository change history to determine whether the current static hotspots
also correspond to repeated maintenance or cross-component coordination. Use
that evidence to re-rank candidates, selecting at most one follow-up
investigation only if repeated, scenario-related changes expose a concrete
complexity cost.

This is a bounded evidence-gathering step, not a refactor, bug audit, or claim
that frequent changes indicate poor design.

## Why this step

The current assessment refresh identifies hotspots by size and a custom AST
decision score, but explicitly leaves change frequency and files changed
together unmeasured. Plan 22 and the closeout through Plan 30 found no further
candidate that met the complexity and validation threshold from static code
evidence alone. The strategy names change history as a complementary signal,
while warning that migrations and incomplete usage can distort it.

The current review series itself contains many same-day documentation and
implementation commits, so it must not dominate the maintenance-frequency
sample. The sample below ends before that series.

## Baseline and scope

- Start revision: `34a405bcecef47d7ba94110609f47658491db589`.
- History window: 2025-11-11 through 2026-11-10, inclusive by commit date.
- Source scope: tracked Python files under `src/ephem_toolkit/play_oem`.
- Tests may be included in a separate implementation/test co-change view, but
  must not be mixed into source-file frequency counts.
- Exclude merge commits, generated/vendor files, and documentation-only
  changes from source frequency counts. Retain the excluded commit totals and
  classify large migration or mechanical-change commits separately.
- Prioritize the currently measured hotspots and their directly coupled
  modules, including `oem_data_store.py`, `app/controller.py`,
  `app/panel_management.py`, `saved_state.py`, `station_access.py`,
  `incremental_loader.py`, and relevant store-backed views.

## Procedure

1. Reproduce the sample with repository-local Git commands and record the
   exact date predicates, revision, and exclusions. Count non-merge commits
   touching each in-scope source file, grouped by month.
2. Count source-file pairs that change in the same commit. Report raw counts
   alongside the number of eligible commits so a few large commits are not
   mistaken for repeated coordination.
3. Inspect the commit messages and representative diffs for the most frequent
   files and co-change pairs. Classify them as independent feature work,
   coordinated behavior, migration/mechanical work, generated changes, or
   unclear. Do not infer the reason from filenames alone.
4. Repeat the ranking after excluding identified bulk migrations and
   mechanical commits. Note whether the top files or pairs materially change.
5. For any promising pair, trace one or more representative changes to the
   affected functions and responsibilities. File-level co-change alone does
   not prove coupling or duplicated policy.
6. Re-rank the assessment. Select one follow-up only if the historical signal
   supports a concrete comprehension/coordination cost, a bounded reduction
   hypothesis, and available validation. Otherwise record that history did
   not justify reopening the implementation sequence.

## Decision criteria

- Repeated co-change must occur across independent, non-mechanical commits,
  not just one migration or a single large feature.
- The affected source changes must be related by a recognizable behavior or
  responsibility; correlated file paths alone are insufficient.
- A selected candidate must name the rules, callers, or ownership interactions
  it would reduce and how that reduction could be validated.
- If the signal is weak or explained by legitimate feature coordination, do
  not produce another implementation plan.
- Make no production-code changes during this analysis.

## Expected output

- Reproducible commands, revision, time window, and exclusions.
- Source-file change-frequency and co-change summaries, including eligible
  commit counts.
- A short classification of dominant change clusters and any bulk activity.
- An updated candidate ranking with either one evidence-backed next
  investigation or an explicit no-candidate decision.
- Documented limitations: Git history does not show unreported work, external
  consumers, defect rates, or developer comprehension directly.

## Implementation checklist

- **Status:** Complete — available history does not justify a new code candidate.
- **Progress:** 6/6 checklist items.
- [x] Reproduce the fixed history sample and record excluded commit classes.
- [x] Measure monthly source-file change counts and same-commit pairs.
- [x] Inspect and classify the dominant files and co-change clusters.
- [x] Check whether the ranking changes after excluding bulk changes.
- [x] Re-rank candidates using the strategy's complexity criteria.
- [x] Update the assessment with a selected follow-up or a no-candidate result.

**Done when:** Change-history evidence either supports one bounded
complexity-reduction investigation or provides a documented reason to keep the
implementation sequence paused.

## Execution record — 2026-11-11

The sample was queried from revision
`34a405bcecef47d7ba94110609f47658491db589` with:

```sh
git log --no-merges \
  --since='2025-11-11 00:00:00' \
  --until='2026-11-10 23:59:59' \
  --format='%H%x09%cs%x09%s' --name-only HEAD -- \
  src/ephem_toolkit/play_oem tests/ephem_toolkit/play_oem
```

Parsing unique `.py` paths per commit produced 173 non-merge commits touching
the scoped source or tests: 165 touched package source, 142 touched tests, and
134 touched both. Despite the one-year query window, the repository's Play-OEM
history starts on 2026-10-15; the latest included commit was 2026-11-10. Thus
the available sample covers only 27 calendar days, with 137 source commits in
October and 28 in November, and cannot establish a stable annual maintenance
rate.

The most frequently changed source files were `app.py` (44 commits),
`app/controller.py` (40), `workspace.py` (32), `control_window.py` (30), and
`views/ground_track.py` (25). `oem_data_store.py` appeared in 14 commits.
Leading same-commit pairs were `app/controller.py` with `app/state.py` (22),
`app.py` with `workspace.py` (21), and `app.py` with `control_window.py` (18).
The store co-changed with its focused test file in 13 commits.

The largest store counts are dominated by the November store migration and
consolidation sequence. For example, commit `5c4f5dd290` touched 28 files and
reported 435 insertions and 2,811 deletions; `703204e485` touched 20 files.
The history also includes the October app/workspace module splits and major
feature batches for Ground Track, stations, and incremental loading. A
sensitivity pass excluding all 19 `OemDataStore`-titled commits and the two
module-split commits left 144 source commits. The leading app/workspace pair
remained at 21 and controller/state remained frequent at 17; store touches
dropped to 3. This broad exclusion also removes legitimate store API and
performance changes, so it is a sensitivity check, not a preferred
maintenance-frequency estimate.

Representative diffs show the co-changes are expected integration: commit
`3419e4ff85` adds a loading-cursor field to both controller behavior and its
`PlayerAppState` protocol, while `7e213cdd9a` wires the open-file workflow
through the application and workspace controls. These changes do not by
themselves establish duplicated policy or an avoidable ownership boundary.
The store/test pairing likewise reflects test updates alongside store behavior.

**Decision:** no new implementation candidate is selected. The short history
is dominated by initial feature development, module splits, and a major store
migration; the observed co-changes are consistent with intentional interface
integration. These counts do not measure comprehension or defect rates. Reopen
candidate ranking only if a longer period of ordinary maintenance or a
specific change blocked by cross-component ownership supplies stronger evidence.
