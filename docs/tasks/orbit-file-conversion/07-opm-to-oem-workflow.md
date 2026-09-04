# Task 7: Add the model-aware OPM-to-OEM workflow

## Goal

Make OPM-to-OEM conversion explicit about whether it generates a two-body
Keplerian history or a numerical force-model history.

## Additional objective

Do not add runtime dependencies; reuse the repository's existing libraries and
tooling.

## Scope

- Support the existing two-body path from OPM osculating elements.
- Support the numerical path from the OPM Cartesian state using the configured
  gravity, force, and integrator models.
- Add a propagator-matched arc-fit workflow where a reference OEM and target
  numerical configuration require an initial-state fit.
- Support fit span, sample spacing, position/velocity weights, and user-supplied
  fixed physical parameters where fitting is requested; never estimate those
  parameters.
- Write `target_model=two-body-kepler` or `target_model=numerical` provenance,
  including numerical settings and fit residuals when applicable.

## Acceptance criteria

- The CLI makes the two-body versus numerical path unambiguous.
- Generated OEMs preserve input identity/frame/time metadata and record the
  selected model.
- Numerical and fit configurations are reproducible from the output comments
  and optional report.
- Tests demonstrate that the two paths produce distinguishable, correctly
  labeled histories.
