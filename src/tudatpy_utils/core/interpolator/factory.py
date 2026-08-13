"""Factory for creating interpolator instances from specifications."""

from __future__ import annotations

from typing import TYPE_CHECKING

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

        Returns
        -------
        Interpolator
            Configured interpolator instance

        Raises
        ------
        ValueError
            If interpolation type is not supported or parameters are invalid
        """
        if spec.interp_type == InterpolationType.LAGRANGE:
            return lagrange.LagrangeInterpolator(
                dimension=dimension,
                degree=spec.degree,
            )
        elif spec.interp_type == InterpolationType.HERMITE:
            return hermite.HermiteInterpolator(
                dimension=dimension,
                degree=spec.degree,
                is_cartesian_state=is_cartesian_state,
            )
        else:
            raise ValueError(f"Unsupported interpolation type: {spec.interp_type}")
