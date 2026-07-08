# tudatpy-utils

Time-conversion utilities built around the `time_conversion/` C++ code.

## Overview

The repository contains a C++ command-line tool for converting between multiple time representations. The current implementation supports several conversion backends and a range of time formats including ISO 8601, POSIX, UTC/TAI/TT seconds since J2000, and backend-specific chrono or TDB formats.

The main user-facing tool is:

- `build/time_conversion/tools/convert_time_cli`

It is built from:

- `time_conversion/tools/convert_time_cli.cpp`

The CLI supports three backends:

- `base`
- `chrono`
- `tudat`

and converts between backend-specific time formats.

## Building

From the repository root:

```bash
cmake -S . -B build
cmake --build build --target convert_time_cli
```

Expected output binary:

```text
build/time_conversion/tools/convert_time_cli
```

## `convert_time_cli`

Convert one or more input times using the selected backend.

### Synopsis

```bash
build/time_conversion/tools/convert_time_cli [OPTIONS] input_time [input_time ...]
```

### Options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help message and exit |
| `-b`, `--backend BACKEND` | Select backend: `base`, `chrono`, or `tudat` |
| `-i`, `--input-format FORMAT` | Specify the input time format |
| `-o`, `--output-format FORMAT` | Specify one or more output formats; multiple formats are comma-separated |

### Important CLI behavior

- Default backend: `base`
- `--input-format` is required in practice; if omitted, the format is unknown and the tool exits with an error.
- At least one `input_time` is required.
- `--output-format` should be provided; if omitted, the tool prints only the original input value and a newline.
- Multiple input times are supported.
- Multiple output formats are supported via a comma-separated list such as `iso,utc,tai`.

### Backends and formats

#### `base` backend

The `base` backend provides leap-second-aware conversions without relying on the Tudat backend.

Formats accepted by the current source:

| Format | Meaning |
|---|---|
| `iso` | UTC ISO 8601 string |
| `posix` | POSIX seconds since Unix epoch |
| `utc` | UTC seconds since J2000 |
| `tai` | TAI seconds since J2000 |
| `tt` | TT seconds since J2000 |

#### `chrono` backend

The `chrono` backend uses C++ `<chrono>` clocks and exposes additional chrono-specific formats when supported by the compiler and standard library.

Formats accepted by the current source:

| Format | Meaning |
|---|---|
| `iso` | UTC ISO 8601 string |
| `posix` | POSIX seconds since Unix epoch |
| `utc` | UTC seconds since J2000 |
| `tai` | TAI seconds since J2000 |
| `tt` | TT seconds since J2000 |
| `chrono_sys_iso` | `std::chrono::system_clock` time point rendered as an ISO-like UTC string |
| `chrono_sys` | `std::chrono::system_clock` time point rendered as seconds since its epoch |
| `chrono_utc_iso` | `std::chrono::utc_clock` time point rendered as an ISO-like UTC string, when supported by the compiler/library |
| `chrono_utc` | `std::chrono::utc_clock` time point rendered as seconds since its epoch, when supported |
| `chrono_tai_iso` | `std::chrono::tai_clock` time point rendered as an ISO-like UTC string, when supported |
| `chrono_tai` | `std::chrono::tai_clock` time point rendered as seconds since its epoch, when supported |

Notes:

- `chrono_utc_*` formats are compiled only when `HAS_CHRONO_UTC_CLOCK` is available.
- `chrono_tai_*` formats are compiled only when `HAS_CHRONO_TAI_CLOCK` is available.

#### `tudat` backend

The `tudat` backend uses Tudat time-conversion routines and adds support for TDB seconds since J2000.

Formats accepted by the current source:

| Format | Meaning |
|---|---|
| `iso` | UTC ISO 8601 string |
| `posix` | POSIX seconds since Unix epoch |
| `utc` | UTC seconds since J2000 |
| `tai` | TAI seconds since J2000 |
| `tt` | TT seconds since J2000 |
| `tdb` | TDB seconds since J2000 |

### Input interpretation

- If the input format is `iso`, each `input_time` is treated as a string.
- For all other formats, each `input_time` is parsed as a floating-point number.

### Output format

For each input time, the tool prints one tab-separated line:

```text
<input>\t<output1>\t<output2> ...
```

Formatting details from the current implementation:

- numeric outputs stored as `double` are printed with 3 decimal places
- string outputs are printed as returned by the backend
- chrono time-point outputs are rendered as human-readable strings by the CLI

### Usage examples

**ISO -> POSIX using the default `base` backend:**

```bash
build/time_conversion/tools/convert_time_cli \
  -i iso -o posix \
  "2000-01-01T12:00:00"
```

**POSIX -> multiple outputs:**

```bash
build/time_conversion/tools/convert_time_cli \
  -i posix -o iso,utc,tai \
  946728000
```

**UTC J2000 -> TDB using the `tudat` backend:**

```bash
build/time_conversion/tools/convert_time_cli \
  -b tudat -i utc -o tdb \
  0.0
```

**Multiple input times:**

```bash
build/time_conversion/tools/convert_time_cli \
  -i iso -o posix,utc \
  "2000-01-01T12:00:00" "2025-11-10T15:42:27"
```

**Inspect supported formats via help:**

```bash
build/time_conversion/tools/convert_time_cli -h
```

## Dependencies

Current top-level CMake configuration requires:

- CMake
- C++20 compiler
- Tudat
- Eigen3

The repository also optionally looks for `nrlmsise00`, but the time-conversion CLI target itself is built from the `time_conversion/` subtree and linked against the local `convert_time` library target.
