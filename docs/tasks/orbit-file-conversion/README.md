# Orbit file conversion task breakdown

This directory decomposes the actionable work in
[`docs/ORBIT_FILE_CONVERSION.md`](../../ORBIT_FILE_CONVERSION.md). The source
document's format descriptions, accuracy warnings, metadata tables, and
conversion examples are requirements and context; they are not separate tasks
unless they imply implementation work.

## Reference matrix

See [the detailed conversion matrix](00-conversion-matrix.md) for the directed
format/model workflows, metadata behavior, provenance requirements, and
verification dimensions covered by these tasks.

## Status

- **In progress:** Task 1. The shared comment/report layer and current
  OEM-to-OMM, OEM-to-OPM, and OEM-to-TLE paths are implemented. Remaining
  work is direct `omm-to-tle` report behavior, broader production report
  configuration coverage, and proposed-command support. See [Task 1
  progress](01-provenance-and-fit-reports.md#progress).
- **Complete:** Task 2 implementation. The shared numerical fitter is wired to
  `oem-to-opm --fit-model numerical`, including fixed propagator configuration,
  Cartesian fitting, OPM conversion, fit reports, and human-readable summaries.
  Representative live Tudat/SPICE verification remains an environment-level
  follow-up. See [Task 2 progress](02-shared-numerical-fitter.md#progress).
- **Complete:** Task 3. Canonical fit-model parsing, deprecated mode handling,
  wrapper delegation, and unsupported-option handling are aligned across the
  current conversion commands.
- **Complete:** Task 4. OEM-to-OMM supports canonical fit-model selection,
  deprecated mode compatibility, theory conflict validation, and reporting.
- **In progress:** Task 10. Direct OMM-to-TLE validation is implemented; the
  non-SGP4 SGP4-refit workflow is composed from `propagate-omm` and
  `oem-to-tle`, with representative live verification remaining.
- **Complete:** Task 6. `omm-to-opm --fit-model numerical` and
  `tle-to-opm --fit-model numerical` wrappers delegate to the shared
  OEM-to-OPM fitter; short- and four-hour live output and fit-report
  verification are complete.
- **Pending:** Tasks 7–9 and 11. Their documents describe planned
  implementation work and acceptance criteria.

## Suggested order

1. **In progress:** [Shared provenance and fit-report contract](01-provenance-and-fit-reports.md)
2. **Complete:** [Shared numerical propagator fitter](02-shared-numerical-fitter.md)
3. **Complete:** [Conversion CLI option contract](03-conversion-cli-options.md)
4. **Complete:** [OEM to OMM fit migration](04-oem-to-omm-fit-model.md)
5. **Complete:** [OEM to OPM numerical fitting](05-oem-to-opm-numerical-fit.md)
6. **Complete:** [OMM and TLE to OPM numerical fitting](06-omm-tle-to-opm-numerical-fit.md)
7. **Pending:** [OPM to OEM model-aware workflow](07-opm-to-oem-workflow.md)
8. **Pending:** [OPM to OMM composed workflow](08-opm-to-omm-workflow.md)
9. **Pending:** [OEM to TLE fit reporting](09-oem-to-tle-fit-report.md)
10. **In progress:** [OMM to TLE validation and refit](10-omm-to-tle-validation-refit.md)
11. **Pending:** [OPM to TLE composed workflow](11-opm-to-tle-workflow.md)

Tasks 1–3 define shared behavior and should land before the format-specific
work. Tasks 5–6 depend on the shared numerical fitter. Tasks 8 and 11 compose
existing propagation and fitting operations and can reuse the lower-level
pieces from earlier tasks.

Latest focused verification: `223 passed, 2 deselected` covering the
provenance/reporting and affected conversion/CCSDS suites; the frame-utils
kernel-loading suite also passes with `13 passed`.

All orbit-file-conversion work has an additional objective: do not add runtime
dependencies; reuse the repository's existing libraries and tooling.

All fitting workflows must also treat physical parameters as user-supplied
fixed inputs. They may be validated and recorded, but must never be varied by
the optimizer.
