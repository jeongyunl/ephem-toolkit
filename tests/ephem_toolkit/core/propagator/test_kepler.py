"""Tests for KeplerPropagator."""

import numpy as np
import pytest

from ephem_toolkit.core.propagator import (
    cartesian_to_keplerian,
)
from ephem_toolkit.core.propagator import (
    AnomalyType,
    KeplerianState,
    KeplerPropagator,
    OutputMode,
)


def test_kepler_propagator_anomaly_type():
    """Verify KeplerPropagator uses true anomaly."""
    assert KeplerPropagator.anomaly_type == AnomalyType.TRUE


def test_kepler_propagator_initialization():
    """Test KeplerPropagator initialization."""
    elements = np.array([7000e3, 0.001, 51.6, 0.0, 0.0, 0.0])
    epoch_s = 0.0
    initial_state = KeplerianState(elements=elements, epoch_s=epoch_s)

    prop = KeplerPropagator(initial_state=initial_state)

    assert prop.get_initial_epoch_s() == epoch_s
    assert prop.reference_epoch_s == epoch_s
    np.testing.assert_array_equal(prop._initial_state.elements, elements)


def test_kepler_propagator_custom_mu():
    """Test KeplerPropagator with custom gravitational parameter."""
    elements = np.array([7000e3, 0.001, 51.6, 0.0, 0.0, 0.0])
    epoch_s = 0.0
    initial_state = KeplerianState(elements=elements, epoch_s=epoch_s)
    custom_mu = 4.0e14

    prop = KeplerPropagator(initial_state=initial_state, mu_m3_s2=custom_mu)

    assert prop._mu_m3_s2 == custom_mu


def test_kepler_propagator_propagate_to_final():
    """Test propagate_to with OutputMode.FINAL."""
    elements = np.array([7000e3, 0.001, np.radians(51.6), 0.0, 0.0, 0.0])
    epoch_s = 0.0
    initial_state = KeplerianState(elements=elements, epoch_s=epoch_s)

    prop = KeplerPropagator(initial_state=initial_state)

    # Propagate forward 1 hour
    target_epoch_s = 3600.0
    result = prop.propagate_to(target_epoch_s, output=OutputMode.FINAL)

    assert isinstance(result, tuple)
    epoch, state = result
    assert epoch == target_epoch_s
    assert isinstance(state, np.ndarray)
    assert state.shape == (6,)

    # Verify reference epoch advanced
    assert prop.reference_epoch_s == target_epoch_s

    # Verify result matches manual calculation via round-trip
    kep_recovered = cartesian_to_keplerian(state, prop._mu_m3_s2)
    assert kep_recovered.shape == (6,)
    # Semi-major axis, eccentricity, inclination unchanged
    np.testing.assert_allclose(kep_recovered[:3], elements[:3], rtol=1e-10)
    # Angles (omega, RAAN) may wrap — compare modulo 2π
    np.testing.assert_allclose(
        kep_recovered[3:5] % (2 * np.pi), elements[3:5] % (2 * np.pi), atol=1e-10
    )


def test_kepler_propagator_propagate_by():
    """Test propagate_by with elapsed time."""
    elements = np.array([7000e3, 0.001, np.radians(51.6), 0.0, 0.0, 0.0])
    epoch_s = 1000.0
    initial_state = KeplerianState(elements=elements, epoch_s=epoch_s)

    prop = KeplerPropagator(initial_state=initial_state)

    # Propagate forward 1 hour from initial epoch
    elapsed_s = 3600.0
    result = prop.propagate_by(elapsed_s, output=OutputMode.FINAL)

    assert isinstance(result, tuple)
    epoch, state = result
    assert epoch == epoch_s + elapsed_s
    assert isinstance(state, np.ndarray)
    assert state.shape == (6,)


def test_kepler_propagator_propagate_to_none():
    """Test propagate_to with OutputMode.NONE."""
    elements = np.array([7000e3, 0.001, np.radians(51.6), 0.0, 0.0, 0.0])
    epoch_s = 0.0
    initial_state = KeplerianState(elements=elements, epoch_s=epoch_s)

    prop = KeplerPropagator(initial_state=initial_state)

    target_epoch_s = 3600.0
    result = prop.propagate_to(target_epoch_s, output=OutputMode.NONE)

    assert result is None
    # Verify reference epoch still advanced
    assert prop.reference_epoch_s == target_epoch_s


def test_kepler_propagator_propagate_to_trajectory():
    """Test propagate_to with OutputMode.TRAJECTORY."""
    elements = np.array([7000e3, 0.001, np.radians(51.6), 0.0, 0.0, 0.0])
    epoch_s = 0.0
    initial_state = KeplerianState(elements=elements, epoch_s=epoch_s)

    prop = KeplerPropagator(initial_state=initial_state)

    target_epoch_s = 3600.0
    result = prop.propagate_to(target_epoch_s, output=OutputMode.TRAJECTORY)

    assert isinstance(result, list)
    assert len(result) == 1  # Default implementation returns single sample
    epoch, state = result[0]
    assert epoch == target_epoch_s
    assert isinstance(state, np.ndarray)
    assert state.shape == (6,)


def test_kepler_propagator_reference_epoch_advances():
    """Test that reference_epoch_s advances correctly."""
    elements = np.array([7000e3, 0.001, np.radians(51.6), 0.0, 0.0, 0.0])
    epoch_s = 0.0
    initial_state = KeplerianState(elements=elements, epoch_s=epoch_s)

    prop = KeplerPropagator(initial_state=initial_state)

    assert prop.reference_epoch_s == epoch_s

    # First propagation
    prop.propagate_to(1000.0, output=OutputMode.NONE)
    assert prop.reference_epoch_s == 1000.0

    # Second propagation
    prop.propagate_to(2000.0, output=OutputMode.NONE)
    assert prop.reference_epoch_s == 2000.0

    # propagate_by uses reference_epoch_s
    prop.propagate_by(500.0, output=OutputMode.NONE)
    assert prop.reference_epoch_s == 2500.0


def test_kepler_propagator_initial_epoch_fixed():
    """Test that get_initial_epoch_s remains fixed."""
    elements = np.array([7000e3, 0.001, np.radians(51.6), 0.0, 0.0, 0.0])
    epoch_s = 0.0
    initial_state = KeplerianState(elements=elements, epoch_s=epoch_s)

    prop = KeplerPropagator(initial_state=initial_state)

    initial_epoch = prop.get_initial_epoch_s()
    assert initial_epoch == epoch_s

    # Propagate forward
    prop.propagate_to(3600.0, output=OutputMode.NONE)

    # Initial epoch should not change
    assert prop.get_initial_epoch_s() == initial_epoch


def test_keplerian_state_immutable():
    """Test that KeplerianState is immutable."""
    elements = np.array([7000e3, 0.001, np.radians(51.6), 0.0, 0.0, 0.0])
    epoch_s = 0.0
    state = KeplerianState(elements=elements, epoch_s=epoch_s)

    # Cannot modify epoch_s
    with pytest.raises(Exception):  # FrozenInstanceError
        state.epoch_s = 1000.0

    # Cannot modify elements array
    with pytest.raises(ValueError):  # array is read-only
        state.elements[0] = 8000e3


def test_keplerian_state_elements_copied():
    """Test that KeplerianState copies the elements array."""
    elements = np.array([7000e3, 0.001, np.radians(51.6), 0.0, 0.0, 0.0])
    epoch_s = 0.0
    state = KeplerianState(elements=elements, epoch_s=epoch_s)

    # Modifying original array should not affect state
    elements[0] = 8000e3
    assert state.elements[0] == 7000e3
