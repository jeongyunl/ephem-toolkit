# Plan: Implementing `KeplerPropagator` Class

## 1. Goal

Implement `KeplerPropagator` class in `core/kepler.py` following the `KeplerPropagator` 
interface defined in [PROPAGATOR_INTERFACE_DESIGN.md](PROPAGATOR_INTERFACE_DESIGN.md).

## 2. Current State

`core/kepler.py` provides function-based two-body Keplerian propagation:
- `propagate_kepler(keplerian_elements, time_elapsed_s, mu_m3_s2=EARTH_GM)` - propagates 
  elements forward in time
- `keplerian_to_cartesian(keplerian_elements, mu_m3_s2=EARTH_GM)` - converts elements to 
  Cartesian state
- Element convention: `[a, e, i, omega, RAAN, true_anomaly]`

No class-based interface exists yet.

## 3. Design

### 3.1 New Class in `core/propagator/kepler.py`

```python
class KeplerPropagator(propagator.KeplerPropagator):
    """Two-body Keplerian propagator.
    
    Propagates orbital elements assuming only gravitational attraction from
    a central body (no perturbations). Element[5] is true anomaly.
    """
    
    anomaly_type = propagator.AnomalyType.TRUE
    
    def __init__(self, mu_m3_s2: float = EARTH_GM, 
                 initial_state: propagator.KeplerianState | None = None):
        """Initialize Kepler propagator.
        
        Parameters
        ----------
        mu_m3_s2 : float
            Gravitational parameter (m³/s²). Defaults to Earth's GM.
        initial_state : KeplerianState, optional
            Initial elements + epoch. If provided, calls set_initial_state.
        """
        self.mu_m3_s2 = mu_m3_s2
        if initial_state is not None:
            self.set_initial_state(initial_state)
    
    def propagate_elements(
        self, keplerian_elements: np.ndarray, time_elapsed_s: float
    ) -> np.ndarray:
        """Propagate Keplerian elements forward by time_elapsed_s."""
        return propagate_kepler(keplerian_elements, time_elapsed_s, self.mu_m3_s2)
```

Inherits from `KeplerPropagator`, which provides:
- `set_initial_state(initial_state: KeplerianState)`
- `get_initial_epoch() -> datetime`
- `propagate_to(target_epoch_utc: datetime) -> np.ndarray` (Cartesian)
- `propagate_by(time_elapsed_s: float) -> np.ndarray` (Cartesian)
- `propagate_history(target_epochs_utc: list[datetime]) -> dict[datetime, np.ndarray]`

Only `propagate_elements` needs implementation; rest inherited.

### 3.2 Required Imports

In `core/propagator/kepler.py`:
```python
from datetime import datetime
from ephem_toolkit.core import kepler
from ephem_toolkit.core.propagator import base
```

### 3.3 Dependencies

Requires `core/propagator/base.py` with:
- `Propagator` ABC
- `KeplerPropagator` base class
- `KeplerianState` dataclass
- `AnomalyType` enum

Wraps `core.kepler.propagate_kepler()` function.

## 4. Migration Steps

1. **Create `core/propagator/` submodule**:
   - `core/propagator/__init__.py` - exports public API
   - `core/propagator/base.py` - base interfaces (`Propagator`, `KeplerPropagator`, 
     `KeplerianState`, `AnomalyType`)

2. **Add `core/propagator/kepler.py`**:
   - Import from `core.kepler` and `core.propagator.base`
   - Implement `KeplerPropagator` class (wraps `propagate_kepler` function)
   - Existing `core/kepler.py` functions remain unchanged

3. **Add unit tests** in `tests/ephem_toolkit/core/propagator/test_kepler.py`:
   - `propagate_elements` matches `propagate_kepler` exactly
   - `propagate_to` produces Cartesian state consistent with manual conversion
   - `propagate_by` works correctly with elapsed time
   - `get_initial_epoch` returns correct epoch from `KeplerianState`
   - Constructor with/without initial state
   - Custom `mu` parameter

4. **Update `core/propagator/__init__.py`** to export `KeplerPropagator`.

5. **Update documentation**:
   - Add propagator submodule to `docs/CORE_LIBRARY_ORBITAL_ELEMENTS.md`
   - Note function-based API remains available

6. **No breaking changes**: Existing `propagate_kepler` function stays; class is additive.

## 5. Example Usage

```python
from datetime import datetime
from ephem_toolkit.core.propagator import KeplerPropagator, KeplerianState
import numpy as np

# Create propagator
elements = np.array([7000e3, 0.001, 51.6, 0, 0, 0])  # ISS-like orbit
initial_state = KeplerianState(
    elements=elements,
    epoch_utc=datetime(2024, 1, 1, 0, 0, 0)
)
prop = KeplerPropagator(initial_state=initial_state)

# Propagate to specific epoch
target = datetime(2024, 1, 1, 1, 30, 0)
cartesian_state = prop.propagate_to(target)  # [x, y, z, vx, vy, vz]

# Or propagate by elapsed time
state_after_1hr = prop.propagate_by(3600.0)

# Or get element-level result
propagated_elements = prop.propagate_elements(elements, 3600.0)
```

## 6. Testing Strategy

Minimal test coverage (function already tested):
- One test verifying `propagate_elements` delegates to `propagate_kepler` correctly
- One test verifying `propagate_to` produces expected Cartesian output
- One test verifying epoch handling via `KeplerianState`

No need to re-test orbital mechanics; focus on interface compliance.

## 7. Future Work

After this lands:
- `MeanJ2Propagator` in `core/propagator/mean_j2.py` (same pattern, `AnomalyType.MEAN`)
- `Sgp4Propagator` in `core/propagator/sgp4.py` (implements `Propagator[Tle]` directly)
- `NumericalPropagator` in `core/propagator/numerical.py` (wraps Tudat integrator)
- CLI tools (`propagate_kepler`) optionally use class interface
