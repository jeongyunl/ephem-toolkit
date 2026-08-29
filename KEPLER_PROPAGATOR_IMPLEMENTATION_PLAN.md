# Plan: Propagator Class Hierarchy Implementation

## Status: Phase 1 & 2 COMPLETE ✅

See [PROPAGATOR_INTERFACE_DESIGN.md](PROPAGATOR_INTERFACE_DESIGN.md) for the full design.
See [PROPAGATOR_IMPLEMENTATION_STATUS.md](PROPAGATOR_IMPLEMENTATION_STATUS.md) for current status.

---

## Completed Work

### Phase 1: KeplerPropagator ✅

**`core/propagator/kepler.py`** — `KeplerPropagator(Propagator[KeplerianState])`
- Propagation logic inlined in `_propagate_to_impl()` (no free function dependency)
- `anomaly_type = AnomalyType.TRUE`; element[5] is true anomaly
- All conversion utilities co-located: `cartesian_to_keplerian`, `keplerian_to_cartesian`, anomaly conversions, mean motion utilities
- `core/kepler.py` deleted; `propagate_kepler()` free function removed
- All callers migrated to `KeplerPropagator`

**Tests**: `tests/ephem_toolkit/core/propagator/test_kepler.py` (11 tests)

### Phase 2: BrouwerJ2Propagator ✅

**`core/mean_kepler.py`** renamed to Brouwer-explicit names:
- `propagate_mean_j2` → `propagate_brouwer_j2`
- `mean_elements_to_cartesian` → `brouwer_mean_to_cartesian`
- `osculating_to_mean_keplerian` → `osculating_to_brouwer_mean`
- `mean_to_osculating_keplerian` → `brouwer_mean_to_osculating`

**`core/propagator/brouwer_j2.py`** — `BrouwerJ2Propagator(Propagator[KeplerianState])`
- `anomaly_type = AnomalyType.MEAN`; element[5] is mean anomaly
- Initial state: **Brouwer mean elements** (not osculating, not SGP4 mean)
- Deferred import of `mean_kepler` to avoid circular dependency

**Tests**: `tests/ephem_toolkit/core/propagator/test_brouwer_j2.py` (12 tests)

---

## Next Steps

### Phase 3: Sgp4Propagator ✅

✅ **`core/tle.py`** — DELETED, migrated to `core/propagator/sgp4.py`
✅ **`core/propagator/sgp4.py`** — `Sgp4Propagator(Propagator[Tle])` + all TLE utilities
✅ **`tests/ephem_toolkit/core/propagator/test_sgp4.py`** — 8 tests (skipped without tudatpy)
✅ **All callers updated** to import from `core.propagator.sgp4`

### Phase 4: NumericalPropagator ⏳ (blocked)

**Blocked by**: `propagate_orbit` → `core` migration.
See [PROPAGATE_ORBIT_CORE_MODULARIZATION_PLAN.md](PROPAGATE_ORBIT_CORE_MODULARIZATION_PLAN.md).

---

## Design Principles

- **No backward compatibility in `core`**: callers updated in same commit as any rename
- **Flat hierarchy**: all propagators implement `Propagator[InitialStateT]` directly
- **TT time standard**: all epochs are TT seconds since J2000
- **Explicit theory names**: `BrouwerJ2Propagator` not `MeanJ2Propagator`; `propagate_brouwer_j2` not `propagate_mean_j2`
