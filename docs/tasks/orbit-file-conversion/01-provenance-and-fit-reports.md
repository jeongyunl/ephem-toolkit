# Task 1: Define provenance and fit-report handling

## Goal

Make generated CCSDS products explain which source model produced the input
history and which model or theory produced the output. Make fit diagnostics
available even when the output format cannot carry them.

## Scope

- Emit portable `COMMENT` entries using the `EPHEMERIS_PROVENANCE` and
  `EPHEMERIS_FIT` forms specified in `ORBIT_FILE_CONVERSION.md`.
- Preserve source frame and time system, target gravity/force model,
  integrator and step settings, estimated parameters, fit span, sample count,
  residual RMS/maxima, and convergence status where applicable.
- Add JSON `--fit-report <path|->` output for the conversion commands listed in
  the source document.
- For TLE output, write provenance to the fit report and/or preceding OMM/OEM;
  do not try to add arbitrary fields to the TLE itself.
- Preserve portable comments when structured OPM `USER_DEFINED_EPHEMERIS_*`
  values are also used.

## Acceptance criteria

- Generated OEM, OMM, and OPM files contain source/target model provenance when
  the conversion is not model-neutral.
- Fit reports are valid, documented JSON and include configuration, optimized
  parameters, residual statistics, and convergence status.
- Direct lossless TLE↔SGP4-compatible OMM mappings do not require a fabricated
  fit report.
- Tests cover path output, stdout output (`-`), missing provenance, and TLE
  companion-report behavior.
