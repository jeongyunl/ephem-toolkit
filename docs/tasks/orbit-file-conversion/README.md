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

- **In progress:** Task 10. Direct OMM-to-TLE validation is implemented for
  SGP4-compatible input. Non-SGP4 refits intentionally compose
  `propagate-omm → OEM → oem-to-tle`; the direct `--refit-sgp4` mode was
  removed. DSST has representative live verification, and direct rejection
  tests now verify theory-specific incompatibility and missing-metadata
  diagnostics and stop before conversion; all supported SGP4 theory aliases
  are also covered. Brouwer and Brouwer-Lyddane fallback behavior is explicitly
  tested, and fallback OEMs now identify their actual Kepler model in provenance
  comments until a Brouwer propagator exists.

## Current focus

- [OMM to TLE validation and refit](10-omm-to-tle-validation-refit.md)

Completed work and historical ordering remain documented in the individual
task files and the conversion matrix.

## Remaining work

- **Task 10 implementation:** Add composed OMM-to-TLE verification for any
  additional non-SGP4 theory once `propagate-omm` supports a matching
  propagator. Brouwer currently uses an explicitly labeled Kepler fallback.
- **Environment validation:** Run representative long-arc Tudat/SPICE checks
  for the numerical fitter when the required kernels and runtime are available.
- **Optional production verification:** Exercise additional OPM-to-OMM
  compositions and confirm their complete propagation provenance in reports.

Latest focused verification: `312 passed, 2 deselected` covering the
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
