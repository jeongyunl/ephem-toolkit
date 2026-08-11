# Common Library - Data Processing

This document covers OEM data slicing and interpolation utilities in the `common/` directory.

## Table of Contents

1. [tudatpy_utils.common.slice_oem - OEM Slicing Utilities](#tudatpy_utilscommonslice_oem---oem-slicing-utilities)
2. [tudatpy_utils.common.interpolator - Interpolation Package](#tudatpy_utilscommoninterpolator---interpolation-package)

---

## tudatpy_utils.common.slice_oem - OEM Slicing Utilities

**Purpose**: Common slice helpers for OEM state selection with time-based and index-based slicing.

### Key Dependencies
- `datetime`, `bisect`, `re`, `dataclasses`
- `tudatpy_utils.common.consts`
- `tudatpy_utils.common.time_utils`
- `tudatpy_utils.common.interpolator.lagrange`

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

#### `extract_sliced_states(oem: CcsdsOem, slice_spec: TimeSliceOptions | slice, verbose: bool = False, interpolation_degree: int = INTERPOLATION_DEGREE) -> CcsdsOem`
Extract sliced OEM states based on a time or index slice specification. Returns a new `CcsdsOem` with preserved metadata.

#### `extract_states_by_time(oem: CcsdsOem, options: TimeSliceOptions, verbose: bool = False, interpolation_degree: int = INTERPOLATION_DEGREE) -> CcsdsOem`
Extract states within a time window using `TimeSliceOptions`. Supports Lagrange interpolation when `step_size` is provided. Returns a new `CcsdsOem` with preserved metadata.

---

## tudatpy_utils.common.interpolator - Interpolation Package

**Purpose**: Provide interpolation capabilities for time-series data with ordered sample storage.

### tudatpy_utils.common.interpolator.interpolator - Base Interpolator

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

### tudatpy_utils.common.interpolator.lagrange - Lagrange Interpolator

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
