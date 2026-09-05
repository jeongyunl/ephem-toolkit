# Orbit-file conversion matrix

This matrix is the route-level index for the conversion guidance in
[`ORBIT_FILE_CONVERSION.md`](ORBIT_FILE_CONVERSION.md). It describes the
current command set and composed workflows; it is not a list of future
commands.

The rows describe directed workflows, not merely format pairs. A route with
different propagation or fitting models has separate rows because the model,
accuracy, metadata, and provenance behavior are materially different.

## Route matrix

| ID | Source | Target | Variant | Type | Workflow / command | Source representation and model | Intermediate | Target model / theory | Key inputs and options | Status / task |
|---|---|---|---|---|---|---|---|---|---|---|
| OMM-OEM-SGP4 | OMM | OEM | SGP4 | Propagation | `propagate-omm` | Mean elements; `MEAN_ELEMENT_THEORY=SGP4` | — | SGP4 Cartesian ephemeris | `--duration`, `--step` | Existing |
| OMM-OEM-DSST | OMM | OEM | DSST or declared theory | Propagation | `propagate-omm` | Mean elements; declared theory | — | Matching mean-element propagator | `--duration`, `--step` | Existing theory-specific path |
| OPM-OEM-2B | OPM | OEM | Two-body Keplerian | Propagation | `propagate-kepler` | Osculating Cartesian/Keplerian state | — | Two-body Keplerian | `--duration`, `--step` | Existing |
| OPM-OEM-NUM | OPM | OEM | Numerical force model | Propagation | `propagate-orbit` | Osculating Cartesian state | — | Configured numerical model | `--duration`, force, gravity, integrator options | Existing |
| TLE-OEM-SGP4 | TLE | OEM | SGP4 | Propagation | `propagate-tle` or `tle-to-omm` → `propagate-omm` | TLE mean elements; SGP4/TEME/UTC | Optional OMM | SGP4 Cartesian ephemeris | `--duration`, `--step` | Existing |
| OEM-OMM-SGP4 | OEM | OMM | SGP4 fit | Fitting | `oem-to-omm --fit-model sgp4` | Cartesian history; source provenance required when known | — | SGP4 mean elements | `--fit-span`, source metadata/report | Existing |
| OEM-OMM-BROUWER | OEM | OMM | Brouwer fit | Fitting | `oem-to-omm --fit-model brouwer` | Cartesian history; source provenance required when known | — | Brouwer mean elements | `--fit-span`, source metadata/report | Existing |
| OEM-OMM-DSST | OEM | OMM | DSST fit | Fitting | `oem-to-omm --fit-model dsst` | Cartesian history; source provenance required when known | — | DSST mean elements | `--fit-span`, source metadata/report | Existing |
| OPM-OMM-2B | OPM | OMM | Two-body intermediate | Composed | `propagate-kepler` → `oem-to-omm` | Osculating state | Two-body OEM | Selected mean-element theory | Duration, step, fit model/span | Existing composition |
| OPM-OMM-NUM | OPM | OMM | Numerical intermediate | Composed | `propagate-orbit` → `oem-to-omm` | Osculating Cartesian state | Numerical OEM | Selected mean-element theory | Force model, integrator, fit model/span | Existing composition |
| TLE-OMM-DIRECT | TLE | OMM | Direct SGP4 mapping | Direct mapping | `tle-to-omm` | SGP4 mean elements | — | SGP4 mean elements | TLE fields and metadata | Existing |
| OEM-OPM-2B | OEM | OPM | Two-body fit | Fitting | `oem-to-opm --fit-model two-body` | Cartesian history | — | Two-body osculating state/elements | Fit span and source provenance | Existing |
| OEM-OPM-NUM | OEM | OPM | Numerical initial-state fit | Fitting | `oem-to-opm --fit-model numerical` | Cartesian reference arc | — | Numerical Cartesian initial state | Fit span, position weighting, fixed physical parameters, force model | Existing |
| OMM-OPM-2B | OMM | OPM | Two-body fit | Composed | `propagate-omm` → `oem-to-opm` | Declared mean-element theory | OEM | Two-body osculating approximation | Propagation settings and fit span | Existing/composed |
| OMM-OPM-NUM | OMM | OPM | Numerical initial-state fit | Composed fitting | `omm-to-opm --fit-model numerical` | Declared mean-element theory | Reference OEM | Numerical Cartesian initial state | Target force model, fit settings, fixed physical parameters | Existing composition |
| TLE-OPM-2B | TLE | OPM | Two-body fit | Composed | `propagate-tle` → `oem-to-opm` | SGP4 mean elements | SGP4 OEM | Two-body osculating approximation | Propagation settings and fit span | Existing/composed |
| TLE-OPM-NUM | TLE | OPM | Numerical initial-state fit | Composed fitting | `tle-to-opm --fit-model numerical` | SGP4 mean elements | SGP4 reference OEM | Numerical Cartesian initial state | Target force model, fit settings, fixed physical parameters | Existing composition |
| OEM-TLE-SGP4 | OEM | TLE | SGP4-compatible fit | Fitting/composed | `oem-to-tle` | Cartesian history; source provenance required when known | Intermediate OMM | SGP4 mean elements/TLE | `--fit-span`, TLE refinement, fit report | Existing |
| OMM-TLE-DIRECT | OMM | TLE | Direct SGP4 mapping | Direct mapping | `omm-to-tle` | SGP4-compatible mean elements | — | SGP4 TLE | Required TLE fields; theory validation | Existing |
| OMM-TLE-REFIT | OMM | TLE | Composed SGP4 refit | Propagation/fitting | `propagate-omm` → OEM → `oem-to-tle` | Supported declared mean-element theory; other theories use labeled Kepler fallback | Reference OEM | SGP4 mean elements/TLE | Propagation settings, fit span, fit report | Existing composition |
| OPM-TLE-2B | OPM | TLE | Two-body intermediate | Composed | `propagate-kepler` → `oem-to-tle` | Osculating state | Two-body OEM | SGP4 mean elements/TLE | Duration, fit span, report | Existing composition |
| OPM-TLE-NUM | OPM | TLE | Numerical intermediate | Composed | `propagate-orbit` → `oem-to-tle` | Osculating Cartesian state | Numerical OEM | SGP4 mean elements/TLE | Force model, integrator, fit span, report | Existing composition |

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
