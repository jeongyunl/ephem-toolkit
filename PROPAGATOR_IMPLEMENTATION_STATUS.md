# Propagator Interface Implementation Status

## Completed

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
✅ **`core/propagator/kepler.py`** - Two-body Keplerian propagator + conversion utilities
- `KeplerPropagator(Propagator[KeplerianState])`
- Propagation logic inlined in `_propagate_to_impl()` (no free function dependency)
- `anomaly_type = AnomalyType.TRUE`
- Custom `mu_m3_s2` parameter support
- All conversion functions: `cartesian_to_keplerian`, `keplerian_to_cartesian`
- Anomaly conversions: `true_to_eccentric_anomaly`, `eccentric_to_true_anomaly`, etc.
- Mean motion utilities: `mean_motion_to_semi_major_axis`, `semi_major_axis_to_mean_motion`
- Element index constants: `SEMI_MAJOR_AXIS_INDEX`, `ECCENTRICITY_INDEX`, etc.

### Migration Completed
✅ **`core/kepler.py`** — DELETED
- All functions moved to `core/propagator/kepler.py`
- `propagate_kepler()` free function removed entirely
- All callers migrated to `KeplerPropagator`

✅ **All source files updated** to import from `core.propagator.kepler`:
- `core/ccsds/omm.py`, `core/convert_tle.py`, `core/mean_kepler.py`
- `oem_to_omm/fit_mean_kepler.py`, `oem_to_omm/fit_tle/estimation.py`
- `oem_to_omm/fit_tle/refinement.py`, `oem_to_opm/__main__.py`
- `tle_info/__main__.py`, `propagate_kepler/__main__.py`
- `propagate_omm/__main__.py`, `oem_to_opm/fit_osculating_kepler.py`

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

✅ **`tests/ephem_toolkit/core/test_kepler.py`** updated
- Section 22 replaced: `propagate_kepler()` tests → `KeplerPropagator` tests

### Module Structure
✅ **`core/propagator/__init__.py`**
- Exports: `Propagator`, `KeplerianState`, `AnomalyType`, `OutputMode`, `KeplerPropagator`
- Exports: `cartesian_to_keplerian`, `keplerian_to_cartesian`, anomaly conversions, mean motion utilities
- Does **not** export `propagate_kepler` (removed)

## Test Coverage

- **751 tests total** (all passing, 0 warnings)
- Base class interface contracts
- Concrete propagator behavior
- Immutability guarantees
- Epoch handling
- Error conditions

## Remaining Work

### Brouwer J2 Propagator ⏳

✅ **`core/mean_kepler.py` renamed** (Brouwer naming applied):
- `propagate_mean_j2` → `propagate_brouwer_j2`
- `mean_elements_to_cartesian` → `brouwer_mean_to_cartesian`
- `osculating_to_mean_keplerian` → `osculating_to_brouwer_mean`
- `mean_to_osculating_keplerian` → `brouwer_mean_to_osculating`
- Old names fully removed (no aliases)
- All callers updated in source and test files

✅ **`core/propagator/brouwer_j2.py`** - Brouwer J2 secular propagator
- `BrouwerJ2Propagator(Propagator[KeplerianState])`
- Wraps `core.mean_kepler.propagate_brouwer_j2()`
- Uses `brouwer_mean_to_cartesian()`
- `anomaly_type = AnomalyType.MEAN`
- Initial state: **Brouwer mean elements** (not osculating, not SGP4 mean)
- Deferred import of `mean_kepler` to avoid circular dependency

✅ **`tests/ephem_toolkit/core/propagator/test_brouwer_j2.py`** (12 tests)
- Initialization and configuration
- `propagate_to` / `propagate_by` correctness
- Matches manual `propagate_brouwer_j2` + `brouwer_mean_to_cartesian`
- Reference epoch advancement
- Uninitialised-state guard
- J2 RAAN drift verification

### SGP4 Propagator (requires tudatpy) ⏳
⏳ **`core/propagator/sgp4.py`** - SGP4 propagator
- `Sgp4Propagator(Propagator[Tle])`
- Wraps TudatPy's `environment_setup.ephemeris.sgp4`
- **Requires**: `tle_epoch_to_tt_s()` — compose `tle_epoch_to_datetime()` + `datetime_to_tt_s()`

⏳ **`core/tle.py`** additions
- Add `tle_epoch_to_tt_s(epoch_year, epoch_day)` function

⏳ **`tests/ephem_toolkit/core/propagator/test_sgp4.py`**

### DSST Propagator (future work) ⏳
⏳ **`core/propagator/dsst.py`** - DSST semi-analytical propagator
- `DsstPropagator(Propagator[KeplerianState])`
- For OMMs with `MEAN_ELEMENT_THEORY = DSST`
- **Not interchangeable** with Brouwer mean elements
- Requires external DSST implementation (not in current codebase)

### USM Propagator (future work) ⏳
⏳ **`core/propagator/usm.py`** - USM semi-analytical propagator
- `UsmPropagator(Propagator[KeplerianState])`
- For OMMs with `MEAN_ELEMENT_THEORY = USM`
- **Not interchangeable** with Brouwer or DSST mean elements
- Requires external USM implementation (not in current codebase)

### Numerical Propagator (blocked) ⏳
⏳ **`core/propagator/numerical.py`** - Tudat numerical propagator
- **Blocked by**: `propagate_orbit` → `core` migration (see `PROPAGATE_ORBIT_CORE_MODULARIZATION_PLAN.md`)

⏳ **`tests/ephem_toolkit/core/propagator/test_numerical.py`**

### Documentation ⏳
⏳ **`docs/CORE_LIBRARY_ORBITAL_ELEMENTS.md`** update
- Document propagator submodule
- Usage examples with `KeplerPropagator`
- API reference

## Design Decisions Implemented

1. **No backward compatibility in `core`**: The `core` library is internal — callers are always updated in the same commit as the rename. No deprecated aliases are kept. Breaking changes to `core` are acceptable and expected.
2. **Flat hierarchy**: All propagators inherit directly from `Propagator[InitialStateT]`
3. **Generic initial state**: Each propagator uses its own state type via `TypeVar`
4. **Unified output**: All propagators return Cartesian states
5. **TT time standard**: All epochs are Terrestrial Time (s since J2000 TT)
6. **Immutable state**: `KeplerianState` is frozen with read-only array
7. **Separate model config**: `__init__` for config, `set_initial_state` for state
8. **Reference epoch tracking**: Advances with each propagation call
9. **Output modes**: NONE (advance only), FINAL (single state), TRAJECTORY (list)
10. **Guard checks**: Raise if propagation attempted before `set_initial_state()`
11. **No free propagation function**: `propagate_kepler()` removed; `KeplerPropagator` is canonical

## Next Steps

1. Implement `tle_epoch_to_tt_s()` in `core/tle.py`
2. Implement `Sgp4Propagator` in `core/propagator/sgp4.py`
6. Update `docs/CORE_LIBRARY_ORBITAL_ELEMENTS.md`
7. Implement `NumericalPropagator` (after `propagate_orbit` core migration)
