# OEM Slicing Utility

The `slice-oem` utility extracts subsets of CCSDS OEM (Orbit Ephemeris Message) ephemeris data by index or time range, with optional interpolation support.

## Overview

This utility provides flexible slicing capabilities for OEM files:

- **Index-based slicing**: Extract states using Python-style slice notation
- **Time-based slicing**: Extract states within specific time windows
- **Interpolation**: Generate uniformly-spaced states at specified intervals
- **Flexible output**: State data only, full OEM format, or a single-state OPM

The script is built on the `ephem_toolkit.core.slice_oem` library module, which provides reusable slicing functions for programmatic use.


## Synopsis

```bash
slice-oem <input_oem|-> --output <file|-> [OPTIONS]
cat data.oem | slice-oem - --output - [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `<input_oem>` | Path to input CCSDS OEM file; use `-` to read from stdin (required) |
| `-s`, `--slice SLICE` | Python-style slice index (e.g., `0:10`, `::2`, `5`, `-5:`) |
| `-t`, `--time-slice TIME_SLICE` | Time slice specifier: `start[,[stop][,step]]` |
| `--interpolate` | Enable interpolation for time slices, including exact-time selection and range boundaries (enabled by default) |
| `--no-interpolate` | Disable interpolation; cannot be combined with a step size |
| `--interpolate-type <type[,degree]>` | Interpolation method: `hermite[,degree]`, `chebyshev[,degree]`, or `lagrange[,degree]` (default: `hermite,5`) |
| `--opm` | Write the first selected state as a CCSDS OPM. Cannot be combined with `--data-only`. |
| `--data-only` | Output state vectors only (default: OEM format) |
| `-o`, `--output <file\|->` | Output file path (required); use `-` for stdout |
| `-v`, `--verbose` | Print detailed debug information to stderr |
| `--debug` | Print low-level debug details to stderr |
| `-h`, `--help` | Show help message and exit |

**Note**: `--slice` and `--time-slice` are mutually exclusive.

### Handling Negative Indices with Argparse

When using negative indices (e.g., `-5:` for the last 5 states), argparse interprets values starting with `-` as option flags. To work around this limitation, use one of these methods:

**Method 1: Use `=` syntax (recommended)**
```bash
slice-oem data.oem --slice="-5:" -o -
```

**Also works with single quotes:**
```bash
slice-oem data.oem --slice='-5:' -o -
```

The `=` syntax is the most reliable method and is recommended for all slice values that start with `-`.

## Index-Based Slicing

Use Python-style slice notation to extract states by position:

### Syntax

```
start[:[stop][:step]]
```

- **start**: Starting index (inclusive)
- **stop**: Ending index (exclusive) - **optional**
- **step**: Step size - **optional**

**Notes**:
- Index-based slicing follows Python conventions where the stop index is **exclusive**. For example, `0:10` selects states at indices 0 through 9 (10 states total).
- Negative indices count from the end of the array (e.g., `-1` is the last state, `-5:` is the last 5 states).
- Both **stop** and **step** are optional and may be omitted independently:
  - `start:` extracts from start index to the end
  - `start:stop` extracts from start to stop (exclusive)
  - `start::step` extracts every step-th element from start to the end
  - `start:stop:step` extracts every step-th element from start to stop
  - `::step` extracts every step-th element from the entire range
  - A single value (e.g., `5`) extracts one state at that index

### Examples

**First 10 states:**
```bash
slice-oem data.oem --slice "0:10" -o -
```

**Every other state:**
```bash
slice-oem data.oem --slice "::2" -o -
```

**Single state at index 5:**
```bash
slice-oem data.oem --slice "5" -o -
```

**Last 5 states:**
```bash
# Use = syntax to avoid argparse interpreting -5 as an option
slice-oem data.oem --slice="-5:" -o -
```

**States 10 through 20:**
```bash
slice-oem data.oem --slice "10:20" -o -
```

**Every third state from index 5 to 50:**
```bash
slice-oem data.oem --slice "5:50:3" -o -
```

**Last state:**
```bash
slice-oem data.oem --slice="-1" -o -
```

**All but the last 10 states:**
```bash
slice-oem data.oem --slice=":-10" -o -
```

**From index 10 to the end:**
```bash
slice-oem data.oem --slice "10:" -o -
```

## Time-Based Slicing

Extract states within specific time windows using ISO 8601 timestamps or relative durations.

### Syntax

```
start[,[stop][,step]]
```

- **start**: Start time (ISO 8601 datetime or duration, inclusive)
- **stop**: Stop time (ISO 8601 datetime or duration, inclusive) - **optional**
- **step**: Resampling interval (duration) - **optional**; interpolation is enabled by default

**Notes**:
- Unlike index-based slicing where the stop index is exclusive, time-based slicing is **inclusive** for both start and stop times.
- Zero (`0`) in start means the OEM start time; zero (`0`) in stop means the OEM end time.
- Negative durations (e.g., `-10m`) are offsets backwards from the OEM end time, so `-10m,` extracts the last 10 minutes.
- Both **stop** and **step** are optional and may be omitted independently:
  - `start` (no comma) extracts one state; with default interpolation enabled this is interpolated at the requested time, while `--no-interpolate` selects the first existing state at or after it
  - `start,` extracts from start to the OEM end time
  - `start,stop` extracts the time range [start, stop] (inclusive)
  - `start,,step` resamples from start to the OEM end time at the given step
  - `start,stop,step` resamples [start, stop] at the given step

### Time Specifications

**Absolute times** use ISO 8601 format:
- `2024-01-01T00:00:00`
- `2024-01-01T12:30:45.123`

**Relative durations** use compact notation:
- `10s` — 10 seconds
- `5m` — 5 minutes
- `2h` — 2 hours
- `1d` — 1 day
- `1h30m` — 1 hour 30 minutes
- `-10m` — 10 minutes before end (negative offset from end)

**Duration interpretation for start:**
- **Positive** (e.g., `1h`, `30m`) → offset from OEM **start time**
- **Zero** (`0`) → OEM **start time**
- **Negative** (e.g., `-10m`) → offset backwards from OEM **end time**

**Duration interpretation for stop:**
- **Positive** (e.g., `1h`, `30m`) → offset from the resolved **start time**
- **Zero** (`0`) or **omitted after comma** → OEM **end time**
- **Negative** (e.g., `-10m`) → offset backwards from OEM **end time**

### Examples

**First hour of data:**
```bash
slice-oem data.oem --time-slice "0,1h" -o -
```

**Specific time window:**
```bash
slice-oem data.oem --time-slice "2024-01-01T00:00:00,2024-01-02T00:00:00" -o -
```

**Single state at specific time:**
```bash
slice-oem data.oem --time-slice "2024-01-01T12:00:00" -o -
```

**Last 30 minutes (from -30m to OEM end):**
```bash
# Use = syntax to avoid argparse interpreting -30m as an option
slice-oem data.oem --time-slice="-30m," -o -
```

**Time window from 1 hour to 3 hours after start:**
```bash
slice-oem data.oem --time-slice "1h,3h" -o -
```

**From 30 minutes after start to OEM end:**
```bash
slice-oem data.oem --time-slice "30m," -o -
```

**From OEM start to end (full range):**
```bash
slice-oem data.oem --time-slice "," -o -     # start omitted → OEM start; stop omitted → OEM end
slice-oem data.oem --time-slice "0," -o -    # explicit OEM start; stop omitted → OEM end
slice-oem data.oem --time-slice ",0" -o -    # start omitted → OEM start; explicit OEM end
slice-oem data.oem --time-slice "0,0" -o -   # explicit OEM start and OEM end
```

**Last 2 hours resampled at 1-minute intervals:**
```bash
slice-oem data.oem --time-slice="-2h,,1m" --interpolate -o -
```

## Interpolation

Generate uniformly spaced states at the requested interval using the selected interpolation method. Interpolation is also used by default to evaluate exact-time selections and range boundaries.

**Note**: Interpolation is **enabled by default**. Use `--no-interpolate` to disable it if needed.

### Requirements

- Must use `--time-slice` (not `--slice`)
- A step size is required for regularly spaced resampling, but not for exact-time selections or interpolated range boundaries.
- Interpolation is enabled by default for time slices. Use `--no-interpolate` to select existing states only; a step size cannot be used with that option.

### Interpolation Method

The default is **5th-degree Hermite interpolation**. Select Hermite, Chebyshev, or Lagrange with `--interpolate-type`; the degree defaults to 5 for any selected method and can be set explicitly. If the input has too few states for the requested degree, the CLI warns that the degree will be reduced to fit the available data.

### Examples

**Resample at 10-minute intervals (interpolation enabled by default):**
```bash
slice-oem data.oem --time-slice "0,1h,10m" -o -
```

**Resample at 30-second intervals:**
```bash
slice-oem data.oem --time-slice "2024-01-01T00:00:00,2024-01-01T01:00:00,30s" -o -
```

**Resample last hour at 5-minute steps:**
```bash
slice-oem data.oem --time-slice="-1h,,5m" -o -
```

**Disable interpolation (use source states only):**
```bash
slice-oem data.oem --time-slice "0,1h" --no-interpolate -o -
```

## Output Formats

### Data-Only Format (`--data-only`)

Outputs state vectors as space-separated values:

```
<ISO-8601 UTC epoch> <X_km> <Y_km> <Z_km> <VX_km/s> <VY_km/s> <VZ_km/s>
```

Example:
```
2024-01-01T00:00:00.000000 6678.137 0.000 0.000 0.000 7.726 0.000
2024-01-01T00:01:00.000000 6724.891 463.560 0.000 -0.339 7.718 0.000
```

### OEM Format (default without `--data-only`)

Outputs a complete CCSDS OEM file with:
- Preserved metadata (object name, reference frame, center, time system)
- Updated start/stop times based on sliced data
- Valid CCSDS OEM structure

Example:
```
CCSDS_OEM_VERS = 2.0
CREATION_DATE = 2024-01-15T10:30:00.000
ORIGINATOR = ephem-toolkit

META_START
OBJECT_NAME = ISS
OBJECT_ID = 1998-067A
CENTER_NAME = EARTH
REF_FRAME = GCRF
TIME_SYSTEM = UTC
START_TIME = 2024-01-01T00:00:00.000
STOP_TIME = 2024-01-01T01:00:00.000
META_STOP

2024-01-01T00:00:00.000000 6678.137 0.000 0.000 0.000 7.726 0.000
2024-01-01T00:01:00.000000 6724.891 463.560 0.000 -0.339 7.718 0.000
...

### OPM Format (`--opm`)

Writes the first selected state as a CCSDS Orbit Parameter Message (OPM).
The selection options still determine which state is selected; `--opm` then
limits the output to that state. OPM output cannot be combined with
`--data-only`.

```bash
slice-oem data.oem --slice "5" --opm -o state.opm
slice-oem data.oem --time-slice "1h" --opm -o state.opm
cat data.oem | slice-oem - --slice "5" --opm -o -
```
```

## Verbose Mode

Use `-v` or `--verbose` to print detailed information to stderr:

```bash
slice-oem data.oem --slice "0:100" --verbose -o -
```

Output includes:
- Input OEM statistics (total states, time span)
- Slice parameters (resolved times, indices)
- Interpolation settings (if applicable)
- Output statistics (selected states, time range)

Example verbose output:
```
[slice_oem] Input OEM:
[slice_oem]   States: 1440
[slice_oem]   Start: 2024-01-01T00:00:00.000
[slice_oem]   End:   2024-01-02T00:00:00.000
[slice_oem]   Span:  1d
[slice_oem] Slicing by index:
[slice_oem]   Range: [0:100], step=1
[slice_oem]   Selected 100 of 1440 states
[slice_oem]   Output start: 2024-01-01T00:00:00.000
[slice_oem]   Output end:   2024-01-01T01:39:00.000
```

## Reading from Standard Input

The script can read OEM data from standard input (stdin) instead of a file. This is useful for piping data from other commands or processing data streams.

### Usage

**Using `-` as the filename:**
```bash
cat orbit.oem | slice-oem - --slice "0:10" -o -
```

The input positional argument is required. Pass `-` explicitly to read from stdin; omitting the input argument is an error.

### Examples

**Pipe from another command:**
```bash
curl https://example.com/orbit.oem | slice-oem - --time-slice "0,1h" -o -
```

**Chain multiple operations:**
```bash
cat large.oem | slice-oem - --slice "::10" -o - | slice-oem - --time-slice "0,1h" -o -
```

**Process compressed files:**
```bash
gunzip -c orbit.oem.gz | slice-oem - --slice "0:100" -o - > sliced.oem
```

**Verbose output with stdin:**
```bash
cat orbit.oem | slice-oem - --slice "0:10" --verbose -o -
```

When reading from stdin, verbose output will show `<stdin>` as the file source:
```
[slice_oem] Input OEM:
[slice_oem]   File: <stdin>
[slice_oem]   Object: ISS
[slice_oem]   Reference frame: GCRF
...
```

## Common Workflows

### Extract First Hour for Analysis

```bash
slice-oem orbit.oem --time-slice "0,1h" -o - > first_hour.txt
```

### Downsample to 5-Minute Intervals

```bash
slice-oem orbit.oem --time-slice "0,,5m" -o - > downsampled.oem
```

### Extract Specific Time Window

```bash
slice-oem orbit.oem \
  --time-slice "2024-06-15T12:00:00,2024-06-15T18:00:00" \
  -o window.oem
```

### Create Reduced OEM File

```bash
slice-oem large.oem --slice "::10" -o - > reduced.oem
```

### Extract Last Orbit Pass

```bash
slice-oem orbit.oem --time-slice="-90m," -o - > last_pass.txt
```

## Programmatic Usage

The underlying library module `ephem_toolkit.core.slice_oem` can be used directly in Python scripts:

```python
import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.slice_oem as slice_oem

# Read OEM file
oem_data = oem.CcsdsOem.read("orbit.oem")

# Slice by index
sliced_oem = slice_oem.extract_sliced_states(oem_data, slice(0, 100))

# Slice by time
from datetime import datetime, timezone
options = slice_oem.TimeSliceOptions(
    start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    stop_time=datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
)
sliced_oem = slice_oem.extract_sliced_states(oem_data, options)

# Write result
sliced_oem.write("sliced.oem")
```

See `tests/ephem_toolkit/core/test_slice_oem.py` for more examples.

## Implementation Details

### Interpolation Algorithm

- **Method**: Hermite interpolation by default; Hermite, Chebyshev, and Lagrange are supported
- **Degree**: 5 by default; set explicitly with `--interpolate-type <type,degree>`
- **API**: Public interpolator implementations selected through the core interpolation factory
- **Application**: Interpolates both position and velocity components

The CLI uses degree 5 when no degree is specified, including when another interpolation method is selected. Internal helper methods are not part of the documented public interface.

### Time Resolution

- All times are resolved to TT seconds since J2000 for internal processing
- Relative durations are computed from OEM start/stop times
- Negative durations offset from the end time
- Positive durations offset from the start time

### Metadata Preservation

When slicing, the following metadata is preserved:
- `OBJECT_NAME`
- `OBJECT_ID` (if present)
- `REF_FRAME`
- `CENTER_NAME`
- `TIME_SYSTEM`

The following metadata is updated:
- `START_TIME` — set to first state timestamp
- `STOP_TIME` — set to last state timestamp
- `USEABLE_START_TIME` and `USEABLE_STOP_TIME` — recalculated for interpolation output, or cleared when no usable interpolated interval remains
- `CREATION_DATE` — set to current time

## Dependencies

- Python 3.9+
- NumPy (for interpolation)
- Local modules:
  - `ephem_toolkit.core.ccsds.oem` — OEM file parsing and writing
  - `ephem_toolkit.core.slice_oem` — Slicing logic and parsers
  - `ephem_toolkit.core.time_utils` — Time parsing and formatting
  - `ephem_toolkit.core.interpolator` — interpolation implementations and factory

## Error Handling

### Common Errors

**Step size without interpolation:**
```
error: step_size requires --interpolate
```
Solution: This error occurs when using `--no-interpolate` with a step size. Remove the `--no-interpolate` flag (interpolation is enabled by default) or remove the step size parameter.

**Invalid slice format:**
```
ValueError: Invalid slice: 0:10:2:3
```
Solution: Use valid Python slice notation (max 3 components).

**Invalid time format:**
```
ValueError: Invalid ISO 8601 datetime: 2024-13-01
```
Solution: Use valid ISO 8601 format or duration notation.

## Related Tools

- `diff-oem` — Compare corresponding states from two OEM files (see [DIFF_OEM.md](DIFF_OEM.md))
- `plot-oem-diff` — Visualize and compare orbits
- `propagate-orbit` — Generate OEM files from propagation
- `oem-to-opm` — Fit an OEM arc and write an OPM with osculating elements
- `oem-to-omm` — Convert OEM to TLE/OMM format

## References

- [CCSDS OEM Standard](https://public.ccsds.org/Pubs/502x0b2c1e2.pdf) — CCSDS 502.0-B-2
- [ISO 8601](https://www.iso.org/iso-8601-date-and-time-format.html) — Date and time format
- [Python slice notation](https://docs.python.org/3/library/functions.html#slice) — Built-in slice objects

## See Also

- [OEM_TO_OPM.md](OEM_TO_OPM.md) — OEM to OPM conversion
- [OEM_TO_OMM.md](OEM_TO_OMM.md) — OEM to OMM/TLE conversion
