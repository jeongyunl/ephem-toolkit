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

The composed source-tree workflow was evaluated with the SGP4-backed
`ISS-ZARYA_1998-067A.omm` fixture using a 2-hour arc and 5-minute output step:

```text
PYTHONPATH=src python -m ephem_toolkit.propagate_omm \
  tests/data/ISS-ZARYA_1998-067A.omm --duration 2h --step 5m \
  --output /tmp/omm-reference-2h.oem
PYTHONPATH=src python -m ephem_toolkit.oem_to_tle \
  /tmp/omm-reference-2h.oem --fit-span 2h \
  --source-model sgp4 --fit-report /tmp/omm-reference-2h.fit.json \
  --output /tmp/omm-composed-2h.tle
```

Result: 25 reference states, valid TLE output, and a `converged` fit report
with six iterations, approximately `0.017 m` position RMS, and approximately
`0.035 m` maximum position residual. The bare `oem-to-tle` executable was not
installed in the evaluation shell, so the source-tree module entry point was
used.

The same workflow with a 10-minute arc failed because the fitted mean-motion
first derivative could not be represented in the fixed-width TLE field. This
is a TLE formatting/fit-span limitation, not a reason to restore a direct
refit implementation.

## Acceptance evidence

- Focused OMM-to-TLE tests cover parser behavior, direct conversion, and early
  rejection without creating output.
- The repository's broader focused conversion verification is recorded in the
  task README; numerical live verification remains environment-dependent.
