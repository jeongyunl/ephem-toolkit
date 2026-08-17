# Perturbed Orbit Propagation Utility

The `propagate-orbit` utility propagates an OEM-style initial state with configurable Earth gravity, third-body gravity, solar radiation pressure, aerodynamic drag, and numerical integration settings.

## Overview

The command reads one OEM-like Cartesian state line and propagates it around
Earth with configurable spherical-harmonic gravity, third-body gravity,
aerodynamic drag, solar radiation pressure, and numerical integration settings.

## Synopsis

```bash
propagate-orbit [OPTIONS]
cat initial_state.txt | propagate-orbit [OPTIONS]
```

## Core Options

| Option | Description |
|--------|-------------|
| `-i`, `--initial-state <state-line>` | Initial OEM-style state line. If omitted, read one line from stdin. |
| `-d`, `--duration <duration>` | Simulation duration. Defaults to the configured simulation duration. |
| `-o`, `--output <output_oem|->` | Output OEM state history. `-` writes to stdout. |
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

The command expects exactly one OEM-like Cartesian state line:

```text
<ISO-8601 epoch> <X_km> <Y_km> <Z_km> <VX_km/s> <VY_km/s> <VZ_km/s>
```

The epoch is an ISO 8601 timestamp, position is in kilometers, and velocity
is in kilometers per second. The state is supplied with `--initial-state` or,
when that option is omitted, from stdin. If neither source provides a state,
the command exits with an error.

## Boolean Values

The model toggles accept `on` or `off`. Defaults for gravity, drag, and solar radiation pressure are shown in the command help and may be changed per run.

## Examples

```bash
propagate-orbit --initial-state "2023-04-10T00:00:00 7000 0 0 0 7.5 1.0" -d 6h
propagate-orbit --duration 90m --output propagated.oem < input_state.txt
cat input.txt | propagate-orbit --output - --dep-vars dep_vars.csv
propagate-orbit --earth-gravity 8x8 --drag on --srp off -d 2h
```

**Propagate from an inline Cartesian state:**

```bash
propagate-orbit \
	-d 1d \
	-i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Propagate from stdin:**

```bash
echo "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217" \
	| propagate-orbit -d 2h
```

**Disable drag and solar radiation pressure:**

```bash
propagate-orbit \
	-d 1d --drag off --srp off \
	-i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Set satellite properties and export dependent variables:**

```bash
propagate-orbit \
	-d 12h --name MySat --mass 500 --drag-coeff 2.5 --drag-area 0.5 \
	--srp-coeff 1.5 --dep-vars dep_vars.csv \
	-i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

**Use a variable-step RKF 7(8) integrator:**

```bash
propagate-orbit \
	-d 12h --integrator rkf_78 --integrator-step-size 30,0.001,1000 \
	--earth-gravity 8x8 \
	-i "2026-05-29T00:00:00.000000 185.541742 6527.421475 -3481.030718 1.283181009 -3.414086560 -6.360538217"
```

## Output

The command prints a pre-propagation configuration summary. By default,
propagated state history is written in CCSDS OEM format to stdout; use
`--output <path>` to write it to a file. Use `--output -` explicitly to write
OEM output to stdout.

With `--data-only`, the command writes raw state-vector lines without the OEM
metadata header:

```text
<ISO-8601 UTC epoch> <X_km> <Y_km> <Z_km> <VX_km/s> <VY_km/s> <VZ_km/s>
```

If `--dep-vars <output_csv>` is provided, dependent variables are written to
that CSV file. The summary includes the selected force model and integrator,
initial state, duration, end epoch, and configured output destinations.

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

See [PROPAGATION.md](PROPAGATION.md) for the grouped propagation workflow.
