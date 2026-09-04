"""Tests for shared numerical-fit validation."""

import numpy as np
import pytest

from ephem_toolkit.oem_to_opm.fit_numerical import (
    NumericalFitConfig,
    build_weighted_residuals,
    validate_numerical_fit,
)


def states(count=2):
    return [(float(index), np.zeros(6)) for index in range(count)]


def test_valid_numerical_fit_configuration() -> None:
    validate_numerical_fit(states(), NumericalFitConfig(observables="state", velocity_weight=2.0))


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (NumericalFitConfig(fit_span_s=0), "fit span"),
        (NumericalFitConfig(observables="state", velocity_weight=0), "weights"),
        (NumericalFitConfig(observables="position", velocity_weight=2), "velocity weight"),
        (NumericalFitConfig(parameters="drag-coeff"), "parameters"),
    ],
)
def test_invalid_numerical_fit_configuration(config, message) -> None:
    with pytest.raises(ValueError, match=message):
        validate_numerical_fit(states(), config)


def test_fit_requires_two_six_component_states() -> None:
    with pytest.raises(ValueError, match="two reference states"):
        validate_numerical_fit(states(1), NumericalFitConfig())
    with pytest.raises(ValueError, match="six Cartesian"):
        validate_numerical_fit([(0.0, np.zeros(3)), (1.0, np.zeros(3))], NumericalFitConfig())


def test_build_weighted_residuals_supports_full_state() -> None:
    reference = [(0.0, np.zeros(6)), (60.0, np.ones(6))]

    residuals, diagnostics = build_weighted_residuals(
        lambda _initial, _epoch: np.zeros(6),
        np.zeros(6),
        reference,
        NumericalFitConfig(observables="state"),
    )

    assert residuals.shape == (12,)
    assert diagnostics.n_records == 2
    assert diagnostics.position_max_m == np.sqrt(3.0)
    assert diagnostics.velocity_rms_m_s == np.sqrt(3.0 / 2.0)


def test_build_weighted_residuals_preserves_initial_position() -> None:
    reference = [(0.0, np.array([10.0, 20.0, 30.0, 1.0, 2.0, 3.0])), (60.0, np.zeros(6))]
    observed_initial_states = []

    def propagate(initial_state, _epoch):
        observed_initial_states.append(initial_state)
        return initial_state

    build_weighted_residuals(propagate, np.ones(6), reference, NumericalFitConfig())

    assert np.array_equal(observed_initial_states[0][:3], reference[0][1][:3])
    assert np.array_equal(observed_initial_states[0][3:], np.ones(3))
