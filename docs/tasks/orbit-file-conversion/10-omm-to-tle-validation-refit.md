# Task 10: Validate OMM-to-TLE input and document composed SGP4 refit

## Status

**In progress.** Direct OMM-to-TLE validation is implemented. Non-SGP4 input
is intentionally refit by composing the existing OMM propagation and OEM-to-
TLE tools; representative live verification of that pipeline remains.

## Goal

Prevent invalid direct OMM-to-TLE conversions and provide a documented,
model-aware path for converting non-SGP4 OMMs to TLEs.

## Additional objective

Do not add runtime dependencies or a second refitting implementation; reuse the
repository's existing propagation and OEM-to-TLE fitting tools.

## Scope

- Validate that direct `omm-to-tle` input declares an SGP4-compatible
  `MEAN_ELEMENT_THEORY` and contains the required TLE parameters.
- Reject DSST, Brouwer-Lyddane, and other non-SGP4 theories with a diagnostic
  naming the declared theory and explaining the incompatibility.
- Use the composed workflow for non-SGP4 input:
  `propagate-omm` → Cartesian OEM reference arc →
  `oem-to-tle` (which performs the SGP4-compatible fit).
- Carry the source theory, propagation settings, fit span, and residuals in the
  intermediate/output fit report where supported.
- Keep direct SGP4-compatible mapping free of fabricated fit diagnostics.

## Acceptance criteria

- Valid direct SGP4 mappings retain their current fields and produce valid TLEs.
- Invalid theories fail before writing output and identify the incompatibility.
- A supported non-SGP4 OMM can be propagated to a Cartesian OEM and then fitted
  to an SGP4-compatible TLE using existing commands.
- `omm-to-tle` does not expose a second direct `--refit-sgp4` implementation.
- Tests distinguish direct conversion from the composed refit workflow.

## Progress

### Completed

- Added direct-conversion validation for SGP4-compatible
  `MEAN_ELEMENT_THEORY` values.
- Direct conversion rejects non-SGP4 theories with an actionable message.
- Direct conversion rejects missing TLE parameters before output is written.
- Preserved direct SGP4-compatible conversion behavior without fabricated fit
  diagnostics.
- Removed the direct `--refit-sgp4` implementation, parser options, and tests.
- Documented the composed propagation-to-OEM-to-TLE workflow.

### Remaining work

- Verify the composed refit path with representative DSST, Brouwer, and other
  supported non-SGP4 OMM inputs.
- Add end-to-end report coverage for the composed path.

## Verification

The direct validation path is covered by the OMM-to-TLE focused tests. The
composed workflow should be verified with a representative non-SGP4 OMM and
checked for a Cartesian reference OEM, SGP4-compatible TLE output, source
provenance, fit span, and residual statistics.

## Acceptance evidence

- Focused OMM-to-TLE tests cover parser behavior, direct conversion, and early
  rejection without creating output.
- The repository's broader focused conversion verification is recorded in the
  task README; numerical live verification remains environment-dependent.
