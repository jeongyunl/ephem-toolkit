"""Tests for shared numerical-fit validation."""

import numpy as np
import pytest

from ephem_toolkit.oem_to_opm.fit_numerical import (
    NumericalFitConfig,
    build_weighted_residuals,
    config_from_propagation_options,
    config_from_fit_options,
    validate_fixed_parameter_values,
    optimize_initial_state,
    make_propagation_callback,
    validate_numerical_fit,
)


def states(count=2):
    return [(float(index), np.zeros(6)) for index in range(count)]


def test_valid_numerical_fit_configuration() -> None:
    validate_numerical_fit(states(), NumericalFitConfig())


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (NumericalFitConfig(fit_span_s=0), "fit span"),
        (NumericalFitConfig(position_weight=0), "position weight"),
        (NumericalFitConfig(parameters="initial-state,drag-coeff", drag_enabled=False), "drag to be enabled"),
        (NumericalFitConfig(parameters="initial-state,srp-coeff", srp_enabled=False), "SRP to be enabled"),
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


def test_force_parameter_fitting_can_be_enabled() -> None:
    validate_numerical_fit(
        states(),
        NumericalFitConfig(parameters="initial-state,drag-coeff", drag_enabled=True, drag_coefficient=2.2),
    )


def test_fixed_parameter_values_returns_only_selected_user_inputs() -> None:
    config = NumericalFitConfig(
        parameters="initial-state,drag-coeff",
        drag_enabled=True,
        drag_coefficient=2.2,
        srp_coefficient=1.3,
    )

    assert config.fixed_parameter_values() == {"drag_coeff": 2.2}


def test_fit_configuration_serializes_fixed_parameters() -> None:
    config = NumericalFitConfig(
        observables="position",
        velocity_weight=2.0,
        parameters="initial-state,srp-coeff",
        srp_enabled=True,
        srp_coefficient=1.3,
    )

    report_config = config.to_report_dict()

    assert report_config["observables"] == "position"
    assert report_config["velocity_weight"] == 2.0
    assert report_config["fixed_parameters"] == {"srp_coeff": 1.3}


def test_fit_configuration_builds_propagator_configuration(monkeypatch) -> None:
    import sys
    import types

    class PropagatorConfig:
        def __init__(self, **values):
            self.values = values

    monkeypatch.setitem(
        sys.modules,
        "ephem_toolkit.core.propagator.numerical",
        types.SimpleNamespace(NumericalPropagatorConfig=PropagatorConfig),
    )
    config = NumericalFitConfig(
        satellite_mass_kg=12.0,
        drag_area_m2=0.4,
        earth_gravity=(8, 8),
        integrator="rkdp_87",
        integrator_step_size_s=(30.0,),
        drag_enabled=True,
        drag_coefficient=2.2,
    )

    propagator_config = config.to_propagator_config(satellite_name="LEO3")

    assert propagator_config.values["satellite_name"] == "LEO3"
    assert propagator_config.values["satellite_drag_coefficient"] == 2.2
    assert propagator_config.values["integrator_method"] == "rkdp_87"


def test_fit_configuration_rejects_incomplete_propagator_settings(monkeypatch) -> None:
    import sys
    import types

    monkeypatch.setitem(
        sys.modules,
        "ephem_toolkit.core.propagator.numerical",
        types.SimpleNamespace(NumericalPropagatorConfig=object),
    )
    with pytest.raises(ValueError, match="mass and drag area"):
        NumericalFitConfig(satellite_mass_kg=None, drag_area_m2=None).to_propagator_config()


def test_config_from_propagation_options_preserves_fixed_coefficients() -> None:
    class Options:
        drag = True
        srp = False
        drag_coeff = 2.2
        srp_coeff = 1.3
        mass = 12.0
        drag_area = 0.4
        earth_gravity = (8, 8)
        integrator = "rkdp_87"
        integrator_step_size = (30.0,)
        moon_gravity = True
        sun_gravity = False
        venus_gravity = False
        mars_gravity = False

    config = config_from_propagation_options(
        Options(), fit_span_s=90.0, fit_step_s=10.0, parameters="initial-state,drag-coeff"
    )
    assert config.fit_span_s == 90.0
    assert config.fixed_parameter_values() == {"drag_coeff": 2.2}
    assert config.earth_gravity == (8, 8)
    assert config.integrator_step_size_s == (30.0,)
    assert config.moon_gravity is True


def test_config_from_fit_options_preserves_cli_fit_controls() -> None:
    from datetime import timedelta

    class Options:
        fit_model = "numerical"
        fit_span = timedelta(hours=1)
        fit_step = 30.0
        fit_observables = "position"
        fit_position_weight = 2.0
        fit_velocity_weight = 0.5
        fit_parameters = "initial-state"

    config = config_from_fit_options(Options())
    assert config.fit_model == "numerical"
    assert config.fit_span_s == 3600.0
    assert config.observables == "position"
    assert config.velocity_weight == 0.5


def test_validate_fixed_parameter_values_requires_exact_propagator_values() -> None:
    config = NumericalFitConfig(
        parameters="initial-state,drag-coeff",
        drag_enabled=True,
        drag_coefficient=2.2,
    )
    validate_fixed_parameter_values(config, {"drag_coeff": 2.2})
    with pytest.raises(ValueError, match="must equal"):
        validate_fixed_parameter_values(config, {"drag_coeff": 2.3})
    validate_numerical_fit(
        states(),
        NumericalFitConfig(parameters="initial-state,srp-coeff", srp_enabled=True, srp_coefficient=1.3),
    )


def test_optimizer_applies_state_bounds() -> None:
    reference = [(0.0, np.zeros(6)), (1.0, np.array([0.0, 0.0, 0.0, 10.0, 10.0, 10.0]))]
    result = optimize_initial_state(
        lambda initial, _epoch: initial,
        np.zeros(6),
        reference,
        NumericalFitConfig(fit_step_s=1.0),
        bounds=(np.full(6, -1.0), np.full(6, 1.0)),
    )

    assert np.all(result.initial_state <= 1.0)
    assert np.all(result.initial_state >= -1.0)


def test_optimizer_rejects_malformed_bounds() -> None:
    with pytest.raises(ValueError, match="six-component"):
        optimize_initial_state(
            lambda initial, _epoch: initial,
            np.zeros(6),
            states(),
            NumericalFitConfig(),
            bounds=(np.zeros(3), np.ones(3)),
        )


def test_optimizer_always_preserves_initial_position() -> None:
    target = np.array([4.0, 5.0, 6.0, 1.0, 2.0, 3.0])
    reference = [(0.0, target), (1.0, target)]
    result = optimize_initial_state(
        lambda initial, _epoch: initial,
        np.zeros(6),
        reference,
        NumericalFitConfig(
            fit_step_s=1.0,
            preserve_initial_position=False,
        ),
    )

    assert result.converged
    assert np.allclose(result.initial_state[:3], target[:3], atol=1.0e-4)


@pytest.mark.parametrize(
    "reference, message",
    [
        ([(1.0, np.zeros(6)), (1.0, np.ones(6))], "strictly increasing"),
        ([(2.0, np.zeros(6)), (1.0, np.ones(6))], "strictly increasing"),
        ([(0.0, np.full(6, np.nan)), (1.0, np.zeros(6))], "finite values"),
    ],
)
def test_validation_rejects_invalid_reference_arc(reference, message) -> None:
    with pytest.raises(ValueError, match=message):
        validate_numerical_fit(reference, NumericalFitConfig())


@pytest.mark.parametrize("initial_state", [np.zeros(3), np.full(6, np.nan)])
def test_optimizer_rejects_invalid_initial_state(initial_state) -> None:
    with pytest.raises(ValueError, match="six finite"):
        optimize_initial_state(
            lambda initial, _epoch: initial,
            initial_state,
            states(),
            NumericalFitConfig(),
        )


def test_optimizer_does_not_report_convergence_without_residual_reduction() -> None:
    reference = [(0.0, np.ones(6)), (1.0, np.ones(6))]
    result = optimize_initial_state(
        lambda _initial, _epoch: np.zeros(6),
        np.zeros(6),
        reference,
        NumericalFitConfig(fit_step_s=1.0),
    )

    assert not result.converged
    assert result.diagnostics.position_rms_m > 0.0


def test_optimizer_keeps_supplied_physical_parameters_fixed() -> None:
    result = optimize_initial_state(
        lambda initial, _epoch: initial,
        np.zeros(6),
        states(),
        NumericalFitConfig(parameters="initial-state,drag-coeff", drag_enabled=True, drag_coefficient=2.2, fit_step_s=1.0),
    )
    assert result.converged


def test_build_weighted_residuals_uses_position_only() -> None:
    reference = [(0.0, np.zeros(6)), (60.0, np.ones(6))]

    residuals, diagnostics = build_weighted_residuals(
        lambda _initial, _epoch: np.zeros(6),
        np.zeros(6),
        reference,
        NumericalFitConfig(fit_step_s=1.0),
    )

    assert residuals.shape == (61 * 3,)
    assert diagnostics.n_records == 61
    assert diagnostics.velocity_rms_m_s is None


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
    reference = [(0.0, np.array([10.0, 20.0, 30.0, 1.0, 2.0, 3.0])), (1.0, np.array([11.0, 22.0, 33.0, 1.0, 2.0, 3.0]))]

    result = optimize_initial_state(
        lambda initial, epoch: np.concatenate((initial[:3] + epoch * initial[3:], initial[3:])),
        np.zeros(6),
        reference,
        NumericalFitConfig(fit_step_s=1.0),
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

        def set_initial_state(self, initial_state):
            created.append(("reset", initial_state))

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


def test_numerical_factory_reuses_propagator_and_resets_state(monkeypatch) -> None:
    import sys
    import types

    created = []

    class InitialState:
        def __init__(self, state_m_m_s, epoch_s):
            self.state_m_m_s = state_m_m_s
            self.epoch_s = epoch_s

    class Propagator:
        def __init__(self, config, initial_state):
            created.append(("create", config, initial_state))

        def set_initial_state(self, initial_state):
            created.append(("reset", initial_state))

    monkeypatch.setitem(
        sys.modules,
        "ephem_toolkit.core.propagator.numerical",
        types.SimpleNamespace(NumericalInitialState=InitialState, NumericalPropagator=Propagator),
    )
    from ephem_toolkit.oem_to_opm.fit_numerical import make_numerical_propagator_factory

    factory = make_numerical_propagator_factory(object(), 100.0)
    first = factory(np.ones(6), 100.0)
    second = factory(np.full(6, 2.0), 100.0)

    assert first is second
    assert [entry[0] for entry in created] == ["create", "reset"]
    assert np.array_equal(created[1][1].state_m_m_s, np.full(6, 2.0))


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

    assert calls == [0.0, 60.0, 100.0]
    assert diagnostics.n_records == 3
