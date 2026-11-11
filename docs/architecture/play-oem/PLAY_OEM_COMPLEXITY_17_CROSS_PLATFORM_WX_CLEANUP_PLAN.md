# play-oem — Cross-Platform wx Cleanup Verification Plan

Strategy: [PLAY_OEM_COMPLEXITY_1_STRATEGY.md](./PLAY_OEM_COMPLEXITY_1_STRATEGY.md).
Assessment and work-item priorities:
[PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md](./PLAY_OEM_COMPLEXITY_2_ASSESSMENT.md).
Subsystem context:
[PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md](./PLAY_OEM_COMPLEXITY_3_SUBSYSTEMS.md).
macOS Cocoa native evidence:
[PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md](./PLAY_OEM_COMPLEXITY_16_NATIVE_WX_STARTUP_CLEANUP_PLAN.md).
Platform and playback dependency constraints:
[PLAY_OEM_IMPLEMENTATION_PLAN.md](./PLAY_OEM_IMPLEMENTATION_PLAN.md),
[PLAY_OEM_CONCEPTS.md](./PLAY_OEM_CONCEPTS.md).

## Goal

Verify the existing partial-startup cleanup integration test on the other
declared desktop targets, wxGTK/Linux and wxMSW/Windows, or establish which
runner and dependency constraints prevent that validation. Determine whether
the macOS Cocoa result generalizes to those backends without changing the
production rollback path.

This is a validation plan, not a new cleanup refactor or a requirement to add
CI infrastructure. First check whether supported runners already exist. If
they do not, record the gap and propose infrastructure separately rather than
silently expanding this work item.

## Remaining-candidate ranking

| Candidate | Current evidence | Relative decision |
| --- | --- | --- |
| Cross-platform native wx cleanup | Plan 16 verified real frame/workspace/timer rollback on macOS Cocoa with wxPython 4.2.4. Linux/GTK and Windows/MSW GUI behavior remain unverified, although both are project targets. | Investigate next: `Destroy()`, event processing, and wrapper invalidation can be backend-specific; compare the same bounded failure test on the other supported wx backends. |
| Raw ingestion reservation protocol | The load lifecycle investigation already mapped reservation, commit, observer failure, epoch replacement, cancellation, and late parse failure. `_StoreRowSink` has one production caller. | Defer absent a new failure path or independent caller. |
| Load event consumption | The event transitions and stale-generation behavior are mapped, and per-tick event draining is bounded. | Defer absent a duplicated consumer or a concrete transition mismatch. |
| Store-backed result-state interpretation | Plan 15 found view-specific presentation rules and no shared production policy. | Complete for the current candidate set; reopen only with a specific inconsistency. |

This ranking follows the unresolved portability claim from plan 16 and the
project's stated macOS, Linux, and Windows targets. It does not imply that
every Python/wxPython combination needs a full Cartesian test matrix.

## Planning baseline and initial evidence

The native rollback test in `test_play_oem_app.py` injects a failure after
`PlayerApp` has constructed the real frame, workspace, control window, and
playback timer. It verifies workspace close, timer state, app preservation,
original exception propagation, and native frame removal after wx event
processing. It passed on macOS Cocoa with wxPython 4.2.4 and wxWidgets 3.2.8.

The implementation plan identifies macOS, Linux, and Windows as supported
platform targets. Its wx dependency notes state that wxPython wheels exist for
macOS and Windows, while the minimum wxPython release requires a source build
with wxGTK dependencies on Linux. The implementation plan describes
`xvfb-run` for display-dependent Linux CI tests. No workflow files are present
under `.github/workflows` in the current repository, so the existence of an
external or hosted runner must not be assumed.

The current test uses `wx.GetTopLevelWindows()`, `wx.YieldIfNeeded()`, and
access to the destroyed frame wrapper to establish deletion on Cocoa. Verify
that these are reliable observations on GTK and MSW before retaining the same
assertions unchanged. Keep exact platform and wxPython version facts alongside
each result.

## Platform and test matrix

| Target | Intended test environment | Feasibility question |
| --- | --- | --- |
| macOS / Cocoa | Existing successful run on wxPython 4.2.4 | Keep as the known-good baseline; avoid rerunning unless test behavior changes. |
| Linux / GTK | Linux with wxGTK and a virtual display such as Xvfb | Is there a maintained runner with wxGTK dependencies and `xvfb-run`, or would a source build be required? |
| Windows / MSW | Windows runner with a usable desktop session | Can the test execute natively in the existing test infrastructure without introducing interactive-session flakiness? |

Start with one representative supported Python/wxPython environment per
backend. Do not claim compatibility across all supported Python versions from
these runs; expand the matrix only if the wx minimum or runtime support
contract requires it.

## Investigation procedure

1. Recheck repository and available test infrastructure for Linux/Windows
   runners, playback-extra installation, wx backend versions, and display
   support. Distinguish files in this repository from hosted infrastructure
   that is not visible here.
2. Select one supported Python/wxPython environment for GTK and one for MSW.
   Record whether each environment uses a wheel or source build and how a
   display is made available.
3. Run the existing
   `test_native_partial_startup_cleanup_destroys_real_wx_frame` test unchanged
   on each available backend first. Preserve the deterministic failure at
   `Workspace.set_oem_loaded()`.
4. If a backend behaves differently, inspect the exact wx event/deletion
   behavior and adjust only the native test's observation mechanism when the
   underlying cleanup is correct. Keep production assertions for app
   preservation, timer state, workspace close, and exception transparency.
5. If the test reveals a concrete cleanup defect, add a backend-specific
   regression and make the narrowest production correction that preserves
   Cocoa behavior.
6. If no runner exists, record the dependency/display blocker, the required
   runner contract, and whether establishing a maintained runner merits a
   separate infrastructure task. Do not add a workflow or dependency in this
   plan without that separate justification.
7. Run the focused app lifecycle suite on each backend that is available.
   Report pass/skip/block status separately for GTK and MSW.
8. Update the assessment and subsystem record with platform-specific evidence,
   any change, limitations, and the next-ranked candidate.

## Required behavior and constraints

- Preserve the tested macOS Cocoa cleanup behavior.
- Preserve the same wx app, propagate the original setup exception, stop the
  playback timer, close the completed workspace, and destroy only the frame
  acquired by the failed constructor.
- Keep cleanup on the wx-owning thread and use deterministic failure
  injection; avoid sleeps and undocumented backend internals.
- Distinguish a missing runner or unavailable display from a test pass.
- Do not add CI infrastructure, packages, or production abstractions unless
  the feasibility evidence justifies a separate change.
- Limit compatibility claims to the tested backend and wxPython version.

## Implementation checklist

- **Status:** Complete — cross-platform execution blocked by available runners.
- **Progress:** 8/8 feasibility actions recorded.
- [x] Inventory existing Linux/GTK and Windows/MSW test runners and display
      support.
- [x] Determine whether a Linux/GTK or Windows/MSW test environment is
      available; record that neither is available locally or through repository
      runner configuration.
- [x] Classify GTK execution as blocked because there is no Linux host,
      `xvfb-run`, container runtime, or configured workflow.
- [x] Classify MSW execution as blocked because there is no Windows host or
      configured workflow.
- [x] Record that backend-specific observation differences cannot be
      established without those runs.
- [x] Make no production fix because no non-Cocoa backend failure was observed.
- [x] Record the existing macOS app-suite pass separately from blocked GTK/MSW
      targets.
- [x] Update the assessment and subsystem record with evidence, limitations,
      and the next-ranked candidate.

**Done when:** GTK and MSW native cleanup behavior is verified on available
supported runners, or their exact runner/dependency blockers are documented
without extending the macOS result into a cross-platform claim.

## Execution record — 2026-11-11

### Runner feasibility

The current host reports `Darwin` / `darwin`. No `xvfb-run`, Docker, Podman,
or GitHub CLI executable is available, and `.github` contains no workflow
configuration. There is no local Linux/GTK or Windows/MSW host available to
execute the native integration test. The repository's implementation notes
also state that Linux requires a wxGTK source build for the minimum wxPython
release, while Windows requires a usable desktop runner.

The known-good macOS Cocoa result remains the **97 passed** app lifecycle suite
recorded in plan 16. GTK and MSW are **blocked**, not passed or skipped:
neither backend could be instantiated in this environment. No backend
assertion differences or production defect can be inferred from that absence.

### Outcome and limitation

Plan 17 is complete as a runner-feasibility investigation. Cross-platform
native cleanup remains unverified. No CI workflow, dependency, or production
change was added because the plan requires that infrastructure to be justified
separately. The next actionable step requires access to a Linux/GTK runner
with wxGTK and Xvfb, and a Windows/MSW desktop-capable runner; until then, the
claim remains limited to macOS Cocoa.
