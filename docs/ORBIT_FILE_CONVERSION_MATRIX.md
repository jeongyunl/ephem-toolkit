# Orbit-file conversion matrix

This matrix is the route-level index for the conversion guidance in
[`ORBIT_FILE_CONVERSION.md`](ORBIT_FILE_CONVERSION.md). It describes the
current command set and composed workflows; it is not a list of future
commands.

The rows describe directed workflows, not merely format pairs. A route with
different propagation or fitting models has separate rows because the model,
accuracy, metadata, and provenance behavior are materially different.

Specific theory-qualified products use the name pattern `OMM(2B)`,
`OMM(BROUWER)`, `OMM(DSST)`, `OMM(SGP4)`, `OPM(2B)`, and `OPM(NUM)`
whenever the model is relevant. Generic `OMM` and `OPM` continue to describe
the format family.

## Route matrix

| Source | Target | Variant | Type | Workflow / command | Source representation and model | Intermediate | Target model / theory | Key inputs and options | Status / task |
|---|---|---|---|---|---|---|---|---|---|
| OMM(2B) | OEM | Two-body | Propagation | `propagate-omm` | Mean elements; two-body Kepler theory | — | Two-body Cartesian ephemeris or Kepler fallback | `--duration`, `--step` | Existing theory-specific path |
| OMM(BROUWER) | OEM | Brouwer | Propagation | `propagate-omm` | Mean elements; Brouwer theory | — | Brouwer Cartesian ephemeris or Kepler fallback | `--duration`, `--step` | Existing theory-specific path |
| OMM(DSST) | OEM | DSST | Propagation | `propagate-omm` | Mean elements; DSST theory | — | Matching mean-element propagator | `--duration`, `--step` | Existing theory-specific path |
| OMM(SGP4) | OEM | SGP4 | Propagation | `propagate-omm` | Mean elements; `MEAN_ELEMENT_THEORY=SGP4` | — | SGP4 Cartesian ephemeris | `--duration`, `--step` | Existing |
| OMM(2B) | OPM(2B) | Two-body fit | Composed | `propagate-omm` → `oem-to-opm` | Mean-element source theory | OEM | Two-body osculating approximation | Propagation settings and fit span | Existing/composed |
| OMM(BROUWER) | OPM(2B) | Two-body fit | Composed | `propagate-omm` → `oem-to-opm` | Mean-element source theory | OEM | Two-body osculating approximation | Propagation settings and fit span | Existing/composed |
| OMM(DSST) | OPM(2B) | Two-body fit | Composed | `propagate-omm` → `oem-to-opm` | Mean-element source theory | OEM | Two-body osculating approximation | Propagation settings and fit span | Existing/composed |
| OMM(SGP4) | OPM(2B) | Two-body fit | Composed | `propagate-omm` → `oem-to-opm` | Mean-element source theory | OEM | Two-body osculating approximation | Propagation settings and fit span | Existing/composed |
| OMM(2B) | OPM(NUM) | Numerical initial-state fit | Composed fitting | `omm-to-opm --fit-model numerical` | Mean-element source theory | Reference OEM | Numerical Cartesian initial state | Target force model, fit settings, fixed physical parameters | Existing composition |
| OMM(BROUWER) | OPM(NUM) | Numerical initial-state fit | Composed fitting | `omm-to-opm --fit-model numerical` | Mean-element source theory | Reference OEM | Numerical Cartesian initial state | Target force model, fit settings, fixed physical parameters | Existing composition |
| OMM(DSST) | OPM(NUM) | Numerical initial-state fit | Composed fitting | `omm-to-opm --fit-model numerical` | Mean-element source theory | Reference OEM | Numerical Cartesian initial state | Target force model, fit settings, fixed physical parameters | Existing composition |
| OMM(SGP4) | OPM(NUM) | Numerical initial-state fit | Composed fitting | `omm-to-opm --fit-model numerical` | Mean-element source theory | Reference OEM | Numerical Cartesian initial state | Target force model, fit settings, fixed physical parameters | Existing composition |
| OMM(2B) | TLE | Composed SGP4 refit | Propagation/fitting | `propagate-omm` → OEM → `oem-to-tle` | Mean-element source theory; unsupported theories use labeled Kepler fallback | Reference OEM | SGP4 mean elements/TLE | Propagation settings, fit span, fit report | Existing composition |
| OMM(BROUWER) | TLE | Composed SGP4 refit | Propagation/fitting | `propagate-omm` → OEM → `oem-to-tle` | Mean-element source theory; unsupported theories use labeled Kepler fallback | Reference OEM | SGP4 mean elements/TLE | Propagation settings, fit span, fit report | Existing composition |
| OMM(DSST) | TLE | Composed SGP4 refit | Propagation/fitting | `propagate-omm` → OEM → `oem-to-tle` | Mean-element source theory; unsupported theories use labeled Kepler fallback | Reference OEM | SGP4 mean elements/TLE | Propagation settings, fit span, fit report | Existing composition |
| OMM(SGP4) | TLE | Direct SGP4 mapping | Direct mapping | `omm-to-tle` | SGP4-compatible mean elements | — | SGP4 TLE | Required TLE fields; theory validation | Existing |
| OPM(2B) | OEM | Two-body Keplerian | Propagation | `propagate-kepler` | Osculating Cartesian/Keplerian state | — | Two-body Keplerian | `--duration`, `--step` | Existing |
| OPM(2B) | OMM(2B) | Two-body intermediate | Composed | `propagate-kepler` → `oem-to-omm` | Osculating state | Two-body OEM | Selected mean-element theory | Duration, step, fit model/span | Existing composition |
| OPM(2B) | OMM(BROUWER) | Two-body intermediate | Composed | `propagate-kepler` → `oem-to-omm` | Osculating state | Two-body OEM | Selected mean-element theory | Duration, step, fit model/span | Existing composition |
| OPM(2B) | OMM(DSST) | Two-body intermediate | Composed | `propagate-kepler` → `oem-to-omm` | Osculating state | Two-body OEM | Selected mean-element theory | Duration, step, fit model/span | Existing composition |
| OPM(2B) | OMM(SGP4) | Two-body intermediate | Composed | `propagate-kepler` → `oem-to-omm` | Osculating state | Two-body OEM | Selected mean-element theory | Duration, step, fit model/span | Existing composition |
| OPM(NUM) | OEM | Numerical force model | Propagation | `propagate-orbit` | Osculating Cartesian state | — | Configured numerical model | `--duration`, force, gravity, integrator options | Existing |
| OPM(NUM) | OMM(2B) | Numerical intermediate | Composed | `propagate-orbit` → `oem-to-omm` | Osculating Cartesian state | Numerical OEM | Selected mean-element theory | Force model, integrator, fit model/span | Existing composition |
| OPM(NUM) | OMM(BROUWER) | Numerical intermediate | Composed | `propagate-orbit` → `oem-to-omm` | Osculating Cartesian state | Numerical OEM | Selected mean-element theory | Force model, integrator, fit model/span | Existing composition |
| OPM(NUM) | OMM(DSST) | Numerical intermediate | Composed | `propagate-orbit` → `oem-to-omm` | Osculating Cartesian state | Numerical OEM | Selected mean-element theory | Force model, integrator, fit model/span | Existing composition |
| OPM(NUM) | OMM(SGP4) | Numerical intermediate | Composed | `propagate-orbit` → `oem-to-omm` | Osculating Cartesian state | Numerical OEM | Selected mean-element theory | Force model, integrator, fit model/span | Existing composition |
| TLE | OEM | SGP4 | Propagation | `propagate-tle` or `tle-to-omm` → `propagate-omm` | TLE mean elements; SGP4/TEME/UTC | Optional OMM | SGP4 Cartesian ephemeris | `--duration`, `--step` | Existing |
| TLE | OMM(SGP4) | Direct SGP4 mapping | Direct mapping | `tle-to-omm` | SGP4 mean elements | — | SGP4 mean elements | TLE fields and metadata | Existing |
| TLE | OPM(2B) | Two-body fit | Composed | `propagate-tle` → `oem-to-opm` | SGP4 mean elements | SGP4 OEM | Two-body osculating approximation | Propagation settings and fit span | Existing/composed |
| TLE | OPM(NUM) | Numerical initial-state fit | Composed fitting | `tle-to-opm --fit-model numerical` | SGP4 mean elements | SGP4 reference OEM | Numerical Cartesian initial state | Target force model, fit settings, fixed physical parameters | Existing composition |
| OEM | OMM(2B) | Two-body fit | Fitting | `oem-to-omm --fit-model two-body` | Cartesian history; source provenance required when known | — | Two-body mean elements | `--fit-span`, source metadata/report | Existing |
| OEM | OMM(BROUWER) | Brouwer fit | Fitting | `oem-to-omm --fit-model brouwer` | Cartesian history; source provenance required when known | — | Brouwer mean elements | `--fit-span`, source metadata/report | Existing |
| OEM | OMM(DSST) | DSST fit | Fitting | `oem-to-omm --fit-model dsst` | Cartesian history; source provenance required when known | — | DSST mean elements | `--fit-span`, source metadata/report | Existing |
| OEM | OMM(SGP4) | SGP4 fit | Fitting | `oem-to-omm --fit-model sgp4` | Cartesian history; source provenance required when known | — | SGP4 mean elements | `--fit-span`, source metadata/report | Existing |
| OEM | OPM(2B) | Two-body fit | Fitting | `oem-to-opm --fit-model two-body` | Cartesian history | — | Two-body osculating state/elements | Fit span and source provenance | Existing |
| OEM | OPM(NUM) | Numerical initial-state fit | Fitting | `oem-to-opm --fit-model numerical` | Cartesian reference arc | — | Numerical Cartesian initial state | Fit span, position weighting, fixed physical parameters, force model | Existing |
| OEM | TLE | SGP4-compatible fit | Fitting/composed | `oem-to-tle` | Cartesian history; source provenance required when known | Intermediate OMM | SGP4 mean elements/TLE | `--fit-span`, TLE refinement, fit report | Existing |

## Data, provenance, and acceptance matrix

The following columns should be maintained for every route ID above. Keeping
these details separate from the route table makes the primary matrix usable in
reviews while preserving the complete conversion contract.

| Column | Required content |
|---|---|
| Required inputs | Required CCSDS fields, TLE parameters, source provenance, minimum number of states, and user-supplied physical parameters |
| Frame and time handling | Input/output frame, center, time system, epoch behavior, and any required conversion |
| Preserved metadata | Fields copied unchanged, such as object identity, center, frame, and time system where supported |
| Derived or transformed data | Fitted elements, propagated states, generated theory labels, or converted metadata |
| Lost data | Time series, covariance, maneuvers, spacecraft parameters, TLE-only fields, or comments that the target cannot represent |
| Provenance/report requirement | Portable `COMMENT` records, companion `--fit-report`, or no additional report for a lossless direct mapping |
| Fit configuration | Fit model, fit span, sample spacing, position weighting, optimizer settings, and fixed physical parameters |
| Accuracy limitation | Model mismatch, arc-length validity, propagation error, TLE fixed-width precision, and whether the conversion is lossless |
| Validation | Theory compatibility, conflicting option checks, required fields, frame/time validity, and minimum sample count |
| Verification evidence | Focused tests, integration tests, live Tudat/SPICE checks, warnings, and unresolved environment limitations |

## Cross-cutting rules

- An OEM state history is not model-neutral. Record its source propagator or
  orbit-determination origin whenever known.
- `--fit-model` identifies the target fitted model. Derive OMM
  `MEAN_ELEMENT_THEORY` from it rather than accepting an inconsistent free
  theory label.
- A fit produces a model-specific approximation over a stated arc; it is not
  a lossless relabeling of the source orbit.
- Physical parameters such as drag and solar-radiation coefficients are
  user-supplied fixed inputs. They may be validated and recorded but must not
  be estimated by the optimizer.
- Direct OMM-to-TLE conversion requires an SGP4-compatible OMM. Other theories
  must be rejected or explicitly processed through the composed SGP4 refit
  route.
- TLE outputs cannot carry arbitrary provenance. Use a companion fit report or
  preserve the information in the preceding CCSDS file.

## Status and verification notes

The route statuses describe the current command set. “Existing composition”
means that the route is performed by chaining exposed commands; it does not
imply a dedicated wrapper command or complete live force-model accuracy
verification.

Focused source-tree tests cover the conversion and fitting implementations.
Representative live Tudat/SPICE verification remains environment-dependent
for some numerical workflows.
