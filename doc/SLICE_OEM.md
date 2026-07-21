# OEM Slicing Utility

The `bin/slice_oem.py` script extracts subsets of CCSDS OEM (Orbit Ephemeris Message) ephemeris data by index or time range, with optional interpolation support.

## Overview

This utility provides flexible slicing capabilities for OEM files:

- **Index-based slicing**: Extract states using Python-style slice notation
- **Time-based slicing**: Extract states within specific time windows
- **Interpolation**: Generate uniformly-spaced states at specified intervals
- **Flexible output**: Raw state vectors or full OEM format

The script is built on the `common.slice_oem` library module, which provides reusable slicing functions for programmatic use.

## Synopsis

```bash
python3 bin/slice_oem.py <oem_file> [OPTIONS]
cat data.oem | python3 bin/slice_oem.py - [OPTIONS]
cat data.oem | python3 bin/slice_oem.py [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `<oem_file>` | Path to input CCSDS OEM file (use `-` or omit to read from stdin) |
| `-s`, `--slice SLICE` | Python-style slice index (e.g., `0:10`, `::2`, `5`, `-5:`) |
| `-t`, `--time-slice TIME_SLICE` | Time slice specifier: `start[,[stop][,step]]` |
| `-i`, `--interpolate` | Enable Lagrange interpolation when step size is provided (enabled by default) |
| `--no-interpolate` | Disable interpolation |
| `--raw` | Output raw state vectors only (default: OEM format) |
| `-v`, `--verbose` | Print detailed debug information to stderr |
| `-h`, `--help` | Show help message and exit |

**Note**: `--slice` and `--time-slice` are mutually exclusive.

### Handling Negative Indices with Argparse

When using negative indices (e.g., `-5:` for the last 5 states), argparse interprets values starting with `-` as option flags. To work around this limitation, use one of these methods:

**Method 1: Use `=` syntax (recommended)**
```bash
python3 bin/slice_oem.py data.oem --slice="-5:"
```

**Method 2: Use `--` to signal end of options**
```bash
python3 bin/slice_oem.py data.oem -- --slice "-5:"
# Note: This doesn't work with argparse's standard behavior
```

**Method 3: Quote and use equals**
```bash
python3 bin/slice_oem.py data.oem --slice='-5:'
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
python3 bin/slice_oem.py data.oem --slice "0:10"
```

**Every other state:**
```bash
python3 bin/slice_oem.py data.oem --slice "::2"
```

**Single state at index 5:**
```bash
python3 bin/slice_oem.py data.oem --slice "5"
```

**Last 5 states:**
```bash
# Use = syntax to avoid argparse interpreting -5 as an option
python3 bin/slice_oem.py data.oem --slice="-5:"
```

**States 10 through 20:**
```bash
python3 bin/slice_oem.py data.oem --slice "10:20"
```

**Every third state from index 5 to 50:**
```bash
python3 bin/slice_oem.py data.oem --slice "5:50:3"
```

**Last state:**
```bash
python3 bin/slice_oem.py data.oem --slice="-1"
```

**All but the last 10 states:**
```bash
python3 bin/slice_oem.py data.oem --slice=":-10"
```

**From index 10 to the end:**
```bash
python3 bin/slice_oem.py data.oem --slice "10:"
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
  - `start` (no comma) extracts a single state nearest to start
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
- **Positive** (e.g., `1h`, `30m`) → offset from OEM **start time**
- **Zero** (`0`) or **omitted after comma** → OEM **end time**
- **Negative** (e.g., `-10m`) → offset backwards from OEM **end time**

### Examples

**First hour of data:**
```bash
python3 bin/slice_oem.py data.oem --time-slice "0,1h"
```

**Specific time window:**
```bash
python3 bin/slice_oem.py data.oem --time-slice "2024-01-01T00:00:00,2024-01-02T00:00:00"
```

**Single state at specific time:**
```bash
python3 bin/slice_oem.py data.oem --time-slice "2024-01-01T12:00:00"
```

**Last 30 minutes (from -30m to OEM end):**
```bash
# Use = syntax to avoid argparse interpreting -30m as an option
python3 bin/slice_oem.py data.oem --time-slice="-30m,"
```

**Time window from 1 hour to 3 hours after start:**
```bash
python3 bin/slice_oem.py data.oem --time-slice "1h,3h"
```

**From 30 minutes after start to OEM end:**
```bash
python3 bin/slice_oem.py data.oem --time-slice "30m,"
```

**From OEM start to end (full range):**
```bash
python3 bin/slice_oem.py data.oem --time-slice ","     # start omitted → OEM start; stop omitted → OEM end
python3 bin/slice_oem.py data.oem --time-slice "0,"    # explicit OEM start; stop omitted → OEM end
python3 bin/slice_oem.py data.oem --time-slice ",0"    # start omitted → OEM start; explicit OEM end
python3 bin/slice_oem.py data.oem --time-slice "0,0"   # explicit OEM start and OEM end
```

**Last 2 hours resampled at 1-minute intervals:**
```bash
python3 bin/slice_oem.py data.oem --time-slice="-2h,,1m" --interpolate
```

## Interpolation

Generate uniformly-spaced states at specified intervals using Lagrange polynomial interpolation.

**Note**: Interpolation is **enabled by default**. Use `--no-interpolate` to disable it if needed.

### Requirements

- Must use `--time-slice` (not `--slice`)
- Must specify step size
- Interpolation is enabled by default (use `--no-interpolate` to disable)

### Interpolation Method

The script uses **8th-degree Lagrange polynomial interpolation** to compute intermediate states. This provides smooth, accurate interpolation suitable for orbital mechanics applications.

### Examples

**Resample at 10-minute intervals (interpolation enabled by default):**
```bash
python3 bin/slice_oem.py data.oem --time-slice "0,1h,10m"
```

**Resample at 30-second intervals:**
```bash
python3 bin/slice_oem.py data.oem --time-slice "2024-01-01T00:00:00,2024-01-01T01:00:00,30s"
```

**Resample last hour at 5-minute steps:**
```bash
python3 bin/slice_oem.py data.oem --time-slice "-1h,,5m"
```

**Disable interpolation (extract nearest states only):**
```bash
python3 bin/slice_oem.py data.oem --time-slice "0,1h" --no-interpolate
```

## Output Formats

### Raw Format (default with `--raw`)

Outputs state vectors as space-separated values:

```
<ISO-8601 UTC epoch> <X_km> <Y_km> <Z_km> <VX_km/s> <VY_km/s> <VZ_km/s>
```

Example:
```
2024-01-01T00:00:00.000000 6678.137 0.000 0.000 0.000 7.726 0.000
2024-01-01T00:01:00.000000 6724.891 463.560 0.000 -0.339 7.718 0.000
```

### OEM Format (default without `--raw`)

Outputs a complete CCSDS OEM file with:
- Preserved metadata (object name, reference frame, center, time system)
- Updated start/stop times based on sliced data
- Valid CCSDS OEM structure

Example:
```
CCSDS_OEM_VERS = 2.0
CREATION_DATE = 2024-01-15T10:30:00.000
ORIGINATOR = tudatpy-utils

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
```

## Verbose Mode

Use `-v` or `--verbose` to print detailed information to stderr:

```bash
python3 bin/slice_oem.py data.oem --slice "0:100" --verbose
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
cat orbit.oem | python3 bin/slice_oem.py - --slice "0:10"
```

**Omitting the filename entirely:**
```bash
cat orbit.oem | python3 bin/slice_oem.py --slice "0:10"
```

### Examples

**Pipe from another command:**
```bash
curl https://example.com/orbit.oem | python3 bin/slice_oem.py - --time-slice "0,1h"
```

**Chain multiple operations:**
```bash
cat large.oem | python3 bin/slice_oem.py --slice "::10" | python3 bin/slice_oem.py - --time-slice "0,1h"
```

**Process compressed files:**
```bash
gunzip -c orbit.oem.gz | python3 bin/slice_oem.py - --slice "0:100" > sliced.oem
```

**Verbose output with stdin:**
```bash
cat orbit.oem | python3 bin/slice_oem.py --slice "0:10" --verbose
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
python3 bin/slice_oem.py orbit.oem --time-slice "0,1h" > first_hour.txt
```

### Downsample to 5-Minute Intervals

```bash
python3 bin/slice_oem.py orbit.oem --time-slice "0,,5m" > downsampled.oem
```

### Extract Specific Time Window

```bash
python3 bin/slice_oem.py orbit.oem \
  --time-slice "2024-06-15T12:00:00,2024-06-15T18:00:00" \
  > window.oem
```

### Create Reduced OEM File

```bash
python3 bin/slice_oem.py large.oem --slice "::10" > reduced.oem
```

### Extract Last Orbit Pass

```bash
python3 bin/slice_oem.py orbit.oem --time-slice "-90m," > last_pass.txt
```

## Programmatic Usage

The underlying library module `common.slice_oem` can be used directly in Python scripts:

```python
import common.oem as oem
import common.slice_oem as slice_oem

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

See `test/common/test_common_slice_oem.py` for more examples.

## Implementation Details

### Interpolation Algorithm

- **Method**: Lagrange polynomial interpolation
- **Degree**: 8th-order polynomial
- **Implementation**: `common.interpolator.lagrange.LagrangeInterpolator`
- **Application**: Interpolates both position and velocity components

The 8th-degree polynomial provides a good balance between accuracy and numerical stability for typical orbital trajectories.

### Time Resolution

- All times are resolved to POSIX timestamps (seconds since 1970-01-01 00:00:00 UTC)
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
- `CREATION_DATE` — set to current time

## Dependencies

- Python 3.7+
- NumPy (for interpolation)
- Local modules:
  - `common.oem` — OEM file parsing and writing
  - `common.slice_oem` — Slicing logic and parsers
  - `common.time_utils` — Time parsing and formatting
  - `common.interpolator.lagrange` — Lagrange interpolation

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

- `bin/state_diff.py` — Compare two OEM states
- `plotting/plot_orbits.py` — Visualize and compare orbits
- `propagation/propagate_orbit.py` — Generate OEM files from propagation
- `oem_to_omm/oem_to_omm.py` — Convert OEM to TLE/OMM format

## References

- [CCSDS OEM Standard](https://public.ccsds.org/Pubs/502x0b2c1e2.pdf) — CCSDS 502.0-B-2
- [ISO 8601](https://www.iso.org/iso-8601-date-and-time-format.html) — Date and time format
- [Python slice notation](https://docs.python.org/3/library/functions.html#slice) — Built-in slice objects

## See Also

- [MISC.md](MISC.md) — Overview of miscellaneous utilities
- [OEM_TO_OMM.md](OEM_TO_OMM.md) — OEM to OMM/TLE conversion
- [PROPAGATION.md](PROPAGATION.md) — Orbit propagation tools
