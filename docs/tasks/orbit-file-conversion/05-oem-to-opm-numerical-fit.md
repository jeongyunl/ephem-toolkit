# Task 5: Add numerical fitting to OEM-to-OPM

## Goal

Allow an OEM to produce an OPM initial state for a configured numerical
propagator, while retaining the current two-body fit as the default.

## Additional objective

Do not add runtime dependencies; reuse the repository's existing libraries and
tooling.

## Scope

- Add `oem-to-opm --fit-model numerical` and retain
  `--fit-model two-body` as the default.
- Route numerical fitting through the shared arc fitter.
- Add fit span, fit step, observables, component weights, user-supplied fixed
  physical parameters, force-model options, and fit-report output. Physical
  parameters must not be estimated.
- Preserve input OEM provenance in OPM comments and identify whether the OPM
  state came from a two-body fit, numerical fit, or supported reconstruction.
- Keep fitted Keplerian fields clearly labeled as derived/osculating values;
  do not present them as source mean elements.

## Acceptance criteria

- Existing two-body behavior remains the default and its tests remain valid.
- Numerical output contains a usable Cartesian initial state and target-model
  configuration.
- Provenance and residual diagnostics are present in the OPM and optional
  report.
- Tests cover an OEM from a mean-element model, a numerical model, and an
  externally sourced/unknown-provenance OEM.
