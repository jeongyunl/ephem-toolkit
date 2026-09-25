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

#### `posix_to_tt_s(posix_s: float) -> float`
Convert a POSIX timestamp (seconds since the Unix epoch) to TT seconds since J2000.

#### `datetime_to_tt_s(dt: datetime) -> float`
Convert a datetime object to TT (Terrestrial Time) seconds since J2000. Naive datetimes are treated as UTC; timezone-aware values are converted to UTC first.

#### `tt_s_to_datetime(tt_s: float) -> datetime`
Convert TT seconds since J2000 to a UTC datetime object.

#### `datetime_to_tdb_s(dt: datetime) -> float`
Convert a datetime object to TDB (Barycentric Dynamical Time) seconds since J2000. Naive datetimes are treated as UTC; timezone-aware values are converted to UTC first. TDB conversion functions remain available, while TT is the primary internal time scale.

#### `posix_to_tdb_s(posix_s: float) -> float`
Convert a POSIX timestamp (seconds since the Unix epoch) to TDB seconds since J2000. This is retained alongside the other TDB conversion functions.

#### `tdb_s_to_datetime(tdb_s: float) -> datetime`
Convert TDB seconds since J2000 to a UTC datetime object. Retained for compatibility; TT is the primary ephemeris time scale.

### ISO 8601 Parsing and Formatting

#### `iso8601_to_datetime(epoch_str: str) -> datetime`
Parse an ISO 8601 epoch string into a UTC-aware `datetime`. Accepts `T` or space separators, up to six fractional-second digits, and an optional uppercase `Z`; numeric UTC offsets are not supported. Strings without a zone are interpreted as UTC.

#### `datetime_to_iso8601(dt: datetime, use_t_separator: bool = True, fractional_second_places: int = 3) -> str`
Convert a datetime object to a UTC ISO 8601 string. Naive datetimes are treated as UTC, aware datetimes are converted to UTC, and the output has no trailing `Z`. Fractional seconds are truncated or zero-padded to the requested precision; zero places omits the fractional part.

### CLI Duration/Step-Size Parsing

#### `parse_time_or_duration(value: str) -> datetime | timedelta`
Parse an ISO 8601 timestamp or a relative duration. Durations without an explicit unit default to minutes; signed and zero durations are allowed. If timestamp parsing fails, the value is parsed as a duration.

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
Return a compact duration using whole hours when possible, otherwise whole minutes when possible, otherwise seconds (for example, `24h`, `30m`, `45s`). This formatter does not use a days unit.

**Returns:** Compact duration string; fractional seconds may be emitted when needed.

#### `format_duration_human(duration: timedelta) -> str`
Format a timedelta into a human-readable string (e.g., `2h 30m`, `45s`, `3d 1h`). Supports negative durations with a leading `-`; fractional seconds are rendered to three significant digits.

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
Calculate relative position and velocity in the reference object's RTN (Radial-Transverse-Normal) frame. The velocity transformation includes the rotating-frame transport term. Supports single and batch state vectors.

**Parameters:**
- `state`: Target object state vector(s) [x, y, z, vx, vy, vz]
  - Shape (6,): Single state vector
  - Shape (N, 6): Batch of N state vectors
- `reference_state`: Reference object state vector for RTN frame definition
  - Shape (6,): Single reference state (used for all targets if batch)
  - Shape (N, 6): Batch of N reference states (one per target)
  - Defaults to [0, 0, 0, 0, 0, 0] if None

The reference position and angular momentum must define a valid orbital frame. Passing `None` uses a zero reference state, which produces a degenerate zero basis and is not useful for a physical RTN transformation.

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

An empty list returns `0.0`; if the sine and cosine sums nearly cancel, the first angle is returned wrapped to `[0, 2π)`.

#### `angle_difference_rad(target: float, reference: float) -> float`
Return signed wrapped angle difference target-reference in (-π, π]. A difference of exactly -π is represented as +π.

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
Load a SPICE kernel from the specified or cached kernel directory. The resolved directory is cached in an XDG-style file when possible, and loading the same joined kernel path more than once in a process is skipped.

**Parameters:**
- `kernel_file`: Name of the kernel file to load (e.g., "naif0012.tls")
- `kernel_path`: Optional path to kernel directory. If None, uses cached path from `get_spice_kernel_path()`

---

## ephem_toolkit.core.consts - Physical Constants

**Purpose**: Earth physical constants for orbital mechanics calculations.

### Constants

- `EARTH_GRAVITATIONAL_PARAMETER_M3_S2 = 3.986004418e14` - Earth gravitational parameter (m³/s²), WGS-84
- `EARTH_EQUATORIAL_RADIUS_M = 6378136.3` - Configured equatorial radius (m); this differs from the WGS-84 semi-major axis of 6378137 m.
- `EARTH_MEAN_RADIUS_M = 6371000.0` - Earth mean radius (m), approximately 6371 km
- `EARTH_J2 = 1.08262668e-3` - Earth J2 zonal harmonic coefficient (dimensionless), WGS-84
- `EARTH_J3 = -2.53265648e-6` - Earth J3 zonal harmonic coefficient (dimensionless), WGS-84
- `EARTH_J4 = -1.61962159e-6` - Earth J4 zonal harmonic coefficient (dimensionless), WGS-84
