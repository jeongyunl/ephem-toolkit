"""Tests for shared numerical-fit validation."""

import numpy as np
import pytest

from ephem_toolkit.oem_to_opm.fit_numerical import (
    NumericalFitConfig,
    build_weighted_residuals,
    optimize_initial_state,
    make_propagation_callback,
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
        NumericalFitConfig(observables="state", fit_step_s=1.0),
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


def test_optimize_initial_state_uses_numpy_only_and_preserves_position() -> None:
    reference = [(0.0, np.array([10.0, 20.0, 30.0, 1.0, 2.0, 3.0])), (1.0, np.array([10.0, 20.0, 30.0, 2.0, 3.0, 4.0]))]

    result = optimize_initial_state(
        lambda initial, epoch: initial + np.array([0.0, 0.0, 0.0, epoch, epoch, epoch]),
        np.zeros(6),
        reference,
        NumericalFitConfig(observables="state", fit_step_s=1.0),
    )

    assert result.converged
    assert np.array_equal(result.initial_state[:3], reference[0][1][:3])
    assert np.allclose(result.initial_state[3:], [1.0, 2.0, 3.0], atol=1.0e-4)


def test_make_propagation_callback_adapts_propagator_factory() -> None:
    class Propagator:
        def propagate_to(self, epoch):
            return epoch, np.full(6, epoch)

    callback = make_propagation_callback(lambda state, epoch: Propagator(), 10.0)
    assert np.array_equal(callback(np.zeros(6), 20.0), np.full(6, 20.0))


def test_numerical_factory_is_lazy_and_builds_initial_state(monkeypatch) -> None:
    import sys
    import types

    created = []

    class InitialState:
        def __init__(self, state_m_m_s, epoch_s):
            self.state_m_m_s = state_m_m_s
            self.epoch_s = epoch_s

    class Propagator:
        def __init__(self, config, initial_state):
            created.append((config, initial_state))

    fake_module = types.SimpleNamespace(
        NumericalInitialState=InitialState,
        NumericalPropagator=Propagator,
    )
    monkeypatch.setitem(sys.modules, "ephem_toolkit.core.propagator.numerical", fake_module)
    config = object()

    from ephem_toolkit.oem_to_opm.fit_numerical import make_numerical_propagator_factory

    factory = make_numerical_propagator_factory(config, 100.0)
    factory(np.ones(6), 100.0)

    assert created[0][0] is config
    assert np.array_equal(created[0][1].state_m_m_s, np.ones(6))
    assert created[0][1].epoch_s == 100.0


def test_residual_sampling_handles_irregular_epochs_and_fit_span() -> None:
    reference = [(0.0, np.zeros(6)), (30.0, np.ones(6)), (75.0, np.full(6, 2.0)), (150.0, np.full(6, 3.0))]
    calls = []

    def propagate(_initial, epoch):
        calls.append(epoch)
        return np.zeros(6)

    _, diagnostics = build_weighted_residuals(
        propagate,
        np.zeros(6),
        reference,
        NumericalFitConfig(fit_span_s=100.0, fit_step_s=60.0),
    )

    assert calls == [0.0, 75.0]
    assert diagnostics.n_records == 2
