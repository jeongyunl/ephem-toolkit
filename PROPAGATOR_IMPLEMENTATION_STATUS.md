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

✅ **All source files updated** to import from `core.propagator.kepler` or `core.propagator.brouwer_j2`:
- `core/ccsds/omm.py`, `core/convert_tle.py`
- `oem_to_omm/fit_mean_kepler.py`, `oem_to_omm/fit_tle/estimation.py`
- `oem_to_omm/fit_tle/refinement.py`, `oem_to_opm/__main__.py`
- `tle_info/__main__.py`, `propagate_kepler/__main__.py`
- `propagate_omm/__main__.py`, `oem_to_opm/fit_osculating_kepler.py`
- `oem_to_omm/__main__.py`

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

- **759 tests total** (all passing, 0 warnings)
- Base class interface contracts
- Concrete propagator behavior
- Immutability guarantees
- Epoch handling
- Error conditions

## Remaining Work

### Brouwer J2 Propagator ✅

✅ **`core/mean_kepler.py`** — DELETED
- All functions moved to `core/propagator/brouwer_j2.py`
- No circular import (functions now local to `brouwer_j2.py`)
- All callers updated to import from `core.propagator.brouwer_j2`

✅ **`core/propagator/brouwer_j2.py`** - Brouwer J2 propagator + all Brouwer utilities
- `BrouwerJ2Propagator(Propagator[KeplerianState])`
- `compute_brouwer_short_period_corrections()` — mean→osculating
- `brouwer_mean_to_osculating()` — alias
- `osculating_to_brouwer_mean()` — iterative inversion
- `brouwer_mean_to_cartesian()` — mean→Cartesian
- `propagate_brouwer_j2()` — J2 secular propagation
- `compute_raan_rate()` — J2 RAAN rate utility
- `anomaly_type = AnomalyType.MEAN`
- Initial state: **Brouwer mean elements** (not osculating, not SGP4 mean)

✅ **`tests/ephem_toolkit/core/propagator/test_brouwer_j2.py`** (12 tests)
- Initialization and configuration
- `propagate_to` / `propagate_by` correctness
- Matches manual `propagate_brouwer_j2` + `brouwer_mean_to_cartesian`
- Reference epoch advancement
- Uninitialised-state guard
- J2 RAAN drift verification

### SGP4 Propagator ✅

✅ **`core/tle.py`** — TLE I/O and object code (restored to `core/tle.py`)
- `Tle` dataclass, `read_tle()`, `write_tle()`, `format_tle_strings()`
- `create_tle_from_mean_keplerian()`
- Epoch conversions: `tle_epoch_to_tt_s()`, `tle_epoch_to_datetime()`, `datetime_to_tle_epoch()`
- ISO 8601 conversions: `tle_epoch_to_iso8601()`, `iso8601_to_tle_epoch()`

✅ **`core/propagator/sgp4.py`** - SGP4 propagator only
- `Sgp4Propagator(Propagator[Tle])`
- Imports `Tle` utilities from `core.tle`
- Wraps TudatPy's `environment_setup.ephemeris.sgp4`

✅ **`tests/ephem_toolkit/core/propagator/test_sgp4.py`** (8 tests, skipped without tudatpy)
- Initialization, epoch derivation
- `propagate_to` / `propagate_by` correctness
- Reference epoch advancement
- `set_initial_state` replacement

✅ **All source files import TLE from `core.tle`**:
- `oem_to_omm/__main__.py`, `oem_to_omm/fit_tle_main.py`
- `oem_to_omm/fit_tle/estimation.py`, `oem_to_omm/fit_tle/tle_builder.py`
- `oem_to_omm/fit_tle/refinement.py`, `tle_to_omm/tle_to_omm.py`
- `omm_to_tle/omm_to_tle.py`, `propagate_omm/__main__.py`
- `core/convert_tle.py`

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

### Documentation ✅
✅ **`docs/CORE_LIBRARY_ORBITAL_ELEMENTS.md`** updated
- Propagator interface (`Propagator` ABC, `KeplerianState`, `AnomalyType`, `OutputMode`)
- `KeplerPropagator`, `BrouwerJ2Propagator`, `Sgp4Propagator` usage examples
- Orbital element utilities API reference (anomaly conversions, mean motion, Brouwer utilities)

✅ **`docs/CORE_LIBRARY_SUMMARY.md`** updated
- Section 2 updated to list `core.propagator` submodules
- Quick Reference "Orbital Propagation" updated with propagator class examples

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

1. Implement `NumericalPropagator` (after `propagate_orbit` → `core` migration per `PROPAGATE_ORBIT_CORE_MODULARIZATION_PLAN.md`)
