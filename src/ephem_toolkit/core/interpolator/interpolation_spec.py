"""Interpolation specification data types.

References:
    https://en.wikipedia.org/wiki/Interpolation
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

DEFAULT_HERMITE_DEGREE: int = 5
"""Default polynomial degree for Hermite interpolation."""

DEFAULT_LAGRANGE_DEGREE: int = 7
"""Default polynomial degree for Lagrange interpolation."""

DEFAULT_CHEBYSHEV_DEGREE: int = 5
"""Default degree for Chebyshev polynomial interpolation."""


class InterpolationType(Enum):
    """Supported interpolation methods."""

    HERMITE = "hermite"
    """Hermite sliding-window interpolation with caching."""

    LAGRANGE = "lagrange"
    """Lagrange polynomial interpolation."""

    CHEBYSHEV = "chebyshev"
    """Chebyshev polynomial interpolation."""


@dataclass
class InterpolationSpec:
    """Interpolation specification with a method type and optional degree."""

    interp_type: InterpolationType
    """Interpolation method type."""

    degree: int | None = None
    """Polynomial degree; defaults to the canonical degree for the chosen method."""

    def __post_init__(self) -> None:
        """Set a default polynomial degree when none is supplied."""
        if self.degree is None:
            if self.interp_type == InterpolationType.HERMITE:
                self.degree = DEFAULT_HERMITE_DEGREE
            elif self.interp_type == InterpolationType.LAGRANGE:
                self.degree = DEFAULT_LAGRANGE_DEGREE
            elif self.interp_type == InterpolationType.CHEBYSHEV:
                self.degree = DEFAULT_CHEBYSHEV_DEGREE
