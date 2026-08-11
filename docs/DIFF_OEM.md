# OEM Comparison Utility

The `diff-oem` utility compares corresponding states from two CCSDS OEM (Orbit Ephemeris Message) files and reports differences in time, position, and velocity.

## Overview

This utility provides comparison capabilities for OEM files:

- **Direct comparison**: Compare states at matching epochs
- **Interpolated comparison**: Compare states with interpolation for non-matching epochs
- **Time window filtering**: Limit comparison to specific time ranges
- **Transformation stages**: Apply rotation and time-shift corrections before comparison
- **RTN frame analysis**: View differences in the reference Radial-Tangential-Normal frame
- **Statistical analysis**: Compute mean, standard deviation, min, and max for all metrics

The script is built on the `diff_oem` library module, which provides reusable comparison functions for programmatic use.

After Poetry installation, use `diff-oem` as the canonical command. The existing `python3 bin/diff_oem.py ...` examples remain supported during the transition.

## Synopsis

```bash
diff-oem <reference_oem.oem> <comparison_oem.oem> [OPTIONS]
diff-oem - <comparison_oem.oem> [OPTIONS]
diff-oem <reference_oem.oem> - [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `<reference_oem.oem>` | Path to reference OEM file (use `-` to read from stdin) |
| `<comparison_oem.oem>` | Path to comparison OEM file (use `-` to read from stdin) |
| `-v`, `--verbose` | Print detailed component-wise differences (dX, dY, dZ, dVX, dVY, dVZ) |
| `--debug` | Print time-range determination details to stderr |
| `--interpolate-ref` | Interpolate reference OEM at each comparison state timestamp |
| `--interpolate-data` | Interpolate comparison OEM at each reference state timestamp (default) |
| `--interpolate` | Interpolate both reference and comparison OEM data |
| `--rtn` | Include comparison state coordinates in the reference RTN frame |
| `--rot` | Fit and apply a fixed 3D rotation before comparison |
| `--rot-xy` | Fit and apply a fixed rotation around X and Y axes only |
| `--rot-z` | Fit and apply a fixed rotation around Z axis only |
| `--time-shift` | Fit and apply a constant time shift to comparison epochs |
| `--rot-fit-span <duration>` | Duration for rotation fitting (default: 3600s) |
| `--start <iso8601\|duration>` | Start epoch for comparison window |
| `--stop <iso8601\|duration>` | Stop epoch for comparison window |
| `-h`, `--help` | Show help message and exit |

**Note**: Only one of `<reference_oem.oem>` or `<comparison_oem.oem>` can be `-` (stdin).

## Basic Usage

### Direct Comparison

Compare two OEM files at their native epochs:

```bash
diff-oem reference.oem comparison.oem
```

This compares states at matching timestamps. If the files have different timestamps, only overlapping epochs are compared.

### Interpolated Comparison

By default, the comparison OEM is interpolated at reference timestamps:

```bash
diff-oem reference.oem comparison.oem --interpolate-data
```

To interpolate the reference at comparison timestamps instead:

```bash
diff-oem reference.oem comparison.oem --interpolate-ref
```

To interpolate both (compare at all unique timestamps):

```bash
diff-oem reference.oem comparison.oem --interpolate
```

### Verbose Output

Include component-wise differences:

```bash
diff-oem reference.oem comparison.oem --verbose
```

This adds columns for dX, dY, dZ (position differences) and dVX, dVY, dVZ (velocity differences) in the reference frame.

## Time Window Filtering

Limit the comparison to a specific time range using `--start` and `--stop` options.

### Time Specifications

**Absolute times** use ISO 8601 format:
- `2024-01-01T00:00:00`
- `2024-01-01T12:30:45.123`

**Relative durations** use compact notation:
- `10s` — 10 seconds
- `5m` — 5 minutes
- `2h` — 2 hours
- `1d` — 1 day
- `1h30m` — 1 hour 30 minutes

**Duration interpretation**:
- For `--start`: offset from the first reference epoch
- For `--stop`: offset from the resolved start time

### Examples

**Compare first hour only:**
```bash
diff-oem reference.oem comparison.oem --start 0 --stop 1h
```

**Compare specific time window:**
```bash
diff-oem reference.oem comparison.oem \
  --start 2024-01-01T00:00:00 \
  --stop 2024-01-01T12:00:00
```

**Compare from 30 minutes to 2 hours after start:**
```bash
diff-oem reference.oem comparison.oem --start 30m --stop 2h
```

## Interpolation

The script uses **8th-degree Lagrange polynomial interpolation** to compute states at non-matching epochs.

### Interpolation Modes

**Default behavior** (`--interpolate-data`):
- Comparison states are interpolated at reference timestamps
- Useful when the reference has the desired sampling

**Reference interpolation** (`--interpolate-ref`):
- Reference states are interpolated at comparison timestamps
- Useful when the comparison has the desired sampling

**Bidirectional interpolation** (`--interpolate`):
- Both files are interpolated at all unique timestamps
- Provides the most comprehensive comparison

### Example

```bash
# Compare with bidirectional interpolation
diff-oem reference.oem comparison.oem --interpolate
```

## RTN Frame Analysis

The `--rtn` option transforms comparison state differences into the reference Radial-Tangential-Normal (RTN) coordinate frame.

### RTN Frame Definition

- **Radial (R)**: Along the position vector from the central body
- **Tangential (T)**: Along the velocity vector (in the orbital plane)
- **Normal (N)**: Perpendicular to the orbital plane (R × T)

### Usage

```bash
diff-oem reference.oem comparison.oem --rtn
```

Output includes additional columns:
- `RTN r (km)`, `RTN t (km)`, `RTN n (km)` — position differences
- `RTN vr (km/s)`, `RTN vt (km/s)`, `RTN vn (km/s)` — velocity differences

### Example Output

```
index  reference              position    velocity    RTN r    RTN t    RTN n    RTN vr      RTN vt      RTN vn
       epoch                  difference  difference  (km)     (km)     (km)     (km/s)      (km/s)      (km/s)
                              (km)        (km/s)
    1  2024-01-01T00:00:00        0.125      0.000012  +0.100  +0.050  +0.025   +0.000010  +0.000005  -0.000003
```

## Transformation Stages

Transformation stages fit and apply corrections to the comparison OEM before computing differences. This is useful for:

- Aligning coordinate frames with small rotational offsets
- Correcting systematic time biases
- Analyzing residual errors after known transformations

### Available Transformations

**Full 3D rotation** (`--rot`):
- Fits a fixed rotation matrix using SVD
- Applies to both position and velocity
- Useful for frame alignment

**X/Y rotation** (`--rot-xy`):
- Fits rotation around X and Y axes only
- Preserves Z-axis alignment
- Useful for correcting pitch and roll

**Z rotation** (`--rot-z`):
- Fits rotation around Z axis only
- Preserves X/Y plane alignment
- Useful for correcting yaw or longitude offset

**Time shift** (`--time-shift`):
- Fits a constant time bias
- Shifts comparison epochs before comparison
- Useful for correcting clock offsets

### Transformation Fitting

Transformations are fitted using the overlapping time range between the two OEM files. By default, rotation fitting uses the first hour of overlap (controlled by `--rot-fit-span`).

### Transformation Order

Multiple transformations can be applied in sequence. The order is determined by the order of options on the command line:

```bash
# First apply rotation, then time shift
diff-oem reference.oem comparison.oem --rot --time-shift

# First apply time shift, then rotation
diff-oem reference.oem comparison.oem --time-shift --rot
```

### Examples

**Apply 3D rotation correction:**
```bash
diff-oem reference.oem comparison.oem --rot
```

**Apply Z-axis rotation only:**
```bash
diff-oem reference.oem comparison.oem --rot-z
```

**Apply time shift correction:**
```bash
diff-oem reference.oem comparison.oem --time-shift
```

**Apply rotation with custom fitting span:**
```bash
diff-oem reference.oem comparison.oem --rot --rot-fit-span 1800
```

**Apply multiple transformations in sequence:**
```bash
diff-oem reference.oem comparison.oem --rot --time-shift
```

### Transformation Output

When transformations are applied, the script outputs:

1. **Normal comparison**: Differences before any transformations
2. **Transformed comparison**: Differences after each transformation stage
3. **Fit description**: Details of the fitted transformation parameters

Example output with `--rot`:

```
Normal comparison
index  reference              position    velocity
       epoch                  difference  difference
                              (km)        (km/s)
    1  2024-01-01T00:00:00        1.234      0.001234
    2  2024-01-01T00:01:00        1.235      0.001235
...

Comparison after stage 1: comparison-to-reference rotation

Applied comparison-to-reference rotation matrix to comparison position and velocity states:
[[ 0.999998 -0.001745  0.000873]
 [ 0.001745  0.999998 -0.000436]
 [-0.000873  0.000436  0.999999]]

Angular separation: 0.123456 deg

Euler angles (ZYX convention, intrinsic rotations):
  Rotation about Z (yaw):   +0.100000 deg
  Rotation about Y (pitch): +0.050000 deg
  Rotation about X (roll):  -0.025000 deg

index  reference              position    velocity
       epoch                  difference  difference
                              (km)        (km/s)
    1  2024-01-01T00:00:00        0.012      0.000012
    2  2024-01-01T00:01:00        0.013      0.000013
...
```

## Output Format

### Standard Output

The script outputs a table with the following columns:

**Without interpolation** (direct epoch matching):
- `index` — Row number (1-based)
- `reference epoch` — Reference state timestamp (ISO 8601)
- `comparison epoch` — Comparison state timestamp (ISO 8601)
- `time difference (s)` — Epoch difference (comparison - reference)
- `position difference (km)` — Euclidean distance between positions
- `velocity difference (km/s)` — Euclidean distance between velocities

**With interpolation** (one file interpolated at the other's epochs):
- `index` — Row number (1-based)
- `reference epoch` — Query timestamp (ISO 8601)
- `position difference (km)` — Euclidean distance between positions
- `velocity difference (km/s)` — Euclidean distance between velocities

**With `--verbose`** (adds component-wise differences):
- `dX (km)`, `dY (km)`, `dZ (km)` — Position differences by component
- `dVX (km/s)`, `dVY (km/s)`, `dVZ (km/s)` — Velocity differences by component

**With `--rtn`** (adds RTN frame differences):
- `RTN r (km)`, `RTN t (km)`, `RTN n (km)` — Position differences in RTN frame
- `RTN vr (km/s)`, `RTN vt (km/s)`, `RTN vn (km/s)` — Velocity differences in RTN frame

### Statistics

After the comparison table, summary statistics are printed:

```
Statistics (mean, std, min, max)
position difference (km): +0.123, +0.045, +0.050, +0.200
velocity difference (km/s): +0.000123, +0.000045, +0.000050, +0.000200
```

With `--verbose`, statistics are also computed for each component (dX, dY, dZ, dVX, dVY, dVZ).

With `--rtn`, RTN statistics show standard deviation, min, and max (mean is omitted as RTN differences can be positive or negative):

```
Statistics (std, min, max)
RTN r (km): +0.045, -0.100, +0.150
RTN t (km): +0.030, -0.080, +0.100
RTN n (km): +0.020, -0.050, +0.060
```

## Reading from Standard Input

The script can read one OEM file from standard input (stdin) instead of a file. This is useful for piping data from other commands.

### Usage

**Reference from stdin:**
```bash
cat reference.oem | diff-oem - comparison.oem
```

**Comparison from stdin:**
```bash
cat comparison.oem | diff-oem reference.oem -
```

### Examples

**Pipe from another command:**
```bash
curl https://example.com/orbit.oem | diff-oem - reference.oem
```

**Chain with slice-oem:**
```bash
slice-oem large.oem --slice "0:100" | diff-oem reference.oem -
```

**Process compressed files:**
```bash
gunzip -c orbit.oem.gz | diff-oem - reference.oem
```

## Debug Mode

Use `--debug` to print time-range determination details to stderr:

```bash
diff-oem reference.oem comparison.oem --debug
```

Debug output includes:
- Reference time range
- Comparison time range
- Initial overlap range
- Requested time window (if `--start` or `--stop` specified)
- Effective comparison range
- Transformation fitting ranges (if transformations are applied)

Example debug output:
```
Reference range: 2024-01-01T00:00:00.000 to 2024-01-02T00:00:00.000
Comparison range: 2024-01-01T00:30:00.000 to 2024-01-01T23:30:00.000
Initial overlap: 2024-01-01T00:30:00.000 to 2024-01-01T23:30:00.000
Effective range: 2024-01-01T00:30:00.000 to 2024-01-01T23:30:00.000
```

## Common Workflows

### Compare Two Propagations

```bash
diff-oem truth.oem propagated.oem --verbose
```

### Compare with Frame Alignment

```bash
diff-oem reference.oem comparison.oem --rot --verbose
```

### Compare Specific Time Window

```bash
diff-oem reference.oem comparison.oem \
  --start 2024-01-01T00:00:00 \
  --stop 2024-01-01T12:00:00 \
  --interpolate
```

### Analyze RTN Differences

```bash
diff-oem reference.oem comparison.oem --rtn --verbose
```

### Multi-Stage Transformation Analysis

```bash
diff-oem reference.oem comparison.oem \
  --rot --time-shift --rtn --verbose
```

### Compare Downsampled Data

```bash
slice-oem reference.oem --slice "::10" | \
  diff-oem - comparison.oem --interpolate-ref
```

## Programmatic Usage

The underlying library modules can be used directly in Python scripts:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from diff_oem.comparison import read_states, compare_states
from diff_oem.utils import build_comparison_pairs, compare_pairs
from diff_oem.pipeline import create_interpolator

# Read OEM files
reference_states = read_states("reference.oem")
comparison_states = read_states("comparison.oem")

# Build comparison pairs
pairs = build_comparison_pairs(
    reference_states,
    comparison_states,
    reference_states[0],
    interpolate_ref=False,
    interpolate_data=True,
    has_time_window=False,
    overlap_start=None,
    overlap_stop=None,
)

# Create interpolators
reference_interpolator = create_interpolator(reference_states, False)
comparison_interpolator = create_interpolator(comparison_states, True)

# Compare pairs
results = compare_pairs(
    pairs,
    reference_interpolator,
    comparison_interpolator,
    None,
)

# Process results
for query_epoch, result in results:
    if result is not None:
        print(f"Position diff: {result.position_diff_magnitude_km:.3f} km")
        print(f"Velocity diff: {result.velocity_diff_magnitude_km_s:.6f} km/s")
```

See `diff_oem/README.md` for module structure and `tests/` directory for more examples.

## Implementation Details

### Interpolation Algorithm

- **Method**: Lagrange polynomial interpolation
- **Degree**: 8th-order polynomial
- **Implementation**: `core.interpolator.lagrange.LagrangeInterpolator`
- **Application**: Interpolates both position and velocity components

The 8th-degree polynomial provides a good balance between accuracy and numerical stability for typical orbital trajectories.

### Rotation Fitting

**Full 3D rotation** (`--rot`):
- Uses Singular Value Decomposition (SVD) to fit optimal rotation
- Minimizes position residuals over the fitting span
- Applies rotation to both position and velocity vectors

**X/Y rotation** (`--rot-xy`):
- Uses iterative least-squares fitting
- Constrains rotation to X and Y axes only
- Converges in typically 5-10 iterations

**Z rotation** (`--rot-z`):
- Uses iterative least-squares fitting
- Constrains rotation to Z axis only
- Converges in typically 5-10 iterations

### Time Shift Fitting

- Uses golden section search to minimize position residuals
- Searches within ±1800s (30 minutes) by default
- Samples up to 120 comparison states for efficiency
- Converges to sub-millisecond accuracy

### RTN Frame Transformation

The RTN (Radial-Tangential-Normal) frame is computed for each reference state:

1. **Radial**: Unit vector along position: `r̂ = r / |r|`
2. **Normal**: Unit vector perpendicular to orbital plane: `n̂ = (r × v) / |r × v|`
3. **Tangential**: Completes right-handed frame: `t̂ = n̂ × r̂`

Comparison state differences are then projected onto these axes.

## Dependencies

- Python 3.7+
- NumPy (for numerical operations and interpolation)
- Local modules:
  - `diff_oem.cli` — Command-line interface
  - `diff_oem.comparison` — Core comparison logic
  - `diff_oem.output` — Output formatting
  - `diff_oem.pipeline` — Transformation pipeline
  - `diff_oem.transformation_stages` — Transformation implementations
  - `diff_oem.utils` — Utility functions
  - `tudatpy_utils.core.ccsds.oem` — OEM file parsing
  - `tudatpy_utils.core.time_utils` — Time parsing and formatting
  - `tudatpy_utils.core.interpolator.lagrange` — Lagrange interpolation

## Error Handling

### Common Errors

**Both inputs from stdin:**
```
error: reference_oem and comparison_oem cannot both be '-'
```
Solution: Only one input can be read from stdin. Specify a file path for the other input.

**No overlapping time range:**
```
(No output)
```
Solution: The two OEM files have no overlapping time range. Check the time spans of both files.

**Insufficient states for transformation:**
```
ValueError: --rot requires at least two state pairs in the rotation fitting span
```
Solution: Increase `--rot-fit-span` or ensure sufficient overlap between the files.

**Invalid time format:**
```
ValueError: Invalid ISO 8601 datetime: 2024-13-01
```
Solution: Use valid ISO 8601 format or duration notation.

**Start after stop:**
```
ValueError: --start must be earlier than or equal to --stop
```
Solution: Ensure `--start` is before or equal to `--stop`.

## Related Tools

- `slice-oem` — Extract subsets of OEM data by index or time range
- `plot-orbit-deltas` — Visualize orbit differences
- `propagate-orbit` — Generate OEM files from propagation
- `oem-to-omm` — Convert OEM to TLE/OMM format

## References

- [CCSDS OEM Standard](https://public.ccsds.org/Pubs/502x0b2c1e2.pdf) — CCSDS 502.0-B-2
- [ISO 8601](https://www.iso.org/iso-8601-date-and-time-format.html) — Date and time format
- [Lagrange Interpolation](https://en.wikipedia.org/wiki/Lagrange_polynomial) — Polynomial interpolation method
- [Singular Value Decomposition](https://en.wikipedia.org/wiki/Singular_value_decomposition) — Matrix factorization for rotation fitting

## See Also

- [SLICE_OEM.md](SLICE_OEM.md) — OEM slicing utility
- [MISC.md](MISC.md) — Overview of miscellaneous utilities
- [PROPAGATION.md](PROPAGATION.md) — Orbit propagation tools
- [diff_oem/README.md](../diff_oem/README.md) — Module structure and design
