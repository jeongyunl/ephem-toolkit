# Propagator Interface Implementation Status

## Completed (Phase 1)

### Core Infrastructure
✅ **`core/propagator/base.py`** - Base classes and types
- `Propagator[InitialStateT]` ABC with generic type parameter
- `OutputMode` enum (NONE, FINAL, TRAJECTORY)
- `AnomalyType` enum (TRUE, MEAN)
- `KeplerianState` dataclass (frozen, immutable array)
- `propagate_to()` implementation with output modes
- `propagate_by()` implementation
- `reference_epoch_s` property with guard
- `_require_initial_state()` guard method
- `_propagate_to_impl()` abstract hook
- `_propagate_trajectory_impl()` default implementation

### Concrete Propagators
✅ **`core/propagator/kepler.py`** - Two-body Keplerian propagator
- `KeplerPropagator(Propagator[KeplerianState])`
- Wraps `core.kepler.propagate_kepler()`
- Converts to Cartesian via `keplerian_to_cartesian()`
- `anomaly_type = AnomalyType.TRUE`
- Custom `mu_m3_s2` parameter support

### Tests
✅ **`tests/ephem_toolkit/core/propagator/test_base.py`** (8 tests)
- Uninitialised-state guards
- `OutputMode` variants
- Reference epoch advancement
- `propagate_by` behavior

✅ **`tests/ephem_toolkit/core/propagator/test_kepler.py`** (11 tests)
- Initialization and configuration
- `propagate_to` / `propagate_by` correctness
- Epoch handling (initial vs reference)
- `KeplerianState` immutability
- Array copying behavior

### Module Structure
✅ **`core/propagator/__init__.py`**
- Exports: `Propagator`, `KeplerianState`, `AnomalyType`, `OutputMode`, `KeplerPropagator`

## Remaining Work (Phase 2)

### Mean J2 Propagator
⏳ **`core/propagator/mean_j2.py`** - J2 secular propagator
- `MeanJ2Propagator(Propagator[KeplerianState])`
- Wraps `core.mean_kepler.propagate_mean_j2()`
- **Requires**: `mean_elements_to_cartesian()` function (doesn't exist yet)
- `anomaly_type = AnomalyType.MEAN`

⏳ **`core/mean_kepler.py`** additions
- Add `mean_elements_to_cartesian()` function
- Convert mean elements → osculating → Cartesian

⏳ **`tests/ephem_toolkit/core/propagator/test_mean_j2.py`**
- Similar structure to `test_kepler.py`

### SGP4 Propagator (Phase 3 - requires tudatpy)
⏳ **`core/propagator/sgp4.py`** - SGP4 TLE propagator
- `Sgp4Propagator(Propagator[Tle])`
- Wraps TudatPy's `environment_setup.ephemeris.sgp4`
- **Requires**: `tle_epoch_to_tt_s()` function
- **Requires**: `format_tle_strings()` function

⏳ **`core/tle.py`** additions
- Add `tle_epoch_to_tt_s(epoch_year, epoch_day)` function
- Compose `tle_epoch_to_datetime()` + `datetime_to_tt_s()`

⏳ **`tests/ephem_toolkit/core/propagator/test_sgp4.py`**

### Numerical Propagator (Phase 4 - requires core migration)
⏳ **`core/propagator/numerical.py`** - Tudat numerical propagator
- `NumericalPropagator(Propagator[NumericalInitialState])`
- `NumericalInitialState` dataclass
- `NumericalPropagatorConfig` dataclass
- Wraps Tudat integrator
- **Blocked by**: `propagate_orbit` → `core` migration

⏳ **`tests/ephem_toolkit/core/propagator/test_numerical.py`**

### Documentation
⏳ **`docs/CORE_LIBRARY_ORBITAL_ELEMENTS.md`** update
- Document propagator submodule
- Usage examples
- API reference

## Design Decisions Implemented

1. **Flat hierarchy**: All propagators inherit directly from `Propagator[InitialStateT]`
2. **Generic initial state**: Each propagator uses its own state type via `TypeVar`
3. **Unified output**: All propagators return Cartesian states
4. **TT time standard**: All epochs are Terrestrial Time (s since J2000 TT)
5. **Immutable state**: `KeplerianState` is frozen with read-only array
6. **Separate model config**: `__init__` for config, `set_initial_state` for state
7. **Reference epoch tracking**: Advances with each propagation call
8. **Output modes**: NONE (advance only), FINAL (single state), TRAJECTORY (list)
9. **Guard checks**: Raise if propagation attempted before `set_initial_state()`

## Test Coverage

- **19 tests total** (all passing)
- Base class interface contracts
- Concrete propagator behavior
- Immutability guarantees
- Epoch handling
- Error conditions

## Next Steps

1. Implement `mean_elements_to_cartesian()` in `core/mean_kepler.py`
2. Implement `MeanJ2Propagator` in `core/propagator/mean_j2.py`
3. Add tests for `MeanJ2Propagator`
4. Implement `tle_epoch_to_tt_s()` in `core/tle.py`
5. Implement `Sgp4Propagator` (after TLE utilities ready)
6. Update documentation
