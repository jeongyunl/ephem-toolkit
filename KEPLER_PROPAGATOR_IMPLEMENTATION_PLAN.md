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

### Phase 3: Sgp4Propagator ⏳

**`core/tle.py`** — add `tle_epoch_to_tt_s(epoch_year, epoch_day) -> float`
- Compose `tle_epoch_to_datetime()` + `datetime_to_tt_s()`

**`core/propagator/sgp4.py`** — `Sgp4Propagator(Propagator[Tle])`

```python
class Sgp4Propagator(Propagator[Tle]):
    """SGP4 propagator built from a NORAD TLE."""

    def __init__(self, initial_state: Tle) -> None:
        super().__init__()
        self.set_initial_state(initial_state)

    def set_initial_state(self, initial_state: Tle) -> None:
        super().set_initial_state(initial_state)
        from tudatpy.dynamics import environment_setup  # deferred, heavy import
        line1, line2 = format_tle_strings(initial_state)
        ephemeris_settings = environment_setup.ephemeris.sgp4(line1, line2)
        self._ephemeris = environment_setup.create_body_ephemeris(
            ephemeris_settings, body_name=initial_state.object_name or "UNKNOWN"
        )
        self._tle = initial_state
        self._reference_epoch_s = tle_epoch_to_tt_s(
            initial_state.epoch_year, initial_state.epoch_day
        )

    def get_initial_epoch_s(self) -> float:
        return tle_epoch_to_tt_s(self._tle.epoch_year, self._tle.epoch_day)

    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        return self._ephemeris.cartesian_state(target_epoch_s)
```

**Tests**: `tests/ephem_toolkit/core/propagator/test_sgp4.py`
- Verify `propagate_to` returns correct Cartesian state at TLE epoch
- Verify epoch derived from TLE `epoch_year`/`epoch_day`
- Verify `set_initial_state` can replace TLE

### Phase 4: NumericalPropagator ⏳ (blocked)

**Blocked by**: `propagate_orbit` → `core` migration.
See [PROPAGATE_ORBIT_CORE_MODULARIZATION_PLAN.md](PROPAGATE_ORBIT_CORE_MODULARIZATION_PLAN.md).

---

## Design Principles

- **No backward compatibility in `core`**: callers updated in same commit as any rename
- **Flat hierarchy**: all propagators implement `Propagator[InitialStateT]` directly
- **TT time standard**: all epochs are TT seconds since J2000
- **Explicit theory names**: `BrouwerJ2Propagator` not `MeanJ2Propagator`; `propagate_brouwer_j2` not `propagate_mean_j2`
