# Task 2: Implement a shared numerical-propagator arc fitter

## Goal

Fit a target numerical propagator's Cartesian initial state, and optionally
supported physical parameters, to a reference OEM arc. This is the common
algorithm for OEM, OMM, and TLE input paths.

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
