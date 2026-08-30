"""Tests for DSSTPropagator."""

import numpy as np
import pytest

from ephem_toolkit.core.consts import EARTH_GRAVITATIONAL_PARAMETER_M3_S2
from ephem_toolkit.core.propagator.dsst import (
    DsstPerturbations,
    DSSTPropagator,
    compute_dsst_j2_short_period_corrections,
    dsst_mean_to_cartesian,
    dsst_mean_to_osculating,
    osculating_to_dsst_mean,
)
from ephem_toolkit.core.propagator import (
    AnomalyType,
    KeplerianState,
    OutputMode,
)
from ephem_toolkit.core.propagator.kepler import (
    cartesian_to_keplerian,
    mean_to_true_anomaly,
    true_to_mean_anomaly,
)

# ISS-like osculating elements: [a, e, i, omega, RAAN, theta]
_ISS_OSCULATING = np.array(
    [
        6778e3,  # a (m)
        0.0005,  # e
        np.radians(51.6),  # i (rad)
        np.radians(30.0),  # omega (rad)
        np.radians(45.0),  # RAAN (rad)
        np.radians(10.0),  # true anomaly (rad)
    ]
)
_MU = EARTH_GRAVITATIONAL_PARAMETER_M3_S2


def _make_dsst_state(epoch_s: float = 0.0) -> KeplerianState:
    """Create a KeplerianState with DSST mean elements."""
    mean_elements = osculating_to_dsst_mean(_ISS_OSCULATING, epoch_s)
    return KeplerianState(elements=mean_elements, epoch_s=epoch_s)


def propagate_dsst(
    mean_elements: np.ndarray,
    time_elapsed_s: float,
    mu_m3_s2: float,
    perturbations: DsstPerturbations | None = None,
) -> np.ndarray:
    """Helper function to propagate DSST mean elements using DSSTPropagator."""
    if perturbations is None:
        perturbations = DsstPerturbations()

    state = KeplerianState(elements=mean_elements, epoch_s=0.0)
    prop = DSSTPropagator(
        initial_state=state, perturbations=perturbations, mu_m3_s2=mu_m3_s2
    )
    _, cart = prop.propagate_to(time_elapsed_s, output=OutputMode.FINAL)

    # Convert back to mean elements
    osc = cartesian_to_keplerian(cart, mu_m3_s2)
    return osculating_to_dsst_mean(osc, time_elapsed_s, perturbations)


# ===================================================================
# Test DsstPerturbations configuration
# ===================================================================


def test_dsst_perturbations_defaults():
    """Test DsstPerturbations default configuration."""
    pert = DsstPerturbations()

    assert pert.include_j2 is True
    assert pert.include_j3 is False
    assert pert.include_j4 is False
    assert pert.include_drag is False
    assert pert.include_srp is False
    assert pert.include_sun is False
    assert pert.include_moon is False
    assert pert.atmosphere_model == "exponential"
    assert pert.ephemeris_source == "analytical"


def test_dsst_perturbations_custom():
    """Test DsstPerturbations with custom configuration."""
    pert = DsstPerturbations(
        include_j2=True,
        include_j3=True,
        include_drag=True,
        drag_coeff=2.5,
        mass_kg=500.0,
    )

    assert pert.include_j2 is True
    assert pert.include_j3 is True
    assert pert.drag_coeff == 2.5
    assert pert.mass_kg == 500.0


# ===================================================================
# Test element conversions
# ===================================================================


def test_dsst_mean_to_osculating_shape():
    """Test dsst_mean_to_osculating returns correct shape."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    osc = dsst_mean_to_osculating(mean_elements, epoch_s=0.0)

    assert osc.shape == (6,)
    assert np.isfinite(osc).all()


def test_dsst_mean_to_osculating_invalid_shape():
    """Test dsst_mean_to_osculating raises on invalid shape."""
    with pytest.raises(ValueError, match="shape"):
        dsst_mean_to_osculating(np.array([1, 2, 3]), epoch_s=0.0)


def test_osculating_to_dsst_mean_shape():
    """Test osculating_to_dsst_mean returns correct shape."""
    mean = osculating_to_dsst_mean(_ISS_OSCULATING, epoch_s=0.0)

    assert mean.shape == (6,)
    assert np.isfinite(mean).all()


def test_osculating_to_dsst_mean_invalid_shape():
    """Test osculating_to_dsst_mean raises on invalid shape."""
    with pytest.raises(ValueError, match="shape"):
        osculating_to_dsst_mean(np.array([1, 2, 3, 4, 5]), epoch_s=0.0)


def test_dsst_mean_osculating_roundtrip():
    """Test mean->osculating->mean conversion round-trip."""
    # Start with osculating elements
    osc_initial = _ISS_OSCULATING.copy()

    # Convert to mean
    mean = osculating_to_dsst_mean(osc_initial, epoch_s=0.0)

    # Convert back to osculating
    osc_final = dsst_mean_to_osculating(mean, epoch_s=0.0)

    # Should match within tolerance
    np.testing.assert_allclose(osc_final, osc_initial, rtol=1e-9, atol=1e-9)


def test_dsst_mean_osculating_roundtrip_reverse():
    """Test osculating->mean->osculating conversion round-trip."""
    # Start with mean elements
    mean_initial = _ISS_OSCULATING.copy()
    mean_initial[5] = true_to_mean_anomaly(mean_initial[5], mean_initial[1])

    # Convert to osculating
    osc = dsst_mean_to_osculating(mean_initial, epoch_s=0.0)

    # Convert back to mean
    mean_final = osculating_to_dsst_mean(osc, epoch_s=0.0)

    # Should match within tolerance
    np.testing.assert_allclose(mean_final, mean_initial, rtol=1e-9, atol=1e-9)


def test_osculating_to_dsst_mean_convergence_failure():
    """Test osculating_to_dsst_mean raises on convergence failure."""
    # Use extreme elements that might not converge
    extreme = np.array([6778e3, 0.9, np.radians(90), 0, 0, 0])

    with pytest.raises(RuntimeError, match="failed to converge"):
        osculating_to_dsst_mean(extreme, epoch_s=0.0, max_iter=2, tolerance=1e-15)


def test_dsst_j2_short_period_corrections_shape():
    """Test compute_dsst_j2_short_period_corrections returns correct shape."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    osc = compute_dsst_j2_short_period_corrections(mean_elements)

    assert osc.shape == (6,)


def test_dsst_mean_to_osculating_no_j2():
    """Test dsst_mean_to_osculating with J2 disabled."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    pert = DsstPerturbations(include_j2=False)
    osc = dsst_mean_to_osculating(mean_elements, epoch_s=0.0, perturbations=pert)

    # Without J2, only anomaly conversion should occur
    expected = mean_elements.copy()
    expected[5] = mean_to_true_anomaly(mean_elements[5], mean_elements[1])

    np.testing.assert_allclose(osc, expected, rtol=1e-12)


# ===================================================================
# Test propagation
# ===================================================================


def test_propagate_dsst_shape():
    """Test propagate_dsst returns correct shape."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    propagated = propagate_dsst(mean_elements, time_elapsed_s=3600.0, mu_m3_s2=_MU)

    assert propagated.shape == (6,)
    assert np.isfinite(propagated).all()


def test_propagate_dsst_zero_time():
    """Test propagate_dsst with zero elapsed time returns same elements."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    propagated = propagate_dsst(mean_elements, time_elapsed_s=0.0, mu_m3_s2=_MU)

    # Relaxed tolerance due to round-trip conversion in helper
    np.testing.assert_allclose(propagated, mean_elements, rtol=1e-9, atol=1e-8)


def test_propagate_dsst_j2_causes_raan_drift():
    """Test J2 secular propagation causes RAAN drift."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    # Propagate one orbital period
    period_s = 2.0 * np.pi * np.sqrt(mean_elements[0] ** 3 / _MU)
    propagated = propagate_dsst(mean_elements, time_elapsed_s=period_s, mu_m3_s2=_MU)

    # RAAN should have changed
    raan_diff = abs(propagated[4] - mean_elements[4])
    assert raan_diff > 1e-6, "RAAN should drift due to J2"


def test_propagate_dsst_j2_causes_omega_drift():
    """Test J2 secular propagation causes argument of periapsis drift."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    # Propagate one orbital period
    period_s = 2.0 * np.pi * np.sqrt(mean_elements[0] ** 3 / _MU)
    propagated = propagate_dsst(mean_elements, time_elapsed_s=period_s, mu_m3_s2=_MU)

    # Argument of periapsis should have changed
    omega_diff = abs(propagated[3] - mean_elements[3])
    assert omega_diff > 1e-6, "Argument of periapsis should drift due to J2"


def test_propagate_dsst_no_j2_keplerian():
    """Test propagate_dsst without J2 is Keplerian motion."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    pert = DsstPerturbations(include_j2=False)
    period_s = 2.0 * np.pi * np.sqrt(mean_elements[0] ** 3 / _MU)
    propagated = propagate_dsst(
        mean_elements, time_elapsed_s=period_s, mu_m3_s2=_MU, perturbations=pert
    )

    # a, e, i, omega, RAAN should be unchanged (Keplerian)
    np.testing.assert_allclose(propagated[0], mean_elements[0], rtol=1e-12)  # a
    np.testing.assert_allclose(propagated[1], mean_elements[1], rtol=1e-12)  # e
    np.testing.assert_allclose(propagated[2], mean_elements[2], rtol=1e-12)  # i
    np.testing.assert_allclose(propagated[3], mean_elements[3], rtol=1e-12)  # omega
    np.testing.assert_allclose(propagated[4], mean_elements[4], rtol=1e-12)  # RAAN


def test_dsst_mean_to_cartesian_shape():
    """Test dsst_mean_to_cartesian returns correct shape."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    cart = dsst_mean_to_cartesian(mean_elements, _MU, epoch_s=0.0)

    assert cart.shape == (6,)
    assert np.isfinite(cart).all()


# ===================================================================
# Test DSSTPropagator class
# ===================================================================


def test_dsst_propagator_anomaly_type():
    """DSSTPropagator uses mean anomaly."""
    assert DSSTPropagator.anomaly_type == AnomalyType.MEAN


def test_dsst_propagator_initialization():
    """Test DSSTPropagator initialization."""
    state = _make_dsst_state(epoch_s=1000.0)
    prop = DSSTPropagator(initial_state=state, mu_m3_s2=_MU)

    assert prop.get_initial_epoch_s() == 1000.0
    assert prop.reference_epoch_s == 1000.0
    np.testing.assert_array_equal(prop._initial_state.elements, state.elements)


def test_dsst_propagator_custom_perturbations():
    """Test DSSTPropagator with custom perturbations."""
    state = _make_dsst_state()
    pert = DsstPerturbations(include_j2=True, include_j3=True)

    prop = DSSTPropagator(initial_state=state, perturbations=pert, mu_m3_s2=_MU)

    assert prop._perturbations.include_j2 is True
    assert prop._perturbations.include_j3 is True


def test_dsst_propagator_propagate_to_final():
    """Test propagate_to with OutputMode.FINAL returns (epoch, Cartesian state)."""
    state = _make_dsst_state()
    prop = DSSTPropagator(initial_state=state, mu_m3_s2=_MU)

    target_s = 3600.0
    result = prop.propagate_to(target_s, output=OutputMode.FINAL)

    assert isinstance(result, tuple)
    epoch, cart = result
    assert epoch == target_s
    assert isinstance(cart, np.ndarray)
    assert cart.shape == (6,)
    assert prop.reference_epoch_s == target_s


def test_dsst_propagator_propagate_by():
    """Test propagate_by with elapsed time."""
    state = _make_dsst_state(epoch_s=500.0)
    prop = DSSTPropagator(initial_state=state, mu_m3_s2=_MU)

    epoch, cart = prop.propagate_by(3600.0, output=OutputMode.FINAL)

    assert epoch == 500.0 + 3600.0
    assert cart.shape == (6,)


def test_dsst_propagator_propagate_to_none():
    """Test propagate_to with OutputMode.NONE advances reference epoch."""
    state = _make_dsst_state()
    prop = DSSTPropagator(initial_state=state, mu_m3_s2=_MU)

    result = prop.propagate_to(3600.0, output=OutputMode.NONE)

    assert result is None
    assert prop.reference_epoch_s == 3600.0


def test_dsst_propagator_matches_manual_calculation():
    """Verify _propagate_to_impl matches manual propagate_dsst + dsst_mean_to_cartesian."""
    state = _make_dsst_state()
    prop = DSSTPropagator(initial_state=state, mu_m3_s2=_MU)

    elapsed_s = 3600.0
    _, cart = prop.propagate_to(elapsed_s, output=OutputMode.FINAL)

    # Manual calculation
    propagated_mean = propagate_dsst(
        state.elements, elapsed_s, _MU, prop._perturbations
    )
    expected_cart = dsst_mean_to_cartesian(
        propagated_mean, _MU, elapsed_s, prop._perturbations
    )

    np.testing.assert_allclose(cart, expected_cart, rtol=1e-12)


def test_dsst_propagator_zero_time_returns_initial_cartesian():
    """At t=0, propagated Cartesian should match initial mean elements converted directly."""
    state = _make_dsst_state()
    prop = DSSTPropagator(initial_state=state, mu_m3_s2=_MU)

    _, cart_t0 = prop.propagate_to(0.0, output=OutputMode.FINAL)
    expected = dsst_mean_to_cartesian(state.elements, _MU, 0.0, prop._perturbations)

    np.testing.assert_allclose(cart_t0, expected, rtol=1e-12)


def test_dsst_propagator_reference_epoch_advances():
    """reference_epoch_s advances correctly across multiple calls."""
    state = _make_dsst_state()
    prop = DSSTPropagator(initial_state=state, mu_m3_s2=_MU)

    prop.propagate_to(1000.0, output=OutputMode.NONE)
    assert prop.reference_epoch_s == 1000.0

    prop.propagate_by(500.0, output=OutputMode.NONE)
    assert prop.reference_epoch_s == 1500.0


def test_dsst_propagator_initial_epoch_fixed():
    """get_initial_epoch_s does not change after propagation."""
    state = _make_dsst_state(epoch_s=100.0)
    prop = DSSTPropagator(initial_state=state, mu_m3_s2=_MU)

    prop.propagate_to(5000.0, output=OutputMode.NONE)

    assert prop.get_initial_epoch_s() == 100.0


def test_dsst_propagator_singularity_warning_circular():
    """Test singularity warning for near-circular orbit."""
    circular_osc = _ISS_OSCULATING.copy()
    circular_osc[1] = 1e-7  # Very small eccentricity

    mean = osculating_to_dsst_mean(circular_osc, epoch_s=0.0)
    state = KeplerianState(elements=mean, epoch_s=0.0)

    with pytest.warns(UserWarning, match="Near-circular"):
        DSSTPropagator(initial_state=state, mu_m3_s2=_MU)


def test_dsst_propagator_singularity_warning_equatorial():
    """Test singularity warning for near-equatorial orbit."""
    equatorial_osc = _ISS_OSCULATING.copy()
    equatorial_osc[2] = np.radians(0.5)  # Very small inclination

    mean = osculating_to_dsst_mean(equatorial_osc, epoch_s=0.0)
    state = KeplerianState(elements=mean, epoch_s=0.0)

    with pytest.warns(UserWarning, match="Near-equatorial"):
        DSSTPropagator(initial_state=state, mu_m3_s2=_MU)


def test_dsst_propagator_j2_causes_raan_drift():
    """J2 secular propagation should cause RAAN to drift over time."""
    state = _make_dsst_state()
    prop = DSSTPropagator(initial_state=state, mu_m3_s2=_MU)

    # Propagate one orbital period
    period_s = 2.0 * np.pi * np.sqrt(state.elements[0] ** 3 / _MU)
    _, cart_after = prop.propagate_to(period_s, output=OutputMode.FINAL)

    # Convert back to Keplerian to check RAAN changed
    kep_after = cartesian_to_keplerian(cart_after, _MU)
    kep_initial = cartesian_to_keplerian(
        dsst_mean_to_cartesian(state.elements, _MU, 0.0, prop._perturbations),
        _MU,
    )

    # RAAN should have drifted
    raan_diff = abs(kep_after[4] - kep_initial[4])
    if raan_diff > np.pi:
        raan_diff = 2 * np.pi - raan_diff
    assert raan_diff > 1e-6, "RAAN should drift due to J2"


def test_dsst_element_indices():
    """Verify element ordering matches kepler.py conventions."""
    from ephem_toolkit.core.propagator.kepler import (
        SEMI_MAJOR_AXIS_INDEX,
        ECCENTRICITY_INDEX,
        INCLINATION_INDEX,
        ARGUMENT_OF_PERIAPSIS_INDEX,
        RAAN_INDEX,
        MEAN_ANOMALY_INDEX,
    )

    assert SEMI_MAJOR_AXIS_INDEX == 0
    assert ECCENTRICITY_INDEX == 1
    assert INCLINATION_INDEX == 2
    assert ARGUMENT_OF_PERIAPSIS_INDEX == 3
    assert RAAN_INDEX == 4
    assert MEAN_ANOMALY_INDEX == 5


# ===================================================================
# Test J3/J4 secular rates
# ===================================================================


def test_propagate_dsst_j3_changes_omega():
    """Test J3 secular rate changes argument of periapsis."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    pert_j2 = DsstPerturbations(include_j2=True, include_j3=False)
    pert_j2j3 = DsstPerturbations(include_j2=True, include_j3=True)

    period_s = 2.0 * np.pi * np.sqrt(mean_elements[0] ** 3 / _MU)

    prop_j2 = propagate_dsst(mean_elements, period_s, _MU, pert_j2)
    prop_j2j3 = propagate_dsst(mean_elements, period_s, _MU, pert_j2j3)

    assert prop_j2[3] != prop_j2j3[3], "J3 should affect omega secular rate"


def test_propagate_dsst_j4_changes_raan():
    """Test J4 secular rate changes RAAN."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    pert_j2 = DsstPerturbations(include_j2=True, include_j4=False)
    pert_j2j4 = DsstPerturbations(include_j2=True, include_j4=True)

    period_s = 2.0 * np.pi * np.sqrt(mean_elements[0] ** 3 / _MU)

    prop_j2 = propagate_dsst(mean_elements, period_s, _MU, pert_j2)
    prop_j2j4 = propagate_dsst(mean_elements, period_s, _MU, pert_j2j4)

    assert prop_j2[4] != prop_j2j4[4], "J4 should affect RAAN secular rate"


def test_propagate_dsst_j2j3j4_all_enabled():
    """Test propagation with J2+J3+J4 all enabled returns valid state."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    pert = DsstPerturbations(include_j2=True, include_j3=True, include_j4=True)
    propagated = propagate_dsst(mean_elements, 3600.0, _MU, pert)

    assert propagated.shape == (6,)
    assert np.isfinite(propagated).all()
    # Relaxed tolerance due to round-trip conversion
    np.testing.assert_allclose(propagated[0], mean_elements[0], rtol=1e-9)
    np.testing.assert_allclose(propagated[1], mean_elements[1], rtol=1e-9)
    np.testing.assert_allclose(propagated[2], mean_elements[2], rtol=1e-9)


def test_propagate_dsst_j3_zero_eccentricity_guard():
    """Test J3 secular rate skipped for near-zero eccentricity."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[1] = 1e-9
    mean_elements[5] = 0.0

    pert = DsstPerturbations(include_j2=True, include_j3=True)
    propagated = propagate_dsst(mean_elements, 3600.0, _MU, pert)
    assert np.isfinite(propagated).all()


# ===================================================================
# Test drag secular rates
# ===================================================================


def test_propagate_dsst_drag_decays_semi_major_axis():
    """Test drag causes semi-major axis decay."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    pert = DsstPerturbations(
        include_j2=True,
        include_drag=True,
        drag_coeff=2.2,
        drag_area_m2=10.0,
        mass_kg=420000.0,  # ISS mass
    )

    propagated = propagate_dsst(mean_elements, 86400.0, _MU, pert)

    # Semi-major axis should decrease due to drag
    assert propagated[0] < mean_elements[0], "Drag should decay semi-major axis"
    assert np.isfinite(propagated).all()


def test_propagate_dsst_drag_circularizes_orbit():
    """Test drag reduces eccentricity (circularization)."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[1] = 0.01  # Larger eccentricity to see effect
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    pert = DsstPerturbations(
        include_j2=True,
        include_drag=True,
        drag_coeff=2.2,
        drag_area_m2=10.0,
        mass_kg=420000.0,
    )

    propagated = propagate_dsst(mean_elements, 86400.0, _MU, pert)

    assert propagated[1] <= mean_elements[1], "Drag should reduce eccentricity"
    assert propagated[1] >= 0.0, "Eccentricity must remain non-negative"


def test_propagate_dsst_no_drag_a_unchanged():
    """Test without drag, semi-major axis is unchanged."""
    mean_elements = _ISS_OSCULATING.copy()
    mean_elements[5] = true_to_mean_anomaly(mean_elements[5], mean_elements[1])

    pert = DsstPerturbations(include_j2=True, include_drag=False)
    propagated = propagate_dsst(mean_elements, 86400.0, _MU, pert)

    np.testing.assert_allclose(propagated[0], mean_elements[0], rtol=1e-12)
