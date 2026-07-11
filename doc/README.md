# tudatpy-utils

Utility scripts and small C++ tools for working with TudatPy and Tudat.

## Overview

This repository provides a collection of command-line tools and helper scripts built on top of [TudatPy](https://docs.tudat.space/en/latest/) and [Tudat](https://docs.tudat.space/) for common astrodynamics tasks.

The repository currently contains utilities in five main areas:

- Frame conversion
- Time conversion
- Orbit propagation
- TLE / OMM / OEM utilities
- Miscellaneous utilities (state comparison, OEM slicing, orbit plotting)

The repository layout is source-oriented:

- `bin/` — Python command-line utilities for TLE/OMM/OEM conversion, frame conversion, state comparison, and orbit analysis
- `time_conversion/` — C++ time-conversion library, CLI, tests, and helper scripts
- `propagation/` — Python propagation scripts
- `oem_to_tle/` — TLE estimation from OEM Cartesian arcs
- `oem_to_kepler/` — Keplerian element extraction from OEM files
- `common/` — shared Python helpers for OEM/OMM/TLE parsing, time conversion, and Keplerian conversions
- `plotting/` — Python scripts for orbit visualization
- `test/` — sample TLE / OMM / OEM files and Python tests

## Frame Conversion

Python scripts for converting OEM-like Cartesian state vectors between inertial and Earth-fixed reference frames. Multiple rotation approaches are supported, including direct SPICE frame rotations and TudatPy Earth rotation models.

Two Python scripts convert OEM-like Cartesian state lines between inertial and Earth-fixed frames:

- `bin/gcrf_to_itrf_spice.py`
  - Uses SPICE rotation matrices and rotation-matrix derivatives.
  - Converts between `J2000` and `ITRF93`.
- `bin/gcrf_to_itrf_rot_model.py`
  - Uses TudatPy Earth rotation models.
  - Supports `gcrs_to_itrs`, `spice_itrf93` / `spice`, and `spice_iau_earth`.

See [FRAME_CONVERSION.md](FRAME_CONVERSION.md) for full usage details.

## Time Conversion

A C++ command-line tool for converting between time representations. The current CLI supports multiple backends and a range of time formats including ISO 8601, POSIX, UTC/TAI/TT J2000, and backend-specific chrono or TDB formats.

The C++ time-conversion tool is built from the `time_conversion/` subtree:

- `time_conversion/tools/convert_time_cli`
  - Multi-backend CLI for converting between ISO 8601, POSIX, UTC/TAI/TT J2000, and backend-specific formats.
  - Backends: `base`, `chrono`, `tudat`.

See [TIME_CONVERSION.md](TIME_CONVERSION.md) for full usage details.

## Orbit Propagation

Python scripts for propagating either a Cartesian initial state or a TLE-derived orbit. The current tools support configurable perturbation models, CCSDS OEM export, raw state-vector output, dependent-variable CSV export, and TLE-based SGP4 propagation.

Two Python propagation scripts are currently present:

- `propagation/propagate_orbit.py`
  - Propagates one OEM-like Cartesian state under configurable perturbations.
  - Can optionally export propagated state history as CCSDS OEM or raw state-vector lines.
  - Can optionally export dependent variables to CSV.
- `propagation/propagate_tle.py`
  - Propagates a TLE with TudatPy's SGP4 ephemeris.
  - Prints OEM-like state lines and can optionally prepend an OEM metadata header.

See [PROPAGATION.md](PROPAGATION.md) for full usage details.

## TLE / OMM / OEM Utilities

The repository contains more than just TLE build/parse helpers. Current Python tools include TLE formatting, parsing, estimation from Cartesian arcs, and format-conversion helpers for related orbital data products.

Current Python tools include:

- `oem_to_tle/oem_to_tle.py` — estimate a TLE from an OEM-like Cartesian arc
- `oem_to_kepler/oem_to_kepler.py` — extract Keplerian elements from OEM files
- `bin/download_tle.py` — download TLE data
- `bin/omm_to_tle.py` — convert OMM to TLE
- `bin/tle_to_omm.py` — convert TLE to OMM
- `bin/tle_info.py` — inspect TLE information
- `bin/cartesian_to_keplerian.py` — convert Cartesian states to Keplerian elements
- `common/convert_tle.py` — shared conversion helper script
- `common/oem.py`, `common/omm.py`, `common/tle.py` — shared parsers / writers
- `common/kepler.py` — Keplerian element conversions with J2 short-period corrections
- `common/mean_kepler.py` — mean Keplerian element conversions
- `common/common.py` — shared utilities (OEM state-line parsing, time conversion, duration/step parsing)

See [TLE.md](TLE.md) for full usage details.

## Miscellaneous Utilities

The repository includes several utility scripts for orbit analysis, comparison, and manipulation:

- `bin/state_diff.py` — compare two OEM-like Cartesian states
- `bin/slice_oem.py` — slice OEM files by index or time range
- `oem_to_tle/evaluate_oem_to_tle.py` — evaluate TLE estimation accuracy
- `plotting/plot_orbits.py` — plot and compare multiple orbits
- `plotting/plot_dependent_variables.py` — plot dependent variables from propagation

See [MISC.md](MISC.md) for full usage details.

## Build and Dependencies

### Python tools

Typical Python dependencies used by the scripts:

- [TudatPy](https://docs.tudat.space/en/latest/) (`tudatpy`)
- NumPy

Some scripts use only the Python standard library plus local helpers.

### C++ tools

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
