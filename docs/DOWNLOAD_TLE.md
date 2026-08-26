# TLE Download Utility

The `download-tle` utility downloads TLE or OMM data for one or more satellites from CelesTrak.

## Overview

- Request data by repeating `--satellite-id`.
- Select a CelesTrak output format with `--format`.
- Write the downloaded response using the command's normal output handling.

## Synopsis

```bash
download-tle --satellite-id <id> [OPTIONS]
download-tle --satellite-id <id> --satellite-id <id> --format omm
```

## Options

| Option | Description |
|--------|-------------|
| `--satellite-id <id>` | Satellite international designator. Repeat for multiple satellites. |
| `--format <format>` | Output format. Defaults to `tle`. |
| `-h`, `--help` | Show the help message and exit. |

Supported format values are `tle`, `3le`, `2le`, `xml`, `kvn`, `omm`, `json`, `json-pretty`, and `csv`. The `omm` value is accepted as an alias for the KVN OMM format.

## Behavior

- Downloads TLE or OMM data from CelesTrak for each requested satellite.
- Retrieves the satellite name from CelesTrak for use in the output filename.
- Supports multiple satellite IDs by repeating `--satellite-id`.
- Supports the output formats listed above.
- Saves each result in the current working directory using the satellite name and international designator.

## Output Files

Output filenames use the following pattern:

```text
<satellite-name>_<satellite-id>.<extension>
```

For example, an ISS TLE download may be saved as:

```text
ISS_(ZARYA)_1998-067A.tle
```

The filename extension is selected from the requested format. The command prints the selected format, satellite name, and saved filename as it processes each request.

## Examples

```bash
download-tle --satellite-id 1998-067A
download-tle --satellite-id 1998-067A --satellite-id 2019-050A
download-tle --satellite-id 1998-067A --format omm
download-tle --satellite-id 1998-067A --format json
```

## Usage

**Download TLE data for the ISS:**

```bash
download-tle --satellite-id 1998-067A
```

**Download data for multiple satellites:**

```bash
download-tle \
	--satellite-id 1998-067A \
	--satellite-id 2019-050A \
	--satellite-id 2023-100G
```

**Download OMM data:**

```bash
download-tle --format omm --satellite-id 1998-067A
```

**Show help:**

```bash
download-tle --help
```

## Requirements

The command requires network access to CelesTrak and satellite IDs that are valid international designators supported by the requested data set. It uses Python's standard-library `urllib` modules for HTTP requests.

## Related Tools

- `tle-info` - Inspect downloaded TLE files.
- `tle-to-omm` - Convert TLE data to OMM.
- `propagate-tle` - Propagate a TLE history.

