# tudatpy-utils

Frame-conversion utilities for CCSDS OEM state vectors.

## Overview

The repository currently provides two Python frame-conversion scripts:

- `bin/gcrf_to_itrf_spice.py`
- `bin/gcrf_to_itrs_tudat.py`

Both scripts read CCSDS OEM files from a path and write converted CCSDS OEM
files to stdout. They also accept raw state-vector lines from stdin (or from a
file without an OEM header) and write converted raw lines in that case. OEM
state vectors use **km** and **km/s**; the conversion helpers use
**m** and **m/s** internally.

## `bin/gcrf_to_itrf_spice.py`

Converts satellite state vectors between **GCRF / J2000** and **ITRF93** using SPICE rotation matrices via TudatPy.

### Synopsis

```bash
python3 bin/gcrf_to_itrf_spice.py [-h] [-r] [input_file]
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `-r` | Reverse conversion: `ITRF93 -> J2000` instead of `J2000 -> ITRF93` |
| `input_file` | Optional path to a CCSDS OEM file or raw state-list file; if omitted, input is read from stdin |

### Behavior

- Default direction: `J2000 -> ITRF93`
- Reverse direction with `-r`: `ITRF93 -> J2000`
- Epochs are converted internally to TDB seconds since J2000 before calling SPICE
- Position and velocity are transformed with a full 6x6 state conversion matrix assembled from:
  - the rotation matrix
  - the rotation-matrix derivative

### Usage

**Convert from stdin, J2000 -> ITRF93:**

```bash
cat input.oem \
  | python3 bin/gcrf_to_itrf_spice.py
```

**Reverse conversion, ITRF93 -> J2000:**

```bash
cat input_itrf93.oem \
  | python3 bin/gcrf_to_itrf_spice.py -r
```

**Convert from a file:**

```bash
python3 bin/gcrf_to_itrf_spice.py input.oem
```

**Save output to a file:**

```bash
python3 bin/gcrf_to_itrf_spice.py input.oem > output.oem
```

**Show help:**

```bash
python3 bin/gcrf_to_itrf_spice.py -h
```

### Dependencies

- TudatPy
- NumPy
- local helper modules `common.common`, `common.time_utils`

The script loads these SPICE kernels from TudatPy's SPICE kernel directory:

- `naif0012.tls`
- `earth_200101_990825_predict.bpc`

## `bin/gcrf_to_itrs_tudat.py`

Converts satellite state vectors between an inertial frame and an Earth-fixed frame using a selectable TudatPy Earth rotation model. The current implementation supports the IAU 2006 GCRS-to-ITRS model as well as SPICE-based Earth rotation models.

### Synopsis

```bash
python3 bin/gcrf_to_itrs_tudat.py [-h] [-r] [-m MODEL] [input_file]
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `-r` | Reverse conversion: body-fixed -> inertial instead of inertial -> body-fixed |
| `-m MODEL` | Rotation model name; valid values are `iau2006`, `spice` |
| `input_file` | Optional path to a CCSDS OEM file or raw state-list file; if omitted, raw state lines are read from stdin |

### Supported rotation models

| Model | Inertial frame | Body-fixed frame | Notes |
|---|---|---|---|
| `iau2006` | `GCRS` | `ITRS` | Default; IAU 2006 GCRS-to-ITRS model |
| `spice` | `J2000` | `ITRF93` | SPICE rotation model |

### Behavior

- Default model: `iau2006`
- Default direction: inertial -> body-fixed
- Reverse direction with `-r`: body-fixed -> inertial
- Velocity conversion includes the rotational transport term using the Earth angular velocity returned by the selected rotation model

### Input format

Each non-comment state line must contain at least 7 fields:

```text
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

Notes:

- **Epoch**: ISO 8601 timestamp such as `2025-11-10T15:42:27.000000`
- A trailing `Z` on the epoch is accepted by the shared parser.
- **Position**: X, Y, Z in kilometres.
- **Velocity**: VX, VY, VZ in km/s.
- Blank lines and lines beginning with `#` are skipped.
- Parse failures are reported and the offending line is skipped.

When `input_file` is a complete CCSDS OEM, the output is a complete CCSDS OEM
with the converted `REF_FRAME` metadata. Raw state-list input produces only
converted state lines, without an OEM header.

### Output format

Each successfully converted line is printed as:

```text
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

### Usage

**Default model (`iau2006`) from stdin:**

```bash
echo "2025-11-10T15:42:27.000000 2070.058475323 4729.228905684 5291.073944519 -0.452686493 -5.378340397 4.970075198" \
  | python3 bin/gcrf_to_itrs_tudat.py
```

**Use the SPICE `ITRF93` model:**

```bash
echo "2025-11-10T15:42:27.000000 2070.058475323 4729.228905684 5291.073944519 -0.452686493 -5.378340397 4.970075198" \
  | python3 bin/gcrf_to_itrs_tudat.py -m spice
```

**Reverse conversion:**

```bash
echo "2025-11-10T15:42:27.000000 -4016.835021864 3234.040363774 5296.435683796 5.299868461 -1.578004407 4.968732515" \
  | python3 bin/gcrf_to_itrs_tudat.py -r
```

**Convert from a file:**

```bash
python3 bin/gcrf_to_itrs_tudat.py -m iau2006 input.oem
```

**Save output to a file:**

```bash
python3 bin/gcrf_to_itrs_tudat.py -m iau2006 input.oem > output.oem
```

**Show help:**

```bash
python3 bin/gcrf_to_itrs_tudat.py -h
```

### Dependencies

- TudatPy
- NumPy
- local helper modules `common.common`, `common.time_utils`

The script loads these SPICE kernels from TudatPy's SPICE kernel directory:

- `naif0012.tls`
- `pck00011.tpc`
- `earth_200101_990825_predict.bpc`

---
