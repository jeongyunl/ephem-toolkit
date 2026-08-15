from __future__ import annotations

import numpy as np

from tudatpy_utils import evaluate_interpolator_accuracy as mod
from tudatpy_utils.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)


def _make_test_states() -> list[tuple[float, np.ndarray]]:
    times = np.linspace(0.0, 10.0, 11)
    positions = np.column_stack(
        [
            np.sin(times),
            0.5 * np.cos(times),
            0.2 * times,
        ]
    )
    velocities = np.column_stack(
        [
            np.cos(times),
            -0.5 * np.sin(times),
            np.full_like(times, 0.2),
        ]
    )
    return [
        (float(t), np.concatenate((position, velocity)))
        for t, position, velocity in zip(times, positions, velocities)
    ]


def test_boundary_accuracy_summary_returns_finite_stats() -> None:
    states = _make_test_states()
    metrics = mod.evaluate_boundary_accuracy(
        states,
        interpolation_spec=InterpolationSpec(
            interp_type=InterpolationType.HERMITE,
            degree=5,
        ),
        step_size=1.0,
    )

    assert metrics["n_boundary_points"] > 0
    assert np.isfinite(metrics["max_pos_err_m"])
    assert np.isfinite(metrics["rms_pos_err_m"])
    assert np.isfinite(metrics["max_vel_err_m_s"])
