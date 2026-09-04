# Task 4: Migrate OEM-to-OMM fitting to `--fit-model`

## Goal

Make OEM-to-OMM conversion explicitly select the target mean-element theory
and report the source history and fit quality.

## Additional objective

Do not add runtime dependencies; reuse the repository's existing libraries and
tooling.

## Scope

- Replace the primary `--mode` interface with
  `--fit-model {brouwer|dsst|sgp4}`.
- Retain `--mode` as a deprecated compatibility alias and map `--mode tle` to
  `--fit-model sgp4`.
- Derive `MEAN_ELEMENT_THEORY`; reject conflicting `--theory` values.
- Add `--source-model`, `--source-report`, and `--fit-report` handling.
- Record source OEM provenance, selected theory, fit span, sample information,
  and position/velocity residual statistics.

## Acceptance criteria

- Existing supported fit models continue to work under the new option.
- Deprecated invocations produce a clear warning and equivalent output.
- Conflicting theory/model combinations fail deterministically.
- Output comments and JSON reports contain enough information to distinguish
  SGP4, DSST, and Brouwer fits.
