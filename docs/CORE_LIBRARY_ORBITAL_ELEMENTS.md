# Core Library - Orbital Elements

This document covers Keplerian orbital element conversions and mean element calculations in the `core/` directory.

## Table of Contents

1. [tudatpy_utils.core.kepler - Keplerian Orbital Elements](#tudatpy_utilscorekepler---keplerian-orbital-elements)
2. [tudatpy_utils.core.mean_kepler - Mean Keplerian Elements](#tudatpy_utilscoremean_kepler---mean-keplerian-elements)

---

## tudatpy_utils.core.kepler - Keplerian Orbital Elements

**Purpose**: Convert between Cartesian state vectors and osculating Keplerian elements using only NumPy.

### Key Dependencies
- `numpy`
- `tudatpy_utils.core.consts`

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

## tudatpy_utils.core.mean_kepler - Mean Keplerian Elements

**Purpose**: Convert between osculating and mean (Brouwer) Keplerian elements with J2 perturbations.

### Key Dependencies
- `numpy`
- `tudatpy_utils.core.kepler`
- `tudatpy_utils.core.consts`

### Mean to Osculating Conversion

#### `compute_brouwer_short_period_corrections(mean_keplerian_elements: np.ndarray, R_e_m: float = EARTH_EQUATORIAL_RADIUS_M, J2: float = EARTH_J2) -> np.ndarray`
Compute Brouwer first-order J2 short-period corrections to convert mean Keplerian elements (as used in TLE/SGP4) to osculating elements.

**Parameters:**
- `mean_keplerian_elements`: Shape (6,) or (N, 6) - [a, e, i, omega, RAAN, M]
- `R_e_m`: Earth equatorial radius (m) (default: WGS-84)
- `J2`: J2 zonal harmonic coefficient (default: WGS-84)

**Returns:** Osculating Keplerian elements [a, e, i, omega, RAAN, theta]

#### `mean_to_osculating_keplerian(mean_keplerian_elements: np.ndarray, R_e_m: float = EARTH_EQUATORIAL_RADIUS_M, J2: float = EARTH_J2) -> np.ndarray`
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
