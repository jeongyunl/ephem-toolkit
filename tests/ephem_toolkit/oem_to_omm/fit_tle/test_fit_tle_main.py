"""Tests for oem_to_omm/fit_tle.py — TLE mean element fitting with SGP4-compatible propagation."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from ephem_toolkit.oem_to_omm import fit_tle_main as fit_tle


def test_fit_tle_module_imports() -> None:
    """Should successfully import the fit_tle module."""
    assert fit_tle is not None


def test_fit_tle_function_exists() -> None:
    """Should have fit_tle function."""
    assert hasattr(fit_tle, "fit_tle")
    assert callable(fit_tle.fit_tle)


def test_compute_tle_propagation_comparison_exists() -> None:
    """Should have compute_tle_propagation_comparison function."""
    assert hasattr(fit_tle, "compute_tle_propagation_comparison")
    assert callable(fit_tle.compute_tle_propagation_comparison)


def test_format_tle_output_exists() -> None:
    """Should have format_tle_output function."""
    assert hasattr(fit_tle, "format_tle_output")
    assert callable(fit_tle.format_tle_output)


def test_cartesian_to_tle_mean_elements_exists() -> None:
    """Should have cartesian_to_tle_mean_elements function."""
    assert hasattr(fit_tle, "cartesian_to_tle_mean_elements")
    assert callable(fit_tle.cartesian_to_tle_mean_elements)


def test_cartesian_to_tle_exists() -> None:
    """Should have cartesian_to_tle function."""
    assert hasattr(fit_tle, "cartesian_to_tle")
    assert callable(fit_tle.cartesian_to_tle)


def test_verify_tle_epoch_position_exists() -> None:
    """Should have verify_tle_epoch_position function."""
    assert hasattr(fit_tle, "verify_tle_epoch_position")
    assert callable(fit_tle.verify_tle_epoch_position)


def test_compute_tle_propagation_comparison_matches_nearby_states(monkeypatch) -> None:
    propagated_epochs = []

    class FakePropagator:
        def __init__(self, _tle):
            pass

        def propagate_to(self, epoch):
            propagated_epochs.append(epoch)
            return epoch, np.zeros(6)

    monkeypatch.setattr(fit_tle, "Sgp4Propagator", FakePropagator)
    tle_object = SimpleNamespace(
        mean_motion_rev_per_day=15.0,
        eccentricity=0.01,
        inclination_deg=51.0,
        arg_perigee_deg=20.0,
        raan_deg=30.0,
        mean_anomaly_deg=40.0,
    )
    states = [
        (100.0, np.array([1, 2, 3, 4, 5, 6], dtype=float)),
        (160.0, np.array([2, 3, 4, 5, 6, 7], dtype=float)),
        (220.0, np.array([3, 4, 5, 6, 7, 8], dtype=float)),
    ]

    comparison = fit_tle.compute_tle_propagation_comparison(
        tle_object, states, mu_m3_s2=1.0, fit_span_s=120.0, interval_s=60.0
    )

    assert [record.elapsed_s for record in comparison] == [0.0, 60.0, 120.0]
    assert propagated_epochs == [100.0, 160.0, 220.0]
    assert comparison[0].pos_err_km == pytest.approx(np.sqrt(14) / 1000)


def test_cartesian_to_tle_mean_elements_stops_when_epoch_position_matches(
    monkeypatch,
) -> None:
    from datetime import datetime

    state = np.array([7.0e6, 0.0, 0.0, 0.0, 7.5e3, 100.0])
    monkeypatch.setattr(
        fit_tle.time_utils, "tt_s_to_datetime", lambda _epoch: datetime(2025, 1, 1)
    )
    monkeypatch.setattr(fit_tle.tle, "datetime_to_tle_epoch", lambda _epoch: (25, 1.0))
    monkeypatch.setattr(fit_tle, "_sgp4_position", lambda *_args: state[:3].copy())

    elements = fit_tle.cartesian_to_tle_mean_elements(state, epoch_timestamp=0.0)

    assert elements.shape == (6,)
    assert elements[0] > 6.0e6
    assert 0.0 <= elements[1] < 1.0
