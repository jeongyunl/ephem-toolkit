# tudatpy-utils

Utility scripts for working with TudatPy.

## Frame Conversion

### `frame_conversion/gcrf_to_itrf_spice.py`

Converts satellite state vectors between **GCRF** (J2000) and **ITRF** (ITRF93) using SPICE rotation matrices via TudatPy.

#### Synopsis

```
python frame_conversion/gcrf_to_itrf_spice.py [-h] [-r] [input_file]
```

#### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `-r` | Reverse conversion (ITRF93 → J2000 instead of J2000 → ITRF93) |

#### Input Format

The script reads OEM-style ephemeris data with 7 whitespace- or comma-separated fields per line:

```
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

- **Epoch**: ISO 8601 timestamp (e.g., `2025-11-10T15:42:27.000000`). A trailing `Z` is accepted and stripped.
- **Position**: X, Y, Z in **kilometres**.
- **Velocity**: VX, VY, VZ in **km/s**.

Blank lines and lines starting with `#` are skipped.

#### Output Format

Each line of output contains the converted state:

```
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

Fields are separated by two spaces.

#### Usage

**GCRF → ITRF from inline data:**

```bash
echo "2025-11-10T15:42:27.000000   2.070058475322879e+03   4.729228905683604e+03   5.291073944519138e+03  -4.526864928985522e-01  -5.378340397167571e+00   4.970075197986098e+00" \
  | python frame_conversion/gcrf_to_itrf_spice.py
```

**Reverse conversion (ITRF → GCRF) from inline data:**

```bash
echo "2025-11-10T15:42:27.000000  -4.016835021863700e+03   3.234040363774085e+03   5.296435683796034e+03   5.299868461486320e+00  -1.578004407441781e+00   4.968732514953014e+00" \
  | python frame_conversion/gcrf_to_itrf_spice.py -r
```

**Save output to a file:**

```bash
echo "2025-11-10T15:42:27.000000   2.070058475322879e+03   4.729228905683604e+03   5.291073944519138e+03  -4.526864928985522e-01  -5.378340397167571e+00   4.970075197986098e+00" \
  | python frame_conversion/gcrf_to_itrf_spice.py > output.txt
```

**Show help:**

```bash
python frame_conversion/gcrf_to_itrf_spice.py -h
```

#### Dependencies

- [TudatPy](https://docs.tudat.space/en/latest/) (`tudatpy`)
- NumPy

The script automatically loads the required SPICE kernels (`naif0012.tls` and `earth_200101_990825_predict.bpc`) from the TudatPy data directory.

### `frame_conversion/gcrf_to_itrf_rot_model.py`

Converts satellite state vectors between an inertial frame (**GCRF**/J2000) and a body-fixed frame (**ITRF**/IAU_Earth) using a selectable Earth rotation model via TudatPy. Supports the IAU 2006 GCRS-to-ITRS precession-nutation model as well as SPICE-based rotation models.

#### Synopsis

```
python frame_conversion/gcrf_to_itrf_rot_model.py [-h] [-r] [-m MODEL] [input_file]
```

#### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `-r` | Reverse conversion (ITRF → GCRF instead of GCRF → ITRF) |
| `-m MODEL` | Name of the rotation model to use (see table below; default: `gcrs_to_itrs`) |

#### Rotation Models

| Model name | Description | Inertial frame |
|---|---|---|
| `gcrs_to_itrs` | IAU 2006 GCRS-to-ITRS precession-nutation model | GCRS |
| `spice_iau_earth` | SPICE IAU_Earth rotation model | J2000 |
| `spice_itrf93` | SPICE ITRF93 rotation model | J2000 |
| `spice` | Alias for `spice_itrf93` | J2000 |

#### Input Format

The script reads OEM-style ephemeris data with 7 whitespace- or comma-separated fields per line:

```
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

- **Epoch**: ISO 8601 timestamp (e.g., `2025-11-10T15:42:27.000000`). A trailing `Z` is accepted and stripped.
- **Position**: X, Y, Z in **kilometres**.
- **Velocity**: VX, VY, VZ in **km/s**.

Blank lines and lines starting with `#` are skipped.

#### Output Format

Each line of output contains the converted state:

```
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

Fields are separated by two spaces.

#### Usage

**GCRF → ITRF from inline data (default model: `gcrs_to_itrs`):**

```bash
echo "2025-11-10T15:42:27.000000   2.070058475322879e+03   4.729228905683604e+03   5.291073944519138e+03  -4.526864928985522e-01  -5.378340397167571e+00   4.970075197986098e+00" \
  | python frame_conversion/gcrf_to_itrf_rot_model.py
```

**GCRF → ITRF using the SPICE ITRF93 model:**

```bash
echo "2025-11-10T15:42:27.000000   2.070058475322879e+03   4.729228905683604e+03   5.291073944519138e+03  -4.526864928985522e-01  -5.378340397167571e+00   4.970075197986098e+00" \
  | python frame_conversion/gcrf_to_itrf_rot_model.py -m spice_itrf93
```

**GCRF → ITRF using the SPICE IAU_Earth model:**

```bash
echo "2025-11-10T15:42:27.000000   2.070058475322879e+03   4.729228905683604e+03   5.291073944519138e+03  -4.526864928985522e-01  -5.378340397167571e+00   4.970075197986098e+00" \
  | python frame_conversion/gcrf_to_itrf_rot_model.py -m spice_iau_earth
```

**Reverse conversion (ITRF → GCRF) from inline data:**

```bash
echo "2025-11-10T15:42:27.000000  -4.016835021863700e+03   3.234040363774085e+03   5.296435683796034e+03   5.299868461486320e+00  -1.578004407441781e+00   4.968732514953014e+00" \
  | python frame_conversion/gcrf_to_itrf_rot_model.py -r
```

**Save output to a file:**

```bash
echo "2025-11-10T15:42:27.000000   2.070058475322879e+03   4.729228905683604e+03   5.291073944519138e+03  -4.526864928985522e-01  -5.378340397167571e+00   4.970075197986098e+00" \
  | python frame_conversion/gcrf_to_itrf_rot_model.py > output.txt
```

**Show help:**

```bash
python frame_conversion/gcrf_to_itrf_rot_model.py -h
```

#### Dependencies

- [TudatPy](https://docs.tudat.space/en/latest/) (`tudatpy`)
- NumPy

The script loads SPICE kernels `naif0012.tls` (leap seconds), `pck00011.tpc` (planetary constants), and `earth_200101_990825_predict.bpc` (Earth rotation prediction, Jan 2001 – Aug 2099) from the TudatPy data directory. The rotation model is selected via the `-m` option and defaults to the IAU 2006 GCRS-to-ITRS model.

---

