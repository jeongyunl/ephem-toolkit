# Common Library Summary

This document provides a comprehensive overview of the libraries and functions available in the `common/` directory of the tudatpy-utils project.

## Table of Contents

1. [time_utils.py - Time Utilities](#time_utilspy---time-utilities)
2. [common.py - Common Utilities](#commonpy---common-utilities)
3. [consts.py - Physical Constants](#constspy---physical-constants)
4. [kepler.py - Keplerian Orbital Elements](#keplerpy---keplerian-orbital-elements)
5. [mean_kepler.py - Mean Keplerian Elements](#mean_keplerpy---mean-keplerian-elements)
6. [convert_tle.py - TLE/OMM Conversion](#convert_tlepy---tleomm-conversion)
7. [tle.py - Two-Line Element Sets](#tlepy---two-line-element-sets)
8. [omm.py - Orbit Mean-Elements Message](#ommpy---orbit-mean-elements-message)
9. [oem.py - Orbit Ephemeris Message](#oempy---orbit-ephemeris-message)
10. [slice_oem.py - OEM Slicing Utilities](#slice_oempy---oem-slicing-utilities)
11. [interpolator/ - Interpolation Package](#interpolator---interpolation-package)

---

## time_utils.py - Time Utilities

**Purpose**: Time conversion, ISO 8601 parsing/formatting, and CLI duration parsing. All time-related functionality is consolidated here; import as `import common.time_utils as time_utils`.

### Key Dependencies
- `tudatpy.astro.time_representation`
- `datetime`, `re`

### Time Conversion Functions

#### `datetime_to_tdb_s(dt: datetime) -> float`
Convert a datetime object to TDB (ephemeris time) seconds since J2000.

#### `tdb_s_to_datetime(tdb_s: float) -> datetime`
Convert TDB seconds since J2000 to a UTC datetime object.

### ISO 8601 Parsing and Formatting

#### `iso8601_to_datetime(epoch_str: str) -> datetime`
Parse an ISO 8601 epoch string into a datetime object. Supports formats with 'T' or space separators, fractional seconds, and optional 'Z' timezone indicator.

#### `datetime_to_iso8601(dt: datetime, use_t_separator: bool = True, fractional_second_places: int = 3) -> str`
Convert a datetime object to an ISO 8601 formatted string in UTC.

### CLI Duration/Step-Size Parsing

#### `parse_duration_to_timedelta(value: str, default_unit: str = "s", allow_negative: bool = False, allow_zero: bool = False) -> timedelta`
Parse a duration string and return a timedelta. Supports both single-component durations (e.g., "5m", "90s") and multi-component durations (e.g., "1h30m", "2m30s").

**Parameters:**
- `value`: Duration string with optional unit suffix (s, m, h, d). Supports multi-component format like "1h30m" or "2m30s".
- `default_unit`: Unit to apply when no unit suffix is present. Default is "s".
- `allow_negative`: If True, allow negative durations (default: False).
- `allow_zero`: If True, allow zero durations (default: False).

**Returns:** Duration as a timedelta object.

#### `parse_duration_to_seconds(value: str, default_unit: str = "s", allow_negative: bool = False, allow_zero: bool = False) -> float`
Parse a duration string and convert to seconds. Convenience wrapper around `parse_duration_to_timedelta` that returns a float in seconds.

**Parameters:**
- `value`: Duration string with optional unit suffix (s, m, h, d). Supports multi-component format like "1h30m" or "2m30s".
- `default_unit`: Unit to apply when no unit suffix is present. Default is "s".
- `allow_negative`: If True, allow negative durations (default: False).
- `allow_zero`: If True, allow zero durations (default: False).

**Returns:** Duration in seconds.

### Constants
- `SECONDS_PER_MINUTE = 60.0`
- `SECONDS_PER_HOUR = 3600.0`
- `SECONDS_PER_DAY = 86400.0`

---

## common.py - Common Utilities

**Purpose**: Shared utilities for frame transformations, angle operations, SPICE kernel management, and CCSDS keyword-value parsing. Time-related functions live in `common.time_utils`.

### Key Dependencies
- `numpy`
- `math`, `pathlib`, `os`

### SPICE Kernel Management

#### `get_spice_kernel_path() -> str`
Return the Tudatpy SPICE kernel path using an XDG-style cache file.

### CCSDS Keyword-Value Parsing

#### `parse_key_value_line(line: str) -> tuple[str, str] | None`
Return (key, value) from `KEY = VALUE` lines, or None. Shared utility used by OEM and OMM parsers for reading CCSDS keyword-value formatted files.

### RTN Frame Transformation

#### `transform_to_rtn(state: np.ndarray, reference_state: np.ndarray | None = None) -> np.ndarray`
Calculate relative position and velocity in the RTN (Radial-Transverse-Normal) frame. Supports both single and batch processing of state vectors.

**Parameters:**
- `state`: Target object state vector(s) [x, y, z, vx, vy, vz]
  - Shape (6,): Single state vector
  - Shape (N, 6): Batch of N state vectors
- `reference_state`: Reference object state vector for RTN frame definition

**Returns:** Relative state vector(s) in RTN coordinates [r, t, n, vr, vt, vn]

### Angle Utilities

#### `wrap_angle_rad(angle: float) -> float`
Wrap angle to [0, 2π) range.

#### `unwrap_angles_rad(angles: list[float]) -> list[float]`
Unwrap angle sequence to remove 2π discontinuities.

#### `circular_mean_angle_rad(angles: list[float]) -> float`
Return circular mean angle in [0, 2π).

#### `angle_difference_rad(target: float, reference: float) -> float`
Return signed wrapped angle difference target-reference in [-π, π].

#### `circular_blend_angle_rad(primary_angle: float, correction_angle: float, correction_weight: float) -> float`
Blend angles along the shortest arc.

---

## consts.py - Physical Constants

**Purpose**: Earth physical constants for orbital mechanics calculations.

### Constants

- `EARTH_GRAVITATIONAL_PARAMETER_M3_S2 = 3.986004418e14` - Earth gravitational parameter (m³/s²), WGS-84
- `EARTH_EQUATORIAL_RADIUS_M = 6378136.3` - Earth equatorial radius (m), WGS-84
- `EARTH_MEAN_RADIUS_M = 6371000.0` - Earth mean radius (m), approximately 6371 km
- `EARTH_J2 = 1.08262668e-3` - Earth J2 zonal harmonic coefficient (dimensionless), WGS-84

---

## kepler.py - Keplerian Orbital Elements

**Purpose**: Convert between Cartesian state vectors and osculating Keplerian elements using only NumPy.

### Key Dependencies
- `numpy`
- `common.consts`

### Keplerian Element Indices
- `SEMI_MAJOR_AXIS_INDEX = 0` - Semi-major axis (m)
- `ECCENTRICITY_INDEX = 1` - Eccentricity (dimensionless)
- `INCLINATION_INDEX = 2` - Inclination (rad)
- `ARGUMENT_OF_PERIAPSIS_INDEX = 3` - Argument of periapsis (rad)
- `RAAN_INDEX = 4` - Right ascension of ascending node (rad)
- `TRUE_ANOMALY_INDEX = 5` - True anomaly (rad)
- `MEAN_ANOMALY_INDEX = 5` - Alias for TRUE_ANOMALY_INDEX

### Cartesian ↔ Keplerian Conversion

#### `cartesian_to_keplerian(cartesian_state_vector: np.ndarray, mu_m3_s2: float) -> np.ndarray`
Convert Cartesian state vector(s) to osculating Keplerian elements. Supports both single and batch processing.

**Parameters:**
- `cartesian_state_vector`: Shape (6,) or (N, 6) - [x, y, z, vx, vy, vz] in meters and m/s
- `mu_m3_s2`: Gravitational parameter (m³/s²)

**Returns:** Keplerian elements [a, e, i, omega, RAAN, theta] in radians and meters

#### `keplerian_to_cartesian(keplerian_elements: np.ndarray, mu_m3_s2: float) -> np.ndarray`
Convert Keplerian elements to Cartesian state vector(s). Supports both single and batch processing.

**Parameters:**
- `keplerian_elements`: Shape (6,) or (N, 6) - [a, e, i, omega, RAAN, theta]
- `mu_m3_s2`: Gravitational parameter (m³/s²)

**Returns:** Cartesian state vector(s) [x, y, z, vx, vy, vz] in m and m/s

### Anomaly Conversions

#### `true_to_eccentric_anomaly(true_anomaly: float, eccentricity: float) -> float`
Convert true anomaly to eccentric anomaly.

#### `eccentric_to_true_anomaly(eccentric_anomaly: float, eccentricity: float) -> float`
Convert eccentric anomaly to true anomaly.

#### `eccentric_to_mean_anomaly(eccentric_anomaly: float, eccentricity: float) -> float`
Convert eccentric anomaly to mean anomaly (Kepler's equation).

#### `mean_to_eccentric_anomaly(mean_anomaly: float, eccentricity: float, tol: float = 1e-14, max_iter: int = 100) -> float`
Solve Kepler's equation M = E − e·sin(E) for eccentric anomaly E using Newton-Raphson iteration.

#### `mean_to_true_anomaly(mean_anomaly: float, eccentricity: float, tol: float = 1e-12) -> float`
Convert mean anomaly to true anomaly via eccentric anomaly.

#### `true_to_mean_anomaly(true_anomaly: float, eccentricity: float) -> float`
Convert true anomaly to mean anomaly via eccentric anomaly.

### Mean Motion Utilities

#### `mean_motion_to_semi_major_axis(mean_motion_rev_per_day: float, mu_m3_s2: float) -> float`
Convert mean motion (rev/day) to semi-major axis (m) using Kepler's third law.

#### `semi_major_axis_to_mean_motion(semi_major_axis_m: float, mu_m3_s2: float) -> float`
Convert semi-major axis (m) to mean motion (rev/day) using Kepler's third law.

### Propagation

#### `propagate_kepler(keplerian_elements: np.ndarray, time_elapsed_s: float, mu_m3_s2: float) -> np.ndarray`
Propagate Keplerian elements forward in time using the two-body solution. Only the true anomaly changes; other elements remain constant.

---

## mean_kepler.py - Mean Keplerian Elements

**Purpose**: Convert between osculating and mean (Brouwer) Keplerian elements with J2 perturbations.

### Key Dependencies
- `numpy`
- `common.kepler`
- `common.consts`

### Mean to Osculating Conversion

#### `compute_brouwer_short_period_corrections(mean_keplerian_elements: np.ndarray, R_e_m: float, J2: float) -> np.ndarray`
Compute Brouwer first-order J2 short-period corrections to convert mean Keplerian elements (as used in TLE/SGP4) to osculating elements.

**Parameters:**
- `mean_keplerian_elements`: Shape (6,) or (N, 6) - [a, e, i, omega, RAAN, M]
- `R_e_m`: Earth equatorial radius (m)
- `J2`: J2 zonal harmonic coefficient

**Returns:** Osculating Keplerian elements [a, e, i, omega, RAAN, theta]

#### `mean_to_osculating_keplerian(mean_keplerian_elements: np.ndarray, R_e_m: float, J2: float) -> np.ndarray`
Alias for `compute_brouwer_short_period_corrections` provided for API consistency. Same parameters and return value.

### Osculating to Mean Conversion

#### `osculating_to_mean_keplerian(osculating_keplerian_elements: np.ndarray, R_e_m: float = EARTH_EQUATORIAL_RADIUS_M, J2: float = EARTH_J2, max_iter: int = 20, tol_m: float = 1e-12) -> np.ndarray`
Convert osculating Keplerian elements to mean (Brouwer) elements using iterative inversion.

**Parameters:**
- `osculating_keplerian_elements`: Shape (6,) - [a, e, i, omega, RAAN, theta]
- `R_e_m`: Earth equatorial radius (m) (default: WGS-84)
- `J2`: J2 zonal harmonic coefficient (default: WGS-84)
- `max_iter`: Maximum iterations for convergence
- `tol_m`: Convergence tolerance on semi-major axis (m)

**Returns:** Mean Keplerian elements [a, e, i, omega, RAAN, M]

### J2 Secular Propagation

#### `compute_raan_rate(keplerian_elements: np.ndarray, mu_m3_s2: float, R_e_m: float, J2: float) -> float`
Compute the J2 secular rate of RAAN (rad/s).

#### `propagate_mean_j2(keplerian_elements: np.ndarray, time_elapsed_s: float, mu_m3_s2: float, R_e_m: float, J2: float) -> np.ndarray`
Propagate mean Keplerian elements forward in time using J2 secular rates.

**Parameters:**
- `keplerian_elements`: Mean elements at epoch [a, e, i, omega, RAAN, M]
- `time_elapsed_s`: Time elapsed since epoch (s)
- `mu_m3_s2`: Gravitational parameter (m³/s²)
- `R_e_m`: Earth equatorial radius (m)
- `J2`: J2 zonal harmonic coefficient

**Returns:** Mean Keplerian elements at epoch + time_elapsed_s

#### `mean_elements_to_cartesian(mean_elements: np.ndarray, mu_m3_s2: float, R_e_m: float, J2: float) -> np.ndarray`
Convert mean elements to Cartesian state via Brouwer short-period corrections.

---

## convert_tle.py - TLE/OMM Conversion

**Purpose**: Convert between TLE and OMM representations, and TLE to osculating Keplerian elements.

### Key Dependencies
- `numpy`
- `common.kepler`
- `common.mean_kepler`
- `common.omm`
- `common.tle`
- `common.consts`

### TLE ↔ OMM Conversion

#### `tle_to_omm(tle_obj: tle.Tle, *, creation_date: str = "", originator: str = "") -> omm.CcsdsOmm`
Convert a TLE to a CCSDS OMM.

**Parameters:**
- `tle_obj`: Parsed TLE dataclass instance
- `creation_date`: Optional creation date for the OMM header
- `originator`: Optional originator for the OMM header

**Returns:** The equivalent OMM representation

#### `omm_to_tle(omm_obj: omm.CcsdsOmm) -> tle.Tle`
Convert a CCSDS OMM to a TLE.

**Parameters:**
- `omm_obj`: Parsed OMM dataclass instance

**Returns:** The equivalent TLE representation (with empty line1 and line2 fields)

### TLE to Osculating Keplerian

#### `tle_to_osculating_keplerian(tle_obj: tle.Tle, mu_m3_s2: float = EARTH_GRAVITATIONAL_PARAMETER_M3_S2, apply_j2: bool = True) -> np.ndarray`
Extract osculating Keplerian elements at the TLE epoch.

**Parameters:**
- `tle_obj`: Parsed TLE dataclass
- `mu_m3_s2`: Gravitational parameter (m³/s²) (default: Earth WGS-84)
- `apply_j2`: If True, apply Brouwer J2 short-period corrections; if False, use simple two-body conversion

**Returns:** Osculating Keplerian elements [a, e, i, omega, RAAN, theta]

---

## tle.py - Two-Line Element Sets

**Purpose**: Read, parse, and write NORAD Two-Line Element (TLE) sets.

### Key Dependencies
- `datetime`, `pathlib`, `re`, `dataclasses`, `typing`
- `common.common`, `common.time_utils`

### Data Structure

#### `class Tle` (dataclass)
Parsed Two-Line Element set data with all fields corresponding to the standard TLE format.

**Key Fields:**
- `name`: Satellite name
- `line1`, `line2`: Raw TLE lines
- `satellite_number`: NORAD catalog number
- `classification`: U=Unclassified, C=Classified, S=Secret
- `epoch_year`, `epoch_day`: Epoch (2-digit year + fractional day)
- `mean_motion_first_derivative`: First time derivative (rev/day²)
- `mean_motion_second_derivative`: Second time derivative (TLE exponential format)
- `bstar`: BSTAR drag term (TLE exponential format)
- `inclination_deg`, `raan_deg`, `arg_perigee_deg`, `mean_anomaly_deg`: Orbital elements (degrees)
- `eccentricity`: Eccentricity (0.0 to 1.0)
- `mean_motion_rev_per_day`: Mean motion (rev/day)
- `revolution_number_at_epoch`: Revolution number at epoch

### Functions

#### `read_tle(stream: TextIO) -> Tle`
Parse TLE elements from a text stream. Accepts 2-line or 3-line format (with name).

#### `write_tle(dest: TextIO | str | Path, tle_data: Tle | Mapping[str, object]) -> tuple[str, str]`
Write a TLE to a text stream or file path. Returns the formatted (line1, line2) strings.

#### `datetime_to_tle_epoch(epoch_dt: datetime) -> tuple[int, float]`
Convert a datetime object to TLE epoch components (2-digit year and fractional day).

#### `tle_epoch_to_iso8601(epoch_year: int, epoch_day: float) -> str`
Convert TLE epoch (2-digit year + fractional day) to ISO 8601 datetime string.

#### `iso8601_to_tle_epoch(iso_str: str) -> tuple[int, float]`
Convert ISO 8601 datetime string to TLE epoch (2-digit year + fractional day).

#### `format_tle_strings(tle_data: Tle | Mapping[str, object]) -> tuple[str, str]`
Format TLE data into raw TLE line strings with checksums.

#### `create_tle_from_mean_keplerian(mean_elements, mu_m3_s2, epoch_year, epoch_day, ...) -> Tle`
Construct a TLE dataclass instance from mean Keplerian elements, with optional TLE header fields.

#### `compute_tle_checksum(line_without_checksum: str) -> str`
Return the single-digit TLE checksum character for a TLE line.

---

## omm.py - Orbit Mean-Elements Message

**Purpose**: Read, parse, and write CCSDS Orbit Mean-Elements Message (OMM) files.

### Key Dependencies
- `dataclasses`, `pathlib`, `typing`, `datetime`
- `numpy`
- `common.common`, `common.consts`, `common.time_utils`, `common.kepler`

### Data Structure

#### `class CcsdsOmm` (dataclass)
Parsed CCSDS Orbit Mean-Elements Message. All angular quantities are stored in degrees and mean motion in revolutions per day.

**Key Fields:**
- `version`: CCSDS OMM format version number
- `creation_date`, `originator`: File metadata
- `comments`: List of comment lines
- `object_name`, `object_id`: Satellite identification
- `center_name`, `ref_frame`, `time_system`: Reference frame information
- `mean_element_theory`: Mean element theory used (e.g., DSST, SGP4)
- `epoch`: Epoch time (ISO 8601 format)
- `mean_motion`, `eccentricity`, `inclination`, `ra_of_asc_node`, `arg_of_pericenter`, `mean_anomaly`: Orbital elements
- `tle_parameters`: Optional `TleParameters` object containing TLE-related metadata such as `ephemeris_type`, `classification_type`, `norad_cat_id`, `element_set_no`, `rev_at_epoch`, `bstar`, `mean_motion_dot`, and `mean_motion_ddot`

### Functions

#### `read_omm(source: TextIO | str | Path) -> tuple[dict, dict]`
Read an OMM file and return (header, data) dictionaries.

#### `write_omm(dest: TextIO | str | Path, header: dict, data: dict) -> None`
Write an OMM file from (header, data) dictionaries.

#### `CcsdsOmm.from_source(source: TextIO | str | Path) -> CcsdsOmm`
Construct a CcsdsOmm from a file or stream.

#### `CcsdsOmm.to_file(dest: TextIO | str | Path) -> None`
Write this OMM to a file or stream.

---

## oem.py - Orbit Ephemeris Message

**Purpose**: Read, parse, and write CCSDS Orbit Ephemeris Message (OEM) files.

### Unit Convention

OEM files use kilometers (km) and km/s per the CCSDS standard. This module converts state vectors to SI units (meters and m/s) when reading, and converts back to km/km·s⁻¹ when writing. This ensures internal consistency with the project-wide SI unit convention while maintaining CCSDS-compliant file output.

### Key Dependencies
- `numpy`, `datetime`, `pathlib`, `dataclasses`
- `common.common`, `common.time_utils`

### Constants
- `KILOMETERS_TO_METERS = 1000.0` - Conversion factor from kilometers to meters

### Data Structures

#### `class OemHeader` (dataclass)
File-level header fields for a CCSDS OEM message.

**Fields:**
- `version`: CCSDS OEM format version number
- `comments`: List of comment lines
- `creation_date`: File creation date (ISO 8601)
- `originator`: Organization that created the file

#### `class OemMeta` (dataclass)
Metadata block fields for a CCSDS OEM segment.

**Fields:**
- `object_name`, `object_id`: Satellite identification
- `center_name`, `ref_frame`, `time_system`: Reference frame information
- `start_time`, `stop_time`: Ephemeris time range
- `useable_start_time`, `useable_stop_time`: Recommended usage time range
- `interpolation`, `interpolation_degree`: Interpolation method and degree
- `comments`: List of comment lines

#### `class CcsdsOem`
Structured CCSDS Orbit Ephemeris Message with header, metadata, and states.

**Attributes:**
- `header`: File-level header fields (OemHeader)
- `meta`: Metadata block fields (OemMeta)
- `states`: List of (POSIX timestamp, state_vector) tuples, sorted by timestamp in ascending order. State vectors are 6-element arrays [x, y, z, vx, vy, vz] in meters (m) and m/s.

**Properties:**
- `epochs`: Sorted list of epoch POSIX timestamps
- `state_vectors`: State vectors ordered by epoch, shape (N, 6) in meters and m/s

**Class Methods:**
- `CcsdsOem.read(source: TextIO | str | Path) -> CcsdsOem`: Read and construct from a file or stream
- `CcsdsOem.from_states(states, object_name, ref_frame, center_name, time_system) -> CcsdsOem`: Create from a list of states with minimal metadata
- `CcsdsOem.parse_state_line(line: str) -> tuple[float, np.ndarray] | None`: Parse a single OEM-style state line

**Instance Methods:**
- `write(dest: TextIO | str | Path) -> None`: Write this OEM to a file or stream
- `update_metadata(**kwargs) -> None`: Update metadata fields in-place
- `with_metadata(**kwargs) -> CcsdsOem`: Return a new CcsdsOem with updated metadata (immutable)
- `find_state_by_timestamp(timestamp: float, tolerance: float = 0.0) -> tuple[float, np.ndarray] | None`: Find a state by timestamp using binary search

### Module-Level Functions

#### `parse_oem_state_line(line: str) -> tuple[float, np.ndarray] | None`
Parse a single line of OEM-style data. Accepts whitespace or comma separated values. Returns (POSIX timestamp, state_vector) where state_vector is in meters (m) and m/s (converted from OEM km/km·s⁻¹).

#### `read_oem(source: TextIO | str | Path) -> tuple[dict, dict, list[tuple[float, np.ndarray]]]`
Read an OEM file and return (header, meta, states) where states is a list of (POSIX timestamp, state_vector) tuples sorted by timestamp. State vectors are in meters (m) and m/s.

#### `find_state_by_timestamp(states: list[tuple[float, np.ndarray]], timestamp: float, tolerance: float = 0.0) -> tuple[float, np.ndarray] | None`
Find a state by timestamp using binary search (O(log n)). Returns the matching (timestamp, state_vector) tuple or None.

#### `write_state(dest: TextIO, epoch: datetime, state_vector: np.ndarray) -> None`
Write a single state vector to a file handle. Converts from SI units (m, m/s) to OEM standard (km, km/s).

#### `write_states(dest: TextIO, states: dict | list) -> None`
Write state vectors to a file handle. Converts from SI units (m, m/s) to OEM standard (km, km/s).

#### `write_oem(dest: TextIO | str | Path, header: dict, meta: dict, states: dict | list) -> None`
Write an OEM file from (header, meta, states) dictionaries. Converts from SI units (m, m/s) to OEM standard (km, km/s).

---

## slice_oem.py - OEM Slicing Utilities

**Purpose**: Common slice helpers for OEM state selection with time-based and index-based slicing.

### Key Dependencies
- `datetime`, `bisect`, `re`, `dataclasses`
- `common.time_utils`
- `common.interpolator.lagrange`

### Constants
- `INTERPOLATION_DEGREE = 8` - Polynomial degree for Lagrange interpolation

### Data Structures

#### `class TimeSliceOptions` (dataclass)
Parsed options for a time-based OEM slice operation.

**Fields:**
- `start_time`: Start of time window (datetime or timedelta offset)
- `stop_time`: End of time window (datetime or timedelta offset)
- `step_size`: Resampling interval (timedelta)
- `interpolate`: Whether to enable Lagrange interpolation

### Functions

#### `parse_slice_args(slice_str: str) -> slice`
Parse a Python-style slice string into a slice object (e.g., "0:10", "::2", "5", "-5:").

#### `parse_time_slice_args(time_slice_str: str) -> TimeSliceOptions`
Parse an ISO-8601 time slice string using comma separators. Format: `start[,stop[,step]]`.

#### `slice_states(states: dict[float, object], slice_spec: TimeSliceOptions | slice) -> list[tuple[float, object]]`
Return sliced OEM states based on a time or index slice specification.

#### `slice_states_by_time(states: dict[float, object], options: TimeSliceOptions) -> list[tuple[float, object]]`
Extract states within a time window using TimeSliceOptions. Supports interpolation when step_size is provided.

---

## interpolator/ - Interpolation Package

**Purpose**: Provide interpolation capabilities for time-series data with ordered sample storage.

### interpolator.py - Base Interpolator

#### `class Interpolator`
Base interpolator supporting fixed-size ordered sample storage.

**Key Methods:**
- `__init__(dimension: int = 1)`: Initialize with dependent-vector dimension
- `add_data_point(independent_value: float, dependent_data: np.ndarray)`: Store a new sample pair
- `set_data(data: dict | list, dependent_data: list | None = None)`: Replace all stored samples
- `reset_state()`: Reset sequential state while keeping buffered samples
- `clear_storage()`: Remove all stored samples and reset internal state
- `interpolate(independent_value: float) -> np.ndarray | None`: Compute interpolated dependent data

**Properties:**
- `force_interpolation`: Whether to force interpolation even with poor conditions
- `allow_extrapolation`: Whether to allow queries outside the data range
- `independent_values`: Ordered independent variable values
- `dependent_values`: Corresponding dependent vectors
- `dependent_dimension`: Number of components in each dependent vector
- `required_points`: Minimum number of samples required

### lagrange.py - Lagrange Interpolator

#### `class LagrangeInterpolator(Interpolator)`
Lagrange polynomial interpolator that selects a local polynomial window around each query point.

**Key Methods:**
- `__init__(dimension: int = 1, degree: int = 8)`: Initialize with dimension and polynomial degree
- `interpolate_value(independent_value: float) -> np.ndarray | None`: Compute interpolated dependent vector
- `check_interpolation_feasibility(independent_value: float) -> int`: Verify query is within range
- `adjust_order_for_points() -> bool`: Decrease polynomial degree when fewer samples available
- `select_candidate_window(independent_value: float)`: Select contiguous point window around query
- `choose_evaluation_start_index(independent_value: float)`: Pick starting index to minimize bias

**Properties:**
- `degree`: Current interpolation polynomial degree
- `base_degree`: Base degree to restore when buffer returns to full capacity
- `MAX_BUFFER_SIZE = 80`: Maximum allowed number of buffered samples

**Constants:**
- `RANGE_OVERSHOOT_TOLERANCE = 1e-8`: Tolerance for queries marginally outside data range
- `MIN_DIFFERENCE_FOR_START = 1.0e30`: Sentinel value for window bias search

---

## Summary of Key Use Cases

### 1. **Time Conversions** (`common.time_utils`)
- Convert between datetime, TDB, and ISO 8601 formats
- Parse and format durations and step sizes

### 2. **Orbital Element Conversions**
- Cartesian ↔ Keplerian (osculating)
- Mean ↔ Osculating (with J2 corrections)
- TLE ↔ OMM ↔ Keplerian

### 3. **Orbital Propagation**
- Two-body Keplerian propagation
- J2 secular propagation of mean elements

### 4. **File I/O**
- Read/write TLE files
- Read/write OMM files
- Read/write OEM files

### 5. **Data Processing**
- Slice OEM data by time or index
- Interpolate ephemeris data using Lagrange polynomials
- Transform states to RTN frame

### 6. **Anomaly Conversions**
- True ↔ Eccentric ↔ Mean anomaly
- Solve Kepler's equation

### 7. **Angle Operations**
- Wrap/unwrap angles
- Circular mean and blending
- Angle differences

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
