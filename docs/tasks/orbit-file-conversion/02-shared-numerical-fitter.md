# Task 2: Implement a shared numerical-propagator arc fitter

## Goal

Fit a target numerical propagator's Cartesian initial state, and optionally
supported physical parameters, to a reference OEM arc. This is the common
algorithm for OEM, OMM, and TLE input paths.

## Additional objectives

- Do not add runtime dependencies. Reuse the repository's existing NumPy-based
  numerical tools and propagation interfaces.
- Keep the optimizer and residual construction independently unit-testable
  without requiring the numerical propagation engine during tests.

## Progress

### Completed

- Added [`src/ephem_toolkit/oem_to_opm/fit_numerical.py`](../../../src/ephem_toolkit/oem_to_opm/fit_numerical.py)
  with shared fit configuration and validation for reference-state count,
  six-component Cartesian states, fit model, observables, weights, span, step,
  and supported parameter selections.
- Added validation tests in
  [`tests/ephem_toolkit/oem_to_opm/test_fit_numerical.py`](../../../tests/ephem_toolkit/oem_to_opm/test_fit_numerical.py).
- Added weighted position/state residual construction and residual diagnostics
  behind a propagator callback, keeping the implementation independent of the
  numerical propagation engine.
- Added a dependency-free NumPy Gauss–Newton initial-state optimizer. With the
  default position constraint it varies only initial velocity and returns
  convergence and residual diagnostics.
- Made initial-position preservation an explicit default: the residual helper
  anchors the propagated epoch position to the first reference OEM position
  while leaving the epoch velocity available for fitting.

This is the validation boundary only. It does not yet run an optimizer or
connect to the numerical propagator.

### Verification

The focused numerical-fit and conversion suites pass; see the latest test
result recorded in the orbit-conversion task README.

### Remaining work

- Connect `NumericalFitConfig` to `core.propagator.numerical`.
- Connect the optimizer to the numerical propagator.
- Preserve the initial position as a hard constraint in the optimizer and
  document that behavior in fit reports.
- Add force-model and physical-parameter validation, diagnostics, and wrapper
  integration.

## Scope

- Accept a reference OEM with at least two states.
- Support `two-body` and `numerical` fit models, retaining two-body as the
  existing default where applicable.
- Support fit span, sample spacing, position-only or full-state observables,
  position/velocity weights, and the supported parameter sets:
  `initial-state`, `initial-state,drag-coeff`, and
  `initial-state,srp-coeff`.
- Reuse `propagate-orbit` force-model options: gravity, drag, drag coefficient
  and area, SRP, SRP coefficient, integrator, and integrator step size.
- Reject parameter estimation when its force is disabled, and reject fewer
  than two reference states.
- Return reusable fit diagnostics for provenance and `--fit-report` output.

## Acceptance criteria

- The fitter is callable by all three input paths without duplicated fitting
  algorithms.
- Default and strict/disabled force-model cases are tested.
- Invalid model, observable, parameter, weight, span, and sample-count inputs
  fail with actionable diagnostics.
- A known reference arc produces a bounded residual and a report containing the
  fitted state, configuration, convergence, and RMS/max residuals.
