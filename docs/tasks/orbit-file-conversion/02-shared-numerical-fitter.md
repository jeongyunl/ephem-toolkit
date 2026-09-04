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
- Added a propagator-factory adapter so the optimizer can consume the existing
  `propagate_to` interface without importing or duplicating a propagation
  engine.
- Replaced fixed-index residual sampling with elapsed-time-based selection so
  irregularly sampled OEM arcs honor `fit-step` and `fit-span` correctly.
- Added a lazy factory for the existing `core.propagator.numerical` API;
  numerical-engine imports occur only when fitting is invoked, while tests can
  continue using injected mock factories.
- Added force-enable validation: drag-coefficient fitting requires drag and
  SRP-coefficient fitting requires SRP to be enabled in the fit configuration.
- Added optional six-component optimizer bounds with validation and clipping of
  state updates.
- Added coverage for the explicit opt-out path where all six initial-state
  components, including position, are optimized.
- Added reference-arc validation for finite Cartesian values and strictly
  increasing epochs.
- Added optimizer initial-state validation for six finite Cartesian values.
- Corrected convergence reporting so a zero optimizer step is not considered
  converged when residuals remain nonzero and do not improve.
- Explicitly reject drag/SRP parameter fitting in the current optimizer until
  a parameterized propagator callback is available, avoiding silent omission
  of requested fit parameters.
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
- Connect the factory and optimizer to conversion CLI paths, including force
  model configuration and physical-parameter fitting.
- Add the corresponding force-model CLI options and map them into this
  configuration.
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
