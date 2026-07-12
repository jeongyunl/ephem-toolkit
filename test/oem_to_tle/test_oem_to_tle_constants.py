"""Tests for oem_to_tle/constants.py — Constants for OEM to TLE conversion."""

from __future__ import annotations

import pytest

from oem_to_tle import constants


def test_constants_module_imports() -> None:
    """Should successfully import the constants module."""
    assert constants is not None
