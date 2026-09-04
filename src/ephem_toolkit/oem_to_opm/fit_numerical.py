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


@dataclass(frozen=True)
class NumericalResidualDiagnostics:
    """Unweighted residual summary for one numerical-fit evaluation."""

    position_rms_m: float
    velocity_rms_m_s: float | None
    position_max_m: float
    velocity_max_m_s: float | None
    n_records: int


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
    selected = [
        (epoch, np.asarray(state, dtype=float))
        for epoch, state in reference_states
        if epoch - reference_states[0][0] <= config.fit_span_s
    ]
    if len(selected) < 2:
        raise ValueError("fit span must include at least two reference states")

    residuals: list[float] = []
    position_errors: list[float] = []
    velocity_errors: list[float] = []
    propagated_initial_state = np.asarray(initial_state, dtype=float).copy()
    if config.preserve_initial_position:
        propagated_initial_state[:3] = selected[0][1][:3]
    for epoch, reference in selected[:: max(1, round(config.fit_step_s / max(1.0, selected[1][0] - selected[0][0])) )]:
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
    if config.fit_span_s <= 0.0 or config.fit_step_s <= 0.0:
        raise ValueError("fit span and fit step must be positive")
    if config.position_weight <= 0.0 or config.velocity_weight <= 0.0:
        raise ValueError("fit weights must be positive")
    if config.observables == "position" and config.velocity_weight != 1.0:
        raise ValueError("velocity weight applies only when observables is 'state'")
    for _, state in states:
        if np.asarray(state).shape != (6,):
            raise ValueError("each reference state must contain six Cartesian values")
