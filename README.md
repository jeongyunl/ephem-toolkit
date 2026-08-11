# tudatpy-utils

Utility scripts and small C++ tools for working with TudatPy and Tudat.

## Overview

This repository provides a collection of command-line tools, reusable libraries, and helper scripts built on top of [TudatPy](https://docs.tudat.space/en/latest/) and [Tudat](https://docs.tudat.space/) for common astrodynamics tasks.

The repository is organized into three layers:

1. **Libraries** — reusable Python modules and a C++ time-conversion library
2. **Application Modules** — higher-level packages that combine library code into domain-specific workflows
3. **Command-Line Tools** — executable scripts for end-user tasks

## Repository Layout

```
src/tudatpy_utils/
├── common/              Shared Python library modules
│   ├── interpolator/    Interpolation sub-library (Lagrange, generic)
│   └── ccsds/          CCSDS ODM, OEM, and OMM definitions and parsers
├── cli/                 Command-line interface entry points
├── diff_oem/           OEM comparison application module
├── oem_to_omm/         OEM-to-OMM estimation application module (includes TLE fitting)
├── propagate_*/        Python propagation packages
├── plot_orbit*/        Python orbit visualization packages
├── slice_oem/          OEM slicing application module
├── xform_oem/          OEM frame transformation application module
└── */                  Other application modules
time_conversion/         C++ time-conversion library, CLI, and tests
tests/                   Unit tests and sample data files
docs/                    Documentation
```


---

## Command-Line Tools

### Poetry Console Commands

After installing the Python package with Poetry, use the canonical commands below:

| Workflow | Command |
| --- | --- |
| OEM comparison | `diff-oem` |
| TLE download | `download-tle` |
| OMM to TLE | `omm-to-tle` |
| OEM slicing | `slice-oem` |
| TLE inspection | `tle-info` |
| TLE to OMM | `tle-to-omm` |
| OEM frame transformation | `xform-oem` |
| OEM to OMM fitting | `oem-to-omm` |
| TLE fit evaluation | `evaluate-fit-tle` |
| Orbit propagation | `propagate-orbit` |
| Kepler propagation | `propagate-kepler` |
| TLE propagation | `propagate-tle` |
| Orbit plotting | `plot-orbit` |
| Orbit-delta plotting | `plot-orbit-deltas` |
| Dependent-variable plotting | `plot-dependent-variables` |

Install plotting support with `poetry install -E plotting`. TudatPy-dependent workflows require TudatPy and its transitive dependencies through an external installation method.

### OEM Utilities

- `diff-oem` — compare corresponding states from two OEM files with optional rotation fitting and time-shift correction. See [DIFF_OEM.md](docs/DIFF_OEM.md) for details
- `slice-oem` — slice OEM files by index or time range (with optional interpolation). See [SLICE_OEM.md](docs/SLICE_OEM.md) for details
- `xform-oem` — convert CCSDS OEM state vectors between supported reference frames, or convert ECEF positions to AER coordinates. See [XFORM_OEM.md](docs/XFORM_OEM.md) for complete documentation.


### Orbit Propagation

- `propagate-orbit` — Cartesian state propagation with configurable perturbations
- `propagate-kepler` — two-body Kepler propagation
- `propagate-tle` — SGP4 TLE propagation

Supports CCSDS OEM export, data-only state-vector output, dependent-variable CSV export, and OEM metadata headers.

See [PROPAGATION.md](docs/PROPAGATION.md) for full usage details.

### OEM-to-OMM

- `oem-to-omm`

Estimates Orbit Mean-Elements Messages (OMM) including Two-Line Element (TLE) sets from OEM Cartesian state vectors. Fits OEM state vectors to osculating Kepler, mean Kepler, or TLE-derived OMM output using iterative least-squares fitting. Includes least-squares estimation, iterative refinement, SGP4 model evaluation, and TLE line construction.

See [OEM_TO_OMM.md](docs/OEM_TO_OMM.md) for full usage details.

### TLE / OMM Utilities

- `download-tle` — download TLE data
- `omm-to-tle` — convert OMM → TLE
- `tle-to-omm` — convert TLE → OMM
- `tle-info` — inspect TLE information

See [TLE.md](docs/TLE.md) for full usage details.

### Visualization

- `plot-orbit-deltas` — plot and compare multiple orbits
- `plot-dependent-variables` — plot dependent variables from propagation output

### Time Conversion

- `time_conversion/tools/convert_time_cli` — C++ multi-backend CLI
- `time_conversion/tools/convert_time.py` — Python wrapper

Converts between ISO 8601, POSIX, UTC/TAI/TT J2000, and backend-specific formats.

See [TIME_CONVERSION.md](docs/TIME_CONVERSION.md) for full usage details.

---

## Libraries

### Python Library (`src/tudatpy_utils/common/`)

Reusable Python modules providing foundational astrodynamics functionality. These are imported by the application modules and CLI tools.

See [COMMON_LIBRARY_SUMMARY.md](docs/COMMON_LIBRARY_SUMMARY.md) for an overview of all available modules and functions.

---

## C++ Time-Conversion Library (`time_conversion/`)

A multi-backend C++ library for converting between time representations. Supports ISO 8601, POSIX, UTC/TAI/TT J2000, and backend-specific chrono or TDB formats.

| Component | Description |
|-----------|-------------|
| `time_conversion/base/` | Core time-conversion logic and dispatch table |
| `time_conversion/chrono/` | `std::chrono`-based backend |
| `time_conversion/tudat/` | Tudat-based backend (TDB support) |
| `time_conversion/tools/` | CLI tool (`convert_time_cli`) |
| `time_conversion/test/` | Google Test unit tests |

See [TIME_CONVERSION.md](docs/TIME_CONVERSION.md) for full usage details.

---

## Build and Dependencies

### Python Tools

Typical Python dependencies used by the scripts:

- [TudatPy](https://docs.tudat.space/en/latest/) (`tudatpy`)
- NumPy

Some scripts use only the Python standard library plus local helpers.

### C++ Tools

The C++ time-conversion code is built with CMake and currently depends on:

- CMake
- A C++20 compiler
- [Tudat](https://docs.tudat.space/)
- Eigen3

Top-level build example:

```bash
cmake -S . -B build
cmake --build build --target convert_time_cli
```

The resulting executable is typically:

```text
build/time_conversion/tools/convert_time_cli
```
