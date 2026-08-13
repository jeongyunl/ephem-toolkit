"""Interpolation specification data types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

DEFAULT_LAGRANGE_DEGREE: int = 7
"""Default polynomial degree for Lagrange interpolation."""

DEFAULT_HERMITE_DEGREE: int = 5
"""Default polynomial degree for Hermite interpolation."""


class InterpolationType(Enum):
    """Interpolation method type."""

    LAGRANGE = "lagrange"
    """Lagrange polynomial interpolation."""

    HERMITE = "hermite"
    """Hermite polynomial interpolation."""


@dataclass
class InterpolationSpec:
    """Interpolation specification with type and optional degree."""

    interp_type: InterpolationType
    """Type of interpolation (Lagrange or Hermite)."""

    degree: int | None = None
    """Polynomial degree (defaults: Lagrange=8, Hermite=3)."""

    def __post_init__(self) -> None:
        """Set default polynomial degree based on interpolation type."""
        if self.degree is None:
            if self.interp_type == InterpolationType.LAGRANGE:
                self.degree = DEFAULT_LAGRANGE_DEGREE
            elif self.interp_type == InterpolationType.HERMITE:
                self.degree = DEFAULT_HERMITE_DEGREE
