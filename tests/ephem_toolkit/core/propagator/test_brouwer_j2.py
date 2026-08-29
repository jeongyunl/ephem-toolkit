"""Tests for BrouwerJ2Propagator."""

import numpy as np
import pytest

from ephem_toolkit.core.consts import EARTH_GRAVITATIONAL_PARAMETER_M3_S2
from ephem_toolkit.core.propagator.brouwer_j2 import (
    brouwer_mean_to_cartesian,
    osculating_to_brouwer_mean,
    propagate_brouwer_j2,
)
from ephem_toolkit.core.propagator import (
    AnomalyType,
    BrouwerJ2Propagator,
    KeplerianState,
    OutputMode,
)
from ephem_toolkit.core.propagator.kepler import cartesian_to_keplerian


# ISS-like Brouwer mean elements: [a, e, i, omega, RAAN, M]
_ISS_OSCULATING = np.array([
    6778e3,          # a (m)
    0.0005,          # e
    np.radians(51.6),  # i (rad)
    np.radians(30.0),  # omega (rad)
    np.radians(45.0),  # RAAN (rad)
    np.radians(10.0),  # true anomaly (rad) — converted to mean below
])
_MU = EARTH_GRAVITATIONAL_PARAMETER_M3_S2


def _make_brouwer_state(epoch_s: float = 0.0) -> KeplerianState:
    """Create a KeplerianState with Brouwer mean elements."""
    mean_elements = osculating_to_brouwer_mean(_ISS_OSCULATING)
    return KeplerianState(elements=mean_elements, epoch_s=epoch_s)


def test_brouwer_j2_propagator_anomaly_type():
    """BrouwerJ2Propagator uses mean anomaly."""
    assert BrouwerJ2Propagator.anomaly_type == AnomalyType.MEAN


def test_brouwer_j2_propagator_initialization():
    """Test BrouwerJ2Propagator initialization."""
    state = _make_brouwer_state(epoch_s=1000.0)
    prop = BrouwerJ2Propagator(initial_state=state, mu_m3_s2=_MU)

    assert prop.get_initial_epoch_s() == 1000.0
    assert prop.reference_epoch_s == 1000.0
    np.testing.assert_array_equal(prop._initial_state.elements, state.elements)


def test_brouwer_j2_propagator_custom_params():
    """Test BrouwerJ2Propagator with custom physical parameters."""
    state = _make_brouwer_state()
    custom_mu = 4.0e14
    custom_Re = 6.37e6
    custom_J2 = 1.08e-3

    prop = BrouwerJ2Propagator(
        initial_state=state,
        mu_m3_s2=custom_mu,
        R_e_m=custom_Re,
        J2=custom_J2,
    )

    assert prop._mu_m3_s2 == custom_mu
    assert prop._R_e_m == custom_Re
    assert prop._J2 == custom_J2


def test_brouwer_j2_propagator_propagate_to_final():
    """Test propagate_to with OutputMode.FINAL returns (epoch, Cartesian state)."""
    state = _make_brouwer_state()
    prop = BrouwerJ2Propagator(initial_state=state, mu_m3_s2=_MU)

    target_s = 3600.0
    result = prop.propagate_to(target_s, output=OutputMode.FINAL)

    assert isinstance(result, tuple)
    epoch, cart = result
    assert epoch == target_s
    assert isinstance(cart, np.ndarray)
    assert cart.shape == (6,)
    assert prop.reference_epoch_s == target_s


def test_brouwer_j2_propagator_propagate_by():
    """Test propagate_by with elapsed time."""
    state = _make_brouwer_state(epoch_s=500.0)
    prop = BrouwerJ2Propagator(initial_state=state, mu_m3_s2=_MU)

    epoch, cart = prop.propagate_by(3600.0, output=OutputMode.FINAL)

    assert epoch == 500.0 + 3600.0
    assert cart.shape == (6,)


def test_brouwer_j2_propagator_propagate_to_none():
    """Test propagate_to with OutputMode.NONE advances reference epoch."""
    state = _make_brouwer_state()
    prop = BrouwerJ2Propagator(initial_state=state, mu_m3_s2=_MU)

    result = prop.propagate_to(3600.0, output=OutputMode.NONE)

    assert result is None
    assert prop.reference_epoch_s == 3600.0


def test_brouwer_j2_propagator_matches_manual_calculation():
    """Verify _propagate_to_impl matches manual propagate_brouwer_j2 + brouwer_mean_to_cartesian."""
    state = _make_brouwer_state()
    prop = BrouwerJ2Propagator(initial_state=state, mu_m3_s2=_MU)

    elapsed_s = 3600.0
    _, cart = prop.propagate_to(elapsed_s, output=OutputMode.FINAL)

    # Manual calculation
    propagated_mean = propagate_brouwer_j2(
        state.elements, elapsed_s, _MU, prop._R_e_m, prop._J2
    )
    expected_cart = brouwer_mean_to_cartesian(
        propagated_mean, _MU, prop._R_e_m, prop._J2
    )

    np.testing.assert_allclose(cart, expected_cart, rtol=1e-12)


def test_brouwer_j2_propagator_zero_time_returns_initial_cartesian():
    """At t=0, propagated Cartesian should match initial mean elements converted directly."""
    state = _make_brouwer_state()
    prop = BrouwerJ2Propagator(initial_state=state, mu_m3_s2=_MU)

    _, cart_t0 = prop.propagate_to(0.0, output=OutputMode.FINAL)
    expected = brouwer_mean_to_cartesian(state.elements, _MU, prop._R_e_m, prop._J2)

    np.testing.assert_allclose(cart_t0, expected, rtol=1e-12)


def test_brouwer_j2_propagator_reference_epoch_advances():
    """reference_epoch_s advances correctly across multiple calls."""
    state = _make_brouwer_state()
    prop = BrouwerJ2Propagator(initial_state=state, mu_m3_s2=_MU)

    prop.propagate_to(1000.0, output=OutputMode.NONE)
    assert prop.reference_epoch_s == 1000.0

    prop.propagate_by(500.0, output=OutputMode.NONE)
    assert prop.reference_epoch_s == 1500.0


def test_brouwer_j2_propagator_initial_epoch_fixed():
    """get_initial_epoch_s does not change after propagation."""
    state = _make_brouwer_state(epoch_s=100.0)
    prop = BrouwerJ2Propagator(initial_state=state, mu_m3_s2=_MU)

    prop.propagate_to(5000.0, output=OutputMode.NONE)

    assert prop.get_initial_epoch_s() == 100.0


def test_brouwer_j2_propagator_uninitialised_guard():
    """Propagation before set_initial_state raises RuntimeError."""
    from ephem_toolkit.core.propagator.base import Propagator

    class _Bare(BrouwerJ2Propagator):
        def __init__(self):
            # Skip parent __init__ to leave state unset
            Propagator.__init__(self)
            self._mu_m3_s2 = _MU
            self._R_e_m = 6378136.3
            self._J2 = 1.08262668e-3

    prop = _Bare()
    with pytest.raises(RuntimeError, match="Initial state not set"):
        prop.propagate_to(1000.0)


def test_brouwer_j2_propagator_j2_causes_raan_drift():
    """J2 secular propagation should cause RAAN to drift over time."""
    state = _make_brouwer_state()
    prop = BrouwerJ2Propagator(initial_state=state, mu_m3_s2=_MU)

    # Propagate one orbital period (~92 min for ISS)
    period_s = 2.0 * np.pi * np.sqrt(state.elements[0] ** 3 / _MU)
    _, cart_after = prop.propagate_to(period_s, output=OutputMode.FINAL)

    # Convert back to Keplerian to check RAAN changed
    kep_after = cartesian_to_keplerian(cart_after, _MU)
    kep_initial = cartesian_to_keplerian(
        brouwer_mean_to_cartesian(state.elements, _MU, prop._R_e_m, prop._J2),
        _MU,
    )

    # RAAN should have drifted (J2 causes nodal regression for prograde orbits)
    raan_diff = abs(kep_after[4] - kep_initial[4])
    if raan_diff > np.pi:
        raan_diff = 2 * np.pi - raan_diff
    assert raan_diff > 1e-6, "RAAN should drift due to J2"
