# Common Library Summary

This document provides an overview of the libraries and functions available in the `common/` directory of the tudatpy-utils project. The documentation has been organized into logical groups for easier navigation.

## Documentation Groups

The common library is organized into the following functional groups:

### 1. [Time & Utilities](COMMON_LIBRARY_TIME_UTILITIES.md)
Core utilities for time conversions, ISO 8601 formatting, duration parsing, and physical constants.
- **tudatpy_utils.common.time_utils** - Time conversion, ISO 8601 parsing/formatting, CLI duration parsing
- **tudatpy_utils.common.common** - SPICE kernel management, CCSDS parsing, RTN frame transformation, angle utilities
- **tudatpy_utils.common.consts** - Earth physical constants (gravitational parameter, radius, J2)

### 2. [Orbital Elements](COMMON_LIBRARY_ORBITAL_ELEMENTS.md)
Conversions between Cartesian states and Keplerian orbital elements, including mean element calculations.
- **tudatpy_utils.common.kepler** - Cartesian ↔ Keplerian conversions, anomaly conversions, mean motion utilities, propagation
- **tudatpy_utils.common.mean_kepler** - Mean ↔ Osculating conversions with J2 perturbations, J2 secular propagation

### 3. [TLE & OMM](COMMON_LIBRARY_TLE_OMM.md)
Two-Line Element sets, Orbit Mean-Elements Messages, and format conversions.
- **tudatpy_utils.common.tle** - Read/parse/write NORAD Two-Line Element sets
- **tudatpy_utils.common.convert_tle** - TLE ↔ OMM conversions, TLE to osculating Keplerian elements
- **tudatpy_utils.common.ccsds.odm** - CCSDS Orbit Data Message reference frame and time system definitions
- **tudatpy_utils.common.ccsds.omm** - Read/parse/write CCSDS Orbit Mean-Elements Message files
- **tudatpy_utils.common.ccsds.oem** - Read/parse/write CCSDS Orbit Ephemeris Message files

### 4. [Coordinate Transformations](COMMON_LIBRARY_COORDINATE_TRANSFORMATIONS.md)
Reference frame conversions and coordinate system transformations.
- **tudatpy_utils.common.frame_utils** - TEME/J2000, SPICE frame, and inertial/body-fixed conversions
- **tudatpy_utils.common.wgs** - WGS-84 coordinate conversions (ECEF ↔ ENU, LLA ↔ ECEF)
- **tudatpy_utils.common.aer** - AER (Azimuth-Elevation-Range) coordinate conversions

### 5. [Data Processing](COMMON_LIBRARY_DATA_PROCESSING.md)
OEM data slicing and interpolation utilities.
- **tudatpy_utils.common.slice_oem** - OEM state selection with time-based and index-based slicing
- **tudatpy_utils.common.interpolator** - Lagrange polynomial interpolation for time-series data

---

## Quick Reference: Key Use Cases

### Time Conversions
- Convert between datetime, TDB, and ISO 8601 formats
- Parse and format durations and step sizes
- See: [Time & Utilities](COMMON_LIBRARY_TIME_UTILITIES.md)

### Orbital Element Conversions
- Cartesian ↔ Keplerian (osculating)
- Mean ↔ Osculating (with J2 corrections)
- TLE ↔ OMM ↔ Keplerian
- See: [Orbital Elements](COMMON_LIBRARY_ORBITAL_ELEMENTS.md) and [TLE & OMM](COMMON_LIBRARY_TLE_OMM.md)

### Orbital Propagation
- Two-body Keplerian propagation
- J2 secular propagation of mean elements
- See: [Orbital Elements](COMMON_LIBRARY_ORBITAL_ELEMENTS.md)

### File I/O
- Read/write TLE files
- Read/write OMM files
- Read/write OEM files
- See: [TLE & OMM](COMMON_LIBRARY_TLE_OMM.md)

### Data Processing
- Slice OEM data by time or index
- Interpolate ephemeris data using Lagrange polynomials
- Transform states to RTN frame
- See: [Data Processing](COMMON_LIBRARY_DATA_PROCESSING.md) and [Time & Utilities](COMMON_LIBRARY_TIME_UTILITIES.md)

### Anomaly Conversions
- True ↔ Eccentric ↔ Mean anomaly
- Solve Kepler's equation
- See: [Orbital Elements](COMMON_LIBRARY_ORBITAL_ELEMENTS.md)

### Coordinate Transformations
- ECEF ↔ ENU ↔ AER conversions
- Geodetic (LLA) ↔ ECEF conversions
- TEME ↔ J2000 conversions
- Batch processing support
- See: [Coordinate Transformations](COMMON_LIBRARY_COORDINATE_TRANSFORMATIONS.md)

### Angle Operations
- Wrap/unwrap angles
- Circular mean and blending
- Angle differences
- See: [Time & Utilities](COMMON_LIBRARY_TIME_UTILITIES.md)

---

## References

- Curtis, H.D. "Orbital Mechanics for Engineering Students"
- Vallado, D.A. "Fundamentals of Astrodynamics and Applications"
- Brouwer, D. "Solution of the Problem of Artificial Satellite Theory Without Drag", Astronomical Journal, 64, 1959
- Hoots, F.R. & Roehrich, R.L. "Spacetrack Report No. 3", 1980
- CCSDS 502.0-B-3 "Orbit Mean-Elements Message (OMM)" standard
- CCSDS 502.0-B-2 "Orbit Ephemeris Message (OEM)" standard
- ISO 8601 "Date and time representations"
- NORAD Two-Line Element Set Format
