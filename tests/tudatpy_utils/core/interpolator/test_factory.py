"""Tests for interpolator factory."""

from __future__ import annotations

import pytest

import core.interpolator.chebyshev as chebyshev
import core.interpolator.factory as factory
import core.interpolator.hermite as hermite
import core.interpolator.lagrange as lagrange
from core.interpolator.interpolation_spec import InterpolationSpec, InterpolationType


def test_factory_creates_lagrange_interpolator() -> None:
    """Test factory creates Lagrange interpolator."""
    spec = InterpolationSpec(interp_type=InterpolationType.LAGRANGE, degree=7)
    interpolator = factory.InterpolatorFactory.create(spec, dimension=6)

    assert isinstance(interpolator, lagrange.LagrangeInterpolator)
    assert interpolator.dependent_dimension == 6
    assert interpolator.degree == 7


def test_factory_creates_hermite_interpolator() -> None:
    """Test factory creates Hermite interpolator."""
    spec = InterpolationSpec(interp_type=InterpolationType.HERMITE, degree=3)
    interpolator = factory.InterpolatorFactory.create(
        spec, dimension=6, is_cartesian_state=True
    )

    assert isinstance(interpolator, hermite.SlidingWindowHermiteInterpolator)
    assert interpolator.dependent_dimension == 6
    assert interpolator.is_cartesian_state is True


def test_factory_uses_default_degree_for_lagrange() -> None:
    """Test factory uses default degree when not specified."""
    spec = InterpolationSpec(interp_type=InterpolationType.LAGRANGE)
    interpolator = factory.InterpolatorFactory.create(spec)

    assert isinstance(interpolator, lagrange.LagrangeInterpolator)
    assert interpolator.degree == 7  # Default Lagrange degree


def test_factory_uses_default_degree_for_hermite() -> None:
    """Test factory uses default degree for Hermite when not specified."""
    spec = InterpolationSpec(interp_type=InterpolationType.HERMITE)
    interpolator = factory.InterpolatorFactory.create(
        spec, dimension=6, is_cartesian_state=True
    )

    assert isinstance(interpolator, hermite.SlidingWindowHermiteInterpolator)
    assert interpolator.required_points == 6  # degree + 1 = 5 + 1


def test_factory_creates_chebyshev_interpolator() -> None:
    """Test factory creates Chebyshev interpolator."""
    spec = InterpolationSpec(interp_type=InterpolationType.CHEBYSHEV, degree=4)
    interpolator = factory.InterpolatorFactory.create(spec, dimension=2)

    assert isinstance(interpolator, chebyshev.ChebyshevInterpolator)
    assert interpolator.dependent_dimension == 2
    assert interpolator.degree == 4


def test_factory_raises_error_for_unsupported_type() -> None:
    """Test factory raises error for unsupported interpolation type."""

    # Create a mock spec with invalid type
    class InvalidSpec:
        interp_type = "invalid"
        degree = 8

    with pytest.raises(ValueError, match="Unsupported interpolation type"):
        factory.InterpolatorFactory.create(InvalidSpec(), dimension=6)


def test_factory_creates_interpolator_with_custom_dimension() -> None:
    """Test factory creates interpolator with custom dimension."""
    spec = InterpolationSpec(interp_type=InterpolationType.LAGRANGE, degree=5)
    interpolator = factory.InterpolatorFactory.create(spec, dimension=3)

    assert interpolator.dependent_dimension == 3
    assert interpolator.degree == 5


def test_factory_hermite_with_non_cartesian_state() -> None:
    """Test factory creates Hermite interpolator with is_cartesian_state=False."""
    spec = InterpolationSpec(interp_type=InterpolationType.HERMITE, degree=1)
    interpolator = factory.InterpolatorFactory.create(
        spec, dimension=3, is_cartesian_state=False
    )

    assert isinstance(interpolator, hermite.SlidingWindowHermiteInterpolator)
    assert interpolator.is_cartesian_state is False
    assert interpolator.dependent_dimension == 3
