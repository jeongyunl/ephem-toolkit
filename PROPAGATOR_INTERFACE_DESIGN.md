# Design: Common Propagator Interface for `core`

## 1. Goal

Introduce a shared interface (`core/propagator.py`) covering **all four** propagators the
project has or plans to have:

- `core.kepler` — two-body Keplerian element propagation (existing, function-based)
- `core.mean_kepler` — J2 secular mean-element propagation (existing, function-based)
- TLE/OMM SGP4 propagation — currently inline in
  [propagate_omm/__main__.py](../src/ephem_toolkit/propagate_omm/__main__.py)'s
  `propagate_tle_sgp4`/`propagate_omm_sgp4`, wrapping TudatPy's
  `environment_setup.ephemeris.sgp4`
- The Tudat-based perturbed numerical propagator — currently in `propagate_orbit/`, not
  yet moved to `core` (see
  [docs/PROPAGATE_ORBIT_CORE_MODULARIZATION_PLAN.md](PROPAGATE_ORBIT_CORE_MODULARIZATION_PLAN.md))

This is the "Propagator interface/class hierarchy" item in `TODO.md`. The four
propagators differ substantially in inputs (Keplerian elements vs. TLE lines vs.
Cartesian state + force model config) and in what a single call naturally produces (one
element/state vector vs. a whole trajectory), so the interface is a **flat hierarchy**:
a single `Propagator` ABC that all four satisfy directly. Each concrete propagator
implements `Propagator[InitialStateT]` with its own state type (`KeplerianState`, `Tle`,
`NumericalInitialState`).

## 2. Analysis of Existing/Planned Propagators

| | `kepler.propagate_kepler` | `mean_kepler.propagate_mean_j2` | SGP4 (`propagate_tle_sgp4`) | Numerical (Tudat) |
|---|---|---|---|---|
| Initial state form | Keplerian elements | Keplerian (mean) elements | TLE line1/line2 | Cartesian state + epoch |
| Model config | `mu` (optional) | `mu`, `R_e_m`, `J2` | none beyond the TLE itself | force-model settings (gravity degree/order, drag, SRP, third bodies, integrator method/step) |
| Time parameter | elapsed seconds (Δt) | elapsed seconds (Δt) | absolute epoch (queried per-sample against a built ephemeris) | integration span (start → stop), stepped by the integrator |
| Natural output of one call | one element vector | one element vector | one Cartesian state per queried epoch | a full `state_history` (`dict[epoch, state]`) built in one integrator run |

Key takeaway: `propagate_kepler`/`propagate_mean_j2` share the same **element vector
convention** (`[a, e, i, ω, Ω, anomaly]`) and **elapsed-time call shape**
`(elements, time_elapsed_s) -> elements` (differing in extra config and
true-vs-mean anomaly semantics — see the original analysis retained below). SGP4 and the
numerical propagator, however, don't operate on Keplerian elements at all, and both are
naturally queried/evaluated **against an absolute epoch** built from a fixed initial
model (an SGP4 ephemeris object; a configured Tudat environment + acceleration model),
rather than a bare `(elements, Δt)` pair.

The one thing all four share is: *given an initial state fixed at construction time, and
a target time, produce a Cartesian state.* That's the top-level interface.

## 2.1 Element-level detail (Kepler vs. mean-J2)

| | `kepler.propagate_kepler` | `mean_kepler.propagate_mean_j2` |
|---|---|---|
| Signature | `(keplerian_elements, time_elapsed_s, mu_m3_s2=EARTH_GM)` | `(keplerian_elements, time_elapsed_s, mu_m3_s2, R_e_m=..., J2=...)` |
| Extra physical params | none beyond `mu` | `R_e_m`, `J2` (perturbation model params) |
| Element[5] semantics | **true anomaly** | **mean anomaly** |
| Constant elements | a, e, i, ω, Ω, θ constant; only θ evolves | a, e, i constant; ω, Ω, M evolve via J2 secular rates |
| `mu` required? | optional (has default) | required positional |

## 3. Top-Level Interface

New submodule: `src/ephem_toolkit/core/propagator/` with base interfaces in 
`core/propagator/base.py`.

All epochs in the propagator interface are **ephemeris time** — seconds since the J2000
epoch (2000-01-01 12:00:00 TT).  Concrete propagators may treat this as TDB or TT; the
≈1.7 ms difference is ignored.  This matches the rest of the codebase
(`time_utils.datetime_to_tdb_s`, `frame_utils` epoch parameters, TudatPy's ephemeris
queries).

```python
class OutputMode(Enum):
    """Controls what propagate_to / propagate_by return."""
    NONE = "none"            # advance reference epoch, return None
    FINAL = "final"          # return (epoch_s, state) for the target epoch
    TRAJECTORY = "trajectory"  # return [(epoch_s, state), ...] from reference epoch


class Propagator(ABC, Generic[InitialStateT]):

    def __init__(self) -> None:
        self._initial_state_set: bool = False
        self._reference_epoch_s: float | None = None

    @abstractmethod
    def set_initial_state(self, initial_state: InitialStateT) -> None:
        """Set initial state and reset reference_epoch_s to the initial epoch."""
        self._initial_state_set = True

    @property
    def reference_epoch_s(self) -> float:
        """Current reference epoch (ephemeris time, s since J2000).
        Advances after each propagation call."""
        ...

    @abstractmethod
    def get_initial_epoch_s(self) -> float:
        """Return the epoch of the initial state (ephemeris time, s since J2000).
        Fixed; does not advance."""

    @abstractmethod
    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        """Subclass hook: Cartesian state at target_epoch_s."""

    def _propagate_trajectory_impl(
        self, from_epoch_s: float, to_epoch_s: float,
    ) -> list[tuple[float, np.ndarray]]:
        """Subclass hook: trajectory samples from from_epoch_s to to_epoch_s.
        Default: single sample at to_epoch_s. Override for integrators that
        produce intermediate samples."""
        return [(to_epoch_s, self._propagate_to_impl(to_epoch_s))]

    def propagate_to(
        self, target_epoch_s: float, output: OutputMode = OutputMode.FINAL,
    ) -> tuple[float, np.ndarray] | list[tuple[float, np.ndarray]] | None:
        """Propagate to target_epoch_s and advance reference_epoch_s.

        output=NONE        -> return None
        output=FINAL       -> return (epoch_s, state)
        output=TRAJECTORY  -> return [(epoch_s, state), ...] from previous
                              reference_epoch_s to target_epoch_s
        """
        ...

    def propagate_by(
        self, time_elapsed_s: float, output: OutputMode = OutputMode.FINAL,
    ) -> tuple[float, np.ndarray] | list[tuple[float, np.ndarray]] | None:
        """Propagate time_elapsed_s past reference_epoch_s."""
        return self.propagate_to(
            self.reference_epoch_s + time_elapsed_s, output=output,
        )
```

Why `set_initial_state` is a separate abstract method rather than leaving construction
entirely up to each subclass's `__init__`:

- **The heterogeneity is real and should be declared, not hidden.** A `KeplerianState`,
  a `Tle`, and a `NumericalInitialState` are genuinely different shapes; forcing a
  common parameter type would either lose information or require an artificial wrapper.
  `InitialStateT` (a `TypeVar`) lets each subclass fix its own concrete type
  (`Propagator[KeplerianState]`, `Propagator[Tle]`,
  `Propagator[NumericalInitialState]`) while the base class still guarantees the
  method exists and has a consistent single-argument signature.
- **A single argument, because the epoch is never separate from the state.** There is
  no such thing as "elements with no epoch" in this design — a raw `np.ndarray` of
  elements isn't a valid `InitialStateT` on its own; it must be paired with its epoch
  (via `KeplerianState`) before it's a complete initial state. This removes any
  ambiguity about which of two arguments "wins" and matches how `Tle` and
  `NumericalInitialState` already carry their own epoch.
- **`get_initial_epoch_s` is its own abstract method, not just a stored attribute,**
  so every subclass has to say explicitly *how* it derives the epoch from whatever it
  stored in `set_initial_state` — reading `KeplerianState.epoch_s`, computing a TLE's
  epoch from `epoch_year`/`epoch_day`, or reading a config field — instead of silently
  duplicating that value into a separate attribute that could get out of sync with the
  stored `initial_state`.
- **Decouples "provide a state" from "construct the object."** Keeping
  `set_initial_state` callable on its own (not only from `__init__`) supports reusing one
  propagator instance across multiple initial states — e.g. re-propagating a Kepler
  propagator from a new epoch/element set without rebuilding `mu`/config, or replacing a
  TLE on an `Sgp4Propagator` when a fresher one becomes available — without repeating
  constructor-only setup. Subclasses that have no reason to support re-initialization can
  still just call `set_initial_state` once from `__init__` and treat it as effectively
  final.
- **Keeps `__init__` free for model configuration.** Parameters that aren't "the initial
  state" (`mu`, `R_e_m`, `J2`, integrator settings) stay as ordinary constructor
  arguments; `set_initial_state` is specifically the one call every propagator has for
  "here is where/when we start."
- **Uninitialised-state guard.** The base class tracks whether `set_initial_state` has
  been called via the instance attribute `_initial_state_set` (initialised to `False` in
  `Propagator.__init__`). The concrete `propagate_to` method calls
  `_require_initial_state` before delegating to the abstract `_propagate_to_impl` hook,
  so the guard is enforced centrally — subclasses never need to call it themselves.
  `propagate_by` goes through `propagate_to` and inherits the same
  guard. Subclasses must call `super().set_initial_state(initial_state)` (or set
  `self._initial_state_set = True`) in their override. Subclasses are expected to call
  `set_initial_state` from `__init__` so that a freshly-constructed propagator is always
  in a valid state.

Why the top-level query contract is `propagate_to(epoch_s) -> Cartesian state`, not
`propagate(elements, dt) -> elements`:

- **Cartesian state is the only representation all four propagators can produce.**
  Kepler/mean-J2 elements convert to Cartesian via existing
  `kepler.keplerian_to_cartesian`; SGP4's TudatPy ephemeris already returns Cartesian
  via `cartesian_state(tdb_s)`; the numerical propagator integrates Cartesian state
  directly. Elements are not universal (SGP4 has no direct "elements in/out" step in
  its current implementation) so they can't be the shared currency.
- **Absolute epoch, not elapsed Δt, is the only time parameter all four already support
  or can trivially support.** SGP4's ephemeris object is naturally queried by absolute
  epoch (TDB seconds). Kepler/mean-J2 need an elapsed Δt, but that's just
  `target_epoch_s - get_initial_epoch_s()` — trivial to derive once the initial epoch
  is fixed at construction.

## 4. Supporting Data Types

Since a bare element vector has no epoch of its own, `KeplerianState` pairs elements
with the epoch at which they're defined. `AnomalyType` tags whether the 6th element is
true or mean anomaly.

```python
class AnomalyType(Enum):
    """Semantic meaning of the 6th Keplerian element produced by a propagator."""

    TRUE = "true"
    MEAN = "mean"


@dataclass(frozen=True)
class KeplerianState:
    """Keplerian elements paired with the epoch at which they are defined.

    The ``elements`` array is made read-only in :meth:`__post_init__` so
    that the frozen-dataclass invariant extends to the array contents, not
    just the attribute binding.
    """

    elements: np.ndarray
    """Keplerian elements ``[a, e, i, omega, RAAN, anomaly]``."""
    epoch_s: float
    """Epoch at which :attr:`elements` is defined (ephemeris time, s since J2000)."""

    def __post_init__(self) -> None:
        # Make the backing array immutable so that the frozen-dataclass
        # guarantee covers the array contents, not just the attribute slot.
        object.__setattr__(
            self, "elements", np.array(self.elements, dtype=float)
        )
        self.elements.flags.writeable = False
```

Note: `frozen=True` prevents reassignment of attributes, and `__post_init__` sets
`elements.flags.writeable = False` to prevent in-place mutation of the array contents.
Together these ensure full immutability. Because `np.ndarray` is unhashable,
`KeplerianState` should not be used as a dict key or set member despite being frozen.

## 5. Concrete Propagators

All four propagators implement `Propagator[InitialStateT]` directly — there is no
intermediate ABC. Each concrete class binds model configuration in `__init__` and calls
`set_initial_state` from `__init__` to ensure the propagator is always queryable.

### 5.1 `KeplerPropagator`

Lives in `core/propagator/kepler.py`, wrapping `core.kepler.propagate_kepler`:

```python
class KeplerPropagator(Propagator[KeplerianState]):
    """Two-body Keplerian propagator."""

    anomaly_type = AnomalyType.TRUE

    def __init__(
        self,
        initial_state: KeplerianState,
        mu_m3_s2: float = EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    ) -> None:
        self._mu_m3_s2 = mu_m3_s2
        self.set_initial_state(initial_state)

    def set_initial_state(self, initial_state: KeplerianState) -> None:
        super().set_initial_state(initial_state)
        self._initial_state = initial_state
        self._reference_epoch_s = initial_state.epoch_s

    def get_initial_epoch_s(self) -> float:
        return self._initial_state.epoch_s

    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        elapsed_s = target_epoch_s - self.get_initial_epoch_s()
        propagated = propagate_kepler(
            self._initial_state.elements, elapsed_s, self._mu_m3_s2,
        )
        return keplerian_to_cartesian(propagated, self._mu_m3_s2)
```

### 5.2 `MeanJ2Propagator`

Lives in `core/propagator/mean_j2.py`, wrapping `core.mean_kepler.propagate_mean_j2`:

```python
class MeanJ2Propagator(Propagator[KeplerianState]):
    """J2 secular mean-element propagator."""

    anomaly_type = AnomalyType.MEAN

    def __init__(
        self,
        initial_state: KeplerianState,
        mu_m3_s2: float,
        R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
        J2: float = EARTH_J2,
    ) -> None:
        self._mu_m3_s2 = mu_m3_s2
        self._R_e_m = R_e_m
        self._J2 = J2
        self.set_initial_state(initial_state)

    def set_initial_state(self, initial_state: KeplerianState) -> None:
        super().set_initial_state(initial_state)
        self._initial_state = initial_state
        self._reference_epoch_s = initial_state.epoch_s

    def get_initial_epoch_s(self) -> float:
        return self._initial_state.epoch_s

    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        elapsed_s = target_epoch_s - self.get_initial_epoch_s()
        propagated = propagate_mean_j2(
            self._initial_state.elements, elapsed_s,
            self._mu_m3_s2, self._R_e_m, self._J2,
        )
        return mean_elements_to_cartesian(
            propagated, self._mu_m3_s2, self._R_e_m, self._J2,
        )
```

### 5.3 `Sgp4Propagator`

Lives in `core/propagator/sgp4.py`, wrapping today's `propagate_tle_sgp4` logic from 
`propagate_omm/__main__.py`:

```python
class Sgp4Propagator(Propagator[Tle]):
    """SGP4 propagator built from a NORAD TLE."""

    def __init__(self, tle_obj: Tle):
        self.set_initial_state(tle_obj)

    def set_initial_state(self, initial_state: Tle) -> None:
        super().set_initial_state(initial_state)
        from tudatpy.dynamics import environment_setup  # deferred, heavy import

        line1, line2 = format_tle_strings(initial_state)
        ephemeris_settings = environment_setup.ephemeris.sgp4(line1, line2)
        self._ephemeris = environment_setup.create_body_ephemeris(
            ephemeris_settings, body_name=initial_state.object_name or "UNKNOWN"
        )
        self._tle = initial_state
        self._reference_epoch_s = tle_epoch_to_tdb_s(
            initial_state.epoch_year, initial_state.epoch_day,
        )

    def get_initial_epoch_s(self) -> float:
        return tle_epoch_to_tdb_s(self._tle.epoch_year, self._tle.epoch_day)

    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        return self._ephemeris.cartesian_state(target_epoch_s)
```

Note that `get_initial_epoch_s` here computes the epoch from the stored TLE's own
`epoch_year`/`epoch_day` fields, exactly analogous to the Keplerian propagators
reading `KeplerianState.epoch_s` — same abstract method, different derivation.

### 5.4 `NumericalPropagator` (target design once moved to `core`)

Lives in `core/propagator/numerical.py` (see
[docs/PROPAGATE_ORBIT_CORE_MODULARIZATION_PLAN.md](PROPAGATE_ORBIT_CORE_MODULARIZATION_PLAN.md)).

The numerical propagator separates **model configuration** (force-model settings,
integrator parameters — set once in `__init__`) from **initial state** (epoch + Cartesian
state vector — passed to `set_initial_state`). This follows the design principle that
`__init__` is for model config and `set_initial_state` is for "here is where/when we
start":

```python
@dataclass(frozen=True)
class NumericalInitialState:
    """Cartesian initial state paired with its epoch."""

    state_m_m_s: np.ndarray
    """Cartesian state vector [x, y, z, vx, vy, vz] in SI units (m, m/s)."""
    epoch_s: float
    """Epoch at which :attr:`state_m_m_s` is defined (ephemeris time, s since J2000)."""


@dataclass(frozen=True)
class NumericalPropagatorConfig:
    """Force-model and integrator settings for numerical propagation.

    This is model configuration, not initial state — it is passed to
    ``__init__``, not to ``set_initial_state``.
    """

    satellite_name: str
    satellite_mass_kg: float
    integrator_method: str
    integrator_step_size_values_s: tuple[float, ...]
    earth_spherical_harmonic_gravity_degree: int
    earth_spherical_harmonic_gravity_order: int
    satellite_drag_area_m2: float
    is_srp_on: bool
    srp_coefficient: float
    is_earth_drag_on: bool
    satellite_drag_coefficient: float
    is_moon_gravity_on: bool
    is_sun_gravity_on: bool
    is_venus_gravity_on: bool
    is_mars_gravity_on: bool


class NumericalPropagator(Propagator[NumericalInitialState]):
    """Perturbed numerical propagator (Tudat translational dynamics)."""

    def __init__(
        self,
        config: NumericalPropagatorConfig,
        initial_state: NumericalInitialState,
    ) -> None:
        self._config = config
        self.set_initial_state(initial_state)

    def set_initial_state(self, initial_state: NumericalInitialState) -> None:
        super().set_initial_state(initial_state)
        self._initial_state = initial_state
        self._reference_epoch_s = initial_state.epoch_s

    def get_initial_epoch_s(self) -> float:
        return self._initial_state.epoch_s

    def _run_integrator(self, target_epoch_s: float) -> dict[float, np.ndarray]:
        # Runs the integrator so that target_epoch_s falls within the
        # propagated span, then returns the resulting state_history keyed
        # by ephemeris time (s since J2000).
        ...

    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        state_history = self._run_integrator(target_epoch_s)
        return _nearest_or_interpolated_state(state_history, target_epoch_s)

    ```

This is deliberately sketched, not final: the "run once, interpolate on demand"
behavior needs design work of its own (extending an existing run vs. re-running from
scratch, interpolation method at off-grid epochs) that should happen as part of the
`core` migration, not this interface design. What matters here is that
`_propagate_to_impl` fits the same `Propagator` base as the other three without needing
any change to the base class itself.

## 6. Migration Steps

1. Create `core/propagator/` submodule structure:
   - `core/propagator/__init__.py` - exports all public classes/types
   - `core/propagator/base.py` - `Propagator`, `KeplerianState`, `AnomalyType`
   - `core/propagator/kepler.py` - `KeplerPropagator`
   - `core/propagator/mean_j2.py` - `MeanJ2Propagator`

2. Add unit tests in `tests/ephem_toolkit/core/propagator/`:
   - `test_base.py` - base interface contracts (including uninitialised-state guard)
   - `test_kepler.py` - `KeplerPropagator` tests
   - `test_mean_j2.py` - `MeanJ2Propagator` tests
   - Verify `propagate_to`/`propagate_by` produce correct Cartesian states
   - Verify epoch handling via `KeplerianState`

3. Document in `docs/CORE_LIBRARY_ORBITAL_ELEMENTS.md`.

4. **Separately** (after numerical propagation migration):
   - Add `core/propagator/sgp4.py` - `Sgp4Propagator` (wraps TudatPy SGP4 ephemeris)
   - Add `core/propagator/numerical.py` - `NumericalPropagator` (wraps Tudat integrator)
   - Add corresponding tests in `tests/ephem_toolkit/core/propagator/`

No existing code needs to change — purely additive. CLI tools can optionally adopt the 
class interface later.

## 7. Submodule Structure

```
core/propagator/
├── __init__.py              # Exports: Propagator, KeplerianState, AnomalyType,
│                            #          KeplerPropagator, MeanJ2Propagator,
│                            #          Sgp4Propagator, NumericalPropagator
├── base.py                  # Propagator, KeplerianState, AnomalyType
├── kepler.py                # KeplerPropagator
├── mean_j2.py               # MeanJ2Propagator
├── sgp4.py                  # Sgp4Propagator (added later, requires tudatpy)
└── numerical.py             # NumericalPropagator, NumericalInitialState,
                             # NumericalPropagatorConfig (added later, requires tudatpy)
```

Heavy `tudatpy` imports isolated to `sgp4.py` and `numerical.py`; lightweight propagators 
importable without TudatPy overhead.

## 8. Open Questions

- `NumericalPropagator`'s "extend an existing run vs. re-run from scratch" strategy
  needs its own design pass before implementation — flagged here, not resolved.
- Do we want a `state_at(epoch_datetime)` convenience method distinct from
  `propagate_to`, or is `propagate_to` itself sufficient? Recommendation: `propagate_to`
  is already that convenience method; no separate name needed.
- Should `set_initial_state` be re-callable after construction (supporting
  re-initialization), or should the base class enforce "set once" (e.g. raising if
  called a second time)? Recommendation: allow re-calling — it's simpler, costs nothing
  for propagators that don't need it, and enables the reuse cases described in §3
  without adding a second method name.
