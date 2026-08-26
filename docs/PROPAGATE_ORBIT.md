# Perturbed Orbit Propagation Utility

The `propagate-orbit` utility propagates an initial Cartesian state from a CCSDS OPM input with configurable Earth gravity, third-body gravity, solar radiation pressure, aerodynamic drag, and numerical integration settings.

## Overview

The command reads one CCSDS OPM message containing a Cartesian state and propagates it around
Earth with configurable spherical-harmonic gravity, third-body gravity,
aerodynamic drag, solar radiation pressure, and numerical integration settings.

The command usage is `propagate-orbit <input_opm|-> [OPTIONS]`, with output written to the
`-o, --output` target or stdout by default.

## Synopsis

```bash
propagate-orbit <input_opm|-> [OPTIONS]
cat input.opm | propagate-orbit - -o - [OPTIONS]
```

## Core Options

| Option | Description |
|--------|-------------|
| `<input_opm\|->` | Positional OPM input path, or `-` to read OPM content from stdin. |
| `-d`, `--duration <duration>` | Simulation duration. Defaults to the configured simulation duration. |
| `-o`, `--output <output_oem\|->` | Output OEM state history. `-` writes to stdout. |
| `--data-only` | Write state vectors without OEM header or metadata. |
| `--dep-vars <output_csv>` | Write dependent variables to a CSV file. |
| `--name <name>` | Propagated satellite name. |
| `--mass <kg>` | Satellite mass in kilograms. |
| `-h`, `--help` | Show the help message and exit. |

## Numerical Model Options

| Option | Description |
|--------|-------------|
| `--integrator <method>` | Numerical integrator method. The help output lists supported methods and the default. |
| `--integrator-step-size <fixed\|init,max\|init,min,max>` | Fixed or variable integrator step sizes in seconds. |
| `--earth-gravity <DxO>` | Earth spherical-harmonic gravity degree and order, such as `8x8`. |
| `--moon-gravity <on\|off>` | Enable or disable Moon point-mass gravity. |
| `--sun-gravity <on\|off>` | Enable or disable Sun point-mass gravity. |
| `--venus-gravity <on\|off>` | Enable or disable Venus point-mass gravity. |
| `--mars-gravity <on\|off>` | Enable or disable Mars point-mass gravity. |
| `--drag-area <m2>` | Aerodynamic drag and cannonball reference area. |
| `--drag <on\|off>` | Enable or disable aerodynamic drag. |
| `--drag-coeff <coefficient>` | Aerodynamic drag coefficient. |
| `--srp <on\|off>` | Enable or disable solar radiation pressure. |
| `--srp-coeff <coefficient>` | Solar radiation pressure coefficient. |

## Integrator Step-Size Forms

The `--integrator-step-size` option accepts one, two, or three comma-separated
values:

- `<fixed>` for a fixed step.
- `<initial_and_minimum>,<maximum>` for a variable step.
- `<initial>,<minimum>,<maximum>` for a variable step.

Examples are `10`, `0.001,1000`, and `30,0.001,1000`.

The default integrator and step-size values are shown in the command help.

## Input Format

The command expects one CCSDS OPM message containing the required Cartesian state-vector
fields (`EPOCH`, `X`, `Y`, `Z`, `X_DOT`, `Y_DOT`, `Z_DOT`) in standard OPM
units (km and km/s).

Provide the OPM source as either a positional file path or `-` for stdin. If stdin is selected
but no data is piped, the command exits with an error.

The input state is interpreted as a single initial Cartesian state at the OPM epoch; the command
then integrates the trajectory for the selected `--duration`.

## Boolean Values

The model toggles accept `on` or `off`. Defaults for gravity, drag, and solar radiation pressure are shown in the command help and may be changed per run.

## Examples

```bash
propagate-orbit input.opm -d 6h
propagate-orbit input.opm --duration 90m --output propagated.oem
cat input.opm | propagate-orbit - --output - --dep-vars dep_vars.csv
propagate-orbit --earth-gravity 8x8 --drag on --srp off -d 2h
```

**Propagate from an OPM file:**

```bash
propagate-orbit \
	-d 1d \
	input.opm
```

**Propagate from stdin OPM content:**

```bash

cat input.opm \
	| propagate-orbit -d 2h
```

**Disable drag and solar radiation pressure:**

```bash
propagate-orbit \
	-d 1d --drag off --srp off \
	input.opm
```

**Set satellite properties and export dependent variables:**

```bash
propagate-orbit \
	-d 12h --name MySat --mass 500 --drag-coeff 2.5 --drag-area 0.5 \
	--srp-coeff 1.5 --dep-vars dep_vars.csv \
	input.opm
```

**Use a variable-step RKF 7(8) integrator:**

```bash
propagate-orbit \
	-d 12h --integrator rkf_78 --integrator-step-size 30,0.001,1000 \
	--earth-gravity 8x8 \
	input.opm
```

## Output

The command prints a pre-propagation configuration summary and then writes the propagated state
history. By default, the output is CCSDS OEM format on stdout; use `-o, --output <path>` to
write the OEM history to a file or `--output -` to explicitly write to stdout.

With `--data-only`, the command writes raw state-vector lines without the OEM metadata header:

```text
<ISO-8601 UTC epoch> <X_km> <Y_km> <Z_km> <VX_km/s> <VY_km/s> <VZ_km/s>
```

If `--dep-vars <output_csv>` is provided, dependent variables are written to that CSV file. The
summary includes the selected force model and integrator, initial state, duration, end epoch, and
configured output destinations.

## Propagation Model

Current force-model behavior includes:

- Earth spherical-harmonic gravity.
- Optional Sun point-mass gravity.
- Optional Moon point-mass gravity.
- Optional Venus point-mass gravity.
- Optional Mars point-mass gravity.
- Optional aerodynamic drag.
- Optional solar radiation pressure.

Sun and Earth are always created. Moon, Mars, and Venus are created when their
corresponding gravity options are enabled. The global frame is Earth-centered
`J2000`.

Additional implementation details:

- The propagated satellite mass is configurable with `--mass`.
- The drag area is reused as the cannonball reference area for solar radiation pressure.
- One integrator step-size value selects fixed-step integration; two or three values select variable-step integration.

## Requirements

The command requires TudatPy, NumPy, and the configured astrodynamics
dependencies. It uses the local OEM, time, and interpolation helpers.

The propagation workflow loads these SPICE kernels through TudatPy:

- `naif0012.tls`
- `pck00011.tpc`
- `gm_de431.tpc`
- `earth_200101_990825_predict.bpc`
- `tudat_merged_spk_kernel.bsp`

## Related Tools

- `propagate-kepler` - Run two-body propagation without perturbations.
- `propagate-tle` - Propagate a TLE with SGP4.
- `plot-dependent-variables` - Plot a dependent-variable CSV.
- `plot-orbit` - Plot the resulting OEM history.

