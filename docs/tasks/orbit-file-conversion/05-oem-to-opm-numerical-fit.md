# Task 5: Add numerical fitting to OEM-to-OPM

## Status

**Complete for the current OEM-to-OPM scope.** Numerical fitting, fixed
propagator configuration, Cartesian OPM output, provenance/fit reports, and
human-readable diagnostics are implemented and tested. Live Tudat/SPICE
verification with representative long OEM arcs remains a follow-up validation
item.

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
- Numerical fitting is Cartesian-only: do not calculate or show osculating
  Keplerian elements or related derived quantities for the numerical path.
  Two-body output retains its existing Keplerian behavior.

## Completed implementation

- Added `--fit-model numerical` while retaining two-body as the default.
- Routed fitting through the shared numerical arc fitter with fixed user-
  supplied physical parameters.
- Added fit controls, force-model configuration, provenance, optional fit
  reports, and Cartesian initial-state output.
- Added verbose numerical summaries containing original/fitted initial states,
  RMS diagnostics, epoch velocity delta, propagation comparisons, and
  residual summary statistics.
- Added unit coverage for dispatch, output shape, and numerical-only summary
  behavior without adding runtime dependencies.

## Acceptance criteria

- Existing two-body behavior remains the default and its tests remain valid.
- Numerical output contains a usable Cartesian initial state and target-model
  configuration.
- Provenance and residual diagnostics are present in the OPM and optional
  report.
- Tests cover an OEM from a mean-element model, a numerical model, and an
  externally sourced/unknown-provenance OEM.
