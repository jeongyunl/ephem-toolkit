# Core Library - Data Processing

This document covers OEM data slicing and interpolation utilities in the `core/` directory.

## Table of Contents

1. [tudatpy_utils.core.slice_oem - OEM Slicing Utilities](#tudatpy_utilscoreslice_oem---oem-slicing-utilities)
2. [tudatpy_utils.core.interpolator - Interpolation Package](#tudatpy_utilscoreinterpolator---interpolation-package)
3. [tudatpy_utils.core.cli - CLI Utilities](#tudatpy_utilscorecli---cli-utilities)

---

## tudatpy_utils.core.slice_oem - OEM Slicing Utilities

**Purpose**: Common slice helpers for OEM state selection with time-based and index-based slicing.

### Key Dependencies
- `datetime`, `bisect`, `re`, `dataclasses`
- `tudatpy_utils.core.consts`
- `tudatpy_utils.core.time_utils`
- `tudatpy_utils.core.interpolator.factory`
- `tudatpy_utils.core.interpolator.interpolation_spec`

### Data Structures

#### `class TimeSliceOptions` (dataclass)
Parsed options for a time-based OEM slice operation.

**Fields:**
- `start_time`: Start of time window (datetime or timedelta offset)
- `stop_time`: End of time window (datetime or timedelta offset)
- `step_size`: Resampling interval (timedelta)
- `interpolation_spec`: Interpolation specification (InterpolationSpec or None)

### Functions

#### `parse_slice_args(slice_str: str) -> slice`
Parse a Python-style slice string into a slice object (e.g., "0:10", "::2", "5", "-5:").

#### `parse_time_slice_args(time_slice_str: str) -> TimeSliceOptions`
Parse an ISO-8601 time slice string using comma separators. Format: `start[,stop[,step]]`.

#### `extract_sliced_states(oem: CcsdsOem, slice_spec: TimeSliceOptions | slice, verbose: bool = False) -> CcsdsOem`
Extract sliced OEM states based on a time or index slice specification. Returns a new `CcsdsOem` with preserved metadata.

#### `extract_states_by_time(oem: CcsdsOem, options: TimeSliceOptions, verbose: bool = False) -> CcsdsOem`
Extract states within a time window using `TimeSliceOptions`. Supports interpolation when `interpolation_spec` is provided. Returns a new `CcsdsOem` with preserved metadata.

---

## tudatpy_utils.core.interpolator - Interpolation Package

**Purpose**: Provide interpolation capabilities for time-series data with ordered sample storage.

### tudatpy_utils.core.interpolator.interpolator - Base Interpolator

#### `class Interpolator`
Base interpolator supporting fixed-size ordered sample storage.

**Public API:**
- `__init__(dimension: int = 1)`: Initialize with dependent-vector dimension
- `add_data_point(independent_value: float, dependent_data: np.ndarray)`: Store a new sample pair
- `set_data(data: dict | list, dependent_data: list | None = None)`: Replace all stored samples
- `reset_state()`: Reset sequential state while keeping buffered samples
- `clear_storage()`: Remove all stored samples and reset internal state
- `interpolate(independent_value: float) -> np.ndarray | None`: Compute interpolated dependent data

**Public properties:**
- `force_interpolation`: Whether to force interpolation even with poor conditions
- `allow_extrapolation`: Whether to allow queries outside the data range
- `independent_values`: Ordered independent variable values
- `dependent_values`: Corresponding dependent vectors
- `dependent_dimension`: Number of components in each dependent vector
- `required_points`: Minimum number of samples required

### tudatpy_utils.core.interpolator.hermite - Hermite Interpolator

#### `class SlidingWindowHermiteInterpolator(Interpolator)`
Sliding-window Hermite polynomial interpolator with cached local windows and derivative support for improved accuracy.

**Public API:**
- `__init__(dimension: int = 1, degree: int = 5, is_cartesian_state: bool = False)`: Initialize with dimension, polynomial degree, and optional Cartesian state mode. Raises ValueError if `is_cartesian_state` is True but the dimension is not 6.
- `add_derivative(independent_value: float, derivative_data: np.ndarray, derivative_order: int = 1) -> bool`: Add derivative data for a specific independent value.
- `set_derivative_data(derivative_data: list[np.ndarray] | None = None, derivative_order: int = 1)`: Replace all stored derivatives.
- `clear_storage()`: Remove all stored samples, derivatives, and reset state.
- `interpolate(independent_value: float) -> np.ndarray | None`: Interpolate dependent values at the requested independent value.
- `interpolate_cartesian_state(independent_value: float) -> np.ndarray | None`: Interpolate a 6D Cartesian state (position + velocity).

**Public properties:**
- `required_points`: Required points for a degree-N polynomial (`N + 1`)
- `is_cartesian_state`: Whether the interpolator is configured for Cartesian-state interpolation
- `derivatives`: Derivative data structure

**Constants:**
- `DEFAULT_HERMITE_DEGREE = 5`: Default polynomial degree
- `DERIVATIVE_UNAVAILABLE_SENTINEL = -9.99999e99`: Sentinel value for unavailable derivatives

### tudatpy_utils.core.interpolator.chebyshev - Chebyshev Interpolator

#### `class ChebyshevInterpolator(Interpolator)`
Chebyshev polynomial interpolator for scalar or vector dependent data using a local window around each query.

**Public API:**
- `__init__(dimension: int = 1, degree: int = 5)`: Initialize with dependent dimension and polynomial degree
- `reset_state()`: Reset transient interpolation state while keeping stored samples
- `clear_storage()`: Clear stored sample data and reset the interpolation state
- `interpolate(independent_value: float) -> np.ndarray | None`: Evaluate the interpolant at a query value

**Public properties:**
- `degree`: Current interpolation polynomial degree
- `base_degree`: Base degree restored when the data set is reset or refilled
- `required_points`: Minimum samples required for a degree-N fit (`degree + 1`)

**Constants:**
- `DEFAULT_CHEBYSHEV_DEGREE = 5`: Default polynomial degree
- `RANGE_EXTRAPOLATION_TOLERANCE = 1.0e-12`: Tolerance when accepting marginal out-of-range values
- `BOUNDARY_DEGREE_BOOST = 2`: Extra points used to widen boundary windows for stability

### tudatpy_utils.core.interpolator.lagrange - Lagrange Interpolator

#### `class LagrangeInterpolator(Interpolator)`
Lagrange polynomial interpolator that selects a local polynomial window around each query point.

**Public API:**
- `__init__(dimension: int = 1, degree: int = 7)`: Initialize with dimension and polynomial degree
- `add_data_point(independent_value: float, dependent_data: np.ndarray)`: Append a new sample
- `reset_state()`: Reset interpolator state while preserving stored samples
- `clear_storage()`: Clear stored sample data and reset state
- `interpolate(independent_value: float) -> np.ndarray | None`: Compute interpolated dependent vector

**Public properties:**
- `degree`: Current interpolation polynomial degree
- `base_degree`: Base degree to restore when the buffer returns to full capacity
- `required_points`: Minimum samples required (`degree + 1`)

**Constants:**
- `DEFAULT_LAGRANGE_DEGREE = 7`: Default polynomial degree
- `RANGE_OVERSHOOT_TOLERANCE = 1e-8`: Tolerance for queries marginally outside the data range
- `MIN_DIFFERENCE_FOR_START = 1.0e30`: Sentinel value for window bias search

### tudatpy_utils.core.interpolator.interpolation_spec - Interpolation Specifications

#### `class InterpolationType` (Enum)
Interpolation method type.

**Values:**
- `HERMITE = "hermite"`: Hermite polynomial interpolation
- `CHEBYSHEV = "chebyshev"`: Chebyshev polynomial interpolation
- `LAGRANGE = "lagrange"`: Lagrange polynomial interpolation

#### `class InterpolationSpec` (dataclass)
Interpolation specification with type and optional degree.

**Fields:**
- `interp_type`: Type of interpolation (InterpolationType)
- `degree`: Polynomial degree; defaults are set in `__post_init__()`

**Constants:**
- `DEFAULT_HERMITE_DEGREE = 5`: Default polynomial degree for Hermite
- `DEFAULT_CHEBYSHEV_DEGREE = 5`: Default degree for Chebyshev interpolation
- `DEFAULT_LAGRANGE_DEGREE = 7`: Default polynomial degree for Lagrange

### tudatpy_utils.core.interpolator.factory - Interpolator Factory

#### `class InterpolatorFactory`
Factory for creating interpolator instances from specifications.

**Key Methods:**
- `create(spec: InterpolationSpec, dimension: int = 6, is_cartesian_state: bool = False, verbose: bool = False, context: str = "factory", data = None, dependent_data = None) -> Interpolator`: Create an interpolator from a specification

**Supported types:**
- `InterpolationType.HERMITE` → `SlidingWindowHermiteInterpolator`
- `InterpolationType.CHEBYSHEV` → `ChebyshevInterpolator`
- `InterpolationType.LAGRANGE` → `LagrangeInterpolator`

---

## tudatpy_utils.core.cli - CLI Utilities

**Purpose**: Common CLI utilities for parsing command-line arguments.

### Constants
- `VALID_INTERPOLATION_TYPES = ["hermite", "chebyshev", "lagrange"]`: Valid interpolation type names for CLI arguments

### Functions

#### `parse_interpolate_type(value: str, default_degree: int) -> InterpolationSpec`
Parse interpolation type argument from CLI.

**Parameters:**
- `value`: Interpolation type as "interpolator" or "interpolator,degree"
- `default_degree`: Default degree to use if not specified

**Returns:**
- `InterpolationSpec`: Interpolation specification with type and degree

**Raises:**
- `argparse.ArgumentTypeError`: If the format is invalid or the interpolation type is unsupported
