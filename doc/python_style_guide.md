# Python Style Guide

---

## 1. Docstring Format

All docstrings follow the **NumPy docstring style**.

### 1.1 Section headers

Use the plural form for all standard section headers, with a dashed
underline exactly as long as the header word:

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

Do **not** use the singular forms `Note`, `Reference`, or `Parameter`.

### 1.2 One-line docstrings

Short functions whose purpose is fully captured in a single sentence may
use a one-line docstring:

```python
def _parse_kv_line(line: str) -> tuple[str, str] | None:
    """Return (key, value) from ``KEY = VALUE`` lines, or *None*."""
```

### 1.3 Multi-line docstrings

Every public function, method, and property must have a multi-line
docstring with at minimum a `Parameters` section (if the function accepts
arguments) and a `Returns` section (if it returns a value):

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

Each parameter entry uses the form `name : type` on the first line,
followed by an indented description:

```python
Parameters
----------
source : TextIO | str | Path
    A readable text stream, file path string, or :class:`Path`.
header : dict
    File-level keywords (``CCSDS_OMM_VERS``, ``CREATION_DATE``, …).
mu : float
    Gravitational parameter (m³/s²).
```

The type annotation must match the function signature exactly.
Do **not** omit the type (e.g. `source:` alone is incorrect).

### 1.5 Private helper functions

Private functions (prefixed with `_`) must have at least a one-line
docstring. They do not require full `Parameters`/`Returns` sections, but
these are welcome when the function is non-trivial:

```python
def _epoch_to_timestamp(epoch: datetime) -> float:
    """Convert a :class:`datetime` to a POSIX timestamp float."""
```

### 1.6 Class methods and properties

All public methods and properties of a class must have docstrings,
including `@classmethod`, `@property`, and `to_file`-style methods.
`@property` docstrings may be a single descriptive line:

```python
@property
def epochs(self) -> list[float]:
    """Sorted list of epoch timestamps (POSIX seconds)."""

@property
def state_vectors(self) -> np.ndarray:
    """State vectors ordered by epoch, shape ``(N, 6)``."""
```

### 1.7 Module-level docstrings

Module docstrings use a brief summary line followed by a description of
what the module provides. References use the `References:` label with an
indented list (not a NumPy section underline, since this is module-level
prose):

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

## 2. Function Naming

### 2.1 Conversion functions use `<source>_to_<target>`

All functions that convert one representation to another follow the
`<source>_to_<target>` pattern. The target name is the *type or concept*
being produced — never a description of the return format (e.g. no
`_string`, `_value`, `_result` suffixes):

    # Correct
    def cartesian_to_keplerian(...) -> np.ndarray:
    def keplerian_to_cartesian(...) -> np.ndarray:
    def tle_to_omm(...) -> CcsdsOmm:
    def omm_to_tle(...) -> Tle:
    def datetime_to_tdb(...) -> float:
    def tdb_to_datetime(...) -> datetime:
    def tle_epoch_to_datetime(...) -> str:   # target is "datetime" (as ISO string)

    # Wrong — suffix describes the return format, not the target concept
    def tle_epoch_to_datetime_string(...) -> str:

### 2.2 Action functions use a verb prefix

Functions that perform an action (parse, read, write, compute, transform)
use a descriptive verb prefix. Do **not** use bare noun phrases as
function names:

    # Correct
    def parse_oem_state_line(...)
    def parse_duration_to_seconds(...)
    def read_oem(...)
    def write_oem(...)
    def compute_tle_checksum(...)
    def compute_brouwer_short_period_corrections(...)
    def transform_to_rtn(...)

    # Wrong — noun phrase with no verb
    def brouwer_short_period_corrections(...)

---

## 3. Parameter Naming

### 3.1 Match signature to docstring

The parameter name in the docstring must exactly match the name in the
function signature:

```python
# Correct
def mean_motion_to_semi_major_axis(mean_motion_rev_per_day: float, mu: float) -> float:
    """...
    Parameters
    ----------
    mean_motion_rev_per_day : float
        Mean motion in revolutions per day.
    """

# Wrong — docstring uses a different name
def mean_motion_to_semi_major_axis(mean_motion_rev_per_day: float, mu: float) -> float:
    """...
    Parameters
    ----------
    n_rev_per_day : float
        Mean motion in revolutions per day.
    """
```

### 3.2 No duplicate parameter entries

Each parameter must appear exactly once in the `Parameters` section.
Duplicate entries (e.g. `J2` listed twice) must be removed.

---

## 4. Units

### 4.1 Unicode superscripts for physical units

Use Unicode superscript characters for exponents in unit strings, not
ASCII caret notation:

| Correct | Wrong |
|---------|-------|
| `m³/s²` | `m^3/s^2` |
| `km·s⁻¹` | `km/s` (acceptable alternative) |

This applies to both inline docstring text and constant docstrings:

```python
MU_EARTH: float = 3.986004418e14
"""Earth gravitational parameter (m³/s²), WGS-84."""
```

---

## 5. Section Separators

Use `# ===` banner comments to divide a module into logical sections.
The banner is 67 characters wide (3 `=` signs, a space, the title, a
space, then `=` signs to fill to 67):

```python
# ===================================================================
# Internal helpers
# ===================================================================

# ===================================================================
# Low-level reader (dict-based)
# ===================================================================

# ===================================================================
# Structured dataclass
# ===================================================================
```

---

## 6. Type Annotations

### 6.1 All public functions are fully annotated

Every public function must have type annotations on all parameters and
the return type:

```python
def datetime_to_tdb(dt: datetime) -> float:
def write_tle(dest: TextIO | str | Path, tle_data: Tle | Mapping[str, object]) -> tuple[str, str]:
```

### 6.2 `|` union syntax

Use `X | Y` for all union types in function signatures, return types,
and local type hints. Do **not** use `Union[X, Y]` from `typing`.
`from __future__ import annotations` (already required) makes `|` safe
at runtime on all supported Python versions:

```python
from typing import TextIO

def read_oem(source: TextIO | str | Path) -> tuple[dict, dict, dict[float, np.ndarray]]:
    ...

def _parse_kv_line(line: str) -> tuple[str, str] | None:
    ...
```

### 6.3 `TYPE_CHECKING` guard for circular imports

Use `TYPE_CHECKING` to avoid circular imports when a type hint is only
needed for documentation:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.tle import Tle
```

### 6.4 Type annotations for local variables

All local variables within functions should have explicit type annotations,
especially for:

- Variables assigned from function calls with complex return types
- Variables that hold intermediate computational results
- Variables whose type may not be immediately obvious from context
- Loop variables and accumulators

Use the same `|` union syntax for local variable annotations as for
function signatures:

```python
def parse_duration_to_seconds(value: str) -> float:
    """Parse a duration token and convert it to seconds."""
    match: re.Match[str] | None = re.fullmatch(r"...", value)
    if not match:
        raise argparse.ArgumentTypeError("...")
    
    magnitude: float = float(match.group(1))
    unit: str = match.group(2).lower() if match.group(2) else "s"
    duration_s: float = magnitude * SECONDS_PER_MINUTE
    return duration_s
```

For NumPy arrays and other complex types, annotate with the specific type:

```python
def transform_to_rtn(state: np.ndarray) -> np.ndarray:
    """Transform state vectors to RTN frame."""
    state_arr: np.ndarray = np.asarray(state, dtype=float)
    single_input: bool = state_arr.ndim == 1
    
    reference_positions: np.ndarray = reference_state_arr[:, 0:3]
    radial_unit_vectors: np.ndarray = (
        reference_positions / reference_position_magnitudes[:, np.newaxis]
    )
    
    result: np.ndarray = np.column_stack([rtn_positions, rtn_velocities])
    return result[0] if single_input else result
```

---

## 7. Constants

Module-level constants are typed and documented with an inline docstring
on the line immediately following the assignment:

```python
MU_EARTH: float = 3.986004418e14
"""Earth gravitational parameter (m³/s²), WGS-84."""

RE_EARTH: float = 6378137.0
"""Earth equatorial radius (m), WGS-84."""

SECONDS_PER_MINUTE = 60.0
SECONDS_PER_HOUR = 3600.0
SECONDS_PER_DAY = 86400.0
```

---

## 8. File I/O Conventions

### 8.1 Consistent `source` / `dest` parameter names

Reader functions use `source` and writer functions use `dest` as the
parameter name for the file argument:

```python
def read_oem(source: TextIO | str | Path) -> ...:
def write_oem(dest: TextIO | str | Path, ...) -> None:
def read_omm(source: TextIO | str | Path) -> ...:
def write_omm(dest: TextIO | str | Path, ...) -> None:
def read_tle(stream: TextIO) -> Tle:          # stream: accepts only TextIO
def write_tle(dest: TextIO | str | Path, ...) -> tuple[str, str]:
```

### 8.2 Recursive dispatch for path arguments

Functions that accept `TextIO | str | Path` open the file and recurse
with the file handle:

```python
def read_oem(source: TextIO | str | Path) -> ...:
    if isinstance(source, (str, Path)):
        with open(source, "r", encoding="utf-8") as fh:
            return read_oem(fh)
    # ... process stream
```

---

## 9. Class and Dataclass Conventions

### 9.1 Class and instance variable documentation with triple-quote docstrings

All class variables, dataclass fields, and instance variables are
documented using triple-quote docstrings on the line immediately following
the variable definition. This applies to all class types (dataclasses,
regular classes, and any other class definitions).

**Every field should have its own docstring** describing its purpose,
format, units, or constraints. Docstrings should be clear, concise, and
informative.

**Dataclass fields with comprehensive documentation:**

```python
@dataclass
class Tle:
    """Parsed Two-Line Element set data."""

    name: str = ""
    """Satellite name (may be empty if not present in the TLE source)"""

    satellite_number: int = 0
    """NORAD catalog number (satellite number)"""
    
    epoch_year: int = 0
    """Epoch year (2-digit)"""
    epoch_day: float = 0.0
    """Epoch day of year with fractional portion"""
    
    inclination_deg: float = 0.0
    """Inclination (degrees)"""
    eccentricity: float = 0.0
    """Eccentricity (decimal value, 0.0 to 1.0)"""
```

**Dataclass fields with grouped sections:**

When fields naturally group into logical sections, the first field of each
section may include a brief section description in its docstring:

```python
@dataclass
class CcsdsOmm:
    """Parsed CCSDS Orbit Mean-Elements Message."""

    version: float = 2.0
    """CCSDS OMM format version number"""
    creation_date: str = ""
    """File creation date (ISO 8601 format)"""

    object_name: str = ""
    """Satellite or object name"""
    object_id: str = ""
    """International designator or NORAD catalog number"""

    epoch: str = ""
    """Epoch time (ISO 8601 format)"""
    mean_motion: float = 0.0
    """Mean motion (revolutions per day)"""
```

**Class variables:**

```python
class LagrangeInterpolator(Interpolator):
    MAX_BUFFER_SIZE = 80
    """Maximum allowed number of buffered samples."""
```

**Instance variables in `__init__` methods:**

```python
class Interpolator:
    def __init__(self, dimension: int = 1) -> None:
        self.independent_values: list[float] = []
        """The ordered independent variable values used for interpolation."""
        self.dependent_values: list[np.ndarray] = []
        """The corresponding dependent vectors for each stored sample."""
        
        self.previous_independent_value = float("-inf")
        """Track monotonicity of input samples; newer values must be greater."""
```

**Documentation guidelines:**

- Use triple-quote docstrings (`"""..."""`) for all variable documentation
- Place the docstring on the line immediately following the variable definition
- Do **not** use hash-style comments (`#`) for variable documentation
- Hash comments may still be used for implementation notes within method bodies
- Include units in parentheses when applicable (e.g., `(degrees)`, `(m³/s²)`)
- Specify value ranges or constraints when relevant (e.g., `0.0 to 1.0`)
- Mention the format for string fields (e.g., `ISO 8601 format`, `TLE exponential format`)

### 9.2 `to_dict` method

Dataclasses that need dict serialisation provide a `to_dict()` method
using `dataclasses.asdict`:

```python
def to_dict(self) -> dict[str, object]:
    """Convert to a plain dictionary."""
    return asdict(self)
```

### 9.3 `from_source` classmethod

Structured classes that can be loaded from a file provide a
`from_source` classmethod with a documented `source` parameter and a
`Returns` section:

```python
@classmethod
def from_source(cls, source: TextIO | str | Path) -> CcsdsOmm:
    """Construct a :class:`CcsdsOmm` from a file or stream.

    Parameters
    ----------
    source : TextIO | str | Path
        A readable text stream, file path string, or :class:`Path`.

    Returns
    -------
    CcsdsOmm
        Parsed OMM instance.
    """
```

### 9.4 `to_file` method

Structured classes that can be written to a file provide a `to_file`
method with a documented `dest` parameter:

```python
def to_file(self, dest: TextIO | str | Path) -> None:
    """Write this OMM to a file or stream.

    Parameters
    ----------
    dest : TextIO | str | Path
        A writable text stream, file path string, or :class:`Path`.
    """
```

---

## 10. `__repr__` Methods

All structured classes implement `__repr__` returning a concise,
unambiguous string showing the class name and key identifying fields:

```python
def __repr__(self) -> str:
    return (
        f"CcsdsOmm(object={self.object_name!r}, "
        f"norad_cat_id={self.norad_cat_id}, "
        f"epoch={self.epoch!r})"
    )
```

---

## 11. CLI Entry Points

Modules that can be run directly include a `if __name__ == "__main__":`
block with a usage message printed to `stderr` on missing arguments:

```python
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m common.oem <oem_file>", file=sys.stderr)
        sys.exit(1)
```

---

## 12. Imports

### 12.1 Order

Follow PEP 8 import ordering:
1. `from __future__ import annotations` (always first if present)
2. Standard library imports
3. Third-party imports
4. Local imports

### 12.2 `from __future__ import annotations`

Include `from __future__ import annotations` at the top of every module
to enable postponed evaluation of annotations:

```python
from __future__ import annotations
```

### 12.3 Import modules as a whole — never import individual names

Always import a module as a whole using `import X as Y`. Do **not** use
`from X import name` to pull individual classes, functions, or constants
into the local namespace:

```python
# Correct — import the whole module
import common.kepler as kepler
import common.oem as oem
import common.tle as tle

# Use with module prefix
kepler.MU_EARTH
oem.parse_oem_state_line(line)
tle.read_tle(stream)

# Wrong — importing individual names
from common.kepler import MU_EARTH, compute_brouwer_short_period_corrections
from common.oem import parse_oem_state_line
from common.tle import Tle
```

This rule applies to all local (`common.*`) imports. Standard-library and
third-party modules may still use `from X import Y` where idiomatic
(e.g. `from __future__ import annotations`, `from pathlib import Path`,
`from datetime import datetime`).
