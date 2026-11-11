# play-oem — Pass Endpoint Look-Angle Policy Plan

Strategy:
[PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Prior view-boundary assessment:
[PLAY_OEM_COMPLEXITY_11_LARGE_GUI_VIEW_RESPONSIBILITIES_PLAN.md](./PLAY_OEM_COMPLEXITY_11_LARGE_GUI_VIEW_RESPONSIBILITIES_PLAN.md).
Panel lifecycle result:
[PLAY_OEM_COMPLEXITY_38_PANEL_OPEN_PREFLIGHT_PLAN.md](./PLAY_OEM_COMPLEXITY_38_PANEL_OPEN_PREFLIGHT_PLAN.md).

## Goal

Evaluate whether `GroundStationPassesView._profile_points` and
`_look_angle_at` can share a small interval-endpoint look-angle policy without
merging their distinct profile sampling and playback interpolation behavior.
This is a local helper review, not a pass-view split or a panel-lifecycle
follow-up.

## Baseline and hypothesis

In the current source, `_profile_points` is 58 lines with decision score 19,
`_look_angle_at` is 66 lines with score 23, and `_draw_sky_plot` is 172 lines
with score 27 under the assessment's AST indicator.

Both helpers apply optional `AccessInterval` start/end azimuth and elevation
values. When an endpoint is not clipped by OEM coverage or limited by a data
gap, both clamp its elevation to the selected station's minimum mask.
`_profile_points` overlays these values only when the endpoint falls within a
profile's time coverage. `_look_angle_at` uses endpoint metadata for a time
within `1e-9` seconds of an interval boundary, then otherwise interpolates
finite profile samples with azimuth unwrap. Both helpers require endpoint
azimuth and elevation together; `_profile_points` returns no points without a
selected station, while `_look_angle_at` can return endpoint metadata without
one and skips the mask clamp.

**Hypothesis:** one local endpoint resolver could make boundary-value and mask
normalization rules easier to maintain. Reject it if the helper has to absorb
profile coverage, time matching, sampling, or interpolation differences, or
if it merely moves the same branches behind new arguments.

Existing pass-view tests cover rendering, playback markers, invalid profile
segments, sample bounds, and row annotations. They do not appear to isolate
the rendering behavior for mask-clamped versus clipped/gap-limited boundary
elevations; the current sky-plot fixtures use endpoint elevations at or above
the station mask. Confirm this coverage gap before adding tests.

## Scope and invariants

- Inspect only `_profile_points`, `_look_angle_at`, their
  `_draw_sky_plot` call sites, and direct pass-view tests.
- Preserve `AccessInterval` endpoint metadata as the preferred boundary value
  when it is available.
- Preserve the requirement that both endpoint azimuth and elevation are
  present, and preserve each helper's behavior when no station is selected.
- Clamp ordinary endpoint elevations to the selected station mask; preserve
  measured elevations at coverage-clipped or gap-limited endpoints.
- Preserve the distinct profile-coverage check in `_profile_points` and
  `1e-9` endpoint-time match in `_look_angle_at`.
- Preserve missing-endpoint fallback to profile interpolation, finite-sample
  handling, azimuth wrap interpolation, and store-backed bounded sampling.
- Do not change access-interval construction, `StationAnalysisContext`,
  station-access algorithms, the elevation-over-time graph, or view/panel
  ownership.
- Plan 38 is complete; do not reopen panel identity, replacement, or rollback
  behavior without new evidence.

## Procedure

1. Trace the sky-path and playback-marker calls and tabulate start/end cases
   for optional endpoint angles, profile coverage, ordinary crossings,
   coverage clipping, and gap limiting.
2. Verify which cases are already pinned by
   `test_ground_station_passes_view.py`. Add characterization tests only for
   concrete untested behavior needed to compare the candidate.
3. Sketch the smallest local endpoint resolver and compare its inputs,
   branches, return shape, and call-site obligations with the current
   duplicate blocks. Do not introduce an endpoint enum, result object, or
   generalized profile-sampling abstraction.
4. Keep a helper only if it centralizes the endpoint policy and reduces
   duplicated control flow or total implementation size without increasing
   combined decision score or obscuring the distinct coverage/time rules.
   Otherwise retain the current code and record the reason.
5. If implementation is justified, run:

   ```sh
   python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_passes_view.py
   ```

6. Update the assessment and subsystem overview with the decision. Do not
   broaden this into a GUI display-platform test or performance study.

## Done when

The endpoint rule is either shared with less total reasoning and focused
behavior coverage, or the two call sites are retained because their distinct
coverage and time-matching semantics make a helper less clear.

## Execution result

The local `_interval_endpoint_look_angle` helper centralizes optional endpoint
metadata selection, paired-angle validation, and ordinary mask clamping. The
profile-coverage check remains in `_profile_points`; endpoint time matching and
interpolation remain in `_look_angle_at`. The store-backed and in-memory
sampling branches now converge before point assembly, preserving bounded
sampling without duplicating endpoint policy.

The comparison passed the plan's simplification gate. The two original methods
totaled 124 source lines and an AST decision score of 42. The final methods and
resolver total 115 lines and a score of 36 (`_profile_points`: 48/13,
`_look_angle_at`: 50/15, resolver: 17/8). `_draw_sky_plot` remains unchanged
at 172 lines and score 27.

Added characterization for ordinary, coverage-clipped, and gap-limited
endpoint elevations; profile coverage versus marker lookup; missing endpoint
metadata; endpoint-time tolerance; and the no-selected-station mask behavior.
The first full focused run caught a missing return on the store-backed
sampling path; point assembly was moved after the sampling-strategy branch and
the suite was rerun successfully:

```text
python3 -m pytest tests/ephem_toolkit/play_oem/test_ground_station_passes_view.py
27 passed, 1 skipped
```

**Status:** Complete; retain the local endpoint resolver.
