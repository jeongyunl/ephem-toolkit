from unittest.mock import Mock

import numpy as np
import pytest

import ephem_toolkit.propagate_orbit.propagation as propagation
from ephem_toolkit.core.propagator.base import OutputMode


def test_run_propagation_writes_state_and_dependent_variable_outputs(
    monkeypatch,
) -> None:
    trajectory = [(10.0, np.zeros(6)), (20.0, np.ones(6))]
    dependent_variables = {"speed": np.array([1.0, 2.0])}
    saved_settings = [object()]
    test_config = object()
    test_initial_state = object()

    class FakePropagator:
        def __init__(self, config, initial_state):
            assert config is test_config
            assert initial_state is test_initial_state
            self.dependent_variable_dictionary = dependent_variables
            self.dependent_variable_save_settings = saved_settings

        def propagate_to(self, target_epoch_s, output):
            assert target_epoch_s == 20.0
            assert output is OutputMode.TRAJECTORY
            return trajectory

    write_oem = Mock()
    write_csv = Mock()
    monkeypatch.setattr(propagation, "NumericalPropagator", FakePropagator)
    monkeypatch.setattr(propagation, "write_state_history_oem", write_oem)
    monkeypatch.setattr(propagation, "write_dependent_variables_csv", write_csv)

    propagation.run_propagation(
        test_config,
        test_initial_state,
        target_epoch_s=20.0,
        output_oem_path="states.oem",
        output_dep_vars_path="dep_vars.csv",
        data_only=True,
    )

    write_oem.assert_called_once_with(
        {10.0: trajectory[0][1], 20.0: trajectory[1][1]},
        "states.oem",
        test_config,
        True,
    )
    write_csv.assert_called_once_with(
        "dep_vars.csv", dependent_variables, saved_settings
    )


@pytest.mark.parametrize(
    ("trajectory", "dictionary", "settings", "message"),
    [
        (None, {}, [], "did not produce a trajectory"),
        ([(20.0, np.zeros(6))], None, [], "did not retain dependent-variable metadata"),
        ([(20.0, np.zeros(6))], {}, None, "did not retain dependent-variable metadata"),
    ],
)
def test_run_propagation_rejects_missing_propagation_outputs(
    monkeypatch, trajectory, dictionary, settings, message
) -> None:
    class FakePropagator:
        def __init__(self, *_args):
            self.dependent_variable_dictionary = dictionary
            self.dependent_variable_save_settings = settings

        def propagate_to(self, *_args, **_kwargs):
            return trajectory

    monkeypatch.setattr(propagation, "NumericalPropagator", FakePropagator)

    with pytest.raises(RuntimeError, match=message):
        propagation.run_propagation(object(), object(), 20.0, "-", None, False)
