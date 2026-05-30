# tudatpy-utils

Utility scripts for working with TudatPy.

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
