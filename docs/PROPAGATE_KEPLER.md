# Keplerian Propagation Utility

The `propagate-kepler` utility performs two-body Keplerian propagation from the
Keplerian elements in one CCSDS OPM file.

## Overview

The command reads one OPM, propagates its Keplerian elements, converts each
propagated state to Cartesian coordinates, and writes the result in OEM format.

## Synopsis

```bash
propagate-kepler <input_opm|-> -o <output_oem|-> [OPTIONS]
cat input.opm | propagate-kepler - -o - [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `<input_opm|->` | CCSDS OPM file path. `-` reads OPM content from stdin. |
| `-d`, `--duration <duration>` | Simulation duration. Accepts values such as `90s`, `2m`, `1.5h`, or `1d`. Defaults to one day. |
| `-o`, `--output <output_oem|->` | Output OEM state history. `-` writes to stdout. Defaults to `-`. |
| `-s`, `--step <duration>` | Output interval, such as `60s` or `1m`. Defaults to 15 minutes. |
| `--data-only` | Write state lines without the OEM metadata header. |
| `-h`, `--help` | Show the help message and exit. |

## Input OPM

The OPM must contain a complete Keplerian element set and either
`TRUE_ANOMALY` or `MEAN_ANOMALY`. OPM angles are in degrees; they are converted
to radians internally. The semi-major axis is in kilometers and is converted to
meters internally.

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

By default, the command writes CCSDS OEM state history. `--data-only` omits the metadata header and writes only propagated state lines.

State-only output uses the following format:

```text
<ISO-8601 UTC epoch> <X_km> <Y_km> <Z_km> <VX_km/s> <VY_km/s> <VZ_km/s>
```

## Dependencies

- NumPy.
- `ephem_toolkit.core.ccsds.oem`.
- `ephem_toolkit.core.kepler`.
- `ephem_toolkit.core.time_utils`.

## Related Tools

- `propagate-orbit` - Propagate with perturbation models.
- `propagate-tle` - Propagate a TLE using SGP4.
- `plot-orbit` - Plot an OEM orbit.

See [PROPAGATION.md](PROPAGATION.md) for the grouped propagation workflow.
