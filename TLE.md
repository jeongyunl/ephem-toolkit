# tudatpy-utils

TLE-related utilities for building, parsing, estimating, and converting orbital data.

## Overview

Current TLE-related scripts in this repository include:

- `tle/write_tle.py`
- `tle/parse_tle.py`
- `tle/build_tle.py`
- `tle/download_tle.py`
- `tle/omm_to_tle.py`
- `tle/tle_to_omm.py`
- `tle/tle_info.py`
- `common/convert_tle.py`

This document focuses on the primary user-facing build/parse tools and the current repository context around them.

## `tle/write_tle.py`

Build a Two-Line Element (TLE) set from explicit command-line fields and write it to stdout or a file.

### Synopsis

```bash
python3 tle/write_tle.py [-h] [--output <file|->] [--name <name>]
  --satellite-number <0..99999> --classification <U|C|S>
  --int-designator-year <0..99> --int-designator-launch-number <0..999> --int-designator-piece <piece>
  --epoch-year <0..99> --epoch-day <day.fraction>
  --mean-motion-first-derivative <value> --mean-motion-second-derivative <tle-exp>
  --bstar <tle-exp> --ephemeris-type <0..9> --element-set-number <0..9999>
  --inclination-deg <deg> --raan-deg <deg> --eccentricity <0.0..1.0)
  --arg-perigee-deg <deg> --mean-anomaly-deg <deg>
  --mean-motion-rev-per-day <rev/day> --revolution-number-at-epoch <0..99999>
```

### Options

| Option | Description | Default |
|---|---|---|
| `-h`, `--help` | Show help message and exit | none |
| `--output` | Output TLE file path; use `-` to print TLE text to stdout | `-` |
| `--name` | Optional name line written above line 1 | none |
| `--satellite-number` | NORAD catalog number | required |
| `--classification` | Classification code: `U`, `C`, or `S` | required |
| `--int-designator-year` | International designator launch year | required |
| `--int-designator-launch-number` | International designator launch number of year | required |
| `--int-designator-piece` | International designator piece identifier | required |
| `--epoch-year` | Epoch year | required |
| `--epoch-day` | Epoch day-of-year with fractional day | required |
| `--mean-motion-first-derivative` | First derivative of mean motion | required |
| `--mean-motion-second-derivative` | Second derivative in compact TLE exponential notation | required |
| `--bstar` | BSTAR drag term in compact TLE exponential notation | required |
| `--ephemeris-type` | Ephemeris type digit | required |
| `--element-set-number` | Element set number | required |
| `--inclination-deg` | Inclination in degrees | required |
| `--raan-deg` | Right ascension of ascending node in degrees | required |
| `--eccentricity` | Eccentricity in decimal form | required |
| `--arg-perigee-deg` | Argument of perigee in degrees | required |
| `--mean-anomaly-deg` | Mean anomaly in degrees | required |
| `--mean-motion-rev-per-day` | Mean motion in revolutions per day | required |
| `--revolution-number-at-epoch` | Revolution number at epoch | required |

### Validation behavior

The current source validates, among other things:

- `satellite-number` in `[0, 99999]`
- `int-designator-year` in `[0, 99]`
- `int-designator-launch-number` in `[0, 999]`
- `int-designator-piece` length in `[1, 3]`
- `epoch-year` in `[0, 99]`
- `epoch-day` in `[0.0, 367.0)`
- `ephemeris-type` in `[0, 9]`
- `element-set-number` in `[0, 9999]`
- `eccentricity` in `[0.0, 1.0)`
- `revolution-number-at-epoch` in `[0, 99999]`

### Output

The script prints a summary including:

1. output destination
2. optional name
3. all line-1 fields
4. all line-2 fields
5. compiled line 1 and line 2

Then it either:

- prints the TLE text to stdout when `--output -` is used, or
- writes the TLE text to the requested file

### Examples

**Write a TLE to a file:**

```bash
python3 tle/write_tle.py \
  --output test/LEO-3_2023-100G.tle \
  --satellite-number 57392 \
  --classification U \
  --int-designator-year 23 \
  --int-designator-launch-number 100 \
  --int-designator-piece G \
  --epoch-year 26 \
  --epoch-day 151.29745462 \
  --mean-motion-first-derivative -0.00000028 \
  --mean-motion-second-derivative 00000+0 \
  --bstar 19634-4 \
  --ephemeris-type 0 \
  --element-set-number 999 \
  --inclination-deg 99.5616 \
  --raan-deg 275.7774 \
  --eccentricity 0.0018951 \
  --arg-perigee-deg 61.1275 \
  --mean-anomaly-deg 299.1769 \
  --mean-motion-rev-per-day 13.68420212 \
  --revolution-number-at-epoch 14333
```

**Print a named TLE to stdout:**

```bash
python3 tle/write_tle.py \
  --output - \
  --name MYSAT-1 \
  --satellite-number 12345 \
  --classification U \
  --int-designator-year 25 \
  --int-designator-launch-number 1 \
  --int-designator-piece A \
  --epoch-year 26 \
  --epoch-day 120.25000000 \
  --mean-motion-first-derivative 0.00001234 \
  --mean-motion-second-derivative 00000+0 \
  --bstar 12345-5 \
  --ephemeris-type 0 \
  --element-set-number 42 \
  --inclination-deg 97.5000 \
  --raan-deg 12.3456 \
  --eccentricity 0.0012345 \
  --arg-perigee-deg 200.0000 \
  --mean-anomaly-deg 150.0000 \
  --mean-motion-rev-per-day 14.12345678 \
  --revolution-number-at-epoch 1
```

## `tle/parse_tle.py`

Parse a TLE from a file or stdin, print a full summary, and generate the equivalent `tle/write_tle.py` reconstruction command.

### Synopsis

```bash
python3 tle/parse_tle.py [-h] [<input.tle>] [--output <file>] [--verify]
```

### Options

| Option | Description | Default |
|---|---|---|
| `-h`, `--help` | Show help message and exit | none |
| `<input.tle>` | Input TLE file path; use `-` or omit to read from stdin | `-` |
| `--output` | Output path inserted into the generated reconstruction command | `reconstructed.tle` |
| `--verify` | Run the generated reconstruction command and compare rebuilt text to the parsed source | off |

### Input format

The parser accepts standard two-line or three-line named TLE text:

```text
<line1>
<line2>
```

or

```text
<name>
<line1>
<line2>
```

The actual parsing is delegated to `common.tle.read_tle(...)`.

### Output

The script prints:

1. parsed name, if present
2. source line 1 and line 2
3. extracted line-1 elements
4. extracted line-2 elements
5. source and expected checksums for both lines
6. a ready-to-run `tle/write_tle.py` command

When `--verify` is enabled, it also:

- runs the generated reconstruction command
- reads the rebuilt output file
- compares rebuilt text against the parsed source text
- prints `PASS` or `FAIL`

### Exit codes

Current behavior from the source:

- `0` on success
- `1` on input/read/parse errors
- `2` when `--verify` is requested and reconstruction does not match

### Examples

**Parse a sample TLE file and print the reconstruction command:**

```bash
python3 tle/parse_tle.py test/LEO-3_2023-100G.tle --output rebuilt.tle
```

**Parse from stdin:**

```bash
cat test/LEO-3_2023-100G.tle | python3 tle/parse_tle.py --output rebuilt.tle
```

**Parse and verify exact reconstruction:**

```bash
cat test/LEO-3_2023-100G.tle | python3 tle/parse_tle.py --output rebuilt.tle --verify
```

**Parse a named TLE provided inline:**

```bash
cat << 'EOF' | python3 tle/parse_tle.py --output out.tle --verify
MYSAT-1
1 12345U 25001A   26120.25000000  .00001234  00000+0  12345-5 0   421
2 12345  97.5000  12.3456 0012345 200.0000 150.0000 14.12345678    19
EOF
```

## `tle/build_tle.py`

This repository also contains `tle/build_tle.py`, which estimates a TLE from an OEM-like Cartesian arc rather than from explicit TLE fields.

That script is documented separately in:

- [`tle/build_tle.md`](tle/build_tle.md)

## Related conversion utilities

Additional scripts currently present in the repository:

- `tle/omm_to_tle.py` — convert OMM input to TLE output
- `tle/tle_to_omm.py` — convert TLE input to OMM output
- `tle/download_tle.py` — download TLE data
- `tle/tle_info.py` — inspect TLE information
- `common/convert_tle.py` — shared conversion helper script

## Dependencies

### `tle/write_tle.py`

- Python standard library
- local helper module `common.tle`

### `tle/parse_tle.py`

- Python standard library
- local helper module `common.tle`

### Other TLE-related scripts

Dependencies vary by script. Some use only the standard library and local helpers, while others may rely on TudatPy for propagation or conversion workflows.
