"""Shared validation and configuration for numerical arc fitting.

The optimizer is intentionally separate from this boundary so OEM, OMM, and
TLE wrappers can share validation before the numerical propagator is invoked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

SUPPORTED_FIT_MODELS = ("two-body", "numerical")
SUPPORTED_OBSERVABLES = ("position", "state")
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
    velocity_weight: float = 1.0
    parameters: str = "initial-state"
    preserve_initial_position: bool = True
    """Keep the fitted epoch position equal to the first reference position."""
    drag_enabled: bool = False
    srp_enabled: bool = False


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
) -> tuple[np.ndarray, NumericalResidualDiagnostics]:
    """Evaluate weighted residuals against a reference arc.

    ``propagate`` receives ``(initial_state, epoch_s)`` and returns a six-value
    Cartesian state in meters and meters per second. Keeping this callback
    boundary free of Tudat makes it reusable by optimizers and unit-testable.
    """
    validate_numerical_fit(reference_states, config)
    candidates = [
        (epoch, np.asarray(state, dtype=float))
        for epoch, state in reference_states
        if epoch - reference_states[0][0] <= config.fit_span_s
    ]
    selected = [candidates[0]]
    for candidate in candidates[1:]:
        if candidate[0] - selected[-1][0] >= config.fit_step_s:
            selected.append(candidate)
    if len(selected) < 2:
        raise ValueError("fit span must include at least two reference states")

    residuals: list[float] = []
    position_errors: list[float] = []
    velocity_errors: list[float] = []
    propagated_initial_state = np.asarray(initial_state, dtype=float).copy()
    if config.preserve_initial_position:
        propagated_initial_state[:3] = selected[0][1][:3]
    for epoch, reference in selected:
        predicted = np.asarray(propagate(propagated_initial_state, epoch), dtype=float)
        if predicted.shape != (6,):
            raise ValueError("propagate callback must return six Cartesian values")
        position_error = predicted[:3] - reference[:3]
        velocity_error = predicted[3:] - reference[3:]
        position_errors.append(float(np.linalg.norm(position_error)))
        velocity_errors.append(float(np.linalg.norm(velocity_error)))
        residuals.extend((position_error / config.position_weight).tolist())
        if config.observables == "state":
            residuals.extend((velocity_error / config.velocity_weight).tolist())

    diagnostics = NumericalResidualDiagnostics(
        position_rms_m=float(np.sqrt(np.mean(np.square(position_errors)))),
        velocity_rms_m_s=(float(np.sqrt(np.mean(np.square(velocity_errors)))) if config.observables == "state" else None),
        position_max_m=max(position_errors),
        velocity_max_m_s=(max(velocity_errors) if config.observables == "state" else None),
        n_records=len(position_errors),
    )
    return np.asarray(residuals, dtype=float), diagnostics


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
) -> NumericalFitResult:
    """Optimize the initial Cartesian state using NumPy Gauss-Newton steps.

    With the default position constraint, only the initial velocity is varied.
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
    if config.preserve_initial_position:
        state[:3] = np.asarray(reference_states[0][1], dtype=float)[:3]
    variable_indices = (3, 4, 5) if config.preserve_initial_position else tuple(range(6))
    converged = False
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        residual, _ = build_weighted_residuals(propagate, state, reference_states, config)
        jacobian = np.empty((residual.size, len(variable_indices)))
        for column, index in enumerate(variable_indices):
            trial = state.copy()
            trial[index] += finite_difference_step
            trial_residual, _ = build_weighted_residuals(propagate, trial, reference_states, config)
            jacobian[:, column] = (trial_residual - residual) / finite_difference_step
        delta, *_ = np.linalg.lstsq(jacobian, -residual, rcond=None)
        state[list(variable_indices)] += delta
        if lower is not None and upper is not None:
            state = np.clip(state, lower, upper)
        if float(np.linalg.norm(delta)) <= tolerance:
            converged = True
            break
    _, diagnostics = build_weighted_residuals(propagate, state, reference_states, config)
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

    def factory(initial_state: np.ndarray, initial_epoch_s: float):
        return NumericalPropagator(
            config,
            NumericalInitialState(
                state_m_m_s=np.asarray(initial_state, dtype=float),
                epoch_s=initial_epoch_s,
            ),
        )

    return factory


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
    if config.parameters.endswith("srp-coeff") and not config.srp_enabled:
        raise ValueError("SRP coefficient fitting requires SRP to be enabled")
    if config.fit_span_s <= 0.0 or config.fit_step_s <= 0.0:
        raise ValueError("fit span and fit step must be positive")
    if config.position_weight <= 0.0 or config.velocity_weight <= 0.0:
        raise ValueError("fit weights must be positive")
    if config.observables == "position" and config.velocity_weight != 1.0:
        raise ValueError("velocity weight applies only when observables is 'state'")
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
