# Core Library - Orbital Elements & Propagators

This document covers Keplerian orbital element conversions, mean element calculations,
and the propagator class hierarchy in the `core/` directory.

## Table of Contents

1. [Propagator Interface (`core.propagator`)](#propagator-interface-corepropagator)
2. [KeplerPropagator + Element Utilities (`core.propagator.kepler`)](#keplerpropagator-corepropagatorkeplery)
3. [BrouwerJ2Propagator + Brouwer Utilities (`core.propagator.brouwer_j2`)](#brouwerj2propagator-corepropagatorbrouwer_j2)
4. [Sgp4Propagator (`core.propagator.sgp4`)](#sgp4propagator-corepropagatorssgp4)
5. [NumericalPropagator (`core.propagator.numerical`)](#numericalpropagator-corepropagatornumerical)

---

## Propagator Interface (`core.propagator`)

**Module**: `ephem_toolkit.core.propagator`

All propagators share a common abstract base class `Propagator[InitialStateT]` defined
in `core/propagator/base.py`. The interface is a **flat hierarchy** — all concrete
propagators implement `Propagator` directly with no intermediate ABCs.

### Design Principles

- **`__init__` is for model config** (`mu`, `R_e_m`, `J2`, integrator settings)
- **`set_initial_state` is for "here is where/when we start"** (epoch + state)
- **All propagators return Cartesian states** `[x, y, z, vx, vy, vz]` in SI units
- **All epochs are TT seconds since J2000** (2000-01-01 12:00:00 TT)
- **`reference_epoch_s` advances** after each `propagate_to`/`propagate_by` call
- **`get_initial_epoch_s()` is fixed** — never changes after construction

### `OutputMode` Enum

```python
from ephem_toolkit.core.propagator import OutputMode

OutputMode.NONE        # advance reference epoch, return None
OutputMode.FINAL       # return (epoch_s, state_array)
OutputMode.TRAJECTORY  # return [(epoch_s, state_array), ...] from previous reference epoch
```

### `KeplerianState` Dataclass

Pairs Keplerian elements with their epoch. Used by `KeplerPropagator` and `BrouwerJ2Propagator`.

```python
from ephem_toolkit.core.propagator import KeplerianState
import numpy as np

state = KeplerianState(
    elements=np.array([7000e3, 0.01, 0.1, 0.3, 0.2, 1.0]),  # [a, e, i, ω, Ω, anomaly]
    epoch_s=0.0,  # TT seconds since J2000
)
# state.elements is read-only (frozen dataclass + writeable=False)
```

### `AnomalyType` Enum

Tags the semantic meaning of element[5]:

```python
AnomalyType.TRUE   # KeplerPropagator — element[5] is true anomaly
AnomalyType.MEAN   # BrouwerJ2Propagator — element[5] is mean anomaly
```

### Base `Propagator` API

```python
prop.set_initial_state(initial_state)       # set/reset initial state
prop.get_initial_epoch_s() -> float         # fixed initial epoch (TT s since J2000)
prop.reference_epoch_s -> float             # current reference epoch (advances)
prop.propagate_to(epoch_s, output=OutputMode.FINAL)   # propagate to absolute epoch
prop.propagate_by(elapsed_s, output=OutputMode.FINAL) # propagate by elapsed seconds
```

---

## KeplerPropagator (`core.propagator.kepler`)

**Module**: `ephem_toolkit.core.propagator.kepler`

Two-body Keplerian propagator. Only true anomaly changes; `a`, `e`, `i`, `ω`, `Ω` are constant.

- `anomaly_type = AnomalyType.TRUE` — element[5] is **true anomaly**
- Initial state: **osculating** Keplerian elements

### Usage

```python
from ephem_toolkit.core.propagator import KeplerPropagator, KeplerianState, OutputMode
from ephem_toolkit.core.consts import EARTH_GRAVITATIONAL_PARAMETER_M3_S2
import numpy as np

# Construct with initial state at epoch
state = KeplerianState(
    elements=np.array([7000e3, 0.001, np.radians(51.6), 0.0, 0.0, 0.0]),
    epoch_s=0.0,
)
prop = KeplerPropagator(initial_state=state, mu_m3_s2=EARTH_GRAVITATIONAL_PARAMETER_M3_S2)

# Propagate to absolute epoch
epoch_s, cartesian = prop.propagate_to(3600.0, output=OutputMode.FINAL)
# cartesian: np.ndarray shape (6,) [x, y, z, vx, vy, vz] in m and m/s

# Propagate by elapsed time
epoch_s, cartesian = prop.propagate_by(3600.0, output=OutputMode.FINAL)

# Advance without returning state
prop.propagate_to(7200.0, output=OutputMode.NONE)

# Get trajectory
trajectory = prop.propagate_to(10800.0, output=OutputMode.TRAJECTORY)
# trajectory: list of (epoch_s, cartesian) tuples
```

### Constructor

```python
KeplerPropagator(
    initial_state: KeplerianState,
    mu_m3_s2: float = EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
)
```

---

## BrouwerJ2Propagator (`core.propagator.brouwer_j2`)

**Module**: `ephem_toolkit.core.propagator.brouwer_j2`

Brouwer (1959) J2 secular mean-element propagator. Applies J2 short-period corrections
to convert mean elements to osculating Cartesian state.

- `anomaly_type = AnomalyType.MEAN` — element[5] is **mean anomaly**
- Initial state: **Brouwer mean elements** (not osculating, not SGP4/TLE mean elements)
- `a`, `e`, `i` are constant; `ω`, `Ω`, `M` evolve via J2 secular rates

### Usage

```python
from ephem_toolkit.core.propagator import BrouwerJ2Propagator, KeplerianState, OutputMode
from ephem_toolkit.core.consts import (
    EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    EARTH_EQUATORIAL_RADIUS_M,
    EARTH_J2,
)
import numpy as np

# Initial state must be Brouwer mean elements
state = KeplerianState(
    elements=np.array([7000e3, 0.001, np.radians(51.6), 0.0, 0.0, 0.0]),
    epoch_s=0.0,
)
prop = BrouwerJ2Propagator(
    initial_state=state,
    mu_m3_s2=EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    R_e_m=EARTH_EQUATORIAL_RADIUS_M,
    J2=EARTH_J2,
)

epoch_s, cartesian = prop.propagate_to(3600.0, output=OutputMode.FINAL)
```

### Constructor

```python
BrouwerJ2Propagator(
    initial_state: KeplerianState,
    mu_m3_s2: float,                          # required (no default)
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
    J2: float = EARTH_J2,
)
```

---

## Sgp4Propagator (`core.propagator.sgp4`)

**Module**: `ephem_toolkit.core.propagator.sgp4`

SGP4 propagator wrapping TudatPy's `environment_setup.ephemeris.sgp4`. Requires `tudatpy`.

- Initial state: `Tle` object (from `core.tle`)
- Epoch derived from TLE `epoch_year`/`epoch_day` fields
- TudatPy import is deferred — only triggered when `set_initial_state` is called

### Usage

```python
from ephem_toolkit.core.propagator import Sgp4Propagator, OutputMode
from ephem_toolkit.core.tle import read_tle

tle_obj = read_tle("satellite.tle")
prop = Sgp4Propagator(initial_state=tle_obj)

epoch_s, cartesian = prop.propagate_to(
    prop.get_initial_epoch_s() + 3600.0,
    output=OutputMode.FINAL,
)
```

### Constructor

```python
Sgp4Propagator(initial_state: Tle)
```

---

## Orbital Element Utilities (`core.propagator.kepler`)

**Module**: `ephem_toolkit.core.propagator.kepler`

All Keplerian element conversion utilities live alongside `KeplerPropagator`.

### Element Index Constants

```python
from ephem_toolkit.core.propagator.kepler import (
    SEMI_MAJOR_AXIS_INDEX,       # 0 — semi-major axis (m)
    ECCENTRICITY_INDEX,          # 1 — eccentricity (dimensionless)
    INCLINATION_INDEX,           # 2 — inclination (rad)
    ARGUMENT_OF_PERIAPSIS_INDEX, # 3 — argument of periapsis (rad)
    RAAN_INDEX,                  # 4 — right ascension of ascending node (rad)
    TRUE_ANOMALY_INDEX,          # 5 — true anomaly (rad)
)
```

### Cartesian ↔ Keplerian Conversion

#### `cartesian_to_keplerian(cartesian_state_vector, mu_m3_s2) -> np.ndarray`
Convert Cartesian state `[x, y, z, vx, vy, vz]` (m, m/s) to osculating Keplerian elements
`[a, e, i, ω, Ω, θ]` (m, rad).

#### `keplerian_to_cartesian(keplerian_elements, mu_m3_s2=EARTH_GM) -> np.ndarray`
Convert Keplerian elements `[a, e, i, ω, Ω, θ]` to Cartesian state `[x, y, z, vx, vy, vz]`.

### Anomaly Conversions

#### `true_to_eccentric_anomaly(true_anomaly, eccentricity) -> float`
#### `eccentric_to_true_anomaly(eccentric_anomaly, eccentricity) -> float`
#### `eccentric_to_mean_anomaly(eccentric_anomaly, eccentricity) -> float`
#### `mean_to_eccentric_anomaly(mean_anomaly, eccentricity, tol=1e-14, max_iter=100) -> float`
Solve Kepler's equation M = E − e·sin(E) via Newton-Raphson.
#### `mean_to_true_anomaly(mean_anomaly, eccentricity, tol=1e-12) -> float`
#### `true_to_mean_anomaly(true_anomaly, eccentricity) -> float`

### Mean Motion Utilities

#### `mean_motion_to_semi_major_axis(mean_motion_rev_per_day, mu_m3_s2=EARTH_GM) -> float`
Convert mean motion (rev/day) to semi-major axis (m) via Kepler's third law.

#### `semi_major_axis_to_mean_motion(semi_major_axis_m, mu_m3_s2=EARTH_GM) -> float`
Convert semi-major axis (m) to mean motion (rev/day) via Kepler's third law.

---

## Brouwer Mean Element Utilities (`core.propagator.brouwer_j2`)

**Module**: `ephem_toolkit.core.propagator.brouwer_j2`

All Brouwer mean element utilities live alongside `BrouwerJ2Propagator`.

### Mean ↔ Osculating Conversion

#### `compute_brouwer_short_period_corrections(mean_elements, R_e_m=..., J2=...) -> np.ndarray`
Apply Brouwer first-order J2 short-period corrections to convert mean elements
`[a, e, i, ω, Ω, M]` to osculating elements `[a, e, i, ω, Ω, θ]`.

#### `brouwer_mean_to_osculating(mean_elements, R_e_m=..., J2=...) -> np.ndarray`
Alias for `compute_brouwer_short_period_corrections`.

#### `osculating_to_brouwer_mean(osculating_elements, R_e_m=..., J2=..., max_iter=20, tol_m=1e-12) -> np.ndarray`
Convert osculating elements `[a, e, i, ω, Ω, θ]` to Brouwer mean elements
`[a, e, i, ω, Ω, M]` via iterative inversion.

### Cartesian Conversion

#### `brouwer_mean_to_cartesian(mean_elements, mu_m3_s2, R_e_m=..., J2=...) -> np.ndarray`
Convert Brouwer mean elements to Cartesian state via short-period corrections.

### J2 Secular Propagation

#### `propagate_brouwer_j2(mean_elements, time_elapsed_s, mu_m3_s2, R_e_m=..., J2=...) -> np.ndarray`
Propagate Brouwer mean elements forward in time using J2 secular rates.
`a`, `e`, `i` are constant; `ω`, `Ω`, `M` evolve.

#### `compute_raan_rate(mean_elements, mu_m3_s2, R_e_m, J2) -> float`
Compute the J2 secular RAAN drift rate (rad/s).

---

## NumericalPropagator (`core.propagator.numerical`)

**Module**: `ephem_toolkit.core.propagator.numerical`

Perturbed numerical propagator wrapping TudatPy's translational dynamics simulator.
Requires `tudatpy`. All tudatpy imports are deferred inside engine functions.

- Initial state: `NumericalInitialState` (Cartesian state + TT epoch)
- Model config: `NumericalPropagatorConfig` (force model + integrator settings)
- `_propagate_to_impl` re-runs the integrator from scratch each call (simple; caching is a future optimization)
- `_propagate_trajectory_impl` overridden to return the full `state_history` from a single integrator run

### Data Types

```python
from ephem_toolkit.core.propagator.numerical import (
    NumericalPropagatorConfig,
    NumericalInitialState,
)
import numpy as np

config = NumericalPropagatorConfig(
    satellite_name="MySat",
    satellite_mass_kg=30.0,
    integrator_method="rkdp_87",           # see SUPPORTED_INTEGRATOR_METHODS
    integrator_step_size_values_s=(10.0, 1.0, 300.0),  # (initial, min, max) for variable-step
    earth_spherical_harmonic_gravity_degree=5,
    earth_spherical_harmonic_gravity_order=5,
    satellite_drag_area_m2=0.045,
    is_srp_on=True,
    srp_coefficient=1.2,
    is_earth_drag_on=True,
    satellite_drag_coefficient=2.2,
    is_moon_gravity_on=True,
    is_sun_gravity_on=True,
    is_venus_gravity_on=False,
    is_mars_gravity_on=False,
)

initial_state = NumericalInitialState(
    state_m_m_s=np.array([-2700816.14, -3314092.80, 5266346.42,
                            5168.61, -5597.55, -2131.98]),  # [x,y,z,vx,vy,vz] m, m/s
    epoch_s=0.0,  # TT seconds since J2000
)
```

### Usage

```python
from ephem_toolkit.core.propagator.numerical import (
    NumericalPropagator,
    NumericalPropagatorConfig,
    NumericalInitialState,
    load_spice_kernels,
)
from ephem_toolkit.core.propagator.base import OutputMode

# Load SPICE kernels once before propagation
load_spice_kernels()

prop = NumericalPropagator(config=config, initial_state=initial_state)

# Propagate to absolute epoch (re-runs integrator from initial state)
epoch_s, cartesian = prop.propagate_to(3600.0, output=OutputMode.FINAL)

# Get full trajectory in one integrator run
trajectory = prop.propagate_to(3600.0, output=OutputMode.TRAJECTORY)
# trajectory: list of (epoch_s, cartesian) tuples — all integrator steps
```

### Constructor

```python
NumericalPropagator(
    config: NumericalPropagatorConfig,
    initial_state: NumericalInitialState,
)
```

### Engine Constants

```python
from ephem_toolkit.core.propagator.numerical import (
    SUPPORTED_INTEGRATOR_METHODS,   # tuple of valid integrator method strings
    INTEGRATOR_METHOD_DESCRIPTIONS, # dict mapping method -> human-readable description
    DEFAULT_INTEGRATOR_METHOD,      # "rkdp_87" (Dormand-Prince 8(7))
)
```

### Engine Functions

These are called internally by `NumericalPropagator` but are also usable directly:

#### `load_spice_kernels() -> None`
Load required SPICE kernels (leapseconds, planetary constants, Earth rotation, ephemerides).
Must be called once before any propagation.

#### `run_numerical_propagation(config, initial_state, target_epoch_s) -> (state_history, dep_var_dict, dep_vars_to_save)`
Run the integrator from `initial_state.epoch_s` to `target_epoch_s`. Returns raw results
with no file I/O. Raises exceptions rather than calling `sys.exit`.

- `state_history`: `dict[float, np.ndarray]` — TT epoch → Cartesian state (6,)
- `dep_var_dict`: Tudat dependent-variable dictionary
- `dep_vars_to_save`: list of dependent-variable save settings (needed for CSV writing)
