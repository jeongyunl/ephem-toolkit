"""Tests for oem_to_omm/fit_osculating_kepler.py — Osculating Keplerian element fitting with two-body propagation."""

from __future__ import annotations

import pytest

from oem_to_omm import fit_osculating_kepler


def test_fit_osculating_kepler_module_imports() -> None:
    """Should successfully import the fit_osculating_kepler module."""
    assert fit_osculating_kepler is not None


def test_fit_osculating_kepler_function_exists() -> None:
    """Should have fit_osculating_kepler function."""
    assert hasattr(fit_osculating_kepler, "fit_osculating_kepler")
    assert callable(fit_osculating_kepler.fit_osculating_kepler)


def test_compute_kepler_propagation_comparison_exists() -> None:
    """Should have compute_kepler_propagation_comparison function."""
    assert hasattr(fit_osculating_kepler, "compute_kepler_propagation_comparison")
    assert callable(fit_osculating_kepler.compute_kepler_propagation_comparison)


def test_format_kepler_output_exists() -> None:
    """Should have format_kepler_output function."""
    assert hasattr(fit_osculating_kepler, "format_kepler_output")
    assert callable(fit_osculating_kepler.format_kepler_output)
