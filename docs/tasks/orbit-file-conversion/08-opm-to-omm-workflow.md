# Task 8: Add the composed OPM-to-OMM workflow

## Goal

Provide one conversion command that composes OPM propagation and mean-element
fitting while exposing both model choices.

## Scope

- Implement `opm-to-omm`.
- Select the intermediate OEM path as two-body or numerical.
- Require explicit target mean-element fitting theory and use the shared
  `--fit-model` vocabulary for it.
- Propagate, fit, and report provenance for both stages, including settings,
  fit span, and residuals.
- Preserve output metadata required by the OMM while documenting information
  that cannot be retained.

## Acceptance criteria

- The command supports both intermediate propagation models and all applicable
  target mean-element theories.
- It cannot label a result with a theory that was not used by the fitter.
- The output records intermediate propagation provenance and mean-element fit
  diagnostics separately.
- End-to-end tests cover two-body and numerical compositions.
