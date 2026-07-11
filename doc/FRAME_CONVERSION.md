# tudatpy-utils

Frame-conversion utilities for OEM-like Cartesian state vectors.

## Overview

The repository currently provides two Python frame-conversion scripts:

- `bin/gcrf_to_itrf_spice.py`
- `bin/gcrf_to_itrf_rot_model.py`

Both scripts:

- read OEM-like state lines from a file or stdin
- accept blank lines and `#` comments
- accept whitespace- or comma-separated fields
- interpret position in **km** and velocity in **km/s**
- print converted states in the same OEM-like text layout

Input/output line format:

```text
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

## `bin/gcrf_to_itrf_spice.py`

Converts satellite state vectors between **GCRF / J2000** and **ITRF93** using SPICE rotation matrices via TudatPy.

### Synopsis

```bash
python bin/gcrf_to_itrf_spice.py [-h] [-r] [input_file]
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `-r` | Reverse conversion: `ITRF93 -> J2000` instead of `J2000 -> ITRF93` |
| `input_file` | Optional path to an OEM-like ephemeris text file; if omitted, stdin is used |

### Behavior

- Default direction: `J2000 -> ITRF93`
- Reverse direction with `-r`: `ITRF93 -> J2000`
- Epochs are converted internally to TDB seconds since J2000 before calling SPICE
- Position and velocity are transformed with a full 6x6 state conversion matrix assembled from:
  - the rotation matrix
  - the rotation-matrix derivative

### Input format

Each non-comment line must contain 7 fields:

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

### Output format

Each successfully converted line is printed as:

```text
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

The epoch is echoed in ISO format and fields are separated by double spaces.

### Usage

**Convert from stdin, J2000 -> ITRF93:**

```bash
echo "2025-11-10T15:42:27.000000 2070.058475323 4729.228905684 5291.073944519 -0.452686493 -5.378340397 4.970075198" \
  | python bin/gcrf_to_itrf_spice.py
```

**Reverse conversion, ITRF93 -> J2000:**

```bash
echo "2025-11-10T15:42:27.000000 -4016.835021864 3234.040363774 5296.435683796 5.299868461 -1.578004407 4.968732515" \
  | python bin/gcrf_to_itrf_spice.py -r
```

**Convert from a file:**

```bash
python bin/gcrf_to_itrf_spice.py input.oem
```

**Save output to a file:**

```bash
python bin/gcrf_to_itrf_spice.py input.oem > output.oem
```

**Show help:**

```bash
python bin/gcrf_to_itrf_spice.py -h
```

### Dependencies

- TudatPy
- NumPy
- local helper modules `common.common`, `common.time_utils`

The script loads these SPICE kernels from TudatPy's SPICE kernel directory:

- `naif0012.tls`
- `earth_200101_990825_predict.bpc`

## `bin/gcrf_to_itrf_rot_model.py`

Converts satellite state vectors between an inertial frame and an Earth-fixed frame using a selectable TudatPy Earth rotation model. The current implementation supports the IAU 2006 GCRS-to-ITRS model as well as SPICE-based Earth rotation models.

### Synopsis

```bash
python bin/gcrf_to_itrf_rot_model.py [-h] [-r] [-m MODEL] [input_file]
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `-r` | Reverse conversion: body-fixed -> inertial instead of inertial -> body-fixed |
| `-m MODEL` | Rotation model name; valid values are `spice_iau_earth`, `spice_itrf93`, `spice`, `gcrs_to_itrs` |
| `input_file` | Optional path to an OEM-like ephemeris text file; if omitted, stdin is used |

### Supported rotation models

| Model | Inertial frame | Body-fixed frame | Notes |
|---|---|---|---|
| `gcrs_to_itrs` | `GCRS` | `ITRS` | Default; IAU 2006 GCRS-to-ITRS model |
| `spice_itrf93` | `J2000` | `ITRF93` | SPICE rotation model |
| `spice` | `J2000` | `ITRF93` | Alias for `spice_itrf93` |
| `spice_iau_earth` | `J2000` | `IAU_Earth` | SPICE rotation model |

### Behavior

- Default model: `gcrs_to_itrs`
- Default direction: inertial -> body-fixed
- Reverse direction with `-r`: body-fixed -> inertial
- Velocity conversion includes the rotational transport term using the Earth angular velocity returned by the selected rotation model

### Input format

Each non-comment line must contain 7 fields:

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

### Output format

Each successfully converted line is printed as:

```text
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

### Usage

**Default model (`gcrs_to_itrs`) from stdin:**

```bash
echo "2025-11-10T15:42:27.000000 2070.058475323 4729.228905684 5291.073944519 -0.452686493 -5.378340397 4.970075198" \
  | python bin/gcrf_to_itrf_rot_model.py
```

**Use the SPICE `ITRF93` model:**

```bash
echo "2025-11-10T15:42:27.000000 2070.058475323 4729.228905684 5291.073944519 -0.452686493 -5.378340397 4.970075198" \
  | python bin/gcrf_to_itrf_rot_model.py -m spice_itrf93
```

**Use the SPICE `IAU_Earth` model:**

```bash
echo "2025-11-10T15:42:27.000000 2070.058475323 4729.228905684 5291.073944519 -0.452686493 -5.378340397 4.970075198" \
  | python bin/gcrf_to_itrf_rot_model.py -m spice_iau_earth
```

**Reverse conversion:**

```bash
echo "2025-11-10T15:42:27.000000 -4016.835021864 3234.040363774 5296.435683796 5.299868461 -1.578004407 4.968732515" \
  | python bin/gcrf_to_itrf_rot_model.py -r
```

**Convert from a file:**

```bash
python bin/gcrf_to_itrf_rot_model.py -m gcrs_to_itrs input.oem
```

**Save output to a file:**

```bash
python bin/gcrf_to_itrf_rot_model.py -m gcrs_to_itrs input.oem > output.oem
```

**Show help:**

```bash
python bin/gcrf_to_itrf_rot_model.py -h
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
