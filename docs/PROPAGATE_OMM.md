# OMM Propagation Utility

The `propagate-omm` utility loads an OMM or TLE input, selects the appropriate propagator, and writes the resulting orbit as CCSDS OEM state history.

## Overview

The command accepts an OMM file, a raw TLE file, or text from stdin, resolves a propagation window, and emits state vectors over the requested time interval. If the supplied input is a raw TLE or an OMM containing TLE parameters, the workflow uses TudatPy SGP4 propagation. Otherwise, it falls back to a two-body Keplerian propagation using the OMM mean elements.

## Synopsis

```bash
propagate-omm <input_omm|input_tle|-> [OPTIONS]
cat satellite.omm | propagate-omm - -o - [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `<input_omm\|input_tle\|->` | Input file path for an OMM or TLE, or `-` to read text from stdin. |
| `--tle` | Interpret the input as a raw TLE instead of an OMM. |
| `-d`, `--duration <duration>` | Simulation duration. Defaults to one day. |
| `-o`, `--output <output_oem\|->` | Output OEM state history. `-` writes to stdout. |
| `--start <timestamp\|duration>` | Propagation start epoch as an ISO 8601 timestamp or offset from the OMM/TLE epoch. |
| `--stop <timestamp\|duration>` | Propagation stop epoch as an ISO 8601 timestamp or offset from the start epoch. |
| `-s`, `--step <duration>` | Output interval. Defaults to five minutes. |
| `--data-only` | Write state lines without the OEM metadata header. |
| `-h`, `--help` | Show the help message and exit. |

## Input Format

The command accepts either:

1. A CCSDS OMM file in KVN format.
2. A raw TLE file, supplied directly or with the `--tle` flag.
3. Raw OMM or TLE text from stdin.

The reference epoch is taken from the OMM epoch or TLE epoch, depending on the input type. For OMM inputs, if TLE parameters are present, the utility converts the OMM to a TLE before propagating with SGP4.

## Duration Values

Durations use compact notation such as `90s`, `2m`, `1.5h`, or `1d`. Start and stop values may also be ISO 8601 timestamps. Negative duration offsets are supported where accepted by the propagation workflow.

## Examples

```bash
propagate-omm satellite.omm --duration 6h -o output.oem
propagate-omm image.tle --tle --duration 6h -o propagated.oem
cat satellite.omm | propagate-omm - -o - --data-only
propagate-omm satellite.omm --start 2026-01-01T00:00:00 --duration 90m -o propagated.oem
```

## Output

By default, the command prints a CCSDS OEM document containing metadata such as:

- `CCSDS_OEM_VERS`
- `CREATION_DATE`
- `ORIGINATOR`
- `OBJECT_NAME`
- `OBJECT_ID`
- `CENTER_NAME`
- `REF_FRAME`
- `TIME_SYSTEM`
- `START_TIME`
- `STOP_TIME`

With `--data-only`, the command prints only state lines:

```text
<ISO-8601 UTC epoch> <X_km> <Y_km> <Z_km> <VX_km/s> <VY_km/s> <VZ_km/s>
```

Current output conventions are:

- `REF_FRAME = EME2000`.
- `TIME_SYSTEM = UTC`.
- Epochs include a trailing `Z`.
- Position is printed in kilometers.
- Velocity is printed in kilometers per second.

## Propagation Behavior

The utility chooses the propagator based on the input content:

- Raw TLE input: SGP4 propagation.
- OMM with embedded TLE parameters: SGP4 propagation after conversion to TLE.
- OMM with `MEAN_ELEMENT_THEORY = DSST`: DSST semi-analytical propagation.
- OMM without TLE parameters (other theories): two-body Kepler propagation.

This allows a single CLI to handle TLE-driven, DSST mean-element, and generic Keplerian OMM data without changing the interface.

## DSST Support

When `MEAN_ELEMENT_THEORY = DSST` is set in the OMM metadata, the utility automatically uses the DSST semi-analytical propagator with J2 secular rates and short-period corrections.

Spacecraft parameters are parsed from the OMM and used to configure drag perturbations:

| OMM Field | DSST Parameter |
|-----------|---------------|
| `DRAG_AREA` | `drag_area_m2` |
| `DRAG_COEFF` | `drag_coeff` |
| `MASS` | `mass_kg` |

### Example DSST OMM

```
CCSDS_OMM_VERS = 3.0
CREATION_DATE  = 2024-01-01T00:00:00.000
ORIGINATOR     = ephem-toolkit

OBJECT_NAME    = ISS
OBJECT_ID      = 1998-067A
CENTER_NAME    = EARTH
REF_FRAME      = J2000
TIME_SYSTEM    = UTC
MEAN_ELEMENT_THEORY = DSST

EPOCH          = 2024-01-01T00:00:00.000000
MEAN_MOTION    = 15.49 [rev/day]
ECCENTRICITY   = 0.0005
INCLINATION    = 51.6 [deg]
RA_OF_ASC_NODE = 45.0 [deg]
ARG_OF_PERICENTER = 30.0 [deg]
MEAN_ANOMALY   = 10.0 [deg]

MASS           = 420000.0 [kg]
DRAG_AREA      = 2500.0 [m**2]
DRAG_COEFF     = 2.2
```

```bash
propagate-omm iss_dsst.omm --stop 1d --step 300s -o iss_dsst.oem
```

See [PROPAGATE_DSST.md](PROPAGATE_DSST.md) for full DSST documentation.

## Usage

**Propagate a sample OMM file:**

```bash
propagate-omm tests/data/sample.omm --duration 2h -o output.oem
```

**Propagate a raw TLE file for 30 minutes with ten-second output steps:**

```bash
propagate-omm tests/data/ISS-ZARYA_1998-067A.tle --tle --stop 30m -s 10s -o propagated.oem
```

**Propagate from stdin and print only state lines:**

```bash
cat satellite.omm | propagate-omm - -o - --data-only
```

**Start 90 minutes after the epoch and propagate for two hours:**

```bash
propagate-omm satellite.omm --start 90m --stop 2h -s 1m -o propagated.oem
```

Relative `--start` durations are measured from the input epoch. Relative `--stop` durations are measured from the resolved start epoch.

**Show help:**

```bash
propagate-omm --help
```

## Dependencies

- TudatPy.
- Python standard library.
- Local OEM, OMM, TLE, and time utility modules.
- SPICE kernels such as `naif0012.tls` and `pck00011.tpc` when SGP4 propagation is used.

## Related Tools

- `omm-to-tle` - Convert a CCSDS OMM to a TLE set.
- `tle-to-omm` - Convert a TLE to OMM format.
- `propagate-tle` - Propagate a TLE directly from a TLE input.
- `propagate-kepler` - Run two-body Keplerian propagation from orbital elements.
- `propagate-orbit` - Run perturbed orbital propagation.
