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

## Time Conversion

### `convert_time_cli`

A C++ command-line tool for converting between various time representations. It supports multiple conversion backends and a wide range of time formats.

#### Building

The tool is built with CMake as part of the project:

```bash
mkdir build && cd build
cmake ..
make convert_time_cli
```

The resulting binary is located at `build/time_conversion/tools/convert_time_cli`.

#### Synopsis

```
convert_time_cli [OPTIONS] input_time [input_time ...]
```

#### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `-b`, `--backend BACKEND` | Select conversion backend (`base`, `chrono`, or `tudat`) |
| `-i`, `--input-format FORMAT` | Specify the input time format |
| `-o`, `--output-format FORMAT` | Specify the output time format(s), comma-separated for multiple |

#### Backends and Formats

**`base` backend** (default) — leap-second-aware conversions without external dependencies:

| Format name | Description |
|---|---|
| `iso` | ISO 8601 UTC string (`YYYY-MM-DDTHH:MM:SS.sss`) |
| `posix` | POSIX timestamp (seconds since 1970-01-01 00:00:00 UTC) |
| `utc` | Seconds since UTC J2000 epoch (2000-01-01 12:00:00.000 UTC) |
| `tai` | Seconds since TAI J2000 epoch (2000-01-01 12:00:00.000 TAI) |
| `tt` | Seconds since TT J2000 epoch (2000-01-01 12:00:00.000 TT) |

**`chrono` backend** — uses C++ `<chrono>` clocks (availability of `chrono_utc_*` and `chrono_tai_*` depends on compiler support):

| Format name | Description |
|---|---|
| `iso` | ISO 8601 UTC string |
| `posix` | POSIX timestamp |
| `utc` | UTC J2000 seconds |
| `tai` | TAI J2000 seconds |
| `tt` | TT J2000 seconds |
| `chrono_sys_iso` | `std::chrono::system_clock` time point as ISO string |
| `chrono_sys` | `std::chrono::system_clock` time point as seconds since epoch |
| `chrono_utc_iso` | `std::chrono::utc_clock` time point as ISO string (if available) |
| `chrono_utc` | `std::chrono::utc_clock` time point as seconds since epoch (if available) |
| `chrono_tai_iso` | `std::chrono::tai_clock` time point as ISO string (if available) |
| `chrono_tai` | `std::chrono::tai_clock` time point as seconds since epoch (if available) |

**`tudat` backend** — uses Tudat's time conversion routines, adds TDB support:

| Format name | Description |
|---|---|
| `iso` | ISO 8601 UTC string |
| `posix` | POSIX timestamp |
| `utc` | UTC J2000 seconds |
| `tai` | TAI J2000 seconds |
| `tt` | TT J2000 seconds |
| `tdb` | TDB (Barycentric Dynamical Time) J2000 seconds |

#### Usage Examples

**Convert an ISO 8601 timestamp to POSIX time:**

```bash
convert_time_cli -i iso -o posix "2000-01-01T12:00:00"
```

**Convert a POSIX timestamp to multiple output formats:**

```bash
convert_time_cli -i posix -o iso,utc,tai 946728000
```

**Use the Tudat backend to convert UTC J2000 to TDB J2000:**

```bash
convert_time_cli -b tudat -i utc -o tdb 0.0
```

**Convert multiple input times at once:**

```bash
convert_time_cli -i iso -o posix,utc "2000-01-01T12:00:00" "2025-11-10T15:42:27"
```

**Show all available formats and help:**

```bash
convert_time_cli -h
```

#### Output

Each input time produces one line of tab-separated output. The first column is the input value, followed by one column per requested output format.

#### Dependencies

- C++20 compiler
- [Tudat](https://docs.tudat.space/) (required for the `tudat` backend and for building)
- Eigen3
