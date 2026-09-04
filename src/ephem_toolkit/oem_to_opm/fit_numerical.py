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
