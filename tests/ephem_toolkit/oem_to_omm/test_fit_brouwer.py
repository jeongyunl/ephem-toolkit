"""Tests for oem_to_omm/fit_brouwer.py — Mean Keplerian element fitting with J2 secular propagation."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

import ephem_toolkit.oem_to_omm.fit_brouwer as fit_brouwer
from ephem_toolkit.oem_to_omm.fit_common import (
    FitDiagnostics,
    PropagationComparison,
)


def test_fit_brouwer_module_imports() -> None:
    """Should successfully import the fit_brouwer module."""
    assert fit_brouwer is not None


def test_fit_brouwer_function_exists() -> None:
    """Should have fit_brouwer function."""
    assert hasattr(fit_brouwer, "fit_brouwer")
    assert callable(fit_brouwer.fit_brouwer)


def test_compute_brouwer_propagation_comparison_exists() -> None:
    """Should have compute_brouwer_propagation_comparison function."""
    assert hasattr(fit_brouwer, "compute_brouwer_propagation_comparison")
    assert callable(fit_brouwer.compute_brouwer_propagation_comparison)


def test_format_brouwer_output_exists() -> None:
    """Should have format_brouwer_output function."""
    assert hasattr(fit_brouwer, "format_brouwer_output")
    assert callable(fit_brouwer.format_brouwer_output)


def test_fit_brouwer_rejects_arcs_with_fewer_than_two_records() -> None:
    with pytest.raises(ValueError, match="At least 2 state vectors"):
        fit_brouwer.fit_brouwer([(0.0, np.zeros(6))], fit_span_s=10.0)


def test_fit_brouwer_fits_velocity_and_filters_to_span(monkeypatch) -> None:
    states = [
        (0.0, np.array([7.0e6, 0, 0, 0.0, 7.5e3, 10.0])),
        (10.0, np.array([7.0e6, 10, 0, 0.0, 7.5e3, 10.0])),
        (30.0, np.array([7.0e6, 30, 0, 0.0, 7.5e3, 10.0])),
    ]
    target_velocity = np.array([0.1, 7.49e3, 9.0])

    def residuals(epoch_state, time_offsets_s, target_positions_m, *args):
        assert time_offsets_s.tolist() == [10.0]
        return epoch_state[3:6] - target_velocity

    monkeypatch.setattr(
        fit_brouwer, "_compute_brouwer_residuals_from_epoch_state", residuals
    )
    monkeypatch.setattr(
        fit_brouwer.kepler,
        "cartesian_to_keplerian",
        lambda *_args: np.array([7.0e6, 0.1, 0.2, 0.3, 0.4, 0.5]),
    )
    monkeypatch.setattr(
        fit_brouwer.brouwer,
        "osculating_to_brouwer_mean",
        lambda elements, **_kwargs: elements,
    )

    elements, diagnostics = fit_brouwer.fit_brouwer(states, fit_span_s=15.0)

    assert elements[0] == 7.0e6
    assert diagnostics.n_records == 2
    assert diagnostics.span_s == 10.0
    assert diagnostics.rms_position_m == pytest.approx(0.0, abs=1e-9)
    assert diagnostics.epoch_vel_delta_m_s > 0.0


def test_compute_brouwer_propagation_comparison_includes_final_epoch(
    monkeypatch,
) -> None:
    propagated_epochs = []

    class FakePropagator:
        def __init__(self, **_kwargs):
            pass

        def propagate_to(self, epoch):
            propagated_epochs.append(epoch)
            return epoch, np.zeros(6)

    monkeypatch.setattr(fit_brouwer, "BrouwerJ2Propagator", FakePropagator)
    states = [
        (100.0, np.array([1, 2, 3, 4, 5, 6], dtype=float)),
        (200.0, np.array([2, 3, 4, 5, 6, 7], dtype=float)),
        (220.0, np.array([3, 4, 5, 6, 7, 8], dtype=float)),
    ]

    result = fit_brouwer.compute_brouwer_propagation_comparison(
        np.ones(6), states, mu_m3_s2=1.0, fit_span_s=120.0, interval_s=100.0
    )

    assert [item.elapsed_s for item in result] == [0.0, 100.0, 120.0]
    assert propagated_epochs == [100.0, 200.0, 220.0]
    assert result[-1].pos_err_km == pytest.approx(np.sqrt(3**2 + 4**2 + 5**2) / 1000)


def test_format_brouwer_output_accepts_dict_diagnostics_and_comparison(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        fit_brouwer.kepler, "semi_major_axis_to_mean_motion", lambda _a: 15.0
    )
    comparison = [
        PropagationComparison(
            elapsed_s=0.0,
            elapsed_min=0.0,
            pos_err_km=1.0,
            vel_err_m_s=2.0,
            dx_km=1.0,
            dy_km=0.0,
            dz_km=0.0,
            dvx_m_s=2.0,
            dvy_m_s=0.0,
            dvz_m_s=0.0,
        )
    ]

    output = fit_brouwer.format_brouwer_output(
        datetime(2025, 1, 1),
        np.array([7.0e6, 0.01, 0.2, 0.3, 0.4, 0.5]),
        {
            "n_records": 3,
            "span_s": 120.0,
            "iterations": 4,
            "rms_position_m": 250.0,
        },
        comparison,
    )

    assert "records used:       3" in output
    assert "Propagation comparison" in output
    assert "Position |Δr|:  min = 1.000000 km" in output
