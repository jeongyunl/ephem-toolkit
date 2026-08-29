# Core Library - Time & Utilities

This document covers time utilities, common utilities, and physical constants in the `core/` directory.

## Table of Contents

1. [ephem_toolkit.core.time_utils - Time Utilities](#ephem_toolkitcoretime_utils---time-utilities)
2. [ephem_toolkit.core.misc - Miscellaneous Utilities](#ephem_toolkitcoremisc---miscellaneous-utilities)
3. [ephem_toolkit.core.spice_utils - SPICE Kernel Management](#ephem_toolkitcorespice_utils---spice-kernel-management)
4. [ephem_toolkit.core.consts - Physical Constants](#ephem_toolkitcoreconsts---physical-constants)

---

## ephem_toolkit.core.time_utils - Time Utilities

**Purpose**: Time conversion, ISO 8601 parsing/formatting, and CLI duration parsing. All time-related functionality is consolidated here; import as `import ephem_toolkit.core.time_utils as time_utils`.

### Key Dependencies
- `tudatpy.astro.time_representation`
- `datetime`, `re`

### Time Conversion Functions

#### `datetime_to_tt_s(dt: datetime) -> float`
Convert a datetime object to TT (Terrestrial Time) seconds since J2000.

#### `tt_s_to_datetime(tt_s: float) -> datetime`
Convert TT seconds since J2000 to a UTC datetime object.

#### `datetime_to_tdb_s(dt: datetime) -> float`
Convert a datetime object to TDB (Barycentric Dynamical Time) seconds since J2000. Retained for compatibility; TT is the primary ephemeris time scale.

#### `tdb_s_to_datetime(tdb_s: float) -> datetime`
Convert TDB seconds since J2000 to a UTC datetime object. Retained for compatibility; TT is the primary ephemeris time scale.

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

### Duration Formatting

#### `format_duration(duration: timedelta) -> str`
Return canonical duration string (e.g., `10h`, `30m`, `45s`).

**Returns:** Canonical duration string using the largest whole-unit denomination.

#### `format_duration_human(duration: timedelta) -> str`
Format a timedelta into a human-readable string (e.g., `2h 30m`, `45s`, `3d 1h`). Supports negative durations with a leading `-`.

### Constants
- `SECONDS_PER_MINUTE = 60.0`
- `SECONDS_PER_HOUR = 3600.0`
- `SECONDS_PER_DAY = 86400.0`

---

## ephem_toolkit.core.misc - Miscellaneous Utilities

**Purpose**: Shared utilities for CCSDS keyword-value parsing, RTN frame transformations, rotation matrix conversions, and angle operations. Time-related functions live in `ephem_toolkit.core.time_utils`.

### Key Dependencies
- `numpy`
- `math`

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
  - Shape (6,): Single reference state (used for all targets if batch)
  - Shape (N, 6): Batch of N reference states (one per target)
  - Defaults to [0, 0, 0, 0, 0, 0] if None

**Returns:** Relative state vector(s) in RTN coordinates [r, t, n, vr, vt, vn]

### Rotation Matrix Utilities

#### `rotation_matrix_to_euler_angles(rotation_matrix: np.ndarray) -> np.ndarray`
Convert a rotation matrix to ZYX Euler angles (intrinsic rotations).

**Parameters:**
- `rotation_matrix`: Three-by-three rotation matrix

**Returns:** Euler angles [yaw, pitch, roll] in degrees (ZYX convention)

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

## ephem_toolkit.core.spice_utils - SPICE Kernel Management

**Purpose**: SPICE kernel path management and loading utilities for Tudat/tudatpy integration.

### Key Dependencies
- `tudatpy.interface.spice`
- `pathlib`, `os`

### SPICE Kernel Management

#### `get_spice_kernel_path() -> str`
Return the Tudatpy SPICE kernel path using an XDG-style cache file.

**Returns:** Path to the SPICE kernel directory.

#### `load_kernel(kernel_file: str, kernel_path: str | Path | None = None) -> None`
Load a SPICE kernel from the specified or cached kernel directory.

**Parameters:**
- `kernel_file`: Name of the kernel file to load (e.g., "naif0012.tls")
- `kernel_path`: Optional path to kernel directory. If None, uses cached path from `get_spice_kernel_path()`

---

## ephem_toolkit.core.consts - Physical Constants

**Purpose**: Earth physical constants for orbital mechanics calculations.

### Constants

- `EARTH_GRAVITATIONAL_PARAMETER_M3_S2 = 3.986004418e14` - Earth gravitational parameter (m³/s²), WGS-84
- `EARTH_EQUATORIAL_RADIUS_M = 6378136.3` - Earth equatorial radius (m), WGS-84
- `EARTH_MEAN_RADIUS_M = 6371000.0` - Earth mean radius (m), approximately 6371 km
- `EARTH_J2 = 1.08262668e-3` - Earth J2 zonal harmonic coefficient (dimensionless), WGS-84
