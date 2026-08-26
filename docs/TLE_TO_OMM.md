# TLE-to-OMM Conversion Utility

The `tle-to-omm` utility converts a Two-Line Element (TLE) set to a CCSDS Orbit Mean-Elements Message (OMM).

## Overview

The command reads TLE text from a file or stdin and writes OMM text to stdout or an output file.

## Overview

This utility reads a standard two-line element set, converts the TLE elements
to CCSDS OMM format, and writes the result to the requested destination.

## Synopsis

```bash
tle-to-omm <input_tle|-> [OPTIONS]
cat input.tle | tle-to-omm - -o -
```

## Options

| Option | Description |
|--------|-------------|
| `<input_tle|->` | Input TLE file path. Use `-` to read TLE text from stdin. |
| `-o`, `--output <output_omm|->` | Output OMM file path. Use `-` to write to stdout. |
| `-h`, `--help` | Show the help message and exit. |

## Behavior

- Reads TLE data from a file or stdin.
- Converts TLE elements to CCSDS OMM format.
- Writes the OMM to a file when `--output` is provided, or to stdout otherwise.

## Input Format

The command accepts standard two-line element format.

## Output Format

The command writes CCSDS OMM format using the KVN representation.

## Examples

```bash
tle-to-omm input.tle -o -
cat input.tle | tle-to-omm - -o -
tle-to-omm input.tle -o output.omm
```

## Output

The command writes the converted OMM to stdout when no output path is supplied. Use `--output` to save the result.

## Dependencies

- `ephem_toolkit.core.convert_tle`.
- `ephem_toolkit.core.tle`.

## Related Tools

- `omm-to-tle` - Convert OMM data to TLE.
- `download-tle` - Download TLE or OMM data.
- `propagate-tle` - Propagate a TLE history.

