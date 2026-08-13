"""Interpolation specification data types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InterpolationType(Enum):
    """Interpolation method type."""

    LAGRANGE = "lagrange"
    HERMITE = "hermite"


@dataclass
class InterpolationSpec:
    """Interpolation specification with type and optional degree."""

    interp_type: InterpolationType
    """Type of interpolation (Lagrange or Hermite)"""

    degree: int | None = None
    """Polynomial degree for Lagrange interpolation (required for Lagrange, ignored for Hermite, default is 8)"""

    def __post_init__(self) -> None:
        """Validate and set defaults for interpolation specification."""
        if self.interp_type == InterpolationType.LAGRANGE:
            if self.degree is None:
                self.degree = 8
