"""Tests for base propagator interface."""

import numpy as np
import pytest

from ephem_toolkit.core.propagator import KeplerianState, OutputMode
from ephem_toolkit.core.propagator.base import Propagator


class MockPropagator(Propagator[KeplerianState]):
    """Mock propagator for testing base class behavior."""

    def __init__(self):
        super().__init__()
        self._state_called = False

    def set_initial_state(self, initial_state: KeplerianState) -> None:
        super().set_initial_state(initial_state)
        self._initial_state = initial_state
        self._reference_epoch_s = initial_state.epoch_s

    def get_initial_epoch_s(self) -> float:
        return self._initial_state.epoch_s

    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        self._state_called = True
        # Return dummy state
        return np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])


def test_propagator_requires_initial_state():
    """Test that propagator raises if initial state not set."""
    prop = MockPropagator()

    with pytest.raises(RuntimeError, match="Initial state not set"):
        prop.propagate_to(1000.0)

    with pytest.raises(RuntimeError, match="Initial state not set"):
        prop.propagate_by(1000.0)


def test_propagator_reference_epoch_requires_initial_state():
    """Test that reference_epoch_s raises if initial state not set."""
    prop = MockPropagator()

    with pytest.raises(RuntimeError, match="Reference epoch not set"):
        _ = prop.reference_epoch_s


def test_propagator_after_set_initial_state():
    """Test that propagator works after set_initial_state."""
    prop = MockPropagator()
    elements = np.array([7000e3, 0.001, 0.0, 0.0, 0.0, 0.0])
    initial_state = KeplerianState(elements=elements, epoch_s=0.0)

    prop.set_initial_state(initial_state)

    # Should not raise
    result = prop.propagate_to(1000.0, output=OutputMode.FINAL)
    assert result is not None
    assert prop._state_called


def test_propagate_to_requires_non_decreasing_epoch():
    """Target epochs cannot move backward relative to the current reference."""
    prop = MockPropagator()
    elements = np.array([7000e3, 0.001, 0.0, 0.0, 0.0, 0.0])
    initial_state = KeplerianState(elements=elements, epoch_s=100.0)
    prop.set_initial_state(initial_state)

    with pytest.raises(
        ValueError, match="greater than or equal to current reference_epoch_s"
    ):
        prop.propagate_to(99.0, output=OutputMode.FINAL)

    result = prop.propagate_to(100.0, output=OutputMode.FINAL)
    assert result[0] == 100.0


def test_output_mode_none():
    """Test OutputMode.NONE returns None."""
    prop = MockPropagator()
    elements = np.array([7000e3, 0.001, 0.0, 0.0, 0.0, 0.0])
    initial_state = KeplerianState(elements=elements, epoch_s=0.0)
    prop.set_initial_state(initial_state)

    result = prop.propagate_to(1000.0, output=OutputMode.NONE)
    assert result is None
    assert prop.reference_epoch_s == 1000.0


def test_output_mode_final():
    """Test OutputMode.FINAL returns (epoch, state)."""
    prop = MockPropagator()
    elements = np.array([7000e3, 0.001, 0.0, 0.0, 0.0, 0.0])
    initial_state = KeplerianState(elements=elements, epoch_s=0.0)
    prop.set_initial_state(initial_state)

    result = prop.propagate_to(1000.0, output=OutputMode.FINAL)
    assert isinstance(result, tuple)
    epoch, state = result
    assert epoch == 1000.0
    assert isinstance(state, np.ndarray)
    assert state.shape == (6,)


def test_output_mode_trajectory():
    """Test OutputMode.TRAJECTORY returns list of (epoch, state)."""
    prop = MockPropagator()
    elements = np.array([7000e3, 0.001, 0.0, 0.0, 0.0, 0.0])
    initial_state = KeplerianState(elements=elements, epoch_s=0.0)
    prop.set_initial_state(initial_state)

    result = prop.propagate_to(1000.0, output=OutputMode.TRAJECTORY)
    assert isinstance(result, list)
    assert len(result) >= 1
    epoch, state = result[0]
    assert isinstance(epoch, float)
    assert isinstance(state, np.ndarray)


def test_invalid_output_mode():
    """Test that invalid output mode raises ValueError."""
    prop = MockPropagator()
    elements = np.array([7000e3, 0.001, 0.0, 0.0, 0.0, 0.0])
    initial_state = KeplerianState(elements=elements, epoch_s=0.0)
    prop.set_initial_state(initial_state)

    # Create an invalid enum-like value
    class FakeMode:
        pass

    with pytest.raises(ValueError, match="Unknown output mode"):
        prop.propagate_to(1000.0, output=FakeMode())


def test_propagate_by_uses_reference_epoch():
    """Test that propagate_by correctly uses reference_epoch_s."""
    prop = MockPropagator()
    elements = np.array([7000e3, 0.001, 0.0, 0.0, 0.0, 0.0])
    initial_state = KeplerianState(elements=elements, epoch_s=100.0)
    prop.set_initial_state(initial_state)

    # Reference epoch starts at initial epoch
    assert prop.reference_epoch_s == 100.0

    # Propagate by 50 seconds
    result = prop.propagate_by(50.0, output=OutputMode.FINAL)
    epoch, _ = result
    assert epoch == 150.0
    assert prop.reference_epoch_s == 150.0

    # Propagate by another 50 seconds (from new reference epoch)
    result = prop.propagate_by(50.0, output=OutputMode.FINAL)
    epoch, _ = result
    assert epoch == 200.0
    assert prop.reference_epoch_s == 200.0
