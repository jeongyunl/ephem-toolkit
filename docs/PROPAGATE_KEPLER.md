# Keplerian Propagation Utility

The `propagate-kepler` utility performs two-body Keplerian propagation from the
Keplerian elements in one CCSDS OPM file.

## Overview

The command reads a single CCSDS OPM containing a Keplerian element set, propagates
those elements with the two-body model, converts each propagated state to Cartesian
coordinates, and writes either CCSDS OEM output or raw state-vector lines.

The command usage is `propagate-kepler <input_opm|-> -o <output_oem|-> [OPTIONS]`.

## Synopsis

```bash
propagate-kepler <input_opm|-> -o <output_oem|-> [OPTIONS]
cat input.opm | propagate-kepler - -o - [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `<input_opm\|->` | CCSDS OPM file path. `-` reads OPM content from stdin. |
| `-d`, `--duration <duration>` | Simulation duration. Accepts values such as `90s`, `2m`, `1.5h`, or `1d`. Defaults to one day. |
| `-o`, `--output <output_oem\|->` | Output OEM state history. `-` writes to stdout. Defaults to `-`. |
| `-s`, `--step <duration>` | Output interval, such as `60s` or `1m`. Defaults to 15 minutes. |
| `--data-only` | Write state lines without the OEM metadata header. |
| `-h`, `--help` | Show the help message and exit. |

## Input OPM

The input must be a CCSDS OPM containing a complete Keplerian element set and either
`TRUE_ANOMALY` or `MEAN_ANOMALY`. OPM angles are given in degrees and are converted
to radians internally. The semi-major axis is given in kilometers and is converted to
meters internally before propagation.

The command accepts either a file path or `-` to read the OPM from standard input.

```text
SEMI_MAJOR_AXIS = <km>
ECCENTRICITY = <dimensionless>
INCLINATION = <degrees>
RA_OF_ASC_NODE = <degrees>
ARG_OF_PERICENTER = <degrees>
TRUE_ANOMALY = <degrees>
```

The values use the following units:

- The OPM `EPOCH` supplies the propagation start time.
- When `MEAN_ANOMALY` is supplied instead, it is converted to true anomaly.

## Examples

```bash
propagate-kepler input.opm -d 6h -o propagated.oem
cat input.opm | propagate-kepler - --duration 90m --output propagated.oem
cat input.opm | propagate-kepler - --output - --data-only
```

## Output

By default, the command writes a CCSDS OEM state history with metadata copied from the input
OPM where available. `--data-only` omits the metadata header and writes only propagated state
lines in the OEM data-only format.

State-only output uses the following format:

```text
<ISO-8601 UTC epoch> <X_km> <Y_km> <Z_km> <VX_km/s> <VY_km/s> <VZ_km/s>
```

The `-o, --output` option writes to a file path or stdout; use `-` to write directly to
standard output.

## Dependencies

- NumPy.
- `ephem_toolkit.core.ccsds.oem`.
- `ephem_toolkit.core.kepler`.
- `ephem_toolkit.core.time_utils`.

## Related Tools

- `propagate-orbit` - Propagate with perturbation models.
- `propagate-tle` - Propagate a TLE using SGP4.
- `propagate-omm` - Propagate an OMM or TLE input using the appropriate solver automatically.
- `plot-orbit` - Plot an OEM orbit.

