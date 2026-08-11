"""Tests for oem_to_omm/fit_common.py — Common data structures for orbital element fitting."""

from __future__ import annotations

import pytest

from oem_to_omm import fit_common


def test_fit_common_module_imports() -> None:
    """Should successfully import the fit_common module."""
    assert fit_common is not None


def test_propagation_comparison_dataclass() -> None:
    """Should create PropagationComparison dataclass instance."""
    comparison = fit_common.PropagationComparison(
        elapsed_s=600.0,
        elapsed_min=10.0,
        pos_err_km=0.5,
        vel_err_m_s=0.1,
        dx_km=0.3,
        dy_km=0.2,
        dz_km=0.1,
        dvx_m_s=0.05,
        dvy_m_s=0.03,
        dvz_m_s=0.02,
    )
    assert comparison.elapsed_s == 600.0
    assert comparison.elapsed_min == 10.0
    assert comparison.pos_err_km == 0.5


def test_fit_diagnostics_dataclass() -> None:
    """Should create FitDiagnostics dataclass instance."""
    diagnostics = fit_common.FitDiagnostics(
        rms_position_m=100.0,
        iterations=10,
        n_records=50,
        span_s=7200.0,
        epoch_pos_delta_m=5.0,
        epoch_vel_delta_m_s=0.1,
        fit_method="mean_kepler_j2_velocity_fit",
    )
    assert diagnostics.rms_position_m == 100.0
    assert diagnostics.iterations == 10
    assert diagnostics.n_records == 50
    assert diagnostics.span_s == 7200.0
    assert diagnostics.fit_method == "mean_kepler_j2_velocity_fit"


def test_fit_diagnostics_optional_fields() -> None:
    """Should create FitDiagnostics with optional fields as None."""
    diagnostics = fit_common.FitDiagnostics(
        rms_position_m=100.0,
        iterations=10,
        n_records=50,
        span_s=7200.0,
    )
    assert diagnostics.epoch_pos_delta_m is None
    assert diagnostics.epoch_vel_delta_m_s is None
    assert diagnostics.fit_method is None
