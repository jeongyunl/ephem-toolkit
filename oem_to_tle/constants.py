"""Constants for TLE estimation."""

from __future__ import annotations

SECONDS_PER_DAY_S: float = 86400.0
"""Number of seconds in one day (s)."""

MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE: float = 0.99999999
"""Maximum absolute value of the TLE mean-motion first derivative field."""

PHASE_MATCH_BLEND_SOFTENING: float = 6.0
"""Softening count used in the phase-match blending weight formula (dimensionless)."""

STATE_MATCH_MAX_ITERATIONS: int = 200
"""Maximum Gauss-Newton iterations for epoch-state matching (dimensionless)."""

STATE_MATCH_POSITION_WEIGHT: float = 1.0
"""Weight applied to position residuals in the state-match cost function."""

STATE_MATCH_VELOCITY_WEIGHT: float = 1000.0
"""Weight applied to velocity residuals in the state-match cost function."""

BSTAR_FIT_MAX_ABS: float = 1.0e-3
"""Maximum absolute B* value considered during B* fitting."""

BSTAR_FIT_INITIAL_STEP_1_ER: float = 2.0e-5
"""Initial step size for the B* coordinate-descent search (1/ER)."""

BSTAR_FIT_MAX_ITERATIONS: int = 12
"""Maximum iterations for the B* coordinate-descent search (dimensionless)."""

BSTAR_SAMPLE_COUNT: int = 9
"""Number of evenly spaced post-epoch records used for B* fitting (dimensionless)."""

STATE_MATCH_PARAMETER_STEPS: dict[str, float] = {
    "inclination_deg": 0.005,
    "raan_deg": 0.005,
    "eccentricity": 2.0e-5,
    "arg_perigee_deg": 0.01,
    "mean_anomaly_deg": 0.01,
    "mean_motion_rev_per_day": 1.0e-4,
}
"""Finite-difference step sizes for each TLE element during state-match refinement."""
