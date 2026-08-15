# Core Library Summary

This document provides an overview of the libraries and functions available in the `core/` directory of the ephem-toolkit project. The documentation has been organized into logical groups for easier navigation.

## Documentation Groups

The core library is organized into the following functional groups:

### 1. [Time & Utilities](CORE_LIBRARY_TIME_UTILITIES.md)
Core utilities for time conversions, ISO 8601 formatting, duration parsing, and physical constants.
- **ephem_toolkit.core.time_utils** - Time conversion, ISO 8601 parsing/formatting, CLI duration parsing
- **ephem_toolkit.core.misc** - CCSDS parsing, RTN frame transformation, rotation matrix utilities, angle utilities
- **ephem_toolkit.core.spice_utils** - SPICE kernel path management and loading
- **ephem_toolkit.core.consts** - Earth physical constants (gravitational parameter, radius, J2)

### 2. [Orbital Elements](CORE_LIBRARY_ORBITAL_ELEMENTS.md)
Conversions between Cartesian states and Keplerian orbital elements, including mean element calculations.
- **ephem_toolkit.core.kepler** - Cartesian ↔ Keplerian conversions, anomaly conversions, mean motion utilities, propagation
- **ephem_toolkit.core.mean_kepler** - Mean ↔ Osculating conversions with J2 perturbations, J2 secular propagation

### 3. [TLE & OMM](CORE_LIBRARY_TLE_OMM.md)
Two-Line Element sets, Orbit Mean-Elements Messages, and format conversions.
- **ephem_toolkit.core.tle** - Read/parse/write NORAD Two-Line Element sets
- **ephem_toolkit.core.convert_tle** - TLE ↔ OMM conversions, TLE to osculating Keplerian elements
- **ephem_toolkit.core.ccsds.odm** - CCSDS Orbit Data Message reference frame and time system definitions
- **ephem_toolkit.core.ccsds.omm** - Read/parse/write CCSDS Orbit Mean-Elements Message files
- **ephem_toolkit.core.ccsds.oem** - Read/parse/write CCSDS Orbit Ephemeris Message files

### 4. [Coordinate Transformations](CORE_LIBRARY_COORDINATE_TRANSFORMATIONS.md)
Reference frame conversions and coordinate system transformations.
- **ephem_toolkit.core.frame_utils** - TEME/J2000, SPICE frame, and inertial/body-fixed conversions
- **ephem_toolkit.core.wgs** - WGS-84 coordinate conversions (ECEF ↔ ENU, LLA ↔ ECEF)
- **ephem_toolkit.core.aer** - AER (Azimuth-Elevation-Range) coordinate conversions

### 5. [Data Processing](CORE_LIBRARY_DATA_PROCESSING.md)
OEM data slicing and interpolation utilities.
- **ephem_toolkit.core.slice_oem** - OEM state selection with time-based and index-based slicing
- **ephem_toolkit.core.interpolator** - Hermite, Chebyshev, and Lagrange polynomial interpolation for time-series data
- **ephem_toolkit.core.cli** - Common CLI utilities for parsing interpolation specifications

---

## Quick Reference: Key Use Cases

### Time Conversions
- Convert between datetime, TDB, and ISO 8601 formats
- Parse and format durations and step sizes
- See: [Time & Utilities](CORE_LIBRARY_TIME_UTILITIES.md)

### Orbital Element Conversions
- Cartesian ↔ Keplerian (osculating)
- Mean ↔ Osculating (with J2 corrections)
- TLE ↔ OMM ↔ Keplerian
- See: [Orbital Elements](CORE_LIBRARY_ORBITAL_ELEMENTS.md) and [TLE & OMM](CORE_LIBRARY_TLE_OMM.md)

### Orbital Propagation
- Two-body Keplerian propagation
- J2 secular propagation of mean elements
- See: [Orbital Elements](CORE_LIBRARY_ORBITAL_ELEMENTS.md)

### File I/O
- Read/write TLE files
- Read/write OMM files
- Read/write OEM files
- See: [TLE & OMM](CORE_LIBRARY_TLE_OMM.md)

### Data Processing
- Slice OEM data by time or index
- Interpolate ephemeris data using Hermite, Chebyshev, or Lagrange polynomials
- Transform states to RTN frame
- See: [Data Processing](CORE_LIBRARY_DATA_PROCESSING.md) and [Time & Utilities](CORE_LIBRARY_TIME_UTILITIES.md)

### Anomaly Conversions
- True ↔ Eccentric ↔ Mean anomaly
- Solve Kepler's equation
- See: [Orbital Elements](CORE_LIBRARY_ORBITAL_ELEMENTS.md)

### Coordinate Transformations
- ECEF ↔ ENU ↔ AER conversions
- Geodetic (LLA) ↔ ECEF conversions
- TEME ↔ J2000 conversions
- Batch processing support
- See: [Coordinate Transformations](CORE_LIBRARY_COORDINATE_TRANSFORMATIONS.md)

### Angle Operations
- Wrap/unwrap angles
- Circular mean and blending
- Angle differences
- See: [Time & Utilities](CORE_LIBRARY_TIME_UTILITIES.md)

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
