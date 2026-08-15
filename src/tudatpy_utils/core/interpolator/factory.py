"""Factory for creating interpolator instances from specifications."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import numpy as np

from . import chebyshev
from . import cubic_spline
from . import hermite
from . import lagrange
from .interpolation_spec import InterpolationSpec, InterpolationType

if TYPE_CHECKING:
    from .interpolator import Interpolator


class InterpolatorFactory:
    """Factory for creating interpolator instances from specifications."""

    @staticmethod
    def create(
        spec: InterpolationSpec,
        dimension: int = 6,
        is_cartesian_state: bool = False,
        verbose: bool = False,
        context: str = "factory",
        data: (
            dict[float, np.ndarray]
            | list[tuple[float, np.ndarray]]
            | list[float]
            | np.ndarray
            | None
        ) = None,
        dependent_data: list[np.ndarray] | None = None,
        boundary_mode: str = "centered",
        boundary_window_extension: int = 0,
    ) -> Interpolator:
        """Create an interpolator from a specification.

        Parameters
        ----------
        spec : InterpolationSpec
            Interpolation specification with type and degree
        dimension : int, optional
            Number of components in each dependent data vector (default: 6)
        is_cartesian_state : bool, optional
            If True, data represents Cartesian state (default: False)
        verbose : bool, optional
            If True, print debug information to stderr (default: False)
        context : str, optional
            Context string for verbose log prefix (default: "factory")
        data : dict[float, np.ndarray] | list[tuple[float, np.ndarray]] | list[float] | np.ndarray
            Either:
            - A mapping of independent variable values to dependent data vectors.
            - A list of (independent_value, dependent_data) tuples.
            - A list or array of independent variable values (requires *dependent_data*).

            If a dictionary is provided, it is sorted by key before storage.
            If a list of tuples is provided, it is assumed to be already sorted.
            If a list/array of floats is provided, *dependent_data* must also be provided,
            and both are assumed to be already sorted and of equal length.
        dependent_data : list[np.ndarray] | None, optional
            List of dependent data vectors, required only when *data* is a list/array
            of independent values. Must be the same length as *data*.

        Returns
        -------
        Interpolator
            Configured interpolator instance

        Raises
        ------
        ValueError
            If interpolation type is not supported or parameters are invalid
        """
        if verbose:
            print(f"[{context}] Creating interpolator:", file=sys.stderr)
            print(f"[{context}]   Type: {spec.interp_type.value}", file=sys.stderr)
            print(f"[{context}]   Degree: {spec.degree}", file=sys.stderr)
            print(f"[{context}]   Dimension: {dimension}", file=sys.stderr)
            if spec.interp_type == InterpolationType.HERMITE:
                print(
                    f"[{context}]   Cartesian state: {is_cartesian_state}",
                    file=sys.stderr,
                )

        if spec.interp_type == InterpolationType.HERMITE:
            interpolator = hermite.SlidingWindowHermiteInterpolator(
                dimension=dimension,
                degree=spec.degree,
                is_cartesian_state=is_cartesian_state,
                boundary_mode=boundary_mode,
                boundary_window_extension=boundary_window_extension,
            )
        elif spec.interp_type == InterpolationType.CHEBYSHEV:
            interpolator = chebyshev.ChebyshevInterpolator(
                dimension=dimension,
                degree=spec.degree,
            )
        elif spec.interp_type == InterpolationType.LAGRANGE:
            interpolator = lagrange.LagrangeInterpolator(
                dimension=dimension,
                degree=spec.degree,
            )
        elif spec.interp_type == InterpolationType.CUBIC:
            interpolator = cubic_spline.CubicSplineInterpolator(
                dimension=dimension,
            )
        else:
            raise ValueError(f"Unsupported interpolation type: {spec.interp_type}")

        if verbose:
            print(
                f"[{context}]   Created: {type(interpolator).__name__}", file=sys.stderr
            )

        if data is not None:
            interpolator.set_data(data, dependent_data)

        return interpolator
