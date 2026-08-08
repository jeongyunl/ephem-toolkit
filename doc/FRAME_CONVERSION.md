# Frame Conversion

`bin/xform_oem.py` is the repository's command-line tool for transforming CCSDS
OEM state vectors between supported reference frames. It uses the conversion
logic in `common/frame_utils.py`, including the TudatPy rotation models and
SPICE kernels required by those models.

See [XFORM_OEM.md](XFORM_OEM.md) for complete command-line documentation,
including AER conversion, metadata overrides, and stream processing.

## Supported frames

The `--ref-frame` and `--src-ref-frame` options accept the frame names exposed
by `common.frame_utils.Frame`:

- `TEME`
- `J2000`, `EME2000`, `ICRF`, `GCRF`
- `ITRF93`, `ITRF`

`J2000`, `EME2000`, `ICRF`, and `GCRF` are treated as equivalent inertial
frames by the conversion helper. The output OEM `REF_FRAME` metadata is
updated to the requested target frame.

## Convert an OEM file

```bash
python3 bin/xform_oem.py input.oem --ref-frame ITRF93 -o output.oem
```

The source frame is read from the OEM metadata. Use `--src-ref-frame` when the
metadata is missing, incorrect, or uses a non-standard name:

```bash
python3 bin/xform_oem.py input.oem \
  --src-ref-frame GCRF --ref-frame ITRF93 -o output.oem
```

Input can also be read from standard input and output can be written to
standard output:

```bash
cat input.oem \
  | python3 bin/xform_oem.py --src-ref-frame J2000 --ref-frame ITRF93 \
  > output.oem
```

OEM positions and velocities are represented in km and km/s. The conversion
helper performs the calculation in SI units and writes the result back in the
OEM units.

## Command-line options

| Option | Description |
|---|---|
| `oem_file` | Optional input CCSDS OEM path; omit it or use `-` for stdin |
| `--src-ref-frame <frame>` | Override the input OEM reference frame |
| `--ref-frame <frame>` | Target reference frame and output `REF_FRAME` value |
| `--set-meta <KEY=VALUE>` | Override output OEM metadata; repeatable and applied after transformations |
| `--set-header <KEY=VALUE>` | Override output OEM header fields; repeatable and applied after transformations |
| `-o, --output <file\|->` | Output path; defaults to stdout |
| `-v, --verbose` | Print input and conversion details to stderr |
| `--aer <lat,lon,alt>` | Convert ECEF/ITRF positions to AER text instead of writing an OEM |

## AER output

`--aer` is a separate mode for ECEF or ITRF input. Its arguments are latitude
and longitude in degrees and altitude in metres:

```bash
python3 bin/xform_oem.py ecef.oem --aer 40.7128,-74.0060,10.0
```

Each output line contains the UTC timestamp, azimuth in degrees, elevation in
degrees, and range in metres. This mode converts positions only; it does not
produce velocity or AER-rate columns. `--aer` cannot be combined with
`--ref-frame`.

## Dependencies and Earth-orientation data

The frame conversion path requires TudatPy, NumPy, and the local `common`
modules. SPICE-backed conversions load kernels through TudatPy's configured
SPICE kernel directory. Commonly used files include:

- `naif0012.tls`
- `pck00011.tpc`
- `earth_200101_990825_predict.bpc`

Their absolute locations and coverage depend on the installed TudatPy/Tudat
resource set.