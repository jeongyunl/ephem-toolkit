# tudatpy-utils

Utility scripts for working with TudatPy.

## Frame Conversion

### `frame_conversion/gcrf_to_itrf_spice.py`

Converts satellite state vectors (position and velocity) from the **GCRF** (Geocentric Celestial Reference Frame) to the **ITRF** (International Terrestrial Reference Frame) using SPICE rotation matrices via TudatPy.

#### Input Format

The script reads OEM-style ephemeris data with 7 whitespace- or comma-separated fields per line:

```
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

- **Epoch**: ISO 8601 timestamp (e.g., `2025-11-10T15:42:27.000000`). A trailing `Z` is accepted and stripped.
- **Position**: X, Y, Z in **kilometres** (GCRF).
- **Velocity**: VX, VY, VZ in **km/s** (GCRF).

Lines that are blank or start with `#` are skipped.

#### Output Format

Each line of output contains the converted state in ITRF:

```
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

Fields are separated by two spaces.

#### Usage

**From a file:**

```bash
python frame_conversion/gcrf_to_itrf_spice.py LEO_1MinInt_GCRF.txt
```

**From stdin (pipe):**

```bash
cat LEO_1MinInt_GCRF.txt | python frame_conversion/gcrf_to_itrf_spice.py
```

**Save output to a file:**

```bash
python frame_conversion/gcrf_to_itrf_spice.py LEO_1MinInt_GCRF.txt > LEO_1MinInt_ITRF_result.txt
```

#### Example

Given an input file `LEO_1MinInt_GCRF.txt`:

```
2025-11-10T15:42:27.000000   2.070058475322879e+03   4.729228905683604e+03   5.291073944519138e+03  -4.526864928985522e-01  -5.378340397167571e+00   4.970075197986098e+00
2025-11-10T15:43:27.000000   2.039244758072811e+03   4.398338130542555e+03   5.579702355150183e+03  -5.741321702569117e-01  -5.648088862971277e+00   4.648027399977921e+00
```

Running:

```bash
python frame_conversion/gcrf_to_itrf_spice.py LEO_1MinInt_GCRF.txt
```

Produces ITRF state vectors (position in km, velocity in km/s) for each epoch.

#### Dependencies

- [TudatPy](https://docs.tudat.space/en/latest/) (`tudatpy`)
- NumPy

The script automatically loads the required SPICE kernels (`naif0012.tls` and `earth_200101_990825_predict.bpc`) from the TudatPy data directory.

### `frame_conversion/gcrf_to_itrf_iau.py`

Converts satellite state vectors between **GCRF** and **ITRF** using the **IAU 2006** Earth rotation model via TudatPy. Unlike the SPICE-based script, this uses TudatPy's full precession-nutation model (`gcrs_to_itrs` with `IAUConventions.iau_2006`).

#### Synopsis

```
python frame_conversion/gcrf_to_itrf_iau.py [-h] [-r] [input_file]
```

#### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `-r` | Reverse conversion (ITRF → GCRF instead of GCRF → ITRF) |

#### Input Format

Same OEM-style format as `gcrf_to_itrf_spice.py` — 7 whitespace- or comma-separated fields per line:

```
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

Blank lines and lines starting with `#` are skipped. A trailing `Z` on the epoch is accepted and stripped.

#### Output Format

Each line of output contains the converted state:

```
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

Fields are separated by two spaces.

#### Usage

**GCRF → ITRF from a file:**

```bash
python frame_conversion/gcrf_to_itrf_iau.py LEO_1MinInt_GCRF.txt
```

**GCRF → ITRF from stdin:**

```bash
cat LEO_1MinInt_GCRF.txt | python frame_conversion/gcrf_to_itrf_iau.py
```

**Reverse conversion (ITRF → GCRF):**

```bash
python frame_conversion/gcrf_to_itrf_iau.py -r LEO_1MinInt_ITRF.txt
```

**Save output to a file:**

```bash
python frame_conversion/gcrf_to_itrf_iau.py LEO_1MinInt_GCRF.txt > LEO_1MinInt_ITRF_iau.txt
```

**Show help:**

```bash
python frame_conversion/gcrf_to_itrf_iau.py -h
```

#### Dependencies

- [TudatPy](https://docs.tudat.space/en/latest/) (`tudatpy`)
- NumPy

The script loads SPICE kernels `naif0012.tls` (leap seconds) and `pck00011.tpc` (planetary constants) from the TudatPy data directory, and creates an IAU 2006 Earth rotation model for the GCRS-to-ITRS transformation.

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
