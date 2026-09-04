# Orbit file conversion task breakdown

This directory decomposes the actionable work in
[`docs/ORBIT_FILE_CONVERSION.md`](../../ORBIT_FILE_CONVERSION.md). The source
document's format descriptions, accuracy warnings, metadata tables, and
conversion examples are requirements and context; they are not separate tasks
unless they imply implementation work.

## Status

- **In progress:** Task 1. The shared comment/report layer and initial
  OEM-to-OMM/OEM-to-OPM wiring are implemented; TLE wrapper integration,
  source-report parsing, and basic convergence reporting are implemented;
  velocity residuals, richer propagation diagnostics, and proposed-command
  support are still pending. See [Task 1 progress](01-provenance-and-fit-reports.md#progress).
- **In progress:** Task 2. The shared numerical-fit configuration and reference
  state validation boundary are implemented; optimizer and propagator wiring
  remain pending.
- **Pending:** Tasks 3–11. These remain planned implementation work; their
  documents describe the intended behavior and acceptance criteria.

## Suggested order

1. **In progress:** [Shared provenance and fit-report contract](01-provenance-and-fit-reports.md)
2. **In progress:** [Shared numerical propagator fitter](02-shared-numerical-fitter.md)
3. **Pending:** [Conversion CLI option contract](03-conversion-cli-options.md)
4. **Pending:** [OEM to OMM fit migration](04-oem-to-omm-fit-model.md)
5. **Pending:** [OEM to OPM numerical fitting](05-oem-to-opm-numerical-fit.md)
6. **Pending:** [OMM and TLE to OPM numerical fitting](06-omm-tle-to-opm-numerical-fit.md)
7. **Pending:** [OPM to OEM model-aware workflow](07-opm-to-oem-workflow.md)
8. **Pending:** [OPM to OMM composed workflow](08-opm-to-omm-workflow.md)
9. **Pending:** [OEM to TLE fit reporting](09-oem-to-tle-fit-report.md)
10. **Pending:** [OMM to TLE validation and refit](10-omm-to-tle-validation-refit.md)
11. **Pending:** [OPM to TLE composed workflow](11-opm-to-tle-workflow.md)

Tasks 1–3 define shared behavior and should land before the format-specific
work. Tasks 5–6 depend on the shared numerical fitter. Tasks 8 and 11 compose
existing propagation and fitting operations and can reuse the lower-level
pieces from earlier tasks.

Latest focused verification: `139 passed, 2 deselected` covering the numerical
fit validation, provenance reporting, and affected conversion suites.
