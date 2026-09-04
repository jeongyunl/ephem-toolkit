# Task 2: Implement a shared numerical-propagator arc fitter

## Goal

Fit a target numerical propagator's Cartesian initial state to a reference OEM
arc using user-supplied fixed physical parameters. This is the common
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
- Physical parameters are fixed user inputs; they are validated but never
  varied by the optimizer.
- Added `fixed_parameter_values()` to expose selected user inputs for
  propagator construction and fit reports without treating them as optimizer
  variables.
- Added `to_report_dict()` to serialize the complete fit configuration,
  including fixed physical parameters, for reproducible reports and future CLI
  integration.
- Connected configuration serialization to the shared fit-report writer, so
  future numerical conversion paths can pass the configuration object directly.
- Added configuration plumbing from existing `propagate-orbit`-style options,
  preserving user-supplied drag/SRP coefficients as fixed values.
- Extended that mapping to include spacecraft mass/area, Earth gravity,
  integrator settings, and third-body switches for reproducible force-model
  construction.
- Added a consistency check that requires the propagator's drag/SRP values to
  exactly match the user-supplied fixed fit parameters.
- Added a lazy `NumericalPropagatorConfig` bridge that carries the complete
  fixed force-model configuration into the existing propagation API.
- Added failure-path coverage requiring mass, area, gravity, and integrator
  settings before a numerical propagator configuration can be constructed.
- Added `oem-to-opm` parser options for fit step, observables, residual weights,
  and fixed-parameter selection; execution remains gated pending force-model
  wiring.
- Added CLI validation requiring strictly positive fit-step and residual-weight
  values.
- Added an adapter that maps parsed OEM-to-OPM fit controls into
  `NumericalFitConfig`, preserving model, span, sampling, observables, weights,
  and fixed-parameter selection.
- Added OEM-to-OPM CLI inputs for fixed spacecraft mass, area, drag/SRP switches,
  and drag/SRP coefficients; these values are mapped as propagation inputs and
  are never optimizer variables.
- Aligned numerical-fit configuration and OEM-to-OPM physical-parameter defaults
  with `propagate-orbit`: mass 30 kg, area 0.18 m², drag/SRP enabled, and
  coefficients 2.2/1.2. The shared configuration also uses its gravity,
  integrator, third-body, and step-size defaults.
- Added the `oem-to-opm --fit-model {two-body|numerical}` parser contract;
  `two-body` remains the default.
- Connected `oem-to-opm --fit-model numerical` to the shared numerical fitter:
  it builds the fixed-parameter propagator configuration, adapts the existing
  numerical propagator to the optimizer callback, fits the OEM arc, converts
  the fitted Cartesian state to OPM Keplerian elements, and records numerical
  fit provenance/configuration. The output comparison table remains specific
  to two-body mode; numerical residual diagnostics are recorded in the fit
  report.
- Made initial-position preservation an explicit default: the residual helper
  anchors the propagated epoch position to the first reference OEM position
  while leaving the epoch velocity available for fitting.

The optimizer and callback adapters are implemented, but conversion CLI wiring
and concrete force-model configuration are still pending.

### Verification

The focused numerical-fit and conversion suites pass; see the latest test
result recorded in the orbit-conversion task README.

### Remaining work

- Verify live Tudat-backed execution with representative OEM data and the
  project's available SPICE kernels.
- Extend numerical residual comparison output if a human-readable numerical
  propagation table is required in addition to fit-report diagnostics.

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
- Reject a requested physical parameter when its force is disabled or its value
  is missing, and reject fewer than two reference states.
- Return reusable fit diagnostics for provenance and `--fit-report` output.

## Acceptance criteria

- The fitter is callable by all three input paths without duplicated fitting
  algorithms.
- Default and strict/disabled force-model cases are tested.
- Invalid model, observable, parameter, weight, span, and sample-count inputs
  fail with actionable diagnostics.
- A known reference arc produces a bounded residual and a report containing the
  fitted state, configuration, convergence, and RMS/max residuals.
