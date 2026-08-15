# Core Library - Coordinate Transformations

This document covers reference frame conversions and coordinate system transformations in the `core/` directory.

## Table of Contents

1. [ephem_toolkit.core.frame_utils - Reference Frame Conversions](#ephem_toolkitcoreframe_utils---reference-frame-conversions)
2. [ephem_toolkit.core.wgs - WGS-84 Coordinate Conversions](#ephem_toolkitcorewgs---wgs-84-coordinate-conversions)
3. [ephem_toolkit.core.aer - AER Coordinate Conversions](#ephem_toolkitcoreaer---aer-coordinate-conversions)

---

## ephem_toolkit.core.frame_utils - Reference Frame Conversions

**Purpose**: Convert Cartesian states between TEME, J2000, SPICE, inertial, and Earth-fixed reference frames.

### Key Dependencies
- `numpy`
- `tudatpy.astro.element_conversion`
- `tudatpy.interface.spice`
- `ephem_toolkit.core.spice_utils`

### TEME/J2000 Conversion

#### `teme_to_j2000(epoch_tdb_s: float, teme_state: np.ndarray) -> np.ndarray`
Convert a six-component Cartesian state from TEME to J2000 coordinates at a TDB epoch.

#### `j2000_to_teme(epoch_tdb_s: float, j2000_state: np.ndarray) -> np.ndarray`
Convert a six-component Cartesian state from J2000 to TEME coordinates at a TDB epoch.

### SPICE Frame Conversion

#### `spice_convert_frame(base_frame: str, target_frame: str, epoch_tdb_s: float, input_state_m: np.ndarray) -> np.ndarray`
Convert a state between SPICE frames using position and velocity rotation terms. Input and output states use metres and metres per second.

### TudatPy Rotation Models

#### `tudat_spice_rotation_model() -> object`
Return a cached TudatPy Earth rotation model based on SPICE orientation data, converting between J2000 and ITRF93.

#### `tudat_iau2006_rotation_model() -> object`
Return a cached TudatPy Earth rotation model based on the IAU 2006 convention, converting between GCRS and ITRS.

### Inertial/Body-Fixed Conversion

#### `tudat_convert_inertial_to_body_fixed(rotation_model: object, input_epoch_et_s: float, input_inertial_state_m: np.ndarray) -> np.ndarray`
Convert an inertial state to a body-fixed state using a TudatPy rotation model. Position and velocity use metres and metres per second.

#### `tudat_convert_body_fixed_to_inertial(rotation_model: object, input_epoch_et_s: float, input_body_fixed_state_m: np.ndarray) -> np.ndarray`
Convert a body-fixed state to an inertial state using a TudatPy rotation model. Position and velocity use metres and metres per second.

---

## ephem_toolkit.core.wgs - WGS-84 Coordinate Conversions

**Purpose**: Coordinate conversion utilities for LLA (Latitude-Longitude-Altitude) and ENU (East-North-Up) frames using the WGS-84 ellipsoid model.

### Key Dependencies
- `numpy`
- `math`
- `ephem_toolkit.core.consts`

### Constants

- `EARTH_FLATTENING = 1.0 / 298.257223563` - Earth flattening factor (dimensionless), WGS-84
- `EARTH_ECCENTRICITY_SQUARED = 2.0 * EARTH_FLATTENING - EARTH_FLATTENING**2` - Earth eccentricity squared (dimensionless), WGS-84

### ECEF ↔ ENU Conversion

#### `ecef_to_enu(ecef_position: np.ndarray, reference_lla: np.ndarray) -> np.ndarray`
Convert ECEF position to ENU coordinates relative to a reference point.

**Parameters:**
- `ecef_position`: Position vector in ECEF coordinates [x, y, z] in meters
  - Shape (3,): Single position vector
  - Shape (N, 3): Batch of N position vectors
- `reference_lla`: Reference point in geodetic coordinates [lat, lon, alt]
  - lat: Latitude in radians
  - lon: Longitude in radians
  - alt: Altitude above WGS-84 ellipsoid in meters

**Returns:** Position vector(s) in ENU coordinates [east, north, up] in meters

#### `ecef_to_enu_velocity(ecef_velocity: np.ndarray, reference_lla: np.ndarray) -> np.ndarray`
Convert ECEF velocity to ENU coordinates relative to a reference point.

**Parameters:**
- `ecef_velocity`: Velocity vector in ECEF coordinates [vx, vy, vz] in m/s
  - Shape (3,): Single velocity vector
  - Shape (N, 3): Batch of N velocity vectors
- `reference_lla`: Reference point in geodetic coordinates [lat, lon, alt]

**Returns:** Velocity vector(s) in ENU coordinates [v_east, v_north, v_up] in m/s

#### `ecef_to_enu_state(ecef_state: np.ndarray, reference_lla: np.ndarray) -> np.ndarray`
Convert ECEF state vector to ENU coordinates relative to a reference point.

**Parameters:**
- `ecef_state`: State vector in ECEF coordinates [x, y, z, vx, vy, vz]
  - Shape (6,): Single state vector
  - Shape (N, 6): Batch of N state vectors
- `reference_lla`: Reference point in geodetic coordinates [lat, lon, alt]

**Returns:** State vector(s) in ENU coordinates [e, n, u, ve, vn, vu]

#### `enu_to_ecef(enu_position: np.ndarray, reference_lla: np.ndarray) -> np.ndarray`
Convert ENU position to ECEF coordinates.

**Parameters:**
- `enu_position`: Position vector in ENU coordinates [east, north, up] in meters
  - Shape (3,): Single position vector
  - Shape (N, 3): Batch of N position vectors
- `reference_lla`: Reference point in geodetic coordinates [lat, lon, alt]

**Returns:** Position vector(s) in ECEF coordinates [x, y, z] in meters

#### `enu_to_ecef_velocity(enu_velocity: np.ndarray, reference_lla: np.ndarray) -> np.ndarray`
Convert ENU velocity to ECEF coordinates.

**Parameters:**
- `enu_velocity`: Velocity vector in ENU coordinates [v_east, v_north, v_up] in m/s
  - Shape (3,): Single velocity vector
  - Shape (N, 3): Batch of N velocity vectors
- `reference_lla`: Reference point in geodetic coordinates [lat, lon, alt]

**Returns:** Velocity vector(s) in ECEF coordinates [vx, vy, vz] in m/s

#### `enu_to_ecef_state(enu_state: np.ndarray, reference_lla: np.ndarray) -> np.ndarray`
Convert ENU state vector to ECEF coordinates.

**Parameters:**
- `enu_state`: State vector in ENU coordinates [e, n, u, ve, vn, vu]
  - Shape (6,): Single state vector
  - Shape (N, 6): Batch of N state vectors
- `reference_lla`: Reference point in geodetic coordinates [lat, lon, alt]

**Returns:** State vector(s) in ECEF coordinates [x, y, z, vx, vy, vz]

### Geodetic Coordinate Conversions

#### `lla_to_ecef(lla: np.ndarray) -> np.ndarray`
Convert geodetic coordinates (LLA) to ECEF coordinates.

**Parameters:**
- `lla`: Geodetic coordinates [lat, lon, alt]
  - lat: Latitude in radians
  - lon: Longitude in radians
  - alt: Altitude above WGS-84 ellipsoid in meters
  - Shape (3,): Single coordinate
  - Shape (N, 3): Batch of N coordinates

**Returns:** Position vector(s) in ECEF coordinates [x, y, z] in meters

#### `ecef_to_lla(ecef: np.ndarray, tolerance: float = 1e-12, max_iterations: int = 10) -> np.ndarray`
Convert ECEF coordinates to geodetic coordinates (LLA) using an iterative algorithm.

**Parameters:**
- `ecef`: Position vector in ECEF coordinates [x, y, z] in meters
  - Shape (3,): Single position vector
  - Shape (N, 3): Batch of N position vectors
- `tolerance`: Convergence tolerance for latitude iteration in radians (default: 1e-12)
- `max_iterations`: Maximum number of iterations for latitude convergence (default: 10)

**Returns:** Geodetic coordinates [lat, lon, alt]

---

## ephem_toolkit.core.aer - AER Coordinate Conversions

**Purpose**: Coordinate conversion utilities for AER (Azimuth-Elevation-Range) frames. The AER coordinate system is a spherical coordinate system centered at a reference point on the Earth's surface.

### Key Dependencies
- `numpy`
- `ephem_toolkit.core.wgs`

### AER Coordinate System

- **Azimuth**: Angle measured clockwise from North (0° = North, 90° = East)
- **Elevation**: Angle above the local horizontal plane (0° = horizon, 90° = zenith)
- **Range**: Distance from the reference point to the target

### ECEF ↔ AER Conversion

#### `ecef_to_aer(ecef_position: np.ndarray, reference_lla: np.ndarray) -> np.ndarray`
Convert ECEF position to AER coordinates relative to a reference point.

**Parameters:**
- `ecef_position`: Position vector in ECEF coordinates [x, y, z] in meters
  - Shape (3,): Single position vector
  - Shape (N, 3): Batch of N position vectors
- `reference_lla`: Reference point in geodetic coordinates [lat, lon, alt]
  - lat: Latitude in radians
  - lon: Longitude in radians
  - alt: Altitude above WGS-84 ellipsoid in meters

**Returns:** Position vector(s) in AER coordinates [azimuth, elevation, range]
- azimuth: Azimuth angle in radians (0 = North, π/2 = East)
- elevation: Elevation angle in radians (0 = horizon, π/2 = zenith)
- range: Distance in meters

#### `ecef_to_aer_velocity(ecef_position: np.ndarray, ecef_velocity: np.ndarray, reference_lla: np.ndarray) -> np.ndarray`
Convert ECEF velocity to AER rate coordinates relative to a reference point.

**Parameters:**
- `ecef_position`: Position vector in ECEF coordinates [x, y, z] in meters
- `ecef_velocity`: Velocity vector in ECEF coordinates [vx, vy, vz] in m/s
- `reference_lla`: Reference point in geodetic coordinates [lat, lon, alt]

**Returns:** Velocity vector(s) in AER rate coordinates [az_rate, el_rate, range_rate]
- az_rate: Azimuth rate in rad/s
- el_rate: Elevation rate in rad/s
- range_rate: Range rate in m/s

#### `ecef_to_aer_state(ecef_state: np.ndarray, reference_lla: np.ndarray) -> np.ndarray`
Convert ECEF state vector to AER coordinates relative to a reference point.

**Parameters:**
- `ecef_state`: State vector in ECEF coordinates [x, y, z, vx, vy, vz]
  - Shape (6,): Single state vector
  - Shape (N, 6): Batch of N state vectors
- `reference_lla`: Reference point in geodetic coordinates [lat, lon, alt]

**Returns:** State vector(s) in AER coordinates [az, el, r, az_rate, el_rate, r_rate]

#### `aer_to_ecef(aer_position: np.ndarray, reference_lla: np.ndarray) -> np.ndarray`
Convert AER position to ECEF coordinates.

**Parameters:**
- `aer_position`: Position vector in AER coordinates [azimuth, elevation, range]
  - azimuth: Azimuth angle in radians (0 = North, π/2 = East)
  - elevation: Elevation angle in radians (0 = horizon, π/2 = zenith)
  - range: Distance in meters
  - Shape (3,): Single position vector
  - Shape (N, 3): Batch of N position vectors
- `reference_lla`: Reference point in geodetic coordinates [lat, lon, alt]

**Returns:** Position vector(s) in ECEF coordinates [x, y, z] in meters

#### `aer_to_ecef_velocity(aer_position: np.ndarray, aer_velocity: np.ndarray, reference_lla: np.ndarray) -> np.ndarray`
Convert AER rate coordinates to ECEF velocity.

**Parameters:**
- `aer_position`: Position vector in AER coordinates [azimuth, elevation, range]
- `aer_velocity`: Velocity vector in AER rate coordinates [az_rate, el_rate, range_rate]
- `reference_lla`: Reference point in geodetic coordinates [lat, lon, alt]

**Returns:** Velocity vector(s) in ECEF coordinates [vx, vy, vz] in m/s

#### `aer_to_ecef_state(aer_state: np.ndarray, reference_lla: np.ndarray) -> np.ndarray`
Convert AER state vector to ECEF coordinates.

**Parameters:**
- `aer_state`: State vector in AER coordinates [az, el, r, az_rate, el_rate, r_rate]
  - Shape (6,): Single state vector
  - Shape (N, 6): Batch of N state vectors
- `reference_lla`: Reference point in geodetic coordinates [lat, lon, alt]

**Returns:** State vector(s) in ECEF coordinates [x, y, z, vx, vy, vz]

### ENU ↔ AER Conversion

#### `enu_to_aer(enu_position: np.ndarray) -> np.ndarray`
Convert ENU position to AER coordinates.

**Parameters:**
- `enu_position`: Position vector in ENU coordinates [east, north, up] in meters
  - Shape (3,): Single position vector
  - Shape (N, 3): Batch of N position vectors

**Returns:** Position vector(s) in AER coordinates [azimuth, elevation, range]

#### `enu_to_aer_velocity(enu_position: np.ndarray, enu_velocity: np.ndarray) -> np.ndarray`
Convert ENU velocity to AER rate coordinates.

**Parameters:**
- `enu_position`: Position vector in ENU coordinates [east, north, up] in meters
- `enu_velocity`: Velocity vector in ENU coordinates [v_east, v_north, v_up] in m/s

**Returns:** Velocity vector(s) in AER rate coordinates [az_rate, el_rate, range_rate]

#### `aer_to_enu(aer_position: np.ndarray) -> np.ndarray`
Convert AER position to ENU coordinates.

**Parameters:**
- `aer_position`: Position vector in AER coordinates [azimuth, elevation, range]
  - Shape (3,): Single position vector
  - Shape (N, 3): Batch of N position vectors

**Returns:** Position vector(s) in ENU coordinates [east, north, up] in meters

#### `aer_to_enu_velocity(aer_position: np.ndarray, aer_velocity: np.ndarray) -> np.ndarray`
Convert AER rate coordinates to ENU velocity.

**Parameters:**
- `aer_position`: Position vector in AER coordinates [azimuth, elevation, range]
- `aer_velocity`: Velocity vector in AER rate coordinates [az_rate, el_rate, range_rate]

**Returns:** Velocity vector(s) in ENU coordinates [v_east, v_north, v_up] in m/s
