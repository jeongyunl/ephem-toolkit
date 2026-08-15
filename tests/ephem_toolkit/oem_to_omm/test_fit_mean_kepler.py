"""Tests for oem_to_omm/fit_mean_kepler.py — Mean Keplerian element fitting with J2 secular propagation."""

from __future__ import annotations

import pytest

from oem_to_omm import fit_mean_kepler


def test_fit_mean_kepler_module_imports() -> None:
    """Should successfully import the fit_mean_kepler module."""
    assert fit_mean_kepler is not None


def test_fit_mean_kepler_function_exists() -> None:
    """Should have fit_mean_kepler function."""
    assert hasattr(fit_mean_kepler, "fit_mean_kepler")
    assert callable(fit_mean_kepler.fit_mean_kepler)


def test_compute_mean_kepler_propagation_comparison_exists() -> None:
    """Should have compute_mean_kepler_propagation_comparison function."""
    assert hasattr(fit_mean_kepler, "compute_mean_kepler_propagation_comparison")
    assert callable(fit_mean_kepler.compute_mean_kepler_propagation_comparison)


def test_format_mean_kepler_output_exists() -> None:
    """Should have format_mean_kepler_output function."""
    assert hasattr(fit_mean_kepler, "format_mean_kepler_output")
    assert callable(fit_mean_kepler.format_mean_kepler_output)
