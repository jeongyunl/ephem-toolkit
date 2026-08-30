"""Tests for NumericalPropagator, NumericalPropagatorConfig, NumericalInitialState.

These tests do not require tudatpy — they cover data type construction,
constants, and base-class interface contracts only.
Tests that require a live Tudat propagation run are marked with
``pytest.importorskip("tudatpy")``.
"""

from __future__ import annotations

import numpy as np
import pytest

from ephem_toolkit.core.propagator.numerical import (
    DEFAULT_INTEGRATOR_METHOD,
    SUPPORTED_INTEGRATOR_METHODS,
    NumericalInitialState,
    NumericalPropagator,
    NumericalPropagatorConfig,
)


# ===================================================================
# Shared fixtures
# ===================================================================

ISS_STATE_M_M_S = np.array(
    [-2700816.14, -3314092.80, 5266346.42, 5168.606550, -5597.546618, -2131.981798],
    dtype=float,
)
"""ISS-like Cartesian state [x, y, z, vx, vy, vz] in m and m/s."""

EPOCH_S = 0.0
"""Reference epoch: J2000 TT."""


def make_config(**overrides) -> NumericalPropagatorConfig:
    """Return a minimal valid NumericalPropagatorConfig."""
    defaults = dict(
        satellite_name="TestSat",
        satellite_mass_kg=30.0,
        integrator_method="rkdp_87",
        integrator_step_size_values_s=(10.0, 1.0, 300.0),
        earth_spherical_harmonic_gravity_degree=5,
        earth_spherical_harmonic_gravity_order=5,
        satellite_drag_area_m2=0.045,
        is_srp_on=False,
        srp_coefficient=1.2,
        is_earth_drag_on=False,
        satellite_drag_coefficient=2.2,
        is_moon_gravity_on=False,
        is_sun_gravity_on=False,
        is_venus_gravity_on=False,
        is_mars_gravity_on=False,
    )
    defaults.update(overrides)
    return NumericalPropagatorConfig(**defaults)


def make_initial_state(
    state: np.ndarray = ISS_STATE_M_M_S,
    epoch_s: float = EPOCH_S,
) -> NumericalInitialState:
    """Return a NumericalInitialState."""
    return NumericalInitialState(state_m_m_s=state, epoch_s=epoch_s)


# ===================================================================
# Constants
# ===================================================================


def test_supported_integrator_methods_nonempty() -> None:
    """SUPPORTED_INTEGRATOR_METHODS is a non-empty tuple of strings."""
    assert isinstance(SUPPORTED_INTEGRATOR_METHODS, tuple)
    assert len(SUPPORTED_INTEGRATOR_METHODS) > 0
    for method in SUPPORTED_INTEGRATOR_METHODS:
        assert isinstance(method, str)


def test_default_integrator_method_in_supported() -> None:
    """DEFAULT_INTEGRATOR_METHOD is in SUPPORTED_INTEGRATOR_METHODS."""
    assert DEFAULT_INTEGRATOR_METHOD in SUPPORTED_INTEGRATOR_METHODS


# ===================================================================
# NumericalPropagatorConfig
# ===================================================================


def test_config_construction() -> None:
    """NumericalPropagatorConfig stores all fields correctly."""
    config = make_config()
    assert config.satellite_name == "TestSat"
    assert config.satellite_mass_kg == 30.0
    assert config.integrator_method == "rkdp_87"
    assert config.integrator_step_size_values_s == (10.0, 1.0, 300.0)
    assert config.earth_spherical_harmonic_gravity_degree == 5
    assert config.earth_spherical_harmonic_gravity_order == 5
    assert config.satellite_drag_area_m2 == 0.045
    assert config.is_srp_on is False
    assert config.srp_coefficient == 1.2
    assert config.is_earth_drag_on is False
    assert config.satellite_drag_coefficient == 2.2
    assert config.is_moon_gravity_on is False
    assert config.is_sun_gravity_on is False
    assert config.is_venus_gravity_on is False
    assert config.is_mars_gravity_on is False


def test_config_is_frozen() -> None:
    """NumericalPropagatorConfig is immutable (frozen dataclass)."""
    config = make_config()
    with pytest.raises(Exception):  # FrozenInstanceError
        config.satellite_name = "Other"  # type: ignore[misc]


def test_config_fixed_step_size() -> None:
    """Config accepts single step-size value (fixed-step integrator)."""
    config = make_config(integrator_step_size_values_s=(30.0,))
    assert config.integrator_step_size_values_s == (30.0,)
    assert len(config.integrator_step_size_values_s) == 1


def test_config_perturbations_enabled() -> None:
    """Config stores perturbation flags correctly when all enabled."""
    config = make_config(
        is_srp_on=True,
        is_earth_drag_on=True,
        is_moon_gravity_on=True,
        is_sun_gravity_on=True,
        is_venus_gravity_on=True,
        is_mars_gravity_on=True,
    )
    assert config.is_srp_on is True
    assert config.is_earth_drag_on is True
    assert config.is_moon_gravity_on is True
    assert config.is_sun_gravity_on is True
    assert config.is_venus_gravity_on is True
    assert config.is_mars_gravity_on is True


# ===================================================================
# NumericalInitialState
# ===================================================================


def test_initial_state_construction() -> None:
    """NumericalInitialState stores state and epoch."""
    state = make_initial_state()
    np.testing.assert_array_equal(state.state_m_m_s, ISS_STATE_M_M_S)
    assert state.epoch_s == EPOCH_S


def test_initial_state_is_frozen() -> None:
    """NumericalInitialState is immutable (frozen dataclass)."""
    state = make_initial_state()
    with pytest.raises(Exception):  # FrozenInstanceError
        state.epoch_s = 1000.0  # type: ignore[misc]


def test_initial_state_nonzero_epoch() -> None:
    """NumericalInitialState stores non-zero epoch correctly."""
    epoch_s = 12345.678
    state = make_initial_state(epoch_s=epoch_s)
    assert state.epoch_s == epoch_s


# ===================================================================
# NumericalPropagator — base class contracts (no tudatpy)
# ===================================================================


def test_numerical_propagator_get_initial_epoch_s() -> None:
    """get_initial_epoch_s returns initial_state.epoch_s."""
    config = make_config()
    initial_state = make_initial_state(epoch_s=5000.0)
    prop = NumericalPropagator(config=config, initial_state=initial_state)
    assert prop.get_initial_epoch_s() == 5000.0


def test_numerical_propagator_reference_epoch_at_construction() -> None:
    """reference_epoch_s equals initial epoch immediately after construction."""
    config = make_config()
    initial_state = make_initial_state(epoch_s=5000.0)
    prop = NumericalPropagator(config=config, initial_state=initial_state)
    assert prop.reference_epoch_s == 5000.0


def test_numerical_propagator_initial_epoch_fixed_after_set_initial_state() -> None:
    """get_initial_epoch_s does not change after set_initial_state with new epoch."""
    config = make_config()
    initial_state = make_initial_state(epoch_s=1000.0)
    prop = NumericalPropagator(config=config, initial_state=initial_state)

    new_state = make_initial_state(epoch_s=9999.0)
    prop.set_initial_state(new_state)

    # get_initial_epoch_s now reflects the new state
    assert prop.get_initial_epoch_s() == 9999.0
    assert prop.reference_epoch_s == 9999.0


def test_numerical_propagator_stores_config() -> None:
    """NumericalPropagator stores config correctly."""
    config = make_config(satellite_name="MySat", satellite_mass_kg=50.0)
    initial_state = make_initial_state()
    prop = NumericalPropagator(config=config, initial_state=initial_state)
    assert prop._config.satellite_name == "MySat"
    assert prop._config.satellite_mass_kg == 50.0


def test_numerical_propagator_initial_state_set_flag() -> None:
    """_initial_state_set is True after construction."""
    config = make_config()
    initial_state = make_initial_state()
    prop = NumericalPropagator(config=config, initial_state=initial_state)
    assert prop._initial_state_set is True
