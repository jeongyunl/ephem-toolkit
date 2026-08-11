# tudatpy-utils

TLE-related utilities for building, estimating, and converting orbital data.

## Overview

Current TLE-related scripts in this repository include:

- `oem-to-omm`
- `download-tle`
- `omm-to-tle`
- `tle-to-omm`
- `tle-info`
- `common/convert_tle.py`

This document focuses on the primary user-facing tools and the current repository context around them.

After Poetry installation, use `download-tle`, `omm-to-tle`, `tle-to-omm`, and `tle-info` as the canonical commands. The existing script paths remain supported during the transition.

## `oem-to-omm`

This utility estimates a TLE from an OEM-like Cartesian arc. For complete usage and algorithm documentation, see [OEM_TO_OMM.md](OEM_TO_OMM.md).

## `download-tle`

Downloads TLE or OMM data from CelesTrak for specified satellites.

### Synopsis

```bash
download-tle [-h] [--format <format>] <satellite_id> [<satellite_id2>] ...
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `--format` | Output format: `tle`, `3le`, `2le`, `xml`, `kvn`, `omm`, `json`, `json-pretty`, `csv` (default: `tle`) |
| `<satellite_id>` | One or more satellite international designators (e.g., `1998-067A`, `2019-050A`) |

### Behavior

- Downloads TLE or OMM data from CelesTrak for specified satellites
- Saves data to files named after the satellite
- Supports multiple output formats
- Automatically retrieves satellite name from CelesTrak

### Usage

**Download TLE for ISS:**

```bash
download-tle 1998-067A
```

**Download TLE for multiple satellites:**

```bash
download-tle 1998-067A 2019-050A 2023-100G
```

**Download in OMM format:**

```bash
download-tle --format omm 1998-067A
```

**Download in JSON format:**

```bash
download-tle --format json 1998-067A
```

**Show help:**

```bash
download-tle -h
```

### Dependencies

- Python standard library (urllib)

## `tle-info`

Inspects and displays detailed TLE information including orbital elements and Cartesian state.

### Synopsis

```bash
tle-info <tle_file> [<tle_file2>] ...
```

### Options

| Option | Description |
|---|---|
| `<tle_file>` | One or more TLE file paths |

### Behavior

- Reads TLE files and extracts orbital parameters
- Displays TLE epoch, orbital elements, and Cartesian state
- Converts TLE mean elements to Keplerian elements
- Loads SPICE kernels for accurate time conversion

### Output

For each TLE file, prints:

- NORAD catalog number
- Element set number
- Revolution number at epoch
- Epoch (ISO 8601 format)
- B-star drag term
- Inclination (degrees)
- Right ascension (degrees)
- Eccentricity
- Argument of perigee (degrees)
- Mean anomaly (degrees)
- Mean motion (degrees/minute and revolutions/day)
- Mean motion first and second derivatives
- Cartesian state at epoch (position in km, velocity in km/s)
- Keplerian elements (semi-major axis, eccentricity, inclination, etc.)

### Usage

**Display TLE information:**

```bash
tle-info tests/data/ISS-ZARYA_1998-067A.tle
```

**Display information for multiple TLE files:**

```bash
tle-info tests/data/ISS-ZARYA_1998-067A.tle tests/data/AMOS-17_2019-050A.tle
```

**Show help:**

```bash
tle-info -h
```

### Dependencies

- TudatPy
- local helper modules `common.common`, `common.kepler`

## `omm-to-tle`

Converts CCSDS Orbit Mean-Elements Message (OMM) format to Two-Line Element (TLE) format.

### Synopsis

```bash
omm-to-tle [-h] [-o <output.tle>] [<input.omm>]
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `<input.omm>` | Input OMM file path or `-` to read from stdin (default: `-`) |
| `-o`, `--output` | Output TLE file path. If omitted, TLE is printed to stdout |

### Behavior

- Reads OMM data from file or stdin
- Converts mean orbital elements to TLE format
- Writes TLE to file or stdout

### Input format

Accepts CCSDS OMM KVN format.

### Output format

Outputs standard two-line element format:

```text
1 NNNNNC UUUUU CCCC NNNNN.NNNNNNNN  .NNNNNNNN  NNNNN-N NNNNN-N N NNNNN
2 NNNNN NNN.NNNN NNN.NNNN NNNNNNN NNN.NNNN NNN.NNNN NN.NNNNNNNNNNNNNN
```

### Usage

**Convert OMM file to TLE:**

```bash
omm-to-tle tests/data/ISS-ZARYA_1998-067A.omm
```

**Convert OMM file and save to output file:**

```bash
omm-to-tle tests/data/ISS-ZARYA_1998-067A.omm -o output.tle
```

**Convert OMM from stdin:**

```bash
cat tests/data/ISS-ZARYA_1998-067A.omm | omm-to-tle
```

**Show help:**

```bash
omm-to-tle -h
```

### Dependencies

- local helper modules `common.convert_tle`, `common.ccsds.omm`, `common.tle`

## `tle-to-omm`

Converts Two-Line Element (TLE) format to CCSDS Orbit Mean-Elements Message (OMM) format.

### Synopsis

```bash
tle-to-omm [-h] [-o <output.omm>] [<input.tle>]
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `<input.tle>` | Input TLE file path or `-` to read from stdin (default: `-`) |
| `-o`, `--output` | Output OMM file path. If omitted, OMM is printed to stdout |

### Behavior

- Reads TLE data from file or stdin
- Converts TLE elements to OMM format
- Writes OMM to file or stdout

### Input format

Accepts standard two-line element format.

### Output format

Outputs CCSDS OMM format (KVN).

### Usage

**Convert TLE file to OMM:**

```bash
tle-to-omm tests/data/ISS-ZARYA_1998-067A.tle
```

**Convert TLE file and save to output file:**

```bash
tle-to-omm tests/data/ISS-ZARYA_1998-067A.tle -o output.omm
```

**Convert TLE from stdin:**

```bash
cat tests/data/ISS-ZARYA_1998-067A.tle | tle-to-omm
```

**Show help:**

```bash
tle-to-omm -h
```

### Dependencies

- local helper modules `common.convert_tle`, `common.tle`

## Related conversion utilities

Additional scripts currently present in the repository:

- `common/convert_tle.py` — shared conversion helper script

## Common library

- `common/tle.py` — shared `Tle` dataclass, `read_tle()`, and `write_tle()` functions used by all TLE-related scripts
- `common/kepler.py` — Keplerian element conversions (`cartesian_to_keplerian`, `keplerian_to_cartesian`, anomaly conversions, mean motion utilities)
- `common/mean_kepler.py` — mean Keplerian element conversions (`osculating_to_mean_keplerian`, `compute_brouwer_short_period_corrections`, J2 secular propagation)
- `common/convert_tle.py` — TLE/OMM conversion and `tle_to_osculating_keplerian` with J2 short-period corrections
- `common/common.py` — shared utilities

### Other TLE-related scripts

Dependencies vary by script. Some use only the standard library and local helpers, while others may rely on TudatPy for propagation or conversion workflows.
