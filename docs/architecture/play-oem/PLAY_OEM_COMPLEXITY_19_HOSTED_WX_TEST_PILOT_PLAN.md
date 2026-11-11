# play-oem — Hosted wx Test Pilot Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Runner feasibility:
[PLAY_OEM_COMPLEXITY_18_WX_CI_RUNNER_ENABLEMENT_PLAN.md](./PLAY_OEM_COMPLEXITY_18_WX_CI_RUNNER_ENABLEMENT_PLAN.md).
Cross-platform cleanup test:
[PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md](./PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md).

## Goal

Resolve the remaining access gap from plan 18 by determining whether a
minimal, manually triggered GitHub Actions pilot can run the native cleanup
test on hosted Ubuntu/wxGTK and Windows/wxMSW. The pilot is intended to
produce evidence, not establish a general CI policy or certify all platforms.

Do not add or trigger a workflow until repository write access and permission
to consume hosted runner minutes are confirmed. If that authorization is not
available, stop with the access blocker documented; do not use credentials,
create self-hosted infrastructure, or claim platform coverage.

## Evidence and decision

Plan 18 found zero configured GitHub Actions workflows and no way from the
local macOS environment to validate hosted policy, Linux wxGTK installation,
or Windows GUI availability. The existing macOS Cocoa result remains the only
native backend evidence. Therefore the next bounded action is an authorized
pilot, not further local analysis or production-code changes.

## Investigation procedure

1. Confirm with the repository owner that a temporary/minimal GitHub Actions
   workflow may be added and manually run, and that hosted Ubuntu and Windows
   minutes are permitted. If either permission is absent, record the blocker
   and stop before editing workflow configuration.
2. Confirm the intended branch and dispatch path. Keep the workflow manually
   triggered for this pilot; do not add it to required checks or broaden
   triggers without separate approval.
3. Use a single representative supported Python version and the existing
   locked playback/test dependencies. Avoid a Python-version matrix.
4. On Ubuntu, install only verified wxGTK/Xvfb system dependencies, install
   the playback extra from the lock, and record whether wxPython installs
   from a wheel or source plus the elapsed setup time.
5. On Windows, install the same locked playback extra and test whether wxMSW
   can create the real test frame in the hosted session. Do not mask display
   initialization or convert a display skip into success.
6. Run the existing native partial-startup cleanup test first. If it passes,
   run the focused app lifecycle suite. Keep backend setup failures, test
   failures, and display unavailability distinct in the report.
7. If both jobs pass reliably, decide whether retaining the small manual
   workflow is useful; do not make it a required check in this task. If a
   backend is infeasible, retain no nonfunctional job and document the exact
   policy/dependency/desktop blocker.
8. Remove any temporary pilot workflow unless the repository owner explicitly
   chooses to retain it. Update plans 18 and 19, the assessment, and subsystem
   overview with the decision and exact runner facts.

## Required behavior and constraints

- Preserve the native cleanup test's real wx resources and deterministic
  failure injection.
- Record runner image, Python version, wxPython/wxWidgets version, backend,
  display mechanism, command, and result.
- Do not add secrets, broad permissions, self-hosted runners, or organization
  configuration.
- Do not change production cleanup behavior absent a reproducible backend bug.
- Do not infer cross-platform support from job setup success alone.
- Make workflow retention and any broader CI trigger policy explicit decisions.

## Implementation checklist

- **Status:** Deferred — non-macOS runners are unavailable.
- **Progress:** Deferred before execution; no non-macOS runners are available.
- [x] Confirm current access constraint: work is limited to macOS, with no
      Ubuntu or Windows runner access; defer hosted execution.
- [ ] Confirm authorization to add/run a manual hosted workflow and consume
      runner minutes if runner access becomes available.
- [ ] Confirm branch/dispatch mechanism and runner images.
- [ ] Prove the Ubuntu wxGTK/Xvfb installation and native test.
- [ ] Prove Windows wxMSW desktop initialization and native test.
- [ ] Run the focused app lifecycle suite on each backend that passed the
      native integration test.
- [ ] Decide whether to retain or remove the pilot workflow.
- [ ] Report exact results without expanding compatibility claims.
- [ ] Update plan 18, plan 19, assessment, and subsystem overview.

**Done when:** The pilot is either successfully executed with explicit
retain/remove decision, or stopped at a documented authorization or technical
blocker. No cross-platform claim is made without a passing native test on that
backend.

## Execution record — 2026-11-11

The user confirmed the available environment is macOS only and that Ubuntu and
Windows are inaccessible, and requested deferral. No workflow was added or
triggered. Keep the GTK and MSW results blocked; resume this plan only if
non-macOS runner access becomes available.
