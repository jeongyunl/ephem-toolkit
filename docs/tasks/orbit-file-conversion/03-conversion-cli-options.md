# Task 3: Align conversion CLI options

## Goal

Give conversion commands a consistent distinction between input provenance,
transformation settings, and output settings.

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
