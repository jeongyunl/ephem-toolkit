import numpy as np
import pytest

from ephem_toolkit.core.interpolator.chebyshev import ChebyshevInterpolator


def make_interpolator(mode="centered", extension=0):
    interpolator = ChebyshevInterpolator(
        dimension=2,
        degree=2,
        boundary_mode=mode,
        boundary_window_extension=extension,
    )
    for value in np.linspace(0.0, 10.0, 11):
        interpolator.add_data_point(value, np.array([value**2, 2.0 * value + 1.0]))
    return interpolator


def test_chebyshev_interpolates_vector_polynomial_and_reuses_cache(monkeypatch) -> None:
    interpolator = make_interpolator()
    original_lstsq = np.linalg.lstsq
    calls = []

    def counted_lstsq(*args, **kwargs):
        calls.append(1)
        return original_lstsq(*args, **kwargs)

    monkeypatch.setattr(np.linalg, "lstsq", counted_lstsq)
    first = interpolator.interpolate(4.2)
    second = interpolator.interpolate(4.3)

    np.testing.assert_allclose(first, [4.2**2, 2.0 * 4.2 + 1.0], atol=1e-10)
    np.testing.assert_allclose(second, [4.3**2, 2.0 * 4.3 + 1.0], atol=1e-10)
    assert len(calls) == 1
    assert "ChebyshevInterpolator" in repr(interpolator)


def test_chebyshev_boundary_policies_select_expected_window_sizes() -> None:
    values = np.arange(11.0)
    centered = make_interpolator()
    widened = make_interpolator("widen", 2)
    edge = make_interpolator("edge", 2)
    compact = make_interpolator("compact", 1)

    assert centered._select_window(values, 0.0) == (0, 3, 2)
    assert centered._select_window(values, 10.0) == (8, 11, 2)
    assert widened._select_window(values, 0.0) == (0, 5, 2)
    assert widened._select_window(values, 10.0) == (6, 11, 2)
    assert widened._select_window(values, 5.0) == (3, 8, 2)
    assert edge._select_window(values, 0.0) == (0, 5, 2)
    assert edge._select_window(values, 10.0) == (6, 11, 2)
    assert compact._select_window(values, 0.0) == (0, 2, 1)
    assert compact._select_window(values, 10.0) == (9, 11, 1)


def test_chebyshev_domain_checks_extrapolation_and_short_data() -> None:
    interpolator = make_interpolator()
    assert interpolator.interpolate(-1.0) is None
    assert interpolator.interpolate(11.0) is None
    assert interpolator.interpolate(0.0 - 5e-13) is not None
    interpolator.allow_extrapolation = True
    assert interpolator.interpolate(-1.0) is not None

    empty = ChebyshevInterpolator()
    assert empty.interpolate(0.0) is None
    empty.add_data_point(0.0, np.array([1.0]))
    assert empty.interpolate(0.0) is None


def test_chebyshev_validates_configuration_and_resets_cache() -> None:
    with pytest.raises(ValueError, match="degree must be at least 1"):
        ChebyshevInterpolator(degree=0)
    with pytest.raises(ValueError, match="boundary_mode"):
        ChebyshevInterpolator(boundary_mode="unknown")
    with pytest.raises(ValueError, match="non-negative"):
        ChebyshevInterpolator(boundary_window_extension=-1)

    interpolator = make_interpolator()
    interpolator.interpolate(4.0)
    assert interpolator._cache_coefficients is not None
    interpolator.degree = 1
    assert interpolator.required_points == 2
    assert interpolator._cache_coefficients is None
    with pytest.raises(ValueError, match="degree must be at least 1"):
        interpolator.degree = 0
    interpolator.interpolate(4.0)
    interpolator.add_data_point(11.0, np.array([121.0, 23.0]))
    assert interpolator._cache_coefficients is None
    interpolator.reset_state()
    assert interpolator.degree == 2
    assert interpolator._cache_coefficients is None
    interpolator.clear_storage()
    assert interpolator.independent_values == []


def test_chebyshev_fit_handles_a_constant_independent_window() -> None:
    interpolator = make_interpolator()

    domain, design_matrix = interpolator._fit_window(np.array([2.0, 2.0]), 1)

    assert domain == (2.0, 3.0)
    np.testing.assert_array_equal(design_matrix, [[1.0, -1.0], [1.0, -1.0]])
