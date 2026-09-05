# Task 8: Add the composed OPM-to-OMM workflow

## Status

**Complete as a composed workflow.** Both existing OPM-to-OEM propagation
paths have been verified with `oem-to-omm`, without adding an `opm-to-omm`
implementation that duplicates those lower-level tools. Remaining work is
aggregating complete propagation provenance for production workflows.

## Goal

Provide a documented workflow that composes OPM propagation and mean-element
fitting while exposing both intermediate-model choices.

## Additional objective

Do not add runtime dependencies; reuse the repository's existing libraries and
tooling.

## Scope

- Compose the existing propagation and fitting commands; do not add a duplicate
  `opm-to-omm` wrapper.
- Select the intermediate OEM path as two-body or numerical.
- Require explicit target mean-element fitting theory and use the shared
  `--fit-model` vocabulary for it.
- Propagate, fit, and report provenance for both stages, including settings,
  fit span, and residuals.
- Preserve output metadata required by the OMM while documenting information
  that cannot be retained.

## Acceptance criteria

- The documented workflow supports both intermediate propagation models and
  all applicable target mean-element theories.
- It cannot label a result with a theory that was not used by the fitter.
- The output records intermediate propagation provenance and mean-element fit
  diagnostics separately.
- End-to-end tests cover two-body and numerical compositions.

## Progress

- Verified the two-body composition with `propagate-kepler` followed by
  `oem-to-omm --fit-model dsst` over a 2-hour, 5-minute-sampled arc.
- Verified a converged DSST fit report with 25 reference states and approximately
  `216.5 m` position RMS.
- Reused the existing `propagate-orbit` path as the numerical composition;
  numerical live verification completed with a converged 2-hour fit over 27
  reference records.
- Deferred a dedicated wrapper because it would duplicate the existing tools.
- End-to-end tests cover both two-body and numerical intermediate OEM paths.
- Final fit reports now preserve the intermediate OEM `COMMENT` records,
  including the two-body model label or numerical force/integrator settings.
- Generated OMMs also retain those intermediate comments alongside the target
  mean-element fit comments.

### Remaining work

- Verify additional production workflows that use the shared report path; the
  current OPM-to-OMM compositions now carry intermediate model/configuration
  comments into the final report.
