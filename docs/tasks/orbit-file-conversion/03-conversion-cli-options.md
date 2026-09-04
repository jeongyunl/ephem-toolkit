# Task 3: Align conversion CLI options

## Status

**Complete for the current conversion commands.** The canonical fit-model
contract, deprecated mode compatibility, wrapper delegation, and unsupported
option handling are implemented and tested for the existing OEM-to-OMM,
OEM-to-TLE, and OMM-to-TLE paths. Future refit workflows will add their own
model-specific options.

## Goal

Give conversion commands a consistent distinction between input provenance,
transformation settings, and output settings.

## Additional objective

Do not add runtime dependencies; reuse the repository's existing libraries and
tooling.

## Scope

- Add shared `--source-model`, `--source-report`, `--fit-span`, `--output`,
  object metadata, and `--fit-report` options where specified in the source
  document.
- Add model-specific `--fit-model` choices:
  `brouwer|dsst|sgp4` for mean-element fitting and
  `two-body|numerical` for OPM initial-state fitting.
- Keep `--fit-method` reserved for a future optimizer choice; do not add
  generic `--fit` or `--propagator` aliases.
- During migration, retain `--mode` as a deprecated alias, mapping `tle` to
  `sgp4`.
- Derive OMM `MEAN_ELEMENT_THEORY` from `--fit-model` and reject a conflicting
  `--theory` value.
- Keep wrapper help synchronized with delegated commands and reject unsupported
  options explicitly.

## Acceptance criteria

- Every command accepts only the options assigned to it in the proposal table.
- Help text shows the shared grouping and model-specific choices accurately.
- Deprecated `--mode` behavior and conflicting `--theory` behavior are tested.
- Unsupported combinations fail before conversion work begins.

## Progress

### Completed

- Added `--fit-model {brouwer,dsst,sgp4}` to OEM-to-OMM.
- Retained `--mode` as a deprecated alias, mapping `tle` to `sgp4`, with a
  deprecation warning and conflict validation when both options are supplied.
- Added model/theory consistency validation before conversion work begins.
- Updated OEM-to-TLE delegation to use canonical `--fit-model sgp4`.
- Added parser and wrapper regression tests.
- Preserved the repository-wide objective of adding no runtime dependencies.

### Remaining work

- Apply the same option-contract rules to proposed conversion commands when
  they are implemented.
