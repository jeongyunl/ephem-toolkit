"""Tests for shared numerical-fit validation."""

import numpy as np
import pytest

from ephem_toolkit.oem_to_opm.fit_numerical import NumericalFitConfig, validate_numerical_fit


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
