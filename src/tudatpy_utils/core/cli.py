"""Common CLI utilities."""

from __future__ import annotations

import argparse

from tudatpy_utils.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)

VALID_INTERPOLATION_TYPES: list[str] = ["hermite", "hermite_sliding", "chebyshev", "lagrange"]
"""Valid interpolation type names for CLI arguments."""

VALID_INTERPOLATION_TYPES_MESSAGE: str = ", ".join(
    f"'{value}'" for value in VALID_INTERPOLATION_TYPES
)
"""Human-readable list of supported interpolation types for CLI errors."""


def parse_interpolate_type(value: str, default_degree: int) -> InterpolationSpec:
    """Parse interpolation type argument.

    Parameters
    ----------
    value : str
        Interpolation type as "interpolator" or "interpolator,degree".
    default_degree : int, optional
        Default degree to use if not specified in value.

    Returns
    -------
    InterpolationSpec
        Interpolation specification with type and degree.

    Raises
    ------
    argparse.ArgumentTypeError
        If the format is invalid.
    """
    parts = value.split(",")
    if len(parts) == 1:
        interp_type = parts[0]
        degree = default_degree
    elif len(parts) == 2:
        interp_type = parts[0]
        try:
            degree = int(parts[1])
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"Invalid degree '{parts[1]}', must be an integer"
            )
        if degree <= 0:
            raise argparse.ArgumentTypeError(
                f"Invalid degree '{degree}', must be greater than 0"
            )
    else:
        raise argparse.ArgumentTypeError(
            f"Invalid format '{value}', expected 'type' or 'type,degree'"
        )

    if interp_type not in VALID_INTERPOLATION_TYPES:
        raise argparse.ArgumentTypeError(
            "Invalid interpolation type "
            f"'{interp_type}', must be one of {VALID_INTERPOLATION_TYPES_MESSAGE}"
        )

    return InterpolationSpec(
        interp_type=InterpolationType(interp_type),
        degree=degree,
    )
