# TLE Propagation Utility

The `propagate-tle` utility loads a TLE, propagates it with TudatPy SGP4, and writes an OEM-like state history.

## Overview

The command accepts a TLE file path or raw TLE text from stdin, propagates the
TLE-derived orbit over a selected time interval, and emits OEM-like state
vectors. It can write a complete CCSDS OEM document or state lines only.

## Synopsis

```bash
propagate-tle [<tle_file|->] [OPTIONS]
cat tle.txt | propagate-tle - -o - [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `<tle_file|->` | Optional TLE file path. Defaults to `-`, which reads TLE text from stdin. |
| `-d`, `--duration <duration>` | Simulation duration. Defaults to one day. |
| `-o`, `--output <output_oem|->` | Output OEM state history. `-` writes to stdout. |
| `--start <timestamp|duration>` | Propagation start epoch as an ISO 8601 timestamp or offset from the TLE epoch. |
| `--stop <timestamp|duration>` | Propagation stop epoch as an ISO 8601 timestamp or offset from the start epoch. |
| `-s`, `--step <duration>` | Output interval. Defaults to five minutes. |
| `--data-only` | Write state lines without the OEM metadata header. |
| `-h`, `--help` | Show the help message and exit. |

## Input Format

The command uses the final two non-empty lines of the input source as the TLE
pair. The selected lines must begin with `1 ` and `2 ` respectively, and the
input must contain at least two non-empty lines.

Accepted sources are:

1. A positional TLE file path.
2. Raw TLE text from stdin.

For file input, the OEM object name is derived from the file stem. For stdin
input, the object name is `TLE_STDIN`.

## Duration Values

Durations use compact notation such as `90s`, `2m`, `1.5h`, or `1d`. Start and stop values may also be ISO 8601 timestamps. Negative duration offsets are supported where accepted by the propagation workflow.

## Examples

```bash
propagate-tle ISS.tle --duration 6h
propagate-tle --start 2026-01-01T00:00:00 --duration 90m --output propagated.oem
cat tle.txt | propagate-tle - --output - --data-only
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

## Usage

**Propagate a sample TLE file:**

```bash
propagate-tle tests/data/ISS-ZARYA_1998-067A.tle
```

**Propagate from stdin for two hours with one-minute output steps:**

```bash
cat tests/data/ISS-ZARYA_1998-067A.tle | propagate-tle - --stop 2h -s 1m -o -
```

**Propagate for 30 minutes with ten-second output steps:**

```bash
propagate-tle tests/data/ISS-ZARYA_1998-067A.tle --stop 30m -s 10s
```

**Start 90 minutes after the TLE epoch and propagate for two hours:**

```bash
propagate-tle tests/data/ISS-ZARYA_1998-067A.tle \
	--start 90m --stop 2h -s 1m
```

Relative `--start` durations are measured from the TLE epoch. Relative
`--stop` durations are measured from the resolved start epoch.

**Print state lines without the OEM metadata header:**

```bash
propagate-tle tests/data/ISS-ZARYA_1998-067A.tle --data-only
```

**Show help:**

```bash
propagate-tle --help
```

## Dependencies

- TudatPy.
- Python standard library.
- Local OEM and time utility modules.

The command loads the `naif0012.tls` and `pck00011.tpc` SPICE kernels through
TudatPy data paths.

## Related Tools

- `download-tle` - Download current TLE data.
- `tle-info` - Inspect TLE parameters.
- `propagate-kepler` - Run two-body Keplerian propagation.
- `propagate-orbit` - Run perturbed propagation.

