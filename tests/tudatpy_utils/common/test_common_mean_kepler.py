"""Tests for common/mean_kepler.py — Mean to osculating Keplerian element conversion."""

from __future__ import annotations

import numpy as np
import pytest

import common.mean_kepler as mean_kepler


def test_osculating_to_mean_keplerian_returns_six_elements() -> None:
    """Should return a 6-element array of mean Keplerian elements."""
    osculating = np.array([7000e3, 0.01, 0.1, 0.3, 0.2, 1.0], dtype=float)
    mean = mean_kepler.osculating_to_mean_keplerian(osculating)

    assert isinstance(mean, np.ndarray)
    assert mean.shape == (6,)


def test_osculating_to_mean_keplerian_preserves_semi_major_axis() -> None:
    """Should have semi-major axis close to osculating (small J2 correction)."""
    osculating = np.array([7000e3, 0.01, 0.1, 0.3, 0.2, 1.0], dtype=float)
    mean = mean_kepler.osculating_to_mean_keplerian(osculating)

    # Mean semi-major axis should be close to osculating (within ~0.1%)
    assert mean[0] == pytest.approx(osculating[0], rel=1e-3)


def test_osculating_to_mean_keplerian_adjusts_eccentricity() -> None:
    """Should adjust eccentricity for J2 perturbations."""
    osculating = np.array([7000e3, 0.01, 0.1, 0.3, 0.2, 1.0], dtype=float)
    mean = mean_kepler.osculating_to_mean_keplerian(osculating)

    # Mean eccentricity should differ from osculating
    assert mean[1] != osculating[1]


def test_mean_to_osculating_keplerian_returns_six_elements() -> None:
    """Should return a 6-element array of osculating Keplerian elements."""
    mean = np.array([7000e3, 0.01, 0.1, 0.3, 0.2, 1.0], dtype=float)
    osculating = mean_kepler.mean_to_osculating_keplerian(mean)

    assert isinstance(osculating, np.ndarray)
    assert osculating.shape == (6,)


def test_mean_osculating_round_trip() -> None:
    """Should approximately round-trip osculating -> mean -> osculating."""
    osculating_original = np.array([7000e3, 0.01, 0.1, 0.3, 0.2, 1.0], dtype=float)
    mean = mean_kepler.osculating_to_mean_keplerian(osculating_original)
    osculating_recovered = mean_kepler.mean_to_osculating_keplerian(mean)

    # Should recover original within reasonable tolerance
    np.testing.assert_allclose(
        osculating_recovered, osculating_original, rtol=1e-6, atol=1e-9
    )
