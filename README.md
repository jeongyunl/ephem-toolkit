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
common/              Shared Python library modules
common/interpolator/ Interpolation sub-library (Lagrange, generic)
time_conversion/     C++ time-conversion library, CLI, and tests
oem_to_omm/          OEM-to-OMM estimation application module (includes TLE fitting)
propagation/         Python propagation scripts
plotting/            Python orbit visualization scripts
bin/                 Command-line utility scripts
test/                Unit tests and sample data files
doc/                 Documentation
```


---

## Command-Line Tools

### OEM Utilities

- `bin/diff_oem.py` — compare corresponding states from two OEM files with optional rotation fitting and time-shift correction. See [DIFF_OEM.md](doc/DIFF_OEM.md) for details
- `bin/slice_oem.py` — slice OEM files by index or time range (with optional interpolation). See [SLICE_OEM.md](doc/SLICE_OEM.md) for details
- `bin/ecef_to_aer.py` — convert ECEF OEM ephemeris to AER (Azimuth-Elevation-Range) coordinates. See [MISC.md](doc/MISC.md) for other details.

### Frame Conversion

- `bin/gcrf_to_itrf_spice.py` — SPICE rotation (J2000 ↔ ITRF93)
- `bin/gcrf_to_itrf_rot_model.py` — TudatPy Earth rotation models

Converts CCSDS OEM state vectors between inertial and Earth-fixed reference frames. Supports SPICE rotation matrices and TudatPy rotation models (`gcrs_to_itrs`, `spice_itrf93`, `spice_iau_earth`).

See [FRAME_CONVERSION.md](doc/FRAME_CONVERSION.md) for full usage details.

### Orbit Propagation

- `propagation/propagate_orbit.py` — Cartesian state propagation with configurable perturbations
- `propagation/propagate_kepler.py` — two-body Kepler propagation
- `propagation/propagate_tle.py` — SGP4 TLE propagation

Supports CCSDS OEM export, raw state-vector output, dependent-variable CSV export, and OEM metadata headers.

See [PROPAGATION.md](doc/PROPAGATION.md) for full usage details.

### OEM-to-OMM

- `oem_to_omm/oem_to_omm.py`

Estimates Orbit Mean-Elements Messages (OMM) including Two-Line Element (TLE) sets from OEM Cartesian state vectors. Fits OEM state vectors to osculating Kepler, mean Kepler, or TLE-derived OMM output using iterative least-squares fitting. Includes least-squares estimation, iterative refinement, SGP4 model evaluation, and TLE line construction.

See [OEM_TO_OMM.md](doc/OEM_TO_OMM.md) for full usage details.

### TLE / OMM Utilities

- `bin/download_tle.py` — download TLE data
- `bin/omm_to_tle.py` — convert OMM → TLE
- `bin/tle_to_omm.py` — convert TLE → OMM
- `bin/tle_info.py` — inspect TLE information

See [TLE.md](doc/TLE.md) for full usage details.

### Visualization

- `plotting/plot_orbit_deltas.py` — plot and compare multiple orbits
- `plotting/plot_dependent_variables.py` — plot dependent variables from propagation output

### Time Conversion

- `time_conversion/tools/convert_time_cli` — C++ multi-backend CLI
- `time_conversion/tools/convert_time.py` — Python wrapper

Converts between ISO 8601, POSIX, UTC/TAI/TT J2000, and backend-specific formats.

See [TIME_CONVERSION.md](doc/TIME_CONVERSION.md) for full usage details.

---

## Libraries

### Python Library (`common/`)

Reusable Python modules providing foundational astrodynamics functionality. These are imported by the application modules and CLI tools.

See [COMMON_LIBRARY_SUMMARY.md](doc/COMMON_LIBRARY_SUMMARY.md) for an overview of all available modules and functions.

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

See [TIME_CONVERSION.md](doc/TIME_CONVERSION.md) for full usage details.

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
