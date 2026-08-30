"""Tests for propagate_orbit/input_handling.py.

Verifies that build_propagation_inputs returns the correct split types
(NumericalPropagatorConfig, NumericalInitialState, target_epoch_s)
and that all fields are mapped correctly from CLI args.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from unittest.mock import patch

import numpy as np
import pytest

from ephem_toolkit.core.propagator.numerical import (
    NumericalInitialState,
    NumericalPropagatorConfig,
)
import ephem_toolkit.core.time_utils as time_utils
from ephem_toolkit.propagate_orbit.input_handling import build_propagation_inputs
from ephem_toolkit.propagate_orbit.constants import DEFAULT_SATELLITE_NAME


# ===================================================================
# Shared fixtures
# ===================================================================

_EPOCH_UTC = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
_STATE_M_M_S = np.array(
    [-2700816.14, -3314092.80, 5266346.42, 5168.606550, -5597.546618, -2131.981798],
    dtype=float,
)


def _make_cli_args(**overrides) -> argparse.Namespace:
    """Return a minimal valid argparse.Namespace for build_propagation_inputs."""
    defaults = dict(
        input_opm="input.opm",
        name="TestSat",
        mass=30.0,
        integrator="rkdp_87",
        integrator_step_size=[10.0, 1.0, 300.0],
        earth_gravity=(5, 5),
        drag_area=0.045,
        srp=False,
        srp_coeff=1.2,
        drag=False,
        drag_coeff=2.2,
        moon_gravity=False,
        sun_gravity=False,
        venus_gravity=False,
        mars_gravity=False,
        duration=3600.0,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _patch_opm_reader(state=_STATE_M_M_S, epoch=_EPOCH_UTC):
    """Patch read_initial_state_from_opm_file_or_stdin to return fixed values."""
    return patch(
        "ephem_toolkit.propagate_orbit.input_handling"
        ".read_initial_state_from_opm_file_or_stdin",
        return_value=(state, epoch),
    )


# ===================================================================
# Return type
# ===================================================================


def test_build_propagation_inputs_returns_three_tuple() -> None:
    """build_propagation_inputs returns (config, initial_state, target_epoch_s)."""
    with _patch_opm_reader():
        result = build_propagation_inputs(_make_cli_args())

    assert isinstance(result, tuple)
    assert len(result) == 3
    config, initial_state, target_epoch_s = result
    assert isinstance(config, NumericalPropagatorConfig)
    assert isinstance(initial_state, NumericalInitialState)
    assert isinstance(target_epoch_s, float)


# ===================================================================
# NumericalPropagatorConfig fields
# ===================================================================


def test_config_satellite_name() -> None:
    """Config satellite_name matches CLI --name."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(name="MySat"))
    assert config.satellite_name == "MySat"


def test_config_empty_name_uses_default() -> None:
    """Empty satellite name falls back to DEFAULT_SATELLITE_NAME."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(name=""))
    assert config.satellite_name == DEFAULT_SATELLITE_NAME


def test_config_whitespace_name_uses_default() -> None:
    """Whitespace-only satellite name falls back to DEFAULT_SATELLITE_NAME."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(name="   "))
    assert config.satellite_name == DEFAULT_SATELLITE_NAME


def test_config_mass() -> None:
    """Config satellite_mass_kg matches CLI --mass."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(mass=75.0))
    assert config.satellite_mass_kg == 75.0


def test_config_integrator_method() -> None:
    """Config integrator_method matches CLI --integrator."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(integrator="rkf_78"))
    assert config.integrator_method == "rkf_78"


def test_config_integrator_step_size_values() -> None:
    """Config integrator_step_size_values_s is a tuple from CLI --integrator-step-size."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(
            _make_cli_args(integrator_step_size=[30.0])
        )
    assert config.integrator_step_size_values_s == (30.0,)


def test_config_earth_gravity() -> None:
    """Config earth gravity degree/order match CLI --earth-gravity."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(earth_gravity=(8, 8)))
    assert config.earth_spherical_harmonic_gravity_degree == 8
    assert config.earth_spherical_harmonic_gravity_order == 8


def test_config_drag_area() -> None:
    """Config satellite_drag_area_m2 matches CLI --drag-area."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(drag_area=0.1))
    assert config.satellite_drag_area_m2 == 0.1


def test_config_perturbation_flags() -> None:
    """Config perturbation flags match CLI flags."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(
            _make_cli_args(
                srp=True,
                drag=True,
                moon_gravity=True,
                sun_gravity=True,
                venus_gravity=True,
                mars_gravity=True,
            )
        )
    assert config.is_srp_on is True
    assert config.is_earth_drag_on is True
    assert config.is_moon_gravity_on is True
    assert config.is_sun_gravity_on is True
    assert config.is_venus_gravity_on is True
    assert config.is_mars_gravity_on is True


def test_config_srp_coefficient() -> None:
    """Config srp_coefficient matches CLI --srp-coeff."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(srp_coeff=1.5))
    assert config.srp_coefficient == 1.5


def test_config_drag_coefficient() -> None:
    """Config satellite_drag_coefficient matches CLI --drag-coeff."""
    with _patch_opm_reader():
        config, _, _ = build_propagation_inputs(_make_cli_args(drag_coeff=2.5))
    assert config.satellite_drag_coefficient == 2.5


# ===================================================================
# NumericalInitialState fields
# ===================================================================


def test_initial_state_vector() -> None:
    """initial_state.state_m_m_s matches OPM-derived state vector."""
    with _patch_opm_reader(state=_STATE_M_M_S):
        _, initial_state, _ = build_propagation_inputs(_make_cli_args())
    np.testing.assert_array_equal(initial_state.state_m_m_s, _STATE_M_M_S)


def test_initial_state_epoch_is_tt_seconds() -> None:
    """initial_state.epoch_s is TT seconds from OPM epoch datetime."""
    with _patch_opm_reader(epoch=_EPOCH_UTC):
        _, initial_state, _ = build_propagation_inputs(_make_cli_args())
    expected_epoch_s = time_utils.datetime_to_tt_s(_EPOCH_UTC)
    assert initial_state.epoch_s == pytest.approx(expected_epoch_s)


# ===================================================================
# target_epoch_s
# ===================================================================


def test_target_epoch_s_equals_epoch_plus_duration() -> None:
    """target_epoch_s == initial_state.epoch_s + cli_args.duration."""
    duration = 7200.0
    with _patch_opm_reader(epoch=_EPOCH_UTC):
        _, initial_state, target_epoch_s = build_propagation_inputs(
            _make_cli_args(duration=duration)
        )
    assert target_epoch_s == pytest.approx(initial_state.epoch_s + duration)


def test_target_epoch_s_zero_duration() -> None:
    """target_epoch_s equals epoch_s when duration is 0."""
    with _patch_opm_reader(epoch=_EPOCH_UTC):
        _, initial_state, target_epoch_s = build_propagation_inputs(
            _make_cli_args(duration=0.0)
        )
    assert target_epoch_s == pytest.approx(initial_state.epoch_s)
