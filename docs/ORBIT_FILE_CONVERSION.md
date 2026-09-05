# Orbit File Conversion Guide

This guide explains the supported orbit-file conversion workflows for TLE,
OMM, OEM, and OPM files. The route-level inventory is maintained in the
[orbit-file conversion matrix](ORBIT_FILE_CONVERSION_MATRIX.md). Use the
matrix to choose a route, and use this guide for model selection, command
options, metadata, and provenance requirements.

The commands listed here are the commands currently exposed by
`pyproject.toml`. A route described with an arrow is a composition of those
commands; it is not a separate executable.

## Format characteristics

| Format | Representation | Model and limitations |
|---|---|---|
| TLE | Two fixed-width ASCII lines | SGP4 mean elements; TEME/UTC; checksums; no covariance or maneuvers |
| OMM | CCSDS mean-element message | Theory-specific mean elements, such as SGP4 or DSST; may carry TLE parameters and covariance |
| OEM | CCSDS Cartesian state history | Multiple position/velocity states; may carry covariance and acceleration, but the Cartesian layout does not identify the generating model |
| OPM | CCSDS single-epoch orbit state | Cartesian and/or osculating Keplerian state; may carry covariance, maneuvers, and spacecraft parameters |

An OEM is not model-neutral. An identical Cartesian state-vector layout can
come from SGP4, DSST, Brouwer, two-body Kepler propagation, numerical
integration, or orbit determination. Preserve the source model, frame, time
system, and force-model information whenever it is known.

## Model and provenance rules

1. A direct conversion is a field mapping only when the source and target
   representations describe the same model. `tle-to-omm` and compatible
   `omm-to-tle` are the direct SGP4 mappings.
2. A propagation route creates a new Cartesian history. Its provenance must
   identify the propagator and its settings.
3. A fitting route creates a model-specific approximation over a stated arc.
   It is not a lossless relabeling of the source orbit.
4. A composed route must record each intermediate model. The intermediate OEM
   is a reference history, not interchangeable with an OEM produced by a
   different propagator.
5. TLE has no portable field for arbitrary provenance. Write fit diagnostics
   to a companion `--fit-report` file or retain them in the preceding OMM/OEM.

For CCSDS output, use portable comments such as:

```text
COMMENT EPHEMERIS_PROVENANCE: source=<format and model>; transformation=<operation>; target_model=<model>
COMMENT EPHEMERIS_FIT: span=<duration>; samples=<count>; position_rms=<value>; velocity_rms=<value>
```

## Command reference

### Propagation commands

| Command | Input | Output | Relevant options |
|---|---|---|---|
| `propagate-tle` | TLE | OEM | `-d/--duration`, `-o/--output`, `--step`, `--data-only` |
| `propagate-omm` | OMM, or TLE with `--tle` | OEM | `-d/--duration`, `-o/--output`, `-s/--step`, `--start`, `--stop`, `--data-only`, `--tle` |
| `propagate-kepler` | OPM | OEM | `-d/--duration`, `-s/--step`, `-o/--output`, `--data-only` |
| `propagate-orbit` | OPM | OEM | `-d/--duration`, `-o/--output`, `--data-only`, `--earth-gravity`, `--integrator`, `--integrator-step-size`, `--drag`, `--drag-coeff`, `--drag-area`, `--srp`, `--srp-coeff`, body-gravity options, `--dep-vars` |

`propagate-omm` dispatches SGP4 and DSST where supported. Other declared
non-TLE theories use the explicitly labeled two-body Kepler fallback; the
fallback does not make the result a theory-specific propagation. No additional
OMM propagator integrations are planned in the current scope.

`propagate-orbit` uses the OPM Cartesian state and the selected numerical
force/gravity/integrator configuration. Its full option set is authoritative;
the conversion matrix records the options relevant to each route.

### Conversion and fitting commands

| Command | Current purpose | Actual options relevant to conversion |
|---|---|---|
| `tle-to-omm` | Direct TLE-to-SGP4 OMM mapping | `-o/--output` |
| `omm-to-tle` | Direct SGP4-compatible OMM-to-TLE mapping | `-o/--output` |
| `oem-to-omm` | Fit OEM states to mean elements | `--fit-model {brouwer,dsst,sgp4}`, deprecated `--mode {brouwer,dsst,tle}`, `--theory`, `--fit-span`, `--fit-report`, `--no-fit-report`, `--source-model`, `--source-report`, TLE metadata options, `--object-name`, `--object-id`, `--mu`, `-o/--output` |
| `oem-to-opm` | Fit an OEM to a two-body or numerical OPM state | `--fit-model {two-body,numerical}`, `--fit-span`, `--fit-position-weight`, `--fit-max-iterations`, `--fit-stagnation-tries`, `--fit-end-weight`, `--fit-parameters`, fixed physical-parameter options, `--fit-report`, `--no-fit-report`, `--source-model`, `--source-report`, `--object-name`, `--object-id`, `--mu`, `-o/--output` |
| `oem-to-tle` | Fit an OEM to SGP4 mean elements and format a TLE | The `oem-to-omm` fitting options, including `--fit-span`, `--fit-report`, `--source-model`, `--source-report`, `--tle-refinement`, TLE metadata options, and `-o/--output` |

`omm-to-opm` and `tle-to-opm` are implemented convenience wrappers. They
require `--fit-model numerical`, generate a reference OEM with
`propagate-omm`/SGP4, and delegate the fit to `oem-to-opm`. Their numerical-fit
options are the options forwarded by the wrapper, including fit span, target
force-model settings, fixed physical parameters, provenance, and fit report.

There is no dedicated `opm-to-omm` or `opm-to-tle` command. Those routes are
compositions of the propagation and fitting commands shown below.

## Routes to OEM

### OMM → OEM: `OMM-OEM-SGP4` and `OMM-OEM-DSST`

Use `propagate-omm input.omm -d 6h -s 5m -o output.oem`. The declared
`MEAN_ELEMENT_THEORY` selects the supported mean-element path. Preserve the
OMM theory, epoch, frame, time system, and propagation settings in provenance.

For an unsupported declared theory, the command’s two-body fallback must be
identified as `target_model=two-body-kepler`; it must not be described as a
Brouwer, DSST, or other theory-specific OEM.

### OPM → OEM: `OPM-OEM-2B` and `OPM-OEM-NUM`

Use `propagate-kepler` for the two-body path. Use `propagate-orbit` when
perturbations are required. The numerical path must record gravity, force
models, integrator, step size, spacecraft parameters, and output sampling.

### TLE → OEM: `TLE-OEM-SGP4`

Use `propagate-tle input.tle -d 6h -s 5m -o output.oem`, or use the equivalent
`propagate-omm input.tle --tle ...` path. Both produce an SGP4 Cartesian
history. The output frame is TEME and the time system is UTC unless the
command’s output contract says otherwise.

## Routes to OMM

### OEM → OMM: `OEM-OMM-SGP4`, `OEM-OMM-BROUWER`, and `OEM-OMM-DSST`

Select the target model explicitly:

```text
oem-to-omm input.oem --fit-model sgp4 --fit-span 2h -o output.omm
oem-to-omm input.oem --fit-model brouwer --fit-span 2h -o output.omm
oem-to-omm input.oem --fit-model dsst --fit-span 2h -o output.omm
```

`--fit-model` determines the target theory. The deprecated `--mode` option is
still accepted for compatibility, and `--mode tle` maps to `--fit-model sgp4`.
Do not use `--theory` to relabel a result inconsistently with the selected fit
model. Supply `--source-model` or `--source-report` when the OEM does not carry
usable provenance. Use `--fit-report` for JSON diagnostics.

### OPM → OMM: `OPM-OMM-2B` and `OPM-OMM-NUM`

There is no one-step command. Generate an intermediate OEM, then fit it:

```text
propagate-kepler input.opm -d 2h -s 5m -o reference.oem
oem-to-omm reference.oem --fit-model sgp4 --fit-span 2h -o output.omm
```

Replace `propagate-kepler` with `propagate-orbit` for the numerical variant.
Record both the intermediate propagation configuration and the OMM fit
configuration.

### TLE → OMM: `TLE-OMM-DIRECT`

Use `tle-to-omm input.tle -o output.omm`. This is a direct SGP4 field mapping;
it does not convert the TLE into DSST, Brouwer, or osculating elements.

## Routes to OPM

### OEM → OPM: `OEM-OPM-2B` and `OEM-OPM-NUM`

The default `oem-to-opm` fit produces a two-body osculating approximation. Use
`--fit-model numerical` to fit a numerical propagator’s Cartesian initial
state. Numerical fits use position residuals; physical parameters are supplied
as fixed values and are not estimated.

Record fit span, weights, convergence settings, target force model, and fit
report. Fitted Keplerian fields are not source-model-consistent osculating
elements for an arbitrary mean-element or numerical OEM.

### OMM → OPM: `OMM-OPM-2B` and `OMM-OPM-NUM`

The two-body route is `propagate-omm` followed by `oem-to-opm`. The numerical
route can use the wrapper:

```text
omm-to-opm input.omm --fit-model numerical --fit-span 2h -o output.opm
```

The reference OEM is generated using the OMM’s declared supported theory, or
the labeled Kepler fallback for an unsupported theory. The OPM is therefore a
fit for a stated arc, not a replacement for the OMM mean elements.

### TLE → OPM: `TLE-OPM-2B` and `TLE-OPM-NUM`

The two-body route is `propagate-tle` followed by `oem-to-opm`. For a numerical
initial-state fit, use:

```text
tle-to-opm input.tle --fit-model numerical --fit-span 2h -o output.opm
```

The wrapper fits the target numerical model to an SGP4 reference arc and must
record SGP4 as the source model.

## Routes to TLE

### OEM → TLE: `OEM-TLE-SGP4`

`oem-to-tle input.oem --fit-span 2h --fit-report fit.json -o output.tle`
fits SGP4-compatible mean elements and then formats the TLE. The result is a
new SGP4 representation of the source arc. The companion report is required
for source provenance and residuals because TLE cannot carry them.

### OMM → TLE: `OMM-TLE-DIRECT` and `OMM-TLE-REFIT`

Use `omm-to-tle` only when the OMM is SGP4-compatible and has the required TLE
parameters. The command validates the declared theory and required fields
before writing output; DSST and Brouwer-Lyddane inputs are rejected.

For another supported OMM propagation path, compose:

```text
propagate-omm input.omm -d 2h -s 5m -o reference.oem
oem-to-tle reference.oem --fit-span 2h --fit-report fit.json -o output.tle
```

This is a refit through an intermediate Cartesian OEM. It is valid only over
the fit arc and does not preserve the source OMM theory in the TLE itself.

### OPM → TLE: `OPM-TLE-2B` and `OPM-TLE-NUM`

Propagate the OPM with `propagate-kepler` or `propagate-orbit`, then pass the
resulting OEM to `oem-to-tle`. The selected intermediate model, SGP4 fitting
settings, and residuals belong in the fit report.

## Validation and verification

Before accepting a conversion, check the route’s theory compatibility, frame
and time system, required TLE fields, minimum reference-state count, output
metadata, and provenance/report behavior. For a fit, inspect convergence,
position/velocity residuals, sample count, and the stated arc validity.

The matrix’s verification notes summarize the current focused and integration
tests. Live Tudat/SPICE-dependent verification remains environment-dependent;
do not represent a source-tree test pass as a live force-model accuracy result.
