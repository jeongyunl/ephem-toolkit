# Keplerian Propagation Utility

The `propagate-kepler` utility performs two-body Keplerian propagation from one OEM-style state line.

## Overview

The command reads one OEM-style line of Keplerian elements, propagates the
orbit, converts each propagated state to Cartesian coordinates, and writes the
result in OEM-like format.

## Synopsis

```bash
propagate-kepler [OPTIONS]
cat initial_state.txt | propagate-kepler - -o - [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-i`, `--initial-state <state-line>` | State line supplied directly on the command line. If omitted, read one line from stdin. |
| `-d`, `--duration <duration>` | Simulation duration. Accepts values such as `90s`, `2m`, `1.5h`, or `1d`. Defaults to one day. |
| `-o`, `--output <output_oem|->` | Output OEM state history. `-` writes to stdout. Defaults to `-`. |
| `-s`, `--step <duration>` | Output interval, such as `60s` or `1m`. Defaults to 15 minutes. |
| `--data-only` | Write state lines without the OEM metadata header. |
| `-h`, `--help` | Show the help message and exit. |

## State Format

The initial state is an OEM-style line containing an epoch followed by six Keplerian state values:

```text
<epoch> <semi-major-axis> <eccentricity> <inclination> <argument-of-periapsis> <longitude-of-ascending-node> <true-anomaly>
```

The values use the following units:

- **Epoch**: ISO 8601 timestamp.
- **Semi-major axis**: kilometers; converted to meters internally.
- **Eccentricity**: dimensionless.
- **Angles**: inclination, argument of periapsis, longitude of ascending node, and true anomaly in radians.

The state can be supplied with `--initial-state`. If that option is omitted,
the command reads one line from stdin.

## Examples

```bash
propagate-kepler --initial-state "2026-05-29T00:00:00.000000 6793.456 0.001234 0.9013 4.094 2.155 0.797" -d 6h
cat initial_state.txt | propagate-kepler - --duration 90m --output propagated.oem
cat input.txt | propagate-kepler - --output - --data-only
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
