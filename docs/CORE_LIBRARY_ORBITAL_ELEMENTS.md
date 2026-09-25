# Core Library - Orbital Elements & Propagators

This document covers Keplerian orbital element conversions, mean element calculations,
and the propagator class hierarchy in the `core/` directory.

## Table of Contents

1. [Propagator Interface (`core.propagator`)](#propagator-interface-corepropagator)
2. [KeplerPropagator + Element Utilities (`core.propagator.kepler`)](#keplerpropagator-corepropagatorkepler)
3. [BrouwerJ2Propagator + Brouwer Utilities (`core.propagator.brouwer_j2`)](#brouwerj2propagator-corepropagatorbrouwer_j2)
4. [DSSTPropagator (`core.propagator.dsst`)](#dsstpropagator-corepropagatordsst)
5. [Sgp4Propagator (`core.propagator.sgp4`)](#sgp4propagator-corepropagatorsgp4)
6. [NumericalPropagator (`core.propagator.numerical`)](#numericalpropagator-corepropagatornumerical)

---

## Propagator Interface (`core.propagator`)

**Module**: `ephem_toolkit.core.propagator`

All propagators share the abstract base class `Propagator[InitialStateT]` defined
in `core/propagator/base.py`. The concrete propagators currently inherit it directly.

### Design Principles

- **Constructors accept model configuration and usually an initial state**
- **`set_initial_state` can set or reset the starting epoch and state**
- **All propagators return Cartesian states** `[x, y, z, vx, vy, vz]` in SI units
- **Cartesian frame depends on the propagator and is not converted by the base class**
- **All epochs are TT seconds since J2000** (2000-01-01 12:00:00 TT)
- **`reference_epoch_s` advances** after each successful `propagate_to`/`propagate_by` call
- **`get_initial_epoch_s()` stays fixed during propagation** and changes only when the initial state is reset

### `OutputMode` Enum

```python
from ephem_toolkit.core.propagator import OutputMode

OutputMode.NONE        # advance reference epoch, return None
OutputMode.FINAL       # return (epoch_s, state_array)
OutputMode.TRAJECTORY  # return trajectory samples; concrete behavior varies
```

The base implementation returns a one-sample trajectory at the target epoch. `NumericalPropagator` overrides it and returns the integrator history from the initial epoch through the target, even after the reference epoch has advanced. `propagate_to` rejects targets earlier than the current reference epoch; `propagate_by` requires a non-negative elapsed time and measures it from that reference epoch.

### `KeplerianState` Dataclass

Pairs Keplerian elements with their epoch. Used by `KeplerPropagator`, `BrouwerJ2Propagator`, and `DSSTPropagator`.

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
AnomalyType.MEAN   # BrouwerJ2Propagator and DSSTPropagator — element[5] is mean anomaly
```

### Base `Propagator` API

```python
prop.set_initial_state(initial_state)       # set/reset initial state
prop.get_initial_epoch_s() -> float         # fixed initial epoch (TT s since J2000)
prop.reference_epoch_s -> float             # current reference epoch (advances)
prop.propagate_to(epoch_s, output=OutputMode.FINAL)   # propagate to absolute epoch
prop.propagate_by(elapsed_s, output=OutputMode.FINAL) # propagate by elapsed seconds
```

All concrete constructors set an initial state, and `set_initial_state()` can reset it later. Resetting also resets `reference_epoch_s` to the new initial epoch; `get_initial_epoch_s()` is fixed only until that reset.

---

## KeplerPropagator (`core.propagator.kepler`)

**Module**: `ephem_toolkit.core.propagator.kepler`

Elliptic two-body Keplerian propagator. Only true anomaly changes; `a`, `e`, `i`, `ω`, `Ω` are constant.

- `anomaly_type = AnomalyType.TRUE` — element[5] is **true anomaly**
- Initial state: **osculating** Keplerian elements, with element[5] as true anomaly

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
    mu_m3_s2: float = EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
    J2: float = EARTH_J2,
)
```

---

## DSSTPropagator (`core.propagator.dsst`)

**Module**: `ephem_toolkit.core.propagator.dsst`

DSST semi-analytical propagator using classical Keplerian elements in the J2000 frame. Its initial state must contain **DSST mean elements** `[a, e, i, ω, Ω, M]`, which are not interchangeable with Brouwer or SGP4/TLE mean elements.

`DSSTPropagator` evolves secular rates and converts the mean elements to Cartesian state using a J2 short-period correction. J3/J4 secular-rate terms and a simplified exponential-atmosphere drag model are implemented. Although `DsstPerturbations` defines SRP and Sun/Moon flags, those perturbations are not currently applied; `atmosphere_model` and `ephemeris_source` are also configuration fields without current effect.

### Configuration and Constructor

```python
DsstPerturbations(
    include_j2=True,
    include_j3=False,
    include_j4=False,
    include_drag=False,
    # Drag/SRP parameters, third-body flags, and gravity constants are configurable.
)

DSSTPropagator(
    initial_state: KeplerianState,
    perturbations: DsstPerturbations | None = None,
    mu_m3_s2: float = EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
)
```

### Mean Element Utilities

- `compute_dsst_j2_short_period_corrections(mean_elements, R_e_m=EARTH_EQUATORIAL_RADIUS_M, J2=EARTH_J2)`: Apply the implemented J2 short-period correction to convert DSST mean elements to osculating elements.
- `dsst_mean_to_osculating(mean_elements, epoch_s, perturbations=None)`: Convert mean elements to osculating elements; the current short-period correction is J2-only, and `epoch_s` is reserved but unused.
- `osculating_to_dsst_mean(osculating_elements, epoch_s, perturbations=None, max_iter=20, tolerance=1e-10)`: Iteratively invert the short-period correction; raises `RuntimeError` if it does not converge.
- `dsst_mean_to_cartesian(mean_elements, mu_m3_s2, epoch_s, perturbations=None)`: Convert DSST mean elements to a Cartesian state.

---

## Sgp4Propagator (`core.propagator.sgp4`)

**Module**: `ephem_toolkit.core.propagator.sgp4`

SGP4 propagator wrapping TudatPy's `environment_setup.ephemeris.sgp4`. Requires `tudatpy`.

- Initial state: `Tle` object (from `core.tle`)
- Epoch derived from TLE `epoch_year`/`epoch_day` fields
- The TudatPy import is deferred until initialization, but the constructor immediately calls `set_initial_state`, so constructing this propagator requires TudatPy.

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
    MEAN_ANOMALY_INDEX,          # alias for index 5 when the element is mean anomaly
)
```

### Cartesian ↔ Keplerian Conversion

#### `cartesian_to_keplerian(cartesian_state_vector, mu_m3_s2) -> np.ndarray`
Convert Cartesian state `[x, y, z, vx, vy, vz]` (m, m/s) to osculating Keplerian elements
`[a, e, i, ω, Ω, θ]` (m, rad). Accepts one state with shape `(6,)` or a batch `(N, 6)`.

#### `keplerian_to_cartesian(keplerian_elements, mu_m3_s2=EARTH_GRAVITATIONAL_PARAMETER_M3_S2) -> np.ndarray`
Convert Keplerian element set(s) `[a, e, i, ω, Ω, θ]` to Cartesian state(s) `[x, y, z, vx, vy, vz]`. Supports shapes `(6,)` and `(N, 6)`; the default gravitational parameter is `EARTH_GRAVITATIONAL_PARAMETER_M3_S2`.

### Anomaly Conversions

#### `true_to_eccentric_anomaly(true_anomaly, eccentricity) -> float`
#### `eccentric_to_true_anomaly(eccentric_anomaly, eccentricity) -> float`
#### `eccentric_to_mean_anomaly(eccentric_anomaly, eccentricity) -> float`
#### `mean_to_eccentric_anomaly(mean_anomaly, eccentricity, tol=1e-14, max_iter=100) -> float`
Solve Kepler's equation M = E − e·sin(E) via Newton-Raphson.
#### `mean_to_true_anomaly(mean_anomaly, eccentricity, tol=1e-12) -> float`
#### `true_to_mean_anomaly(true_anomaly, eccentricity) -> float`

### Mean Motion Utilities

#### `mean_motion_to_semi_major_axis(mean_motion_rev_per_day, mu_m3_s2=EARTH_GRAVITATIONAL_PARAMETER_M3_S2) -> float`
Convert mean motion (rev/day) to semi-major axis (m) via Kepler's third law. The default gravitational parameter is `EARTH_GRAVITATIONAL_PARAMETER_M3_S2`.

#### `semi_major_axis_to_mean_motion(semi_major_axis_m, mu_m3_s2=EARTH_GRAVITATIONAL_PARAMETER_M3_S2) -> float`
Convert semi-major axis (m) to mean motion (rev/day) via Kepler's third law. The default gravitational parameter is `EARTH_GRAVITATIONAL_PARAMETER_M3_S2`.

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

Secular propagation is provided by `BrouwerJ2Propagator.propagate_to()` and `propagate_by()`, not by a standalone `propagate_brouwer_j2()` function. `a`, `e`, and `i` remain constant; `ω`, `Ω`, and `M` evolve.

#### `compute_raan_rate(keplerian_elements, mu_m3_s2, R_e_m=EARTH_EQUATORIAL_RADIUS_M, J2=EARTH_J2) -> float`
Compute the J2 secular RAAN drift rate (rad/s).

---

## NumericalPropagator (`core.propagator.numerical`)

**Module**: `ephem_toolkit.core.propagator.numerical`

Perturbed numerical propagator wrapping TudatPy's translational dynamics simulator.
Requires `tudatpy`, which is imported at module import time. Required SPICE kernels are also loaded during module import.

- Initial state: `NumericalInitialState` (Cartesian state + TT epoch)
- Model config: `NumericalPropagatorConfig` (force model + integrator settings)
- `_propagate_to_impl` re-runs the integrator from scratch each call (simple; caching is a future optimization)
- `_propagate_trajectory_impl` overridden to return the full `state_history` from a single integrator run, from the initial epoch through the target epoch

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

Every `NumericalPropagatorConfig` field is required; the example explicitly supplies `integrator_method` even though `DEFAULT_INTEGRATOR_METHOD` is available as a constant. `integrator_step_size_values_s` must contain one value for fixed-step integration or three values `(initial, minimum, maximum)` for variable-step integration.

### Usage

```python
from ephem_toolkit.core.propagator.numerical import (
    NumericalPropagator,
    NumericalPropagatorConfig,
    NumericalInitialState,
)
from ephem_toolkit.core.propagator.base import OutputMode

prop = NumericalPropagator(config=config, initial_state=initial_state)

# Propagate to absolute epoch (re-runs integrator from initial state)
epoch_s, cartesian = prop.propagate_to(3600.0, output=OutputMode.FINAL)

# Get full trajectory in one integrator run
trajectory = prop.propagate_to(3600.0, output=OutputMode.TRAJECTORY)
# trajectory: all integrator steps from initial_state.epoch_s to the target
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
    DEFAULT_INTEGRATOR_TOLERANCE,   # 1.0e-10 relative and absolute variable-step tolerances
)
```

### Engine Helpers and Results

The environment-building helpers are static methods on `NumericalPropagator`, not standalone functions:

- `create_environment_and_bodies(config)`
- `create_acceleration_models(config, bodies, bodies_to_propagate, central_bodies)`
- `create_dependent_variables_to_save(config)`
- `create_translational_propagator_settings(...)`

There is no standalone `load_spice_kernels()` or `run_numerical_propagation()` function in this module. Kernel loading occurs during module import. The propagator exposes the most recent run through these properties:

- `state_history`: sorted `list[tuple[float, np.ndarray]]` of TT epochs and Cartesian states
- `dependent_variable_dictionary`: Tudat dependent-variable dictionary, or `None` before a run
- `dependent_variable_save_settings`: dependent-variable settings used by the integrator
