"""Tests for common/consts.py — Physical and mathematical constants."""

from __future__ import annotations

import pytest

import common.consts as consts


def test_earth_gravitational_parameter_defined() -> None:
    """Should define Earth's gravitational parameter in m³/s²."""
    assert consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2 > 0
    # WGS84 value is approximately 3.986004418e14
    assert 3.9e14 < consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2 < 4.0e14


def test_earth_radius_defined() -> None:
    """Should define Earth's mean radius in meters."""
    assert consts.EARTH_MEAN_RADIUS_M > 0
    # Earth's mean radius is approximately 6.371e6 m
    assert 6.3e6 < consts.EARTH_MEAN_RADIUS_M < 6.4e6


def test_earth_j2_defined() -> None:
    """Should define Earth's J2 coefficient."""
    assert consts.EARTH_J2 > 0
    # J2 is approximately 1.08263e-3
    assert 1.0e-3 < consts.EARTH_J2 < 1.1e-3
