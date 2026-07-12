"""Tests for common/interpolator/interpolator.py — Base interpolator interface."""

from __future__ import annotations

import numpy as np
import pytest

from common.interpolator import interpolator


def test_interpolator_base_class_exists() -> None:
    """Should define the base Interpolator class."""
    assert hasattr(interpolator, 'Interpolator')


def test_interpolator_has_interpolate_method() -> None:
    """Should define the interpolate abstract method."""
    # This is a placeholder test - actual implementation may vary
    # The base class should define the interface
    pass
