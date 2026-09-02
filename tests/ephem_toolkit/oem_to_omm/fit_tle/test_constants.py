"""Tests for oem_to_omm/constants.py — Constants for OEM to TLE conversion."""

from __future__ import annotations


import ephem_toolkit.oem_to_omm.fit_tle.constants as constants


def test_constants_module_imports() -> None:
    """Should successfully import the constants module."""
    assert constants is not None
