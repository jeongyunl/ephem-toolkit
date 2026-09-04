# Task 10: Validate OMM-to-TLE input and add SGP4 refit

## Goal

Prevent invalid direct OMM-to-TLE conversions and provide an explicit path for
converting non-SGP4 OMMs through a new SGP4 fit.

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
