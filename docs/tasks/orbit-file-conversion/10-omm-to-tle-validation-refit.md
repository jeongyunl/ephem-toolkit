# Task 10: Validate OMM-to-TLE input and document composed SGP4 refit

## Status

**In progress.** Direct OMM-to-TLE validation is implemented, and the selected
composed refit workflow has been verified with a DSST OMM. Remaining work is
limited to additional non-SGP4 theories when matching propagators become
available.

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

## Decision

Do not add a direct `--refit-sgp4` mode to `omm-to-tle`. Direct conversion is
reserved for SGP4-compatible OMMs. A non-SGP4 OMM is refitted by composing the
existing tools:

```text
propagate-omm → Cartesian OEM → oem-to-tle
```

This keeps propagation and SGP4 fitting in their existing implementations and
ensures the generated TLE is clearly treated as a new SGP4 model. The
intermediate OEM and companion fit report carry the source theory, fit span,
provenance, and residual information.

## Progress

### Completed

- Added direct-conversion validation for SGP4-compatible
  `MEAN_ELEMENT_THEORY` values.
- Direct conversion rejects non-SGP4 theories with an actionable message that
  names the declared theory and SGP4 incompatibility.
- Direct conversion rejects missing TLE parameters before output is written.
- Regression coverage now verifies missing TLE parameters are rejected before
  output is written for an otherwise SGP4-declared OMM.
- Preserved direct SGP4-compatible conversion behavior without fabricated fit
  diagnostics.
- Fallback-generated OEMs now record the declared source theory and the actual
  `two-body-kepler` propagation target in a portable provenance comment.
- Removed the direct `--refit-sgp4` implementation, parser options, and tests;
  no replacement refit mode is planned.
- Documented the composed propagation-to-OEM-to-TLE workflow.
- Added a DSST OMM integration fixture and verified the composed workflow,
  including a converged SGP4 fit report.
- DSST propagation OEMs now retain `source=OMM/DSST` and `target_model=DSST`
  provenance before they are consumed by the composed SGP4 refit.

### Remaining work

- Verify the composed refit path with additional non-SGP4 propagators if and
  when `propagate-omm` supports them. The current dispatch provides DSST and
  falls back to Kepler for other non-TLE theories; it does not provide a
  Brouwer propagator. The fallback is covered explicitly for Brouwer-declared
  input so it is not mistaken for a Brouwer-accurate refit.

## Verification

The direct validation path is covered by the OMM-to-TLE focused tests. The
composed workflow should be verified with a representative non-SGP4 OMM and
checked for a Cartesian reference OEM, SGP4-compatible TLE output, source
provenance, fit span, and residual statistics.

The direct-validation tests also verify that DSST and Brouwer-Lyddane OMMs are
rejected before the TLE output is created with diagnostics naming the declared
theory and SGP4 incompatibility. Refit-only options, including the removed
`--refit-sgp4` option, are not accepted by `omm-to-tle`.

Fallback dispatch tests verify that both generic non-DSST input and
Brouwer-declared input produce an OEM comment identifying the actual Kepler
fallback rather than implying Brouwer propagation.

The composed source-tree workflow was evaluated with the non-SGP4
`TEST-DSST_2020-001A.omm` fixture using a 2-hour arc and 5-minute output step:

```text
PYTHONPATH=src python -m ephem_toolkit.propagate_omm \
  tests/ephem_toolkit/oem_to_tle/data/TEST-DSST_2020-001A.omm \
  --duration 2h --step 5m \
  --output /tmp/dsst-reference.oem
PYTHONPATH=src python -m ephem_toolkit.oem_to_tle \
  /tmp/dsst-reference.oem --fit-span 2h \
  --source-model dsst --fit-report /tmp/dsst-reference.fit.json \
  --output /tmp/dsst-composed.tle
```

Result: 25 reference states, valid TLE output, and a `converged` fit report
with approximately `11 km` position RMS and `17 km` maximum position
residual. The residual is expected to be larger than the SGP4-to-SGP4
composition because the source DSST history is being fit to a different SGP4
model. The generated OEM uses `EME2000` while retaining `UTC`; the source OMM
uses `ICRF`. The bare `oem-to-tle` executable was not installed in the
evaluation shell, so the source-tree module entry point was used.

The same workflow with a 10-minute arc failed because the fitted mean-motion
first derivative could not be represented in the fixed-width TLE field. This
is a TLE formatting/fit-span limitation; the 2-hour DSST evaluation completed
successfully without restoring a direct refit implementation.

## Acceptance evidence

- Focused OMM-to-TLE tests cover parser behavior, direct conversion, rejection
  of DSST and Brouwer-Lyddane theories, rejection of the removed direct-refit
  option, and early rejection without creating output.
- The composed integration test checks the intermediate OEM, generated TLE,
  convergence, source/target provenance, frame/time provenance, fit span,
  record count, and residuals.
- The repository's broader focused conversion verification is recorded in the
  task README; numerical live verification remains environment-dependent.
