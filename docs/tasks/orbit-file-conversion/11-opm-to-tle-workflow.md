# Task 11: Add the composed OPM-to-TLE workflow

## Goal

Provide a model-aware OPM-to-TLE conversion that propagates an OPM, fits
SGP4-compatible mean elements, and records the approximation.

## Scope

- Implement `opm-to-tle`.
- Select either the intermediate two-body or numerical OEM propagation path.
- Fit SGP4-compatible mean elements before TLE formatting.
- Support fit span and the relevant propagation/fit options.
- Write a companion fit report containing the selected path, source OPM
  provenance, SGP4 fit settings, and propagation and fitting residuals.

## Acceptance criteria

- Both intermediate paths are available and clearly labeled.
- The generated TLE is valid and is documented as a new SGP4 model.
- The report separates propagation settings from mean-element fit settings and
  includes residual statistics for both stages.
- End-to-end tests cover both paths and verify that unsupported output-theory
  combinations fail explicitly.
