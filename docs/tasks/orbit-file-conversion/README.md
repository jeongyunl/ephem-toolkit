# Orbit file conversion task breakdown

This directory decomposes the actionable work in
[`docs/ORBIT_FILE_CONVERSION.md`](../../ORBIT_FILE_CONVERSION.md). The source
document's format descriptions, accuracy warnings, metadata tables, and
conversion examples are requirements and context; they are not separate tasks
unless they imply implementation work.

## Suggested order

1. [Shared provenance and fit-report contract](01-provenance-and-fit-reports.md)
2. [Shared numerical propagator fitter](02-shared-numerical-fitter.md)
3. [Conversion CLI option contract](03-conversion-cli-options.md)
4. [OEM to OMM fit migration](04-oem-to-omm-fit-model.md)
5. [OEM to OPM numerical fitting](05-oem-to-opm-numerical-fit.md)
6. [OMM and TLE to OPM numerical fitting](06-omm-tle-to-opm-numerical-fit.md)
7. [OPM to OEM model-aware workflow](07-opm-to-oem-workflow.md)
8. [OPM to OMM composed workflow](08-opm-to-omm-workflow.md)
9. [OEM to TLE fit reporting](09-oem-to-tle-fit-report.md)
10. [OMM to TLE validation and refit](10-omm-to-tle-validation-refit.md)
11. [OPM to TLE composed workflow](11-opm-to-tle-workflow.md)

Tasks 1–3 define shared behavior and should land before the format-specific
work. Tasks 5–6 depend on the shared numerical fitter. Tasks 8 and 11 compose
existing propagation and fitting operations and can reuse the lower-level
pieces from earlier tasks.
