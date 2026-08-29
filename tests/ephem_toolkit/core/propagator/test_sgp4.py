"""Tests for Sgp4Propagator (requires tudatpy)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ephem_toolkit.core.propagator.base import OutputMode
from ephem_toolkit.core.propagator.sgp4 import read_tle, tle_epoch_to_tt_s

pytest.importorskip("tudatpy")

from ephem_toolkit.core.propagator.sgp4 import Sgp4Propagator

TEST_DATA_DIR = Path(__file__).parents[3] / "data"
ISS_TLE_PATH = TEST_DATA_DIR / "ISS-ZARYA_1998-067A.tle"


@pytest.fixture(scope="module")
def iss_tle():
    return read_tle(ISS_TLE_PATH)


def test_sgp4_propagator_initialization(iss_tle):
    """Sgp4Propagator initializes without error."""
    prop = Sgp4Propagator(initial_state=iss_tle)
    assert prop._tle is iss_tle
    assert prop._initial_state_set


def test_sgp4_propagator_initial_epoch(iss_tle):
    """get_initial_epoch_s matches tle_epoch_to_tt_s."""
    prop = Sgp4Propagator(initial_state=iss_tle)
    expected = tle_epoch_to_tt_s(iss_tle.epoch_year, iss_tle.epoch_day)
    assert prop.get_initial_epoch_s() == pytest.approx(expected)
    assert prop.reference_epoch_s == pytest.approx(expected)


def test_sgp4_propagator_propagate_to_final(iss_tle):
    """propagate_to returns (epoch, Cartesian state) at TLE epoch."""
    prop = Sgp4Propagator(initial_state=iss_tle)
    epoch_s = prop.get_initial_epoch_s()

    result = prop.propagate_to(epoch_s, output=OutputMode.FINAL)

    assert isinstance(result, tuple)
    epoch, state = result
    assert epoch == pytest.approx(epoch_s)
    assert isinstance(state, np.ndarray)
    assert state.shape == (6,)
    # Position magnitude should be LEO range (~6400–8000 km)
    pos_km = np.linalg.norm(state[:3]) / 1000.0
    assert 6400.0 < pos_km < 8000.0


def test_sgp4_propagator_propagate_by(iss_tle):
    """propagate_by advances reference epoch correctly."""
    prop = Sgp4Propagator(initial_state=iss_tle)
    initial_epoch = prop.reference_epoch_s

    epoch, state = prop.propagate_by(3600.0, output=OutputMode.FINAL)

    assert epoch == pytest.approx(initial_epoch + 3600.0)
    assert state.shape == (6,)
    assert prop.reference_epoch_s == pytest.approx(initial_epoch + 3600.0)


def test_sgp4_propagator_propagate_to_none(iss_tle):
    """propagate_to with NONE advances epoch without returning state."""
    prop = Sgp4Propagator(initial_state=iss_tle)
    target = prop.get_initial_epoch_s() + 1000.0

    result = prop.propagate_to(target, output=OutputMode.NONE)

    assert result is None
    assert prop.reference_epoch_s == pytest.approx(target)


def test_sgp4_propagator_reference_epoch_advances(iss_tle):
    """reference_epoch_s advances across multiple calls."""
    prop = Sgp4Propagator(initial_state=iss_tle)
    t0 = prop.reference_epoch_s

    prop.propagate_to(t0 + 1000.0, output=OutputMode.NONE)
    assert prop.reference_epoch_s == pytest.approx(t0 + 1000.0)

    prop.propagate_by(500.0, output=OutputMode.NONE)
    assert prop.reference_epoch_s == pytest.approx(t0 + 1500.0)


def test_sgp4_propagator_initial_epoch_fixed(iss_tle):
    """get_initial_epoch_s does not change after propagation."""
    prop = Sgp4Propagator(initial_state=iss_tle)
    initial_epoch = prop.get_initial_epoch_s()

    prop.propagate_by(10000.0, output=OutputMode.NONE)

    assert prop.get_initial_epoch_s() == pytest.approx(initial_epoch)


def test_sgp4_propagator_set_initial_state_replaces_tle(iss_tle):
    """set_initial_state can replace the TLE after construction."""
    prop = Sgp4Propagator(initial_state=iss_tle)
    original_epoch = prop.get_initial_epoch_s()

    # Re-set with same TLE — epoch should be identical
    prop.set_initial_state(iss_tle)
    assert prop.get_initial_epoch_s() == pytest.approx(original_epoch)
    assert prop.reference_epoch_s == pytest.approx(original_epoch)
