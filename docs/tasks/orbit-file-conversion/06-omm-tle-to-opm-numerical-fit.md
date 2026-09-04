# Task 6: Add OMM/TLE-to-OPM numerical fitting

## Status

**In progress.** Both wrapper commands are registered and delegate reference-
arc fitting to the shared OEM-to-OPM numerical workflow. Live propagation and
end-to-end output verification remain.

## Goal

Provide convenience wrappers that generate a source-model reference arc and
fit the requested numerical propagator using the common OEM-to-OPM fitter.

## Additional objective

Do not add runtime dependencies; reuse the repository's existing libraries and
tooling.

## Scope

- Implement `omm-to-opm --fit-model numerical`.
- Implement `tle-to-opm --fit-model numerical`.
- For OMM, propagate using its declared `MEAN_ELEMENT_THEORY` before fitting.
- For TLE, propagate with SGP4 before fitting and identify the reference arc as
  SGP4/TEME/UTC.
- Expose the numerical force-model, fit, metadata, and fit-report options.
- Store the fitted Cartesian state in the OPM; treat optional Keplerian fields
  as osculating derived fields, not source mean elements.

## Acceptance criteria

- Both wrappers invoke the shared fitter rather than maintaining separate fit
  implementations.
- OMM theory dispatch rejects unsupported or missing theories clearly.
- TLE output provenance identifies SGP4 and the fitted target model.
- Reports include source theory/model, target force model, fit span, settings,
  residuals, and convergence status.

## Progress

### Completed

- Registered `omm-to-opm` and `tle-to-opm` console commands.
- Added numerical wrapper entry points that generate source-model OEM arcs and
  delegate fitting/output to the existing OEM-to-OPM implementation.
- Passed fit-span, force-model, metadata, and report options through the
  shared parser/delegation boundary.
- Identified OMM source theory and TLE source provenance as `sgp4`.
- Added parser/delegation regression tests without adding runtime dependencies.

### Remaining work

- Verify both wrappers with live Tudat-backed propagation and representative
  OMM/TLE fixtures.
- Confirm complete source/target configuration and residual content in wrapper
  fit reports.
