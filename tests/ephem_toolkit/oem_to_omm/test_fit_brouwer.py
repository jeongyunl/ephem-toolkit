"""Tests for oem_to_omm/fit_brouwer.py — Mean Keplerian element fitting with J2 secular propagation."""

from __future__ import annotations


import ephem_toolkit.oem_to_omm.fit_brouwer as fit_brouwer


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
