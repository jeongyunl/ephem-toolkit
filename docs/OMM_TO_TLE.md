# OMM-to-TLE Conversion Utility

The `omm-to-tle` utility converts a CCSDS Orbit Mean-Elements Message (OMM) to a Two-Line Element (TLE) set.

## Overview

The command reads OMM data from a file or standard input, converts the mean
orbital elements to TLE format, and writes the result to standard output or a
file.

## Synopsis

```bash
omm-to-tle <input_omm|-> [OPTIONS]
cat input.omm | omm-to-tle -
```

## Options

| Option | Description |
|--------|-------------|
| `<input_omm|->` | Input OMM file path. Use `-` to read OMM text from stdin. |
| `-o`, `--output <output_tle|->` | Output TLE file path. Use `-` to write to stdout. |
| `-h`, `--help` | Show the help message and exit. |

## Behavior

- Reads OMM data from a file or stdin.
- Converts mean orbital elements to TLE format.
- Writes the TLE to a file when `--output` is provided, or to stdout otherwise.

## Input Format

The command accepts CCSDS OMM KVN format.

## Output Format

The command writes a standard two-line element set:

```text
1 NNNNNC UUUUU CCCC NNNNN.NNNNNNNN  .NNNNNNNN  NNNNN-N NNNNN-N N NNNNN
2 NNNNN NNN.NNNN NNN.NNNN NNNNNNN NNN.NNNN NNN.NNNN NN.NNNNNNNNNNNNNN
```

## Examples

```bash
omm-to-tle input.omm
cat input.omm | omm-to-tle -
omm-to-tle input.omm -o output.tle
```

## Output

The command writes the converted TLE set to stdout when no output path is supplied. Use `--output` to save the result to a file.

## Dependencies

- `ephem_toolkit.core.convert_tle`.
- `ephem_toolkit.core.ccsds.omm`.
- `ephem_toolkit.core.tle`.

## Related Tools

- `tle-to-omm` - Convert a TLE set to OMM.
- `tle-info` - Display TLE parameters and derived orbital elements.

See [TLE.md](TLE.md) for the grouped TLE workflow.
