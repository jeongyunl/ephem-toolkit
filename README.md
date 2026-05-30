# tudatpy-utils

Utility scripts for working with TudatPy.

## Overview

This repository provides a collection of command-line tools built on top of [TudatPy](https://docs.tudat.space/en/latest/) and [Tudat](https://docs.tudat.space/) for common astrodynamics tasks. The tools are organised into three areas:

### Frame Conversion

Python scripts for converting satellite state vectors between inertial (GCRF/J2000) and Earth-fixed (ITRF/IAU_Earth) reference frames. Multiple rotation models are supported, including SPICE-based rotations and the IAU 2006 GCRS-to-ITRS precession-nutation model.

- `frame_conversion/gcrf_to_itrf_spice.py` — GCRF ↔ ITRF conversion using SPICE rotation matrices.
- `frame_conversion/gcrf_to_itrf_rot_model.py` — GCRF ↔ ITRF conversion with a selectable Earth rotation model.

See [FRAME_CONVERSION.md](FRAME_CONVERSION.md) for full usage details.

### Time Conversion

A C++ command-line tool for converting between time representations (ISO 8601, POSIX, UTC/TAI/TT/TDB seconds since J2000). Three backends are available: a standalone leap-second-aware converter, a C++ `<chrono>`-based converter, and a Tudat-based converter that adds TDB support.

- `time_conversion/tools/convert_time_cli` — multi-backend time conversion CLI (built with CMake).

See [TIME_CONVERSION.md](TIME_CONVERSION.md) for full usage details.

### Orbit Propagation

A Python script for propagating a perturbed satellite orbit around Earth. It accepts a single OEM-style Cartesian state line and propagates it forward under configurable perturbations (spherical-harmonic gravity, third-body gravity, aerodynamic drag, solar radiation pressure). Post-propagation plots of accelerations, ground track, and Keplerian elements are generated automatically.

- `propagation/propagate_satellite_orbit.py` — perturbed orbit propagation with configurable perturbation toggles.

See [PROPAGATION.md](PROPAGATION.md) for full usage details.

## Dependencies

- [TudatPy](https://docs.tudat.space/en/latest/) (`tudatpy`) — Python tools
- [Tudat](https://docs.tudat.space/) — C++ tools (time conversion)
- NumPy
- Matplotlib (propagation script)
- C++20 compiler and CMake (time conversion tool)
