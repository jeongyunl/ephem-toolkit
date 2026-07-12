# Python Style Guide

---

## 1. Docstrings

All docstrings follow **NumPy style** with plural section headers (`Parameters`, `Returns`, `Raises`, `Notes`, `References`).

**One-line** for simple functions:
```python
def _parse_kv_line(line: str) -> tuple[str, str] | None:
    """Return (key, value) from ``KEY = VALUE`` lines, or *None*."""
```

**Multi-line** for public functions (include `Parameters` if arguments exist, `Returns` if returning):
```python
def read_tle(stream: TextIO) -> Tle:
    """Parse TLE elements from a text stream.

    Parameters
    ----------
    stream : TextIO
        Readable text stream containing TLE data.

    Returns
    -------
    Tle
        Parsed TLE dataclass instance.
    """
```

**Properties** may use one-line:
```python
@property
def epochs(self) -> list[float]:
    """Sorted list of epoch timestamps (POSIX seconds)."""
```

**Module-level** docstrings use `References:` with indented list (not NumPy section):
```python
"""Convert between Cartesian and Keplerian elements.

References:
    Curtis, H.D. "Orbital Mechanics for Engineering Students", Ch. 4.
"""
```

**Executable scripts** (with `#!/usr/bin/env python3` shebang) use `Usage:`:
```python
#!/usr/bin/env python3
"""Plot orbit trajectories with various views and RTN coordinates.

Usage:
    python3 plot_orbits.py <reference_oem> [comparison_oem1] ...
"""
```

---

## 2. Naming

### 2.1 Functions and methods

**Verb prefix is most preferred** — use descriptive action verbs.

- **Actions (PREFERRED):** `parse`, `read`, `write`, `compute`, `transform`, `find`, `update`, `calculate`, `validate`, `convert`
- **Conversions:** `<source>_to_<target>` (only when primary purpose is type conversion)
- **Factory classmethods:** `from_<source>`
- **Export methods:** `to_<target>`

```python
# Verb prefix (preferred)
def parse_oem_state_line(line: str) -> tuple[float, np.ndarray] | None:
def read_tle(stream: TextIO) -> Tle:
def compute_tle_checksum(line: str) -> int:
def validate_state_vector(state: np.ndarray) -> bool:

# Conversions (when primary purpose is type conversion)
def cartesian_to_keplerian(state_m: np.ndarray, mu_m3_s2: float) -> np.ndarray:

# Class methods (same conventions)
class CcsdsOem:
    @classmethod
    def from_source(cls, source: TextIO | str | Path) -> CcsdsOem:  # Factory
    
    def to_file(self, dest: TextIO | str | Path) -> None:  # Export
    def find_state_by_timestamp(self, timestamp: float) -> ...:  # Action (preferred)
    def update_metadata(self, **kwargs) -> None:  # Action (preferred)
```

### 2.2 Variables and parameters

Use clear, full words. **Avoid:** single letters (except `i`/`j`/`k` indices, `x`/`y`/`z` in math), cryptic abbreviations (`tmp`, `buf`, `arr`), over-abbreviated params (`src` → `source`, `dst` → `dest`).

**Exception:** Single-letter names acceptable for standard math notation when documented:
```python
a = semi_major_axis_m       # Semi-major axis (m)
e = eccentricity            # Eccentricity (dimensionless)
mu = gravitational_parameter_m3_s2  # Gravitational parameter (m³/s²)
```

### 2.3 Physical unit suffixes

Append unit suffixes for clarity. Use underscores for division (`_m_s` for m/s, `_m3_s2` for m³/s²):

| Quantity | Suffix | Example |
|----------|--------|---------|
| Distance (m/km) | `_m` / `_km` | `altitude_m`, `altitude_km` |
| Time (s/d) | `_s` / `_d` | `duration_s`, `duration_d` |
| Angle (deg/rad) | `_deg` / `_rad` | `inclination_deg`, `inclination_rad` |
| Velocity | `_m_s` / `_km_s` | `velocity_m_s`, `velocity_km_s` |
| Acceleration | `_m_s2` | `acceleration_m_s2` |
| Grav. parameter | `_m3_s2` | `mu_m3_s2` |

**CLI arguments:** Unit suffixes on `dest` only, not on argument name or `metavar`:
```python
parser.add_argument("--mu", dest="mu_m3_s2", metavar="<value>", help="Gravitational parameter (m³/s²).")
```

---

## 3. Units

### 3.1 Unicode superscripts

Use Unicode superscripts for exponents: `m³/s²` not `m^3/s^2`.

### 3.2 SI units internally, display units for output

**All internal computations use SI units: meters, seconds, radians.**
**Output/display use km and degrees for readability.**

Three-stage pattern:
1. **Input:** Read native format (e.g., OEM uses km/km·s⁻¹)
2. **Internal:** Convert to SI (m, m/s, rad) for computations
3. **Output:** Convert to display units (km, deg)

```python
def compute_position_error(oem_position_km: np.ndarray, predicted_position_m: np.ndarray) -> float:
    """Compute position error magnitude.
    
    Converts OEM position from km to m (SI units). Returns error in km for display.
    """
    oem_position_m = oem_position_km * 1000.0  # Convert to SI
    error_m = float(np.linalg.norm(oem_position_m - predicted_position_m))  # Compute in SI
    return error_m / 1000.0  # Convert to km for display
```

Common conversions: `m = km * 1000.0`, `km = m / 1000.0`, `rad = np.radians(deg)`, `deg = np.degrees(rad)`

---

## 4. Type Annotations

- **All public functions** fully annotated (parameters and return type)
- **Union syntax:** `X | Y` not `Union[X, Y]`
- **Circular imports:** Use `TYPE_CHECKING` guard
- **Local variables:** Annotate complex types, intermediate results, non-obvious types

```python
from __future__ import annotations  # Always first import
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.tle import Tle

def read_oem(source: TextIO | str | Path) -> tuple[dict, dict, list[tuple[float, np.ndarray]]]:
    match: re.Match[str] | None = re.fullmatch(r"...", value)  # Annotate locals
    ...
```

---

## 5. File I/O

- **Parameter names:** Readers use `source`, writers use `dest`
- **Recursive dispatch:** Functions accepting `TextIO | str | Path` open file and recurse

```python
def read_oem(source: TextIO | str | Path) -> ...:
    if isinstance(source, (str, Path)):
        with open(source, "r", encoding="utf-8") as fh:
            return read_oem(fh)
    # ... process stream
```

---

## 6. Classes and Dataclasses

### 6.1 Variable documentation

Document all fields with triple-quote docstring immediately after definition. **No hash comments.**

```python
@dataclass
class Tle:
    """Parsed Two-Line Element set data."""
    
    name: str = ""
    """Satellite name (may be empty if not present in TLE source)"""
    
    inclination_deg: float = 0.0
    """Inclination (degrees)"""
```

### 6.2 Standard methods

| Method | Purpose |
|--------|---------|
| `from_source(cls, source)` | Classmethod to construct from file/stream |
| `to_file(self, dest)` | Write instance to file/stream |
| `to_dict(self)` | Dict serialization via `dataclasses.asdict` |

### 6.3 `__repr__`

Return concise string with class name and key fields:
```python
def __repr__(self) -> str:
    return f"CcsdsOmm(object={self.object_name!r}, norad_cat_id={self.norad_cat_id})"
```

---

## 7. Constants

Module-level constants typed and documented:
```python
MU_EARTH: float = 3.986004418e14
"""Earth gravitational parameter (m³/s²), WGS-84."""
```

---

## 8. Comments

### 8.1 Inline comments

Keep comments that provide **non-obvious context**:
- Complex logic/algorithms
- Important constraints/assumptions
- "Magic number" explanations
- Non-obvious variable assignments
- External source references (equations, standards)
- Array shapes and units

```python
# Curtis Eq. 4.62: specific angular momentum vector
h_vec = np.cross(position_m, velocity_m_s)

# Normalize to [0, 2π) to avoid convergence issues
mean_anomaly_rad = mean_anomaly_rad % (2.0 * np.pi)

state_m = np.concatenate([position_m, velocity_m_s])  # (6,) state vector [pos, vel] in SI units
```

### 8.2 Section separators

Use 67-character `# ===` banners:
```python
# ===================================================================
# Internal helpers
# ===================================================================
```

---

## 9. Imports

**Order:**
1. `from __future__ import annotations` (always first)
2. Standard library
3. Third-party
4. Local

**Local imports:** Import module, not individual names:
```python
# Correct
import common.kepler as kepler
kepler.MU_EARTH

# Wrong
from common.kepler import MU_EARTH
```

Standard library and third-party may use `from X import Y` where idiomatic (`from pathlib import Path`).

---

## 10. CLI Entry Points

Include `if __name__ == "__main__":` with usage message to stderr:
```python
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 -m common.oem <oem_file>", file=sys.stderr)
        sys.exit(1)
```
