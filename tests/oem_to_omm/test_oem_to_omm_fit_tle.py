"""Tests for oem_to_omm/fit_tle.py — TLE mean element fitting with SGP4-compatible propagation."""

from __future__ import annotations

import pytest

from oem_to_omm import fit_tle_main as fit_tle


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
