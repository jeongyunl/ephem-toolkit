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

- **Complete:** Task 1. The shared comment/report layer and current
  OEM-to-OMM, OEM-to-OPM, and OEM-to-TLE paths are implemented, including
  composed OMM-to-TLE refit coverage. Shared numerical fit reports preserve
  force and integrator settings, and source reports without usable provenance
  resolve to `unknown`.
  See [Task 1
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
- **In progress:** Task 10. Direct OMM-to-TLE validation is implemented for
  SGP4-compatible input. Non-SGP4 refits intentionally compose
  `propagate-omm → OEM → oem-to-tle`; the direct `--refit-sgp4` mode was
  removed. DSST has representative live verification, and direct rejection
  tests now verify theory-specific incompatibility diagnostics. Additional
  theories await matching propagator support; Brouwer fallback behavior is
  explicitly tested, and fallback OEMs now identify their actual Kepler model
  in provenance comments until a Brouwer propagator exists.
- **Complete:** Task 6. `omm-to-opm --fit-model numerical` and
  `tle-to-opm --fit-model numerical` wrappers delegate to the shared
  OEM-to-OPM fitter; short- and four-hour live output and fit-report
  verification are complete.
- **Complete as composition:** Task 7. Existing `propagate-kepler` and
  `propagate-orbit` commands provide the two-body and numerical OPM-to-OEM
  paths; both OEM types identify their propagation model, and numerical OEMs
  also record their propagation configuration. No dedicated wrapper is planned.
- **Complete as composition:** Task 8. Both Task 7 paths compose with
  `oem-to-omm`, and final reports preserve the intermediate OEM provenance and
  propagation-configuration comments.
- **Complete:** Task 9. OEM-to-TLE emits SGP4 fit provenance and diagnostics in
  a JSON report, with coverage for file/stdout reports, unknown source
  provenance, and fixed-width TLE checksums.
- **Complete as composition:** Task 11. Existing propagation commands compose
  with `oem-to-tle` for two-body and numerical OPM-to-TLE conversion; no
  dedicated wrapper is planned.

## Suggested order

1. **Complete:** [Shared provenance and fit-report contract](01-provenance-and-fit-reports.md)
2. **Complete:** [Shared numerical propagator fitter](02-shared-numerical-fitter.md)
3. **Complete:** [Conversion CLI option contract](03-conversion-cli-options.md)
4. **Complete:** [OEM to OMM fit migration](04-oem-to-omm-fit-model.md)
5. **Complete:** [OEM to OPM numerical fitting](05-oem-to-opm-numerical-fit.md)
6. **Complete:** [OMM and TLE to OPM numerical fitting](06-omm-tle-to-opm-numerical-fit.md)
7. **Complete as composition:** [OPM to OEM model-aware workflow](07-opm-to-oem-workflow.md)
8. **Complete as composition:** [OPM to OMM composed workflow](08-opm-to-omm-workflow.md)
9. **Complete:** [OEM to TLE fit reporting](09-oem-to-tle-fit-report.md)
10. **In progress:** [OMM to TLE validation and refit](10-omm-to-tle-validation-refit.md)
11. **Complete as composition:** [OPM to TLE composed workflow](11-opm-to-tle-workflow.md)

Tasks 1–3 define shared behavior and should land before the format-specific
work. Tasks 5–6 depend on the shared numerical fitter. Tasks 8 and 11 compose
existing propagation and fitting operations and can reuse the lower-level
pieces from earlier tasks.

Latest focused verification: `308 passed, 2 deselected` covering the
provenance/reporting, conversion, propagation, and CCSDS suites; the
frame-utils kernel-loading suite also passes with `13 passed`.

Task 10 composed-workflow verification: `51 passed` covering OEM-to-TLE,
OMM-to-TLE, and TLE conversion tests, including the propagation-to-OEM-to-TLE
integration test with a DSST OMM fixture. A source-tree 2-hour DSST
composition also produced a converged fit report; broader non-SGP4 live
verification is limited by the currently supported propagators.

Task 8 composition verification: `168 passed, 13 warnings`, including
two-body and numerical OPM-to-OEM-to-OMM integration tests. Both DSST fits
converged over 2-hour arcs; the numerical path used 27 fitted records.

Task 9 verification: `12 passed` in the OEM-to-TLE suite. A direct 10-minute
OEM fit produced a converged report with unknown-source provenance and a
69-character, checksum-valid TLE; report-file and stdout destinations are
covered.

Task 11 verification: two end-to-end tests compose `sample2.opm` with
two-body or numerical propagation, followed by an SGP4 OEM fit. Both paths
produced converged reports and checksum-valid TLEs; the numerical path used
27 reference records. Unsupported direct OMM output-theory combinations remain
explicitly rejected by the existing OMM-to-TLE tests.

Task 10 decision: direct `omm-to-tle` remains a field mapping for SGP4-compatible
OMMs only. Non-SGP4 OMMs use `propagate-omm → OEM → oem-to-tle`; no separate
direct refit implementation or `--refit-sgp4` option is planned.

All orbit-file-conversion work has an additional objective: do not add runtime
dependencies; reuse the repository's existing libraries and tooling.

All fitting workflows must also treat physical parameters as user-supplied
fixed inputs. They may be validated and recorded, but must never be varied by
the optimizer.
