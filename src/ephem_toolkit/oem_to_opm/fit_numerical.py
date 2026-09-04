"""Shared validation and configuration for numerical arc fitting.

The optimizer is intentionally separate from this boundary so OEM, OMM, and
TLE wrappers can share validation before the numerical propagator is invoked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

from ephem_toolkit.propagate_orbit.constants import (
    DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2,
    DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_DEGREE,
    DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_ORDER,
    DEFAULT_INTEGRATOR_STEP_SIZE_S,
    DEFAULT_SATELLITE_DRAG_COEFFICIENT,
    DEFAULT_SATELLITE_MASS_KG,
    DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT,
)

DEFAULT_INTEGRATOR_METHOD = "rkdp_87"

SUPPORTED_FIT_MODELS = ("two-body", "numerical")
SUPPORTED_OBSERVABLES = ("position",)
SUPPORTED_PARAMETERS = (
    "initial-state",
    "initial-state,drag-coeff",
    "initial-state,srp-coeff",
)


@dataclass(frozen=True)
class NumericalFitConfig:
    """Validated options shared by numerical-fitting conversion commands."""

    fit_model: str = "numerical"
    fit_span_s: float = 7200.0
    fit_step_s: float = 60.0
    observables: str = "position"
    position_weight: float = 1.0
    end_of_span_weight: float = 2.0
    velocity_weight: float = 1.0
    parameters: str = "initial-state"
    """Parameters used by propagation; physical parameters remain fixed."""
    preserve_initial_position: bool = True
    """Legacy report field; numerical fitting always preserves initial position."""
    drag_enabled: bool = True
    srp_enabled: bool = True
    drag_coefficient: float | None = DEFAULT_SATELLITE_DRAG_COEFFICIENT
    srp_coefficient: float | None = DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT
    satellite_mass_kg: float | None = DEFAULT_SATELLITE_MASS_KG
    drag_area_m2: float | None = DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2
    earth_gravity: tuple[int, int] | None = (
        DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_DEGREE,
        DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_ORDER,
    )
    integrator: str | None = DEFAULT_INTEGRATOR_METHOD
    integrator_step_size_s: tuple[float, ...] | None = DEFAULT_INTEGRATOR_STEP_SIZE_S
    moon_gravity: bool = True
    sun_gravity: bool = True
    venus_gravity: bool = True
    mars_gravity: bool = True

    def fixed_parameter_values(self) -> dict[str, float]:
        """Return user-supplied physical parameters selected for propagation."""
        values: dict[str, float] = {}
        if self.parameters.endswith("drag-coeff") and self.drag_coefficient is not None:
            values["drag_coeff"] = self.drag_coefficient
        if self.parameters.endswith("srp-coeff") and self.srp_coefficient is not None:
            values["srp_coeff"] = self.srp_coefficient
        return values

    def to_report_dict(self) -> dict[str, object]:
        """Return a JSON-compatible description of the fit configuration."""
        return {
            "fit_model": self.fit_model,
            "fit_span_s": self.fit_span_s,
            "fit_step_s": self.fit_step_s,
            "observables": self.observables,
            "position_weight": self.position_weight,
            "end_of_span_weight": self.end_of_span_weight,
            "velocity_weight": self.velocity_weight,
            "preserve_initial_position": self.preserve_initial_position,
            "fixed_parameters": self.fixed_parameter_values(),
            "satellite_mass_kg": self.satellite_mass_kg,
            "drag_area_m2": self.drag_area_m2,
            "earth_gravity": self.earth_gravity,
            "integrator": self.integrator,
            "integrator_step_size_s": self.integrator_step_size_s,
            "moon_gravity": self.moon_gravity,
            "sun_gravity": self.sun_gravity,
            "venus_gravity": self.venus_gravity,
            "mars_gravity": self.mars_gravity,
        }

    def to_propagator_config(self, *, satellite_name: str = "FIT_TARGET"):
        """Build the existing numerical propagator configuration lazily."""
        from ephem_toolkit.core.propagator.numerical import NumericalPropagatorConfig

        if self.satellite_mass_kg is None or self.drag_area_m2 is None:
            raise ValueError("satellite mass and drag area are required for numerical propagation")
        if self.earth_gravity is None or self.integrator is None or self.integrator_step_size_s is None:
            raise ValueError("gravity and integrator settings are required for numerical propagation")
        return NumericalPropagatorConfig(
            satellite_name=satellite_name,
            satellite_mass_kg=self.satellite_mass_kg,
            integrator_method=self.integrator,
            integrator_step_size_values_s=self.integrator_step_size_s,
            earth_spherical_harmonic_gravity_degree=self.earth_gravity[0],
            earth_spherical_harmonic_gravity_order=self.earth_gravity[1],
            satellite_drag_area_m2=self.drag_area_m2,
            is_srp_on=self.srp_enabled,
            srp_coefficient=self.srp_coefficient or 0.0,
            is_earth_drag_on=self.drag_enabled,
            satellite_drag_coefficient=self.drag_coefficient or 0.0,
            is_moon_gravity_on=self.moon_gravity,
            is_sun_gravity_on=self.sun_gravity,
            is_venus_gravity_on=self.venus_gravity,
            is_mars_gravity_on=self.mars_gravity,
        )


def config_from_propagation_options(options, *, fit_span_s: float = 7200.0, fit_step_s: float = 60.0, parameters: str = "initial-state") -> NumericalFitConfig:
    """Build fixed-parameter fit configuration from propagate-orbit options."""
    return NumericalFitConfig(
        fit_span_s=fit_span_s,
        fit_step_s=fit_step_s,
        parameters=parameters,
        drag_enabled=bool(options.drag),
        srp_enabled=bool(options.srp),
        drag_coefficient=float(options.drag_coeff),
        srp_coefficient=float(options.srp_coeff),
        satellite_mass_kg=float(options.mass),
        drag_area_m2=float(options.drag_area),
        earth_gravity=tuple(options.earth_gravity),
        integrator=str(options.integrator),
        integrator_step_size_s=tuple(options.integrator_step_size),
        moon_gravity=bool(options.moon_gravity),
        sun_gravity=bool(options.sun_gravity),
        venus_gravity=bool(options.venus_gravity),
        mars_gravity=bool(options.mars_gravity),
    )


def config_from_fit_options(options) -> NumericalFitConfig:
    """Build fit configuration from parsed conversion fit-control options."""
    return NumericalFitConfig(
        fit_model=str(options.fit_model),
        fit_span_s=float(options.fit_span.total_seconds()),
        fit_step_s=float(options.fit_step),
        observables=str(options.fit_observables),
        position_weight=float(options.fit_position_weight),
        end_of_span_weight=float(getattr(options, "fit_end_weight", 2.0)),
        velocity_weight=float(getattr(options, "fit_velocity_weight", 1.0)),
        parameters=str(options.fit_parameters),
        drag_enabled=bool(getattr(options, "drag", True)),
        srp_enabled=bool(getattr(options, "srp", True)),
        drag_coefficient=getattr(options, "drag_coeff", DEFAULT_SATELLITE_DRAG_COEFFICIENT),
        srp_coefficient=getattr(options, "srp_coeff", DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT),
        satellite_mass_kg=getattr(options, "mass", DEFAULT_SATELLITE_MASS_KG),
        drag_area_m2=getattr(options, "drag_area", DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2),
        earth_gravity=tuple(getattr(options, "earth_gravity", (
            DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_DEGREE,
            DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_ORDER,
        ))),
        integrator=getattr(options, "integrator", DEFAULT_INTEGRATOR_METHOD),
        integrator_step_size_s=tuple(getattr(options, "integrator_step_size", DEFAULT_INTEGRATOR_STEP_SIZE_S)),
        moon_gravity=bool(getattr(options, "moon_gravity", True)),
        sun_gravity=bool(getattr(options, "sun_gravity", True)),
        venus_gravity=bool(getattr(options, "venus_gravity", True)),
        mars_gravity=bool(getattr(options, "mars_gravity", True)),
    )


def validate_fixed_parameter_values(config: NumericalFitConfig, propagated_values: dict[str, float]) -> None:
    """Ensure the propagator uses the configured physical values unchanged."""
    expected = config.fixed_parameter_values()
    for name, value in expected.items():
        actual = propagated_values.get(name)
        if actual is None or not np.isclose(actual, value, rtol=0.0, atol=0.0):
            raise ValueError(f"propagator {name} must equal user-supplied value {value}")


@dataclass(frozen=True)
class NumericalResidualDiagnostics:
    """Unweighted residual summary for one numerical-fit evaluation."""

    position_rms_m: float
    velocity_rms_m_s: float | None
    position_max_m: float
    velocity_max_m_s: float | None
    n_records: int


@dataclass(frozen=True)
class NumericalFitResult:
    """Result returned by the dependency-free numerical optimizer."""

    initial_state: np.ndarray
    diagnostics: NumericalResidualDiagnostics
    iterations: int
    converged: bool


def build_weighted_residuals(
    propagate,
    initial_state: np.ndarray,
    reference_states: Sequence[tuple[float, np.ndarray]],
    config: NumericalFitConfig,
    *,
    propagate_trajectory=None,
) -> tuple[np.ndarray, NumericalResidualDiagnostics]:
    """Evaluate weighted residuals against a reference arc.

    ``propagate`` receives ``(initial_state, epoch_s)`` and returns a six-value
    Cartesian state in meters and meters per second. Keeping this callback
    boundary free of Tudat makes it reusable by optimizers and unit-testable.
    """
    validate_numerical_fit(reference_states, config)
    selected = hermite_sample_reference_states(reference_states, config)
    if len(selected) < 2:
        raise ValueError("fit span must include at least two reference states")

    residuals: list[float] = []
    position_errors: list[float] = []
    propagated_initial_state = np.asarray(initial_state, dtype=float).copy()
    propagated_initial_state[:3] = selected[0][1][:3]
    if propagate_trajectory is not None:
        predicted_states = propagate_trajectory(
            propagated_initial_state, [epoch for epoch, _ in selected]
        )
    else:
        predicted_states = {
            epoch: np.asarray(propagate(propagated_initial_state, epoch), dtype=float)
            for epoch, _ in selected
        }
    for epoch, reference in selected:
        predicted = np.asarray(predicted_states[epoch], dtype=float)
        if predicted.shape != (6,):
            raise ValueError("propagate callback must return six Cartesian values")
        position_error = predicted[:3] - reference[:3]
        position_errors.append(float(np.linalg.norm(position_error)))
        # The fit objective is position-only by design. OEM velocities are used
        # only as Hermite derivative data, never as residual components.
        elapsed = epoch - selected[0][0]
        fraction = min(1.0, max(0.0, elapsed / config.fit_span_s))
        time_weight = 1.0 + fraction * (config.end_of_span_weight - 1.0)
        residuals.extend((position_error * time_weight / config.position_weight).tolist())

    diagnostics = NumericalResidualDiagnostics(
        position_rms_m=float(np.sqrt(np.mean(np.square(position_errors)))),
        velocity_rms_m_s=None,
        position_max_m=max(position_errors),
        velocity_max_m_s=None,
        n_records=len(position_errors),
    )
    return np.asarray(residuals, dtype=float), diagnostics


def hermite_sample_reference_states(
    reference_states: Sequence[tuple[float, np.ndarray]],
    config: NumericalFitConfig,
) -> list[tuple[float, np.ndarray]]:
    """Sample OEM positions on the fit grid using a Cartesian Hermite interpolator."""
    from ephem_toolkit.core.interpolator.hermite import SlidingWindowHermiteInterpolator

    first_epoch = float(reference_states[0][0])
    last_epoch = min(float(reference_states[-1][0]), first_epoch + config.fit_span_s)
    degree = min(5, len(reference_states) - 1)
    interpolator = SlidingWindowHermiteInterpolator(
        dimension=6, degree=max(1, degree), is_cartesian_state=True
    )
    interpolator.set_data(list(reference_states))
    epochs = list(np.arange(first_epoch, last_epoch, config.fit_step_s))
    if not epochs or epochs[-1] < last_epoch:
        epochs.append(last_epoch)
    sampled: list[tuple[float, np.ndarray]] = []
    for epoch in epochs:
        state = interpolator.interpolate(float(epoch))
        if state is None:
            raise ValueError("Hermite interpolation failed within the OEM arc")
        sampled.append((float(epoch), np.asarray(state, dtype=float)))
    if len(sampled) < 2:
        raise ValueError("fit span must include at least two Hermite samples")
    return sampled


def optimize_initial_state(
    propagate,
    initial_state: np.ndarray,
    reference_states: Sequence[tuple[float, np.ndarray]],
    config: NumericalFitConfig,
    *,
    max_iterations: int = 25,
    tolerance: float = 1.0e-6,
    finite_difference_step: float = 1.0e-3,
    bounds: tuple[np.ndarray, np.ndarray] | None = None,
    iteration_callback: Callable[[int, float, float, float, bool], None] | None = None,
    propagate_trajectory=None,
) -> NumericalFitResult:
    """Optimize the initial Cartesian state using NumPy Gauss-Newton steps.

    The initial position is always held at the first OEM position; only the
    three initial-velocity components are varied.
    The propagator is supplied as a callback, so this function adds no
    numerical-propagation dependency.
    """
    validate_numerical_fit(reference_states, config)
    if max_iterations <= 0 or finite_difference_step <= 0.0 or tolerance <= 0.0:
        raise ValueError("optimizer limits and finite-difference step must be positive")
    state = np.asarray(initial_state, dtype=float).copy()
    if state.shape != (6,) or not np.all(np.isfinite(state)):
        raise ValueError("initial state must contain six finite Cartesian values")
    lower = upper = None
    if bounds is not None:
        lower, upper = (np.asarray(value, dtype=float) for value in bounds)
        if lower.shape != (6,) or upper.shape != (6,) or np.any(lower > upper):
            raise ValueError("optimizer bounds must be ordered six-component vectors")
        state = np.clip(state, lower, upper)
    state[:3] = np.asarray(reference_states[0][1], dtype=float)[:3]
    variable_indices = (3, 4, 5)
    converged = False
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        residual, _ = build_weighted_residuals(propagate, state, reference_states, config, propagate_trajectory=propagate_trajectory)
        residual_norm = float(np.linalg.norm(residual))
        jacobian = np.empty((residual.size, len(variable_indices)))
        for column, index in enumerate(variable_indices):
            trial = state.copy()
            trial[index] += finite_difference_step
            trial_residual, _ = build_weighted_residuals(propagate, trial, reference_states, config, propagate_trajectory=propagate_trajectory)
            jacobian[:, column] = (trial_residual - residual) / finite_difference_step
        delta, *_ = np.linalg.lstsq(jacobian, -residual, rcond=None)
        state[list(variable_indices)] += delta
        if lower is not None and upper is not None:
            state = np.clip(state, lower, upper)
        updated_residual, _ = build_weighted_residuals(propagate, state, reference_states, config, propagate_trajectory=propagate_trajectory)
        updated_norm = float(np.linalg.norm(updated_residual))
        if updated_norm <= tolerance or (
            float(np.linalg.norm(delta)) <= tolerance and updated_norm < residual_norm
        ):
            converged = True
            break
        if iteration_callback is not None:
            iteration_callback(
                iterations,
                residual_norm,
                float(np.linalg.norm(delta)),
                updated_norm,
                converged,
            )
    if iteration_callback is not None and converged:
        iteration_callback(
            iterations,
            residual_norm,
            float(np.linalg.norm(delta)),
            updated_norm,
            converged,
        )
    _, diagnostics = build_weighted_residuals(propagate, state, reference_states, config, propagate_trajectory=propagate_trajectory)
    return NumericalFitResult(state, diagnostics, iterations, converged)


def make_propagation_callback(propagator_factory, epoch_s: float):
    """Adapt a propagator factory to the optimizer callback protocol.

    The factory receives ``(initial_state, epoch_s)`` and returns an object
    exposing ``propagate_to(epoch_s)``. The result may be either a state array
    or the common ``(epoch_s, state)`` tuple.
    """
    def propagate(initial_state: np.ndarray, target_epoch_s: float) -> np.ndarray:
        propagator = propagator_factory(np.asarray(initial_state, dtype=float), epoch_s)
        result = propagator.propagate_to(target_epoch_s)
        if isinstance(result, tuple):
            result = result[1]
        return np.asarray(result, dtype=float)

    return propagate


def make_numerical_propagator_factory(config, epoch_s: float):
    """Create a lazy factory for the repository's numerical propagator.

    The import is local so validation and optimizer unit tests do not require
    the optional propagation engine to be importable.
    """
    from ephem_toolkit.core.propagator.numerical import (
        NumericalInitialState,
        NumericalPropagator,
    )

    propagator = None

    def factory(initial_state: np.ndarray, initial_epoch_s: float):
        nonlocal propagator
        state = NumericalInitialState(
            state_m_m_s=np.asarray(initial_state, dtype=float),
            epoch_s=initial_epoch_s,
        )
        if propagator is None:
            propagator = NumericalPropagator(config, state)
        else:
            # Keep the environment and force model, but reset the trial state
            # and propagation history for every optimizer evaluation.
            propagator.set_initial_state(state)
        return propagator

    return factory


def make_numerical_trajectory_callback(propagator_factory, initial_epoch_s: float, fit_span_s: float):
    """Propagate each trial once to the fit endpoint and interpolate its trajectory."""
    from ephem_toolkit.core.interpolator.hermite import SlidingWindowHermiteInterpolator
    from ephem_toolkit.core.propagator import OutputMode

    def propagate_trajectory(initial_state: np.ndarray, target_epochs: Sequence[float]):
        propagator = propagator_factory(np.asarray(initial_state, dtype=float), initial_epoch_s)
        result = propagator.propagate_to(
            initial_epoch_s + fit_span_s, output=OutputMode.TRAJECTORY
        )
        if not isinstance(result, list) or not result:
            raise ValueError("numerical propagator did not return a trajectory")
        degree = min(5, len(result) - 1)
        interpolator = SlidingWindowHermiteInterpolator(
            dimension=6, degree=max(1, degree), is_cartesian_state=True
        )
        interpolator.set_data(result)
        values = {}
        for epoch in target_epochs:
            state = interpolator.interpolate(float(epoch))
            if state is None:
                raise ValueError("propagated trajectory interpolation failed")
            values[epoch] = np.asarray(state, dtype=float)
        return values

    return propagate_trajectory


def validate_numerical_fit(
    states: Sequence[tuple[float, np.ndarray]], config: NumericalFitConfig
) -> None:
    """Validate a numerical fit request before propagation or optimization."""
    if len(states) < 2:
        raise ValueError("at least two reference states are required for fitting")
    if config.fit_model not in SUPPORTED_FIT_MODELS:
        raise ValueError(f"fit model must be one of: {', '.join(SUPPORTED_FIT_MODELS)}")
    if config.observables not in SUPPORTED_OBSERVABLES:
        raise ValueError(f"observables must be one of: {', '.join(SUPPORTED_OBSERVABLES)}")
    if config.parameters not in SUPPORTED_PARAMETERS:
        raise ValueError("unsupported fit parameters")
    if config.parameters.endswith("drag-coeff") and not config.drag_enabled:
        raise ValueError("drag coefficient fitting requires drag to be enabled")
    if config.parameters.endswith("drag-coeff") and config.drag_coefficient is None:
        raise ValueError("drag coefficient must be provided when drag is enabled")
    if config.parameters.endswith("srp-coeff") and not config.srp_enabled:
        raise ValueError("SRP coefficient fitting requires SRP to be enabled")
    if config.parameters.endswith("srp-coeff") and config.srp_coefficient is None:
        raise ValueError("SRP coefficient must be provided when SRP is enabled")
    if config.drag_coefficient is not None and config.drag_coefficient <= 0.0:
        raise ValueError("drag coefficient must be positive")
    if config.srp_coefficient is not None and config.srp_coefficient <= 0.0:
        raise ValueError("SRP coefficient must be positive")
    if config.fit_span_s <= 0.0 or config.fit_step_s <= 0.0:
        raise ValueError("fit span and fit step must be positive")
    if config.position_weight <= 0.0:
        raise ValueError("position weight must be positive")
    if config.end_of_span_weight < 1.0:
        raise ValueError("end-of-span weight must be at least 1")
    previous_epoch = None
    for epoch, state in states:
        if not np.isfinite(epoch):
            raise ValueError("reference epochs must be finite")
        if previous_epoch is not None and epoch <= previous_epoch:
            raise ValueError("reference epochs must be strictly increasing")
        previous_epoch = epoch
        if np.asarray(state).shape != (6,):
            raise ValueError("each reference state must contain six Cartesian values")
        if not np.all(np.isfinite(np.asarray(state, dtype=float))):
            raise ValueError("reference states must contain only finite values")
