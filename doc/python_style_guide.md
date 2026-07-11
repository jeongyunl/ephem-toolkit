# Python Style Guide

---

## 1. Docstring Format

All docstrings follow the **NumPy docstring style**.

### 1.1 Section headers

Use plural forms with a dashed underline matching the header length:

```python
Parameters
----------
Returns
-------
Raises
------
Notes
-----
References
----------
```

Do **not** use singular forms (`Note`, `Reference`, `Parameter`).

### 1.2 One-line docstrings

Short functions may use a one-line docstring:

```python
def _parse_kv_line(line: str) -> tuple[str, str] | None:
    """Return (key, value) from ``KEY = VALUE`` lines, or *None*."""
```

### 1.3 Multi-line docstrings

Public functions/methods/properties require multi-line docstrings with `Parameters` (if arguments exist) and `Returns` (if returning a value):

```python
def read_tle(stream: TextIO) -> Tle:
    """Parse TLE elements from a text stream (file-like object).

    Parameters
    ----------
    stream : TextIO
        Readable text stream containing TLE data.

    Returns
    -------
    Tle
        A :class:`Tle` dataclass instance with all parsed elements.
    """
```

### 1.4 Parameter documentation format

Use `name : type` with indented description. Type must match function signature exactly:

```python
Parameters
----------
source : TextIO | str | Path
    A readable text stream, file path string, or :class:`Path`.
mu : float
    Gravitational parameter (m³/s²).
```

### 1.5 Private helper functions

Private functions (`_` prefix) require at least a one-line docstring. Full `Parameters`/`Returns` sections optional but recommended for non-trivial helpers.

### 1.6 Class methods and properties

Public methods and properties require docstrings. `@property` docstrings may be single-line:

```python
@property
def epochs(self) -> list[float]:
    """Sorted list of epoch timestamps (POSIX seconds)."""
```

### 1.7 Module-level docstrings

Brief summary line followed by description. Use `References:` with indented list (not NumPy section underline):

```python
"""Convert between Cartesian state vectors and osculating Keplerian elements.

Provides :func:`cartesian_to_keplerian`, :func:`keplerian_to_cartesian`,
and :func:`tle_to_osculating_keplerian` for two-body orbital element
conversions using only NumPy.

References:
    Curtis, H.D. "Orbital Mechanics for Engineering Students", Chapter 4.
    Vallado, D.A. "Fundamentals of Astrodynamics and Applications", Algorithm 9.
"""
```

---

## 2. Naming

All names must be **descriptive and self-documenting**. Parameter names in docstrings must **exactly match** function signatures and appear **exactly once** in `Parameters`.

### 2.1 Function names

- **Conversions:** `<source>_to_<target>` — target is type/concept produced, never format description (no `_string`, `_value` suffixes)
- **Actions:** verb prefix (`parse`, `read`, `write`, `compute`, `transform`) — no bare noun phrases

```python
def cartesian_to_keplerian(...) -> np.ndarray:
def tle_to_omm(...) -> CcsdsOmm:
def parse_oem_state_line(...)
def compute_tle_checksum(...)
```

### 2.2 Variables and parameters

Use clear, full words that convey intent:

```python
def compute_orbital_period(semi_major_axis: float, gravitational_parameter: float) -> float:
    ...
```

**Avoid:** single-letter names (except `i`/`j`/`k` indices or `x`/`y`/`z` in math), cryptic abbreviations (`tmp`, `buf`, `arr`, `val`, `res`, `ret`), ambiguous shorts (`d`, `s`, `t`, `n`), over-abbreviated params (`src` → `source`, `dst` → `dest`, `cfg` → `config`).

### 2.3 Exception: standard mathematical notation

Single-letter names matching domain notation acceptable when documented:

```python
a = semi_major_axis       # (m)
e = eccentricity          # (dimensionless)
mu = gravitational_parameter  # (m³/s²)
```

### 2.4 Physical unit suffixes

Append unit suffixes to physical quantities for clarity. Use underscores for division (e.g., `_m_s` for m/s):

```python
def compute_orbital_period(semi_major_axis_m: float, mu_m3_s2: float) -> float:
    """Compute the orbital period.
    
    Parameters
    ----------
    semi_major_axis_m : float
        Semi-major axis (m).
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    
    Returns
    -------
    float
        Orbital period (s).
    """
    period_s = 2.0 * np.pi * np.sqrt(semi_major_axis_m**3 / mu_m3_s2)
    return period_s
```

Common unit suffixes:

| Quantity | Suffix | Example |
|----------|--------|---------|
| Distance (meters) | `_m` | `altitude_m` |
| Distance (kilometers) | `_km` | `altitude_km` |
| Time (seconds) | `_s` | `duration_s` |
| Time (days) | `_d` | `duration_d` |
| Angle (degrees) | `_deg` | `inclination_deg` |
| Angle (radians) | `_rad` | `inclination_rad` |
| Velocity (m/s) | `_m_s` | `velocity_m_s` |
| Velocity (km/s) | `_km_s` | `velocity_km_s` |
| Acceleration (m/s²) | `_m_s2` | `acceleration_m_s2` |
| Gravitational parameter (m³/s²) | `_m3_s2` | `mu_m3_s2` |

**Note:** Use underscores for division in compound units (`_m_s` for m/s, `_m3_s2` for m³/s²). Write exponents directly after unit symbol without separators (`s2` for s², `m3` for m³).

**Exception:** Omit suffix when unit is obvious from context or using standard mathematical notation (see 2.3), but always document unit in docstring.

#### 2.4.1 CLI argument naming

For `argparse` arguments, unit suffixes apply **only** to `dest` (Python variable name), **not** to argument name or `metavar`:

```python
argument_parser.add_argument(
    "--mu",                                              # Simple, user-friendly
    type=float,
    default=consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    metavar="<value>",                                   # Generic placeholder
    dest="mu_m3_s2",                                     # Python variable with unit suffix
    help=(
        "Gravitational parameter (m³/s²). "
        f"Default: {consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2:.6e} (Earth WGS-84)."
    ),
)
```

**Rationale:**
- CLI argument names (`--mu`, `--fit-span`) should be concise and user-friendly
- The `metavar` appears in help text and should use generic placeholders (`<value>`, `<hours>`)
- The `dest` parameter becomes a Python variable and must follow the unit suffix convention
- Units are documented in the `help` text for user clarity

**Correct:**
```python
argument_parser.add_argument("--mu", dest="mu_m3_s2", metavar="<value>", ...)
argument_parser.add_argument("--fit-span", dest="fit_span_hours", metavar="<hours>", ...)
```

**Wrong:**
```python
argument_parser.add_argument("--mu-m3-s2", dest="mu_m3_s2", metavar="<mu_m3_s2>", ...)  # Too verbose
argument_parser.add_argument("--mu", dest="mu", metavar="<mu>", ...)  # Missing unit suffix on dest
```

---

## 3. Units

### 3.1 Unicode superscript characters

Use Unicode superscript characters for exponents — not ASCII caret notation:

| Correct | Wrong |
|---------|-------|
| `m³/s²` | `m^3/s^2` |
| `km·s⁻¹` | `km/s` (acceptable alternative) |

### 3.2 Internal computations vs. output/display

**All internal computations use SI units: meters, seconds, radians.**

**Output/display use km and degrees for human readability.**

Ensures: consistency with scientific libraries, numerical stability, compatibility with physical constants, human-readable output.

#### 3.2.1 Implementation pattern

Three-stage pattern:
1. **Input**: Read data in native format (e.g., OEM files use km/km/s per CCSDS)
2. **Internal**: Convert to SI units (meters, m/s, radians) for computations
3. **Output**: Convert to display units (km, degrees) for readability

Example:

```python
def fit_orbital_elements(
    records: list[tuple[datetime, np.ndarray, np.ndarray]],
    mu_m3_s2: float,
) -> np.ndarray:
    """Fit Keplerian elements to state vector records.
    
    All internal computations use SI units (meters, seconds, radians).
    
    Parameters
    ----------
    records : list[tuple[datetime, np.ndarray, np.ndarray]]
        List of (epoch, position_km (3,), velocity_km_s (3,)) tuples.
        Positions in km, velocities in km/s (as read from OEM files).
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    
    Returns
    -------
    np.ndarray
        Keplerian elements (6,): [a, e, i, omega, RAAN, M].
        Semi-major axis in meters, angles in radians (SI units).
    """
    # Convert input from km to meters (SI units)
    position_m: np.ndarray = records[0][1] * 1000.0
    velocity_m_s: np.ndarray = records[0][2] * 1000.0
    
    # All computations in SI units
    state_m: np.ndarray = np.concatenate([position_m, velocity_m_s])
    elements: np.ndarray = kepler.cartesian_to_keplerian(state_m, mu_m3_s2)
    
    return elements  # Returns in SI units (meters, radians)


def format_elements_for_display(elements: np.ndarray) -> str:
    """Format Keplerian elements for human-readable output.
    
    Converts internal SI units to display units (km, degrees).
    
    Parameters
    ----------
    elements : np.ndarray
        Keplerian elements (6,): [a, e, i, omega, RAAN, M].
        Semi-major axis in meters, angles in radians (SI units).
    
    Returns
    -------
    str
        Formatted string with semi-major axis in km, angles in degrees.
    """
    semi_major_axis_km: float = elements[0] / 1000.0
    inclination_deg: float = np.degrees(elements[2])
    raan_deg: float = np.degrees(elements[4])
    
    return (
        f"a = {semi_major_axis_km:.3f} km, "
        f"i = {inclination_deg:.3f} deg, "
        f"RAAN = {raan_deg:.3f} deg"
    )
```

#### 3.2.2 Documentation requirements

For functions handling unit conversions, document:
- **Input units**: Units of input data
- **Internal units**: Computations use SI units
- **Output units**: Units returned or displayed

Example docstring:

```python
def compute_position_error(
    oem_position_km: np.ndarray,
    predicted_position_m: np.ndarray,
) -> float:
    """Compute position error magnitude.
    
    Converts OEM position from km to m for comparison (SI units).
    Returns error in km for display.
    
    Parameters
    ----------
    oem_position_km : np.ndarray
        Position from OEM file (3,) in km.
    predicted_position_m : np.ndarray
        Predicted position (3,) in meters (SI units).
    
    Returns
    -------
    float
        Position error magnitude in km (for display).
    """
    # Convert to SI units for computation
    oem_position_m: np.ndarray = oem_position_km * 1000.0
    
    # Compute in SI units
    error_m: float = float(np.linalg.norm(oem_position_m - predicted_position_m))
    
    # Convert to km for display
    return error_m / 1000.0
```

#### 3.2.3 Variable naming for clarity

Use unit suffixes to make conversions explicit:

```python
# Input (OEM standard: km)
position_km: np.ndarray = read_oem_position(...)

# Convert to SI units for computation
position_m: np.ndarray = position_km * 1000.0

# Compute in SI units
distance_m: float = np.linalg.norm(position_m)

# Convert to display units
distance_km: float = distance_m / 1000.0
print(f"Distance: {distance_km:.3f} km")
```

#### 3.2.4 Common conversions

| Conversion | Formula | Example |
|------------|---------|---------|
| km → m | `m = km * 1000.0` | `position_m = position_km * 1000.0` |
| m → km | `km = m / 1000.0` | `distance_km = distance_m / 1000.0` |
| deg → rad | `rad = np.radians(deg)` | `inclination_rad = np.radians(inclination_deg)` |
| rad → deg | `deg = np.degrees(rad)` | `inclination_deg = np.degrees(inclination_rad)` |
| km/s → m/s | `m_s = km_s * 1000.0` | `velocity_m_s = velocity_km_s * 1000.0` |
| m/s → km/s | `km_s = m_s / 1000.0` | `velocity_km_s = velocity_m_s / 1000.0` |

---

## 4. Section Separators

Use 67-character-wide `# ===` banner comments to divide modules into
logical sections:

```python
# ===================================================================
# Internal helpers
# ===================================================================
```

---

## 5. Type Annotations

### 5.1 All public functions are fully annotated

Public functions must annotate all parameters and return type.

### 5.2 `|` union syntax

Use `X | Y` (not `Union[X, Y]`). `from __future__ import annotations` enables runtime safety:

```python
def read_oem(source: TextIO | str | Path) -> tuple[dict, dict, dict[float, np.ndarray]]:
    ...
```

### 5.3 `TYPE_CHECKING` guard

Use `TYPE_CHECKING` to avoid circular imports for documentation-only hints:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.tle import Tle
```

### 5.4 Local variable annotations

Annotate local variables explicitly, especially for complex types, intermediate results, or non-obvious types:

```python
match: re.Match[str] | None = re.fullmatch(r"...", value)
magnitude: float = float(match.group(1))
state_arr: np.ndarray = np.asarray(state, dtype=float)
```

---

## 6. Constants

Module-level constants are typed and documented with triple-quote docstring immediately following assignment:

```python
MU_EARTH: float = 3.986004418e14
"""Earth gravitational parameter (m³/s²), WGS-84."""

RE_EARTH: float = 6378137.0
"""Earth equatorial radius (m), WGS-84."""
```

---

## 7. File I/O Conventions

### 7.1 Parameter names

Readers use `source`; writers use `dest`:

```python
def read_oem(source: TextIO | str | Path) -> ...:
def write_oem(dest: TextIO | str | Path, ...) -> None:
```

### 7.2 Recursive dispatch for path arguments

Functions accepting `TextIO | str | Path` open the file and recurse:

```python
def read_oem(source: TextIO | str | Path) -> ...:
    if isinstance(source, (str, Path)):
        with open(source, "r", encoding="utf-8") as fh:
            return read_oem(fh)
    # ... process stream
```

---

## 8. Class and Dataclass Conventions

### 8.1 Variable documentation

Document all class variables, dataclass fields, and instance variables with triple-quote docstring immediately following definition. Do **not** use hash comments.

Include units, value ranges, or format info where applicable:

```python
@dataclass
class Tle:
    """Parsed Two-Line Element set data."""

    name: str = ""
    """Satellite name (may be empty if not present in the TLE source)"""

    inclination_deg: float = 0.0
    """Inclination (degrees)"""

    eccentricity: float = 0.0
    """Eccentricity (decimal value, 0.0 to 1.0)"""
```

Instance variables in `__init__`:

```python
class Interpolator:
    def __init__(self, dimension: int = 1) -> None:
        self.independent_values: list[float] = []
        """The ordered independent variable values used for interpolation."""
```

### 8.2 Standard methods

| Method | Purpose |
|--------|---------|
| `to_dict()` | Dict serialisation via `dataclasses.asdict` |
| `from_source(cls, source)` | Classmethod to construct from file/stream |
| `to_file(self, dest)` | Write instance to file/stream |

---

## 9. `__repr__` Methods

Structured classes implement `__repr__` returning concise string with class name and key identifying fields:

```python
def __repr__(self) -> str:
    return (
        f"CcsdsOmm(object={self.object_name!r}, "
        f"norad_cat_id={self.norad_cat_id}, "
        f"epoch={self.epoch!r})"
    )
```

---

## 10. CLI Entry Points

Directly runnable modules include `if __name__ == "__main__":` with usage message to `stderr` on missing arguments:

```python
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m common.oem <oem_file>", file=sys.stderr)
        sys.exit(1)
```

---

## 11. Inline Comments

### 11.1 Keep notable inline comments

Inline comments should be preserved when they provide **non-obvious context** that aids understanding. Keep comments that:

- **Explain complex logic or algorithms**: Clarify non-trivial mathematical operations, coordinate transformations, or algorithmic steps
- **Document important constraints or assumptions**: Note physical limits, numerical stability concerns, or domain-specific requirements
- **Provide context for "magic numbers"**: Explain the origin or significance of numerical constants not defined as named constants
- **Clarify non-obvious variable assignments**: Explain why a particular value or formula is used when it's not immediately clear
- **Reference external sources**: Cite equations, algorithms, or standards being implemented
- **Document array/list shapes and units**: Specify dimensions and physical units for arrays, especially when shape or units are not obvious from the variable name or type annotation

**Examples of notable comments to keep:**

```python
# Convert from CCSDS epoch format (days since J2000) to POSIX timestamp
epoch_posix = (epoch_j2000 * 86400.0) + J2000_EPOCH_POSIX

# Normalize mean anomaly to [0, 2π) to avoid convergence issues
mean_anomaly_rad = mean_anomaly_rad % (2.0 * np.pi)

# Use Laguerre's method for better convergence with high eccentricity (e > 0.8)
if eccentricity > 0.8:
    eccentric_anomaly_rad = _solve_kepler_laguerre(mean_anomaly_rad, eccentricity)

# Curtis Eq. 4.62: specific angular momentum vector
h_vec = np.cross(position_m, velocity_m_s)

# Array shape and unit comments
position_m = np.array([x, y, z])  # (3,) position vector in meters
state_m = np.concatenate([position_m, velocity_m_s])  # (6,) state vector [pos, vel] in SI units
elements = np.zeros(6)  # (6,) Keplerian elements [a, e, i, ω, Ω, M]
covariance_matrix = np.eye(6)  # (6, 6) state covariance matrix
```

### 11.2 Standard mathematical notation comments

When using single-letter variables for standard mathematical notation (see §2.3), include inline comments documenting the physical meaning and units:

```python
a = semi_major_axis_m       # Semi-major axis (m)
e = eccentricity            # Eccentricity (dimensionless)
i = inclination_rad         # Inclination (rad)
mu = gravitational_parameter_m3_s2  # Gravitational parameter (m³/s²)
```

These comments are **required** because they provide essential context for abbreviated notation.

### 11.3 Placement and formatting

- Place inline comments on the same line as the code, separated by at least two spaces
- Use complete sentences with proper capitalization for multi-word comments
- Keep comments concise but informative
- Align related inline comments vertically when it improves readability

```python
# Good: Aligned comments for related variables
a = elements[0]  # Semi-major axis (m)
e = elements[1]  # Eccentricity (dimensionless)
i = elements[2]  # Inclination (rad)

# Good: Explanatory comment for complex operation
# Solve Kepler's equation using Newton-Raphson (typically converges in 3-5 iterations)
eccentric_anomaly_rad = _solve_kepler_newton(mean_anomaly_rad, eccentricity)
```

---

## 12. Imports

### 12.1 Order

1. `from __future__ import annotations` (always first)
2. Standard library
3. Third-party
4. Local

### 12.2 `from __future__ import annotations`

Include in every module.

### 12.3 Import modules as a whole

For local (`common.*`) imports, always import module — never individual names:

```python
# Correct
import common.kepler as kepler
kepler.MU_EARTH

# Wrong
from common.kepler import MU_EARTH
```

Standard-library and third-party modules may use `from X import Y` where idiomatic (e.g., `from pathlib import Path`, `from datetime import datetime`).
