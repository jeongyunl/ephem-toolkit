# Core Library - Data Processing

This document covers OEM data slicing and interpolation utilities in the `core/` directory.

## Table of Contents

1. [ephem_toolkit.core.slice_oem - OEM Slicing Utilities](#ephem_toolkitcoreslice_oem---oem-slicing-utilities)
2. [ephem_toolkit.core.interpolator - Interpolation Package](#ephem_toolkitcoreinterpolator---interpolation-package)
3. [ephem_toolkit.core.cli - CLI Utilities](#ephem_toolkitcorecli---cli-utilities)

---

## ephem_toolkit.core.slice_oem - OEM Slicing Utilities

**Purpose**: Common slice helpers for OEM state selection with time-based and index-based slicing.

### Key Dependencies
- `datetime`, `bisect`, `re`, `dataclasses`
- `ephem_toolkit.core.consts`
- `ephem_toolkit.core.time_utils`
- `ephem_toolkit.core.interpolator.factory`
- `ephem_toolkit.core.interpolator.interpolation_spec`

### Data Structures

#### `class TimeSliceOptions` (dataclass)
Parsed options for a time-based OEM slice operation.

**Fields:**
- `start_time`: Start of time window (`datetime`, relative `timedelta`, or `None`; defaults to `None`)
- `stop_time`: End of time window (`datetime`, relative `timedelta`, or `None`; defaults to `None`)
- `step_size`: Resampling interval (`timedelta` or `None`; defaults to `None`)
- `interpolation_spec`: Interpolation specification (`InterpolationSpec` or `None`; defaults to `None`)

Time bounds are inclusive. Absolute timestamps are ISO-8601 datetimes; durations use `s`, `m`, `h`, or `d` units (for example, `5m` or `1h30m`; a missing unit means minutes here). A positive start duration is offset from the OEM start, while a negative start duration is offset from the OEM end. A positive stop duration is offset from the resolved start; a zero or negative stop duration is offset from the OEM end.

With no start or stop, the full OEM interval is selected; a start with no stop requests one time. An empty stop after a comma resolves to the OEM end. A missing start resolves to the OEM beginning.

### Functions

#### `parse_slice_args(slice_str: str) -> slice`
Parse a Python-style slice string into a slice object (e.g., "0:10", "::2", "5", "-5:").

#### `parse_time_slice_args(time_slice_str: str) -> TimeSliceOptions`
Parse an ISO-8601 time slice string using comma separators. Format: `start[,stop[,step]]`.

#### `extract_sliced_states(oem: CcsdsOem, slice_spec: TimeSliceOptions | slice, verbose: bool = False, clamp_to_oem_bounds: bool = True) -> CcsdsOem`
Extract sliced OEM states based on a time or index slice specification. Index slices follow Python's exclusive-stop rules; time bounds include both endpoints. `clamp_to_oem_bounds` defaults to `True`: it clamps starts earlier than the OEM start and stops later than the OEM stop; other invalid time ranges can still fail validation. Index bounds use Python slicing by default and are validated when clamping is disabled. Returns a new `CcsdsOem` with copied metadata and updated creation and time-bound fields.

#### `extract_states_by_time(oem: CcsdsOem, options: TimeSliceOptions, verbose: bool = False, clamp_to_oem_bounds: bool = True) -> CcsdsOem`
Extract states within an inclusive time window. Without interpolation, returns existing samples in the window; for a single requested time without a stop, it selects the first sample at or after that time. With an interpolation specification, missing start/stop samples are interpolated. When `step_size` is set, samples are generated from the resolved start at fixed intervals while the time is less than or equal to the stop, so the stop is included only if it falls on a step. `step_size` requires `interpolation_spec`. The result copies metadata and updates creation, start/stop, and usable-time fields.

---

## ephem_toolkit.core.interpolator - Interpolation Package

**Purpose**: Provide interpolation capabilities for time-series data with ordered sample storage. Samples are kept in an unbounded in-memory history; `add_data_point` requires strictly increasing independent values. `set_data` sorts dictionary input, while sequence input must already be ordered.

### ephem_toolkit.core.interpolator.interpolator - Base Interpolator

#### `class Interpolator`
Base interpolator supporting ordered sample storage and shared configuration.

**Public API:**
- `__init__(dimension: int = 1)`: Initialize with dependent-vector dimension
- `add_data_point(independent_value: float, dependent_data: np.ndarray)`: Store a new sample pair
- `set_data(data: dict[float, np.ndarray] | list[tuple[float, np.ndarray]] | list[float] | np.ndarray, dependent_data: list[np.ndarray] | None = None)`: Replace all stored samples; `dependent_data` pairs with independent values when supplied
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

Both flags default to `True` (`force_interpolation`) and `False` (`allow_extrapolation`). `force_interpolation` is currently only stored by the base class and is not consulted by the concrete implementations. Chebyshev and Lagrange enforce the extrapolation setting (with a small range tolerance); Hermite currently evaluates its polynomial outside the stored range regardless of this flag. Concrete interpolators generally return `None` when they lack enough samples or reject an out-of-range query.

### ephem_toolkit.core.interpolator.hermite - Hermite Interpolator

#### `class SlidingWindowHermiteInterpolator(Interpolator)`
Sliding-window Hermite polynomial interpolator with cached local windows and derivative support for improved accuracy.

**Public API:**
- `__init__(dimension: int = 1, degree: int = 5, is_cartesian_state: bool = False, boundary_mode: str = "centered", boundary_window_extension: int = 0)`: Initialize with dimension, polynomial degree, optional Cartesian-state mode, and window-boundary policy. Raises `ValueError` for an invalid boundary policy/extension or if Cartesian-state mode is enabled with a dimension other than 6.
- `add_derivative(independent_value: float, derivative_data: np.ndarray, derivative_order: int = 1) -> bool`: Add first-derivative data at an independent value already in the sample set; other derivative orders are rejected.
- `set_derivative_data(derivative_data: list[np.ndarray] | None = None, derivative_order: int = 1)`: Replace all stored derivatives.
- `clear_storage()`: Remove all stored samples, derivatives, and reset state.
- `interpolate(independent_value: float) -> np.ndarray | None`: Interpolate dependent values at the requested independent value.
- `interpolate_cartesian_state(independent_value: float) -> np.ndarray | None`: Interpolate a 6D Cartesian state (position + velocity).

**Public properties:**
- `required_points`: Base number of sample points for a degree-N polynomial (`N + 1`); derivative data contributes additional interpolation constraints.
- `is_cartesian_state`: Whether the interpolator is configured for Cartesian-state interpolation
- `derivatives`: Derivative data structure

**Constants:**
- `DEFAULT_HERMITE_DEGREE = 5`: Default polynomial degree
- `DERIVATIVE_UNAVAILABLE_SENTINEL = -9.99999e99`: Declared sentinel constant; current interpolation code does not use it to mark missing derivative data.

In Cartesian-state mode, the interpolator uses the three velocity components as derivatives of position and returns velocity from the derivative of the fitted position polynomial.

### ephem_toolkit.core.interpolator.chebyshev - Chebyshev Interpolator

#### `class ChebyshevInterpolator(Interpolator)`
Chebyshev polynomial interpolator for scalar or vector dependent data using a local window around each query.

**Public API:**
- `__init__(dimension: int = 1, degree: int = 5, boundary_mode: str = "centered", boundary_window_extension: int = 0)`: Initialize with dependent dimension, polynomial degree, and window-boundary policy
- `reset_state()`: Reset transient interpolation state while keeping stored samples
- `clear_storage()`: Clear stored sample data and reset the interpolation state
- `interpolate(independent_value: float) -> np.ndarray | None`: Evaluate the interpolant at a query value

**Public properties:**
- `degree`: Current interpolation polynomial degree
- `base_degree`: Base degree restored when the data set is reset or refilled
- `required_points`: Minimum samples required for a degree-N fit (`degree + 1`)

**Constants:**
- `DEFAULT_CHEBYSHEV_DEGREE = 5`: Default polynomial degree
- `RANGE_EXTRAPOLATION_TOLERANCE = 1.0e-12`: Tolerance for marginal out-of-range queries when extrapolation is disabled
- `BOUNDARY_DEGREE_BOOST = 2`: Declared module constant; boundary extension is controlled by `boundary_window_extension` and does not use this constant.

### ephem_toolkit.core.interpolator.lagrange - Lagrange Interpolator

#### `class LagrangeInterpolator(Interpolator)`
Lagrange polynomial interpolator that selects a local polynomial window around each query point.

**Public API:**
- `__init__(dimension: int = 1, degree: int = 7, boundary_mode: str = "compact", boundary_window_extension: int = 2)`: Initialize with dimension, polynomial degree, and window-boundary policy
- `add_data_point(independent_value: float, dependent_data: np.ndarray)`: Append a new sample
- `reset_state()`: Reset interpolator state while preserving stored samples
- `clear_storage()`: Clear stored sample data and reset state
- `interpolate(independent_value: float) -> np.ndarray | None`: Compute interpolated dependent vector

**Public properties:**
- `degree`: Current interpolation polynomial degree
- `required_points`: Minimum samples required (`degree + 1`)
- `boundary_mode`: Window policy (`centered`, `widen`, `edge`, or `compact`)
- `boundary_window_extension`: Additional support points used by boundary policies

**Constants:**
- `DEFAULT_LAGRANGE_DEGREE = 7`: Default polynomial degree
- `RANGE_EXTRAPOLATION_TOLERANCE = 1.0e-12`: Tolerance for marginal out-of-range queries when extrapolation is disabled
- `BOUNDARY_WINDOW_REDUCTION = 2`: Declared module constant; the active window size is controlled by `boundary_mode` and `boundary_window_extension`.

### ephem_toolkit.core.interpolator.interpolation_spec - Interpolation Specifications

#### `class InterpolationType` (Enum)
Interpolation method type.

**Values:**
- `HERMITE = "hermite"`: Hermite polynomial interpolation
- `LAGRANGE = "lagrange"`: Lagrange polynomial interpolation
- `CHEBYSHEV = "chebyshev"`: Chebyshev polynomial interpolation

#### `class InterpolationSpec` (dataclass)
Interpolation specification with type and optional degree.

**Fields:**
- `interp_type`: Type of interpolation (InterpolationType)
- `degree`: Polynomial degree; when omitted, `__post_init__()` fills in the method default (Hermite 5, Chebyshev 5, Lagrange 7)

**Constants:**
- `DEFAULT_HERMITE_DEGREE = 5`: Default polynomial degree for Hermite
- `DEFAULT_CHEBYSHEV_DEGREE = 5`: Default degree for Chebyshev interpolation
- `DEFAULT_LAGRANGE_DEGREE = 7`: Default polynomial degree for Lagrange

### ephem_toolkit.core.interpolator.factory - Interpolator Factory

#### `class InterpolatorFactory`
Factory for creating interpolator instances from specifications.

**Key Methods:**
- `create(spec: InterpolationSpec, dimension: int = 6, is_cartesian_state: bool = False, verbose: bool = False, context: str = "factory", data = None, dependent_data = None, boundary_mode: str = "centered", boundary_window_extension: int = 0) -> Interpolator`: Create an interpolator and optionally populate it with data; boundary policy arguments are passed to all concrete types.

**Supported types:**
- `InterpolationType.HERMITE` → `SlidingWindowHermiteInterpolator`
- `InterpolationType.LAGRANGE` → `LagrangeInterpolator`
- `InterpolationType.CHEBYSHEV` → `ChebyshevInterpolator`

---

## ephem_toolkit.core.cli - CLI Utilities

**Purpose**: Common CLI utilities for parsing command-line arguments.

### Constants
- `VALID_INTERPOLATION_TYPES = ["hermite", "hermite_sliding", "chebyshev", "lagrange"]`: Names listed by the CLI helper.

### Functions

#### `parse_interpolate_type(value: str, default_degree: int) -> InterpolationSpec`
Parse interpolation type argument from CLI. The parser accepts a canonical enum name, optionally followed by a positive integer degree. A bare type uses the caller-supplied `default_degree`.

**Parameters:**
- `value`: Interpolation type as `type` or `type,degree`
- `default_degree`: Default degree to use if not specified

**Returns:**
- `InterpolationSpec`: Interpolation specification with type and degree

**Raises:**
- `argparse.ArgumentTypeError`: If the format is invalid or the interpolation type is unsupported

Although `VALID_INTERPOLATION_TYPES` lists `hermite_sliding`, `InterpolationType` has no such enum value, so `parse_interpolate_type("hermite_sliding", ...)` currently fails during enum construction. Use `hermite` for the sliding-window Hermite implementation.
