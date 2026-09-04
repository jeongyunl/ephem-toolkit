# Task 10: Validate OMM-to-TLE input and add SGP4 refit

## Status

**In progress.** Direct conversion validation and the explicit
`--refit-sgp4` workflow are implemented. Live validation with representative
non-SGP4 OMMs remains before this task can be closed.

## Goal

Prevent invalid direct OMM-to-TLE conversions and provide an explicit path for
converting non-SGP4 OMMs through a new SGP4 fit.

## Additional objective

Do not add runtime dependencies; reuse the repository's existing libraries and
tooling.

## Scope

- Validate that direct `omm-to-tle` input declares an SGP4-compatible
  `MEAN_ELEMENT_THEORY` and contains required TLE parameters.
- Reject DSST, Brouwer-Lyddane, and other non-SGP4 theories with a diagnostic
  naming the declared theory and explaining the incompatibility.
- Add `--refit-sgp4`: propagate the source OMM with its declared theory, fit
  SGP4-compatible mean elements, and write a TLE.
- Add fit span, source provenance, and `--fit-report` handling to the refit
  path.
- Keep direct SGP4-compatible mapping free of fabricated fit diagnostics.

## Acceptance criteria

- Valid direct SGP4 mappings retain their current fields and produce valid TLEs.
- Invalid theories fail before writing output and identify the incompatibility.
- `--refit-sgp4` succeeds for supported non-SGP4 input and reports source
  theory, fit settings, and residuals.
- Tests distinguish direct conversion from refitting.

## Progress

### Completed

- Added direct-conversion validation for SGP4-compatible
  `MEAN_ELEMENT_THEORY` values.
- Direct conversion now rejects non-SGP4 theories with an actionable message
  naming the declared theory and pointing to `--refit-sgp4`.
- Direct conversion now rejects missing TLE parameters before output is
  written.
- Preserved direct SGP4-compatible conversion behavior without fabricated fit
  diagnostics.
- Added regression coverage for early rejection and output non-creation.
- Added `--refit-sgp4`, `--fit-span`, source provenance, and fit-report options.
- Connected refitting to the existing OMM propagators and shared SGP4/TLE fit
  implementation; reports identify the source theory and SGP4 target.
- Preserved the no-new-runtime-dependencies objective.
- Added no runtime dependencies.

### Remaining work

- Verify the refit path with representative DSST, Brouwer, and other supported
  non-SGP4 OMM inputs.
- Add end-to-end regression coverage for successful refitting and report
  contents once a stable fixture is selected.
