# OMM-to-TLE Conversion Utility

The `omm-to-tle` utility converts a CCSDS Orbit Mean-Elements Message (OMM) to a Two-Line Element (TLE) set.

## Overview

The command reads OMM data from a file or standard input and directly maps
SGP4-compatible mean elements and their TLE parameters to TLE format. It writes
the result to standard output or a file. This is not an element-fitting
operation: OMMs with another mean-element theory, or without TLE parameters,
cannot be converted by this command.

## Synopsis

```bash
omm-to-tle <input_omm|-> [OPTIONS]
cat input.omm | omm-to-tle - -o -
```

## Options

| Option | Description |
|--------|-------------|
| `<input_omm\|->` | Input OMM file path. Use `-` to read OMM text from stdin. |
| `-o`, `--output <output_tle\|->` | **Required.** Output TLE file path. Use `-` to write to stdout. |
| `-h`, `--help` | Show the help message and exit. |
| `--version` | Show the installed `ephem-toolkit` version and exit. |

## Behavior

- Reads OMM data from a file or stdin.
- Converts OMMs whose `MEAN_ELEMENT_THEORY` is `SGP`, `PPT3`, `SGP4`, or `SGP/SGP4`, provided TLE parameters are present.
- Writes the TLE to the destination specified by the required `--output` option. Use `-` for stdout.
- Reports input, parsing, or conversion errors to stderr and exits with a nonzero status.

## Input Format

The command accepts CCSDS OMM KVN (keyword-value notation) text. Direct
conversion requires an SGP4-compatible `MEAN_ELEMENT_THEORY` and TLE parameters
such as catalog number, classification, element set number, revolution number,
BSTAR, and mean-motion derivatives. Omitted individual TLE parameter fields
may receive parser defaults, but the OMM must contain TLE parameter data. It
does not fit TLE elements for other mean-element theories; use `oem-to-tle`
with an OEM when fitting is required.

## Output Format

The command writes two 69-character TLE lines, including checksums. If the OMM
contains an object name, that name is written as an additional first line.
The TLE lines contain the catalog and epoch data, mean-motion derivatives,
BSTAR, and orbital elements. Values are formatted and rounded to TLE field
precision.

## Examples

```bash
omm-to-tle input.omm -o -
cat input.omm | omm-to-tle - -o -
omm-to-tle input.omm -o output.tle
```

## Output

The `--output` option is required. Set it to `-` to write to stdout or provide
a path to save the TLE set to a file.

## Dependencies

- `ephem_toolkit.core.convert_tle`.
- `ephem_toolkit.core.ccsds.omm`.
- `ephem_toolkit.core.tle`.

## Related Tools

- `tle-to-omm` - Convert a TLE set to OMM.
- `tle-info` - Display TLE parameters and derived orbital elements.

