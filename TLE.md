# tudatpy-utils

Utility scripts for building and parsing TLE files.

## TLE

### `tle/write_tle.py`

Builds a Two-Line Element (TLE) set from explicit command-line arguments, computes both line checksums, prints a summary of all provided elements plus compiled lines, and writes the result to a `.tle` file.

#### Synopsis

```bash
python3 tle/write_tle.py [-h] [--output <file|->] [--name <name>]
  --satellite-number <0..99999> --classification <U|C|S>
  --int-designator-year <0..99> --int-designator-launch-number <0..999> --int-designator-piece <1..3 chars>
  --epoch-year <0..99> --epoch-day <float>
  --mean-motion-first-derivative <float> --mean-motion-second-derivative <tle-exp>
  --bstar <tle-exp> --ephemeris-type <0..9> --element-set-number <0..9999>
  --inclination-deg <float> --raan-deg <float> --eccentricity <0.0..1.0)
  --arg-perigee-deg <float> --mean-anomaly-deg <float>
  --mean-motion-rev-per-day <float> --revolution-number-at-epoch <0..99999>
```

#### Options

| Option | Description | Default |
|---|---|---|
| `-h`, `--help` | Show help message and exit | None |
| `--output` | Output `.tle` file path to write. Use `-` or omit to print TLE to stdout. | `-` |
| `--name` | Optional name line written before TLE line 1 | None |
| `--satellite-number` | NORAD catalog number (0 to 99999) | Required |
| `--classification` | Classification code (`U`, `C`, `S`) | Required |
| `--int-designator-year` | International designator launch year (2-digit) | Required |
| `--int-designator-launch-number` | Launch number of year (3-digit field) | Required |
| `--int-designator-piece` | Launch piece identifier (1 to 3 chars) | Required |
| `--epoch-year` | Epoch year (2-digit) | Required |
| `--epoch-day` | Epoch day-of-year with fractional day | Required |
| `--mean-motion-first-derivative` | First derivative of mean motion (line 1 field) | Required |
| `--mean-motion-second-derivative` | Second derivative in TLE compact exponential notation (e.g. `00000+0`, `29661-4`) | Required |
| `--bstar` | BSTAR drag term in TLE compact exponential notation | Required |
| `--ephemeris-type` | Ephemeris type digit (0 to 9) | Required |
| `--element-set-number` | Element set number (0 to 9999) | Required |
| `--inclination-deg` | Inclination in degrees | Required |
| `--raan-deg` | Right ascension of ascending node in degrees | Required |
| `--eccentricity` | Eccentricity in decimal form (converted to 7-digit TLE field) | Required |
| `--arg-perigee-deg` | Argument of perigee in degrees | Required |
| `--mean-anomaly-deg` | Mean anomaly in degrees | Required |
| `--mean-motion-rev-per-day` | Mean motion in revolutions per day | Required |
| `--revolution-number-at-epoch` | Revolution number at epoch (0 to 99999) | Required |

#### Output

The script prints:

1. A full summary of all input data elements.
2. The compiled TLE line 1 and line 2 (including checksum).
3. A save confirmation message.

The script writes:

- A `.tle` file containing either:
  - line 1 + line 2, or
  - name + line 1 + line 2 (when `--name` is provided).

When `--output -` is used or `--output` is omitted, the script prints the TLE text to stdout instead of writing a file.

#### Usage

**Build a TLE without a name line:**

```bash
python3 tle/write_tle.py \
  --output tle/LEO-3_2023-100G.tle \
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

**Build a TLE with a satellite name line:**

```bash
python3 tle/write_tle.py \
  --output mysat.tle \
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

---

### `tle/parse_tle.py`

Parses a TLE from stdin, prints a full summary of extracted data elements and checksums, prints a `tle/write_tle.py` command that reconstructs the same TLE, and can optionally verify exact reconstruction.

#### Synopsis

```bash
python3 tle/parse_tle.py [-h] [input.tle] [--output <file>] [--verify]
```

#### Options

| Option | Description | Default |
|---|---|---|
| `-h`, `--help` | Show help message and exit | None |
| `input` | Positional input TLE file path. Use `-` or omit to read from stdin. | `-` |
| `--output` | Output path used in the generated `tle/write_tle.py` command; also used as verification target when `--verify` is enabled | `reconstructed.tle` |
| `--verify` | Execute the generated `tle/write_tle.py` command and verify the rebuilt content is identical to the parsed source | `off` |

#### Input Format

The script reads from stdin and accepts either:

1. Two-line form:

```text
<line1>
<line2>
```

2. Three-line form with a name:

```text
<name>
<line1>
<line2>
```

Where `line1` starts with `1 ` and `line2` starts with `2 `.

#### Output

The script prints:

1. Parsed source lines (and optional name).
2. All extracted TLE data elements for line 1 and line 2.
3. Source and computed checksums for both lines.
4. A ready-to-run `tle/write_tle.py` command that should reproduce the source TLE.
5. If `--verify` is set: a `PASS`/`FAIL` reconstruction result.

#### Usage

**Parse a TLE from a positional file argument and print summary + reconstruction command:**

```bash
python3 tle/parse_tle.py tle/LEO-3_2023-100G.tle --output tle/rebuilt.tle
```

**Parse a TLE from file via stdin and print summary + reconstruction command:**

```bash
cat tle/LEO-3_2023-100G.tle | python3 tle/parse_tle.py --output tle/rebuilt.tle
```

**Parse and verify exact reconstruction in one step:**

```bash
cat tle/LEO-3_2023-100G.tle | python3 tle/parse_tle.py --output tle/rebuilt.tle --verify
```

**Parse a named TLE provided inline:**

```bash
cat << 'EOF' | python3 tle/parse_tle.py --output tle/out.tle --verify
MYSAT-1
1 12345U 25001A   26120.25000000  .00001234  00000+0  12345-5 0   421
2 12345  97.5000  12.3456 0012345 200.0000 150.0000 14.12345678    19
EOF
```

#### Verification Behavior (`--verify`)

When enabled, `tle/parse_tle.py` runs the generated reconstruction command and compares output text against the parsed source text.

- Exit code `0`: verification succeeded.
- Exit code `2`: verification failed.
- Exit code `1`: input/parse error.

#### Dependencies

- Python 3 standard library only (`argparse`, `sys`, `re`, `subprocess`, `shlex`).

---
