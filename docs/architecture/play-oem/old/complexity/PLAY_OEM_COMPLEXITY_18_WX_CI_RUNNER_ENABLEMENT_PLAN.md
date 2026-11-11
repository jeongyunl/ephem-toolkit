# play-oem — Native wx Cross-Platform Runner Enablement Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
Cross-platform feasibility evidence:
[PLAY_OEM_COMPLEXITY_17_CROSS_PLATFORM_WX_CLEANUP_PLAN.md](./PLAY_OEM_COMPLEXITY_17_CROSS_PLATFORM_WX_CLEANUP_PLAN.md).
Native cleanup test and macOS evidence:
[PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md](./PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md).
Platform dependency constraints:
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md),
[PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md).

## Goal

Establish a repeatable, maintained way to execute the existing real-wx
partial-startup cleanup test on wxGTK/Linux and wxMSW/Windows. Prefer existing
hosted CI capabilities if they can support the dependencies and native GUI
requirements. Add only the narrow CI coverage needed for this validation;
do not imply that one test job certifies the complete application on every
platform or Python version.

Plan 17 established that no usable non-macOS runner or repository workflow is
available in the current environment. This plan treats runner enablement as a
separate infrastructure task, with Linux dependency cost and Windows desktop
availability to be proven before committing to a CI design.

## Remaining-candidate ranking

| Candidate | Current evidence | Relative decision |
| --- | --- | --- |
| wx native CI runner enablement | Plan 16 verified cleanup on macOS Cocoa; plan 17 found GTK/Linux and MSW/Windows blocked by absent runners. | Investigate next: a minimal maintained runner path is the prerequisite to completing the cross-platform behavior check. |
| Raw ingestion reservation protocol | Reservation, commit, observer failure, epoch replacement, cancellation, and late parse failure have been mapped; `_StoreRowSink` has one production caller. | Defer absent a new failure path or independent caller. |
| Load event consumption | Event transitions and stale-generation behavior are mapped, and per-tick event draining is bounded. | Defer absent a duplicated consumer or a concrete transition mismatch. |
| Store-backed result-state interpretation | Plan 15 found view-specific presentation rules and no shared production policy. | Complete for the current candidate set; reopen only with a specific inconsistency. |

This is a targeted validation-enablement step, not a general CI migration or
an expansion of the supported Python/wxPython matrix.

## Baseline and constraints

The existing test
`test_native_partial_startup_cleanup_destroys_real_wx_frame` exercises real
wx resources and deterministic failure injection. On macOS Cocoa with wxPython
4.2.4 / wxWidgets 3.2.8, the complete app lifecycle suite passed 97 tests.
GTK/Linux and MSW/Windows remain unverified; they must not be reported as
passed until that test has actually run under those backends.

The repository's playback extra declares wxPython 4.2.4 or newer. Existing
platform notes indicate that the minimum wxPython version may require building
against wxGTK dependencies on Linux, and that display-dependent tests need a
virtual display such as Xvfb. Windows needs a usable native wxMSW session.
Hosted-runner capability, installation time, and display behavior must be
measured rather than presumed.

## Investigation procedure

1. Recheck the test's display guard, failure injection, current test command,
   lockfile installation flow, and existing platform dependency notes. Identify
   the narrowest command that exercises the native cleanup test and its
   surrounding app lifecycle tests.
2. Verify whether the repository's GitHub Actions configuration and
   organization policy permit hosted Ubuntu and Windows jobs. Record runner
   image, Python version, wxPython version/backend, display mechanism, and
   any job permissions or cost constraints that affect the design.
3. Prove wxPython installation on the candidate Ubuntu runner using the
   locked playback dependencies and required wxGTK system libraries. Capture
   install duration and whether it uses a wheel or source build. Do not add a
   speculative package list or lengthy source build to a permanent workflow
   until this proof succeeds.
4. Prove the candidate Windows runner can initialize wxMSW and execute the
   real-frame test non-interactively. If native desktop availability is
   insufficient or flaky, stop and document the limitation rather than
   weakening the test's cleanup assertions.
5. If both hosted paths are viable, add the smallest separate CI workflow or
   jobs that run the native cleanup test and focused app lifecycle suite on
   Ubuntu/GTK and Windows/MSW. Use the existing lock and project test
   conventions; avoid a broad OS/Python Cartesian matrix.
6. Run each job and record exact OS image, Python/wxPython versions, backend,
   display setup, command, and pass/fail/block outcome. Keep macOS Cocoa as a
   separate known-good result.
7. If hosted execution is not viable, do not silently introduce self-hosted
   infrastructure. Document the specific dependency, policy, or desktop
   blocker and the operational requirements of the remaining option for a
   separate user decision.
8. Update the assessment, subsystem overview, and this plan with the result,
   limitations, and next-ranked candidate.

## Required behavior and constraints

- Preserve the native test's deterministic setup failure and cleanup
  guarantees: workspace close, timer stop, app preservation, original
  exception propagation, and cleanup of only the acquired frame.
- Keep GTK display setup and MSW desktop execution explicit and reproducible.
- Distinguish job setup failures, display skips, test failures, and successful
  backend runs; do not convert an unavailable display into a pass.
- Do not change production cleanup code unless a backend run reproduces a
  concrete defect.
- Do not add self-hosted runners, credentials, or organization-level
  configuration as part of this bounded task.
- Limit compatibility claims to the tested runner images and dependency
  versions; this is not full platform certification.

## Implementation checklist

- **Status:** Blocked — hosted execution cannot be proven from this session.
- **Progress:** 5/8 feasibility actions recorded.
- [x] Confirm repository workflow configuration: GitHub Actions reports zero
      workflows for this repository.
- [x] Confirm the current workspace is macOS-only and has no Linux/Windows
      host, Xvfb, or local container runtime.
- [x] Establish the existing macOS Cocoa result separately: 97 app lifecycle
      tests passed as recorded in plan 16.
- [x] Record that hosted runner policy, Linux wxGTK installation, and Windows
      desktop behavior cannot be validated without actually running hosted
      jobs.
- [x] Decide not to add speculative workflow or dependency configuration
      without proven runner feasibility and a successful execution path.
- [ ] Prove wxGTK installation and display setup on a hosted Linux runner.
- [ ] Prove non-interactive wxMSW startup and native test execution on Windows.
- [ ] Run the tests on verified runners and update this plan, assessment, and
      subsystem overview with backend-specific results.

**Done when:** Each non-macOS backend either has a repeatable, passing native
cleanup job with exact environment facts recorded, or has a concrete,
reviewable blocker documented without claiming cross-platform verification.

## Execution record — 2026-11-11

GitHub Actions reports zero configured workflows for `jeongyunl/ephem-toolkit`.
The available repository and local environment evidence therefore does not
provide an existing job, runner image, or organization policy with which to
prove hosted Ubuntu or Windows capability. The local host is macOS and has no
Linux/Windows machine, Xvfb, or container runtime. Consequently, this session
cannot measure Linux wxGTK dependency installation, Windows wxMSW desktop
availability, or either backend's test behavior.

No workflow, system dependency list, or self-hosted runner configuration was
added. The 97-test macOS Cocoa result from plan 16 is unchanged and does not
count as GTK/MSW validation. A future execution needs permission and an
available mechanism to add and run a minimal hosted workflow (or independently
provided runners); otherwise the platform verification remains blocked. Before
adding persistent infrastructure, confirm that hosted jobs are allowed and
that the Linux wxGTK install is practical.
