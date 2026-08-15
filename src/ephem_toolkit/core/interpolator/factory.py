"""Factory for constructing interpolators from interpolation specifications."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import numpy as np

from . import chebyshev
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
        """Create an interpolator instance from a specification.

        Parameters
        ----------
        spec : InterpolationSpec
            Interpolation specification with a type and optional polynomial degree.
        dimension : int, optional
            Number of components in each dependent data vector. Default is 6.
        is_cartesian_state : bool, optional
            If True, the data represents a Cartesian state vector. Default is False.
        verbose : bool, optional
            If True, print debug information to stderr. Default is False.
        context : str, optional
            Context string used in verbose log prefixes. Default is "factory".
        data : dict[float, np.ndarray] | list[tuple[float, np.ndarray]] | list[float] | np.ndarray | None, optional
            Sample data used to populate the interpolator immediately after creation.
        dependent_data : list[np.ndarray] | None, optional
            Dependent vectors paired with `data` when `data` is a list or array of
            independent values.

        Returns
        -------
        Interpolator
            Configured interpolator instance.

        Raises
        ------
        ValueError
            If the interpolation type is unsupported or the supplied parameters are
            invalid.
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
                boundary_mode=boundary_mode,
                boundary_window_extension=boundary_window_extension,
            )
        elif spec.interp_type == InterpolationType.LAGRANGE:
            interpolator = lagrange.LagrangeInterpolator(
                dimension=dimension,
                degree=spec.degree,
                boundary_mode=boundary_mode,
                boundary_window_extension=boundary_window_extension,
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
