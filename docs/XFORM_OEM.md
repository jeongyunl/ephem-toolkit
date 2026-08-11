# OEM Transformation Utility

The `xform-oem` utility transforms CCSDS OEM (Orbit Ephemeris Message)
state histories between supported reference frames, converts ECEF positions to
Azimuth-Elevation-Range (AER) coordinates, or rewrites OEM data and metadata.
It can read from a file or standard input and write either an OEM file, AER
text, or standard output.

After Poetry installation, use `xform-oem` as the canonical command. The existing `python3 src/xform_oem/xform_oem.py ...` examples remain supported during the transition.

## Overview

This utility provides several related operations:

- **Reference-frame conversion**: Transform position and velocity state vectors
  between supported inertial, TEME, and Earth-fixed frames
- **AER conversion**: Convert ECEF/ITRF positions to azimuth, elevation, and
  range relative to a ground station
- **Metadata overrides**: Rewrite OEM metadata fields after a frame conversion
- **Header overrides**: Rewrite CCSDS OEM header fields
- **Stream processing**: Read OEM input from stdin and write results to stdout

With no transformation or override options, the input OEM is written back out
as an OEM file.

Use `--data-only` to omit the OEM header and metadata and write only the state
rows. Without `--x-csv`, rows use the standard space-separated OEM state format;
with `--x-csv`, the output includes the CSV state header.

## Synopsis

```bash
xform-oem <oem_file> [OPTIONS]
cat data.oem | xform-oem [OPTIONS]
```

Use `-` or omit `<oem_file>` to read CCSDS OEM data from standard input. The
default output destination is standard output.

## Options

| Option | Description |
|---|---|
| `<oem_file>` | Optional path to an input CCSDS OEM file; use `-` or omit to read from stdin |
| `--x-ref-frame <frame>` | Convert state vectors to the target frame using the OEM `REF_FRAME` as source |
| `--x-ref-frame <base_frame,target_frame>` | Override the source frame and convert state vectors to the target frame |
| `--x-aer <lat,lon,alt>` | Convert ECEF/ITRF positions to AER text using latitude/longitude in degrees and altitude in metres |
| `--data-only` | Write only state data without the OEM header and metadata |
| `--set-meta <KEY=VALUE>` | Override an OEM metadata field; repeatable |
| `--set-header <KEY=VALUE>` | Override an OEM header field; repeatable |
| `-o`, `--output <file\|->` | Output file path; defaults to `-` for stdout |
| `-v`, `--verbose` | Print input and transformation details to stderr |
| `-h`, `--help` | Show help message and exit |

The `--x-aer` mode cannot be combined with `--x-ref-frame`, `--set-meta`, or
`--set-header`.

## Supported Reference Frames

The `--x-ref-frame` option accepts the frame names exposed by
`core.frame_utils.Frame`:

- `TEME`
- `J2000`
- `EME2000`
- `ICRF`
- `GCRF`
- `ITRF1993` (alias `ITRF93`)
- `ITRF`

`J2000`, `EME2000`, `ICRF`, and `GCRF` are treated as equivalent inertial
frames by the conversion helper. The `--x-ref-frame` option transforms state
data, including positions and velocities, rather than only changing metadata.
After a successful conversion, the output OEM `REF_FRAME` metadata is updated
to the target frame, except where the helper returns its canonical frame value.

Frame conversion is epoch-dependent. The script converts each state at its
own timestamp, including the velocity contribution from time-dependent Earth
rotation models where applicable.

## Reference-Frame Conversion

Convert an OEM state history to a new reference frame:

```bash
xform-oem input.oem --x-ref-frame ITRF1993 -o output.oem
```

By default, the source frame is read from the input OEM metadata. Override it
when the metadata does not describe the actual state vectors:

```bash
xform-oem input.oem \
  --x-ref-frame GCRF,ITRF1993 \
  -o output.oem
```

OEM Cartesian states use kilometres and kilometres per second. The conversion
library performs calculations in metres and metres per second, then converts
the results back to OEM units before writing the output.

### Frame Conversion Behavior

- Positions and velocities are both transformed.
- Each state is evaluated at its input timestamp.
- The input OEM is modified in memory and then written to the selected output.
- The output `REF_FRAME` metadata is updated after a successful conversion.
- If a state cannot be converted, an error is written to stderr and the
  conversion returns without writing the transformed OEM.

## AER Conversion

Convert ECEF or ITRF positions to Azimuth-Elevation-Range coordinates relative
to a ground station:

```bash
xform-oem ecef.oem --x-aer 40.7128,-74.0060,10.0
```

The three comma-separated values are:

1. Latitude in degrees, positive north
2. Longitude in degrees, positive east
3. Altitude above the WGS-84 ellipsoid in metres

For example, read OEM data from stdin and save AER output to a file:

```bash
cat ecef.oem | xform-oem \
  --x-aer 40.7128,-74.0060,10.0 \
  -o station_aer.txt
```

The script warns when the input reference frame does not contain `ECEF` or
`ITRF` in its name, but it still attempts the position conversion. AER mode
converts positions only; velocities are not converted to AER rates.

### AER Output Format

Each output line contains four space-separated values:

```text
<ISO-8601 UTC timestamp> <azimuth_deg> <elevation_deg> <range_m>
```

Example:

```text
2024-01-01T00:00:00.000000     82.451203    18.720114       734512.382
2024-01-01T00:01:00.000000     83.102845    18.534901       735108.947
```

- **Timestamp**: UTC ISO 8601 timestamp
- **Azimuth**: Degrees, with 0 degrees pointing north and 90 degrees east
- **Elevation**: Degrees, with 0 degrees at the horizon and 90 degrees at zenith
- **Range**: Metres

AER mode writes text rather than a CCSDS OEM document, so OEM metadata and
headers are not included.

## Metadata Overrides

Use repeated `--set-meta KEY=VALUE` options to override output OEM metadata:

```bash
xform-oem input.oem \
  --x-ref-frame ITRF1993 \
  --set-meta OBJECT_NAME=ISS \
  --set-meta CENTER_NAME=EARTH \
  -o output.oem
```

Supported metadata keys are the fields defined by `core.ccsds.oem.OemMeta`,
including:

- `OBJECT_NAME`
- `OBJECT_ID`
- `CENTER_NAME`
- `REF_FRAME`
- `TIME_SYSTEM`
- `START_TIME`
- `STOP_TIME`
- `INTERPOLATION`
- `INTERPOLATION_DEGREE`

Keys are case-insensitive. `INTERPOLATION_DEGREE` must be an integer. When
both `--x-ref-frame` and `--set-meta REF_FRAME=...` are supplied, the metadata
override is applied after the frame conversion and determines the final
metadata value. Set the metadata value to the actual target frame unless you
intentionally need a different label.

## Header Overrides

Use repeated `--set-header KEY=VALUE` options to override CCSDS OEM header
fields:

```bash
xform-oem input.oem \
  --set-header ORIGINATOR=tudatpy-utils \
  --set-header CREATION_DATE=2026-08-07T12:00:00.000 \
  -o output.oem
```

Supported header keys are:

- `CCSDS_OEM_VERS` — numeric OEM version
- `CREATION_DATE` — creation timestamp value
- `ORIGINATOR` — originator name
- `CLASSIFICATION` — optional message classification
- `MESSAGE_ID` — optional message identifier

Header keys are case-insensitive. Header overrides are applied after any
reference-frame conversion.

## Input and Output Streams

The input file is optional. These commands are equivalent ways to read from
standard input:

```bash
cat orbit.oem | xform-oem --x-ref-frame J2000
cat orbit.oem | xform-oem - --x-ref-frame J2000
```

Write an OEM result to standard output or to a file:

```bash
xform-oem orbit.oem --x-ref-frame ITRF1993 > orbit_itrf1993.oem
xform-oem orbit.oem --x-ref-frame ITRF1993 -o orbit_itrf1993.oem
```

AER output can also be chained with other command-line tools:

```bash
cat orbit.oem \
  | xform-oem --x-aer 52.5200,13.4050,45.0 \
  | awk '$3 > 10.0'
```

## Verbose Mode

Use `-v` or `--verbose` to print input information and transformation details
to stderr, keeping stdout available for OEM or AER output:

```bash
xform-oem orbit.oem --x-ref-frame ITRF1993 --verbose > output.oem
```

Verbose output includes:

- Input source path, or `<stdin>` for standard input
- Object name
- Input reference frame
- Source-frame override, when supplied
- Center and time system
- Number of states
- Input start and end timestamps
- Input time span
- Ground-station coordinates and converted-state count in AER mode

## Common Workflows

### Rewrite an OEM Without Transforming States

```bash
xform-oem input.oem \
  --set-meta OBJECT_NAME=TEST_OBJECT \
  --set-header ORIGINATOR=tudatpy-utils \
  -o rewritten.oem
```

### Convert TEME to an Earth-Fixed Frame

```bash
xform-oem input.oem \
  --x-ref-frame TEME,ITRF1993 \
  -o output.oem
```

### Convert an Earth-Fixed Frame to an Inertial Frame

```bash
xform-oem input.oem \
  --x-ref-frame ITRF1993,J2000 \
  -o output.oem
```

### Convert ECEF Positions for Ground-Station Analysis

```bash
xform-oem input.oem \
  --x-aer 35.6762,139.6503,40.0 \
  --output tokyo_aer.txt
```

## Programmatic and Implementation Details

The command-line tool uses these local modules:

- `tudatpy_utils.core.ccsds.oem` — CCSDS OEM parsing and writing
- `tudatpy_utils.core.frame_utils` — reference-frame enumeration and state conversion
- `tudatpy_utils.core.aer` — ECEF position to AER conversion
- `tudatpy_utils.core.time_utils` — UTC timestamp formatting and TDB epoch conversion

The frame-conversion path uses TudatPy rotation models and SPICE resources
where required. The AER path uses the ground-station latitude, longitude, and
altitude to convert each ECEF position independently.

SPICE-backed frame conversions load kernels through TudatPy's configured SPICE
kernel directory. Commonly used files include:

- `naif0012.tls`: leap-seconds kernel
- `pck00011.tpc`: planetary constants kernel
- `earth_200101_990825_predict.bpc`: Earth rotation prediction kernel

Their absolute locations and coverage depend on the installed TudatPy/Tudat
resource set.

## Error Handling

Common argument errors include:

```text
--x-aer and --x-ref-frame cannot be used together
--x-aer cannot be combined with --set-meta
--x-aer cannot be combined with --set-header
--set-meta requires KEY=VALUE
--set-header requires KEY=VALUE
```

Other common failures are invalid frame names, unsupported frame pairs, invalid
numeric AER coordinates, unreadable OEM input, and missing TudatPy/SPICE
resources required by a frame conversion.

## Dependencies

- Python 3.10+
- NumPy
- TudatPy for frame conversion and Earth-orientation models
- Local modules:
  - `tudatpy_utils.core.ccsds.oem`
  - `tudatpy_utils.core.frame_utils`
  - `tudatpy_utils.core.aer`
  - `tudatpy_utils.core.time_utils`

## Related Tools

- `slice-oem` — Extract OEM states by index or time range (see
  [SLICE_OEM.md](SLICE_OEM.md))
- `diff-oem` — Compare states from two OEM files (see
  [DIFF_OEM.md](DIFF_OEM.md))
- `tudatpy_utils.core.frame_utils` — Lower-level frame conversion implementation
- [tudatpy_frame_conversion.md](tudatpy_frame_conversion.md) — TudatPy API and
  rotation-model notes
