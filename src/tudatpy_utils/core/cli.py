"""Common CLI utilities."""

from __future__ import annotations

import argparse

VALID_INTERPOLATION_TYPES: list[str] = ["lagrange", "hermite"]
"""Valid interpolation type names for CLI arguments."""


def parse_interpolate_type(value: str, default_degree: int) -> tuple[str, int]:
    """Parse interpolation type argument.

    Parameters
    ----------
    value : str
        Interpolation type as "interpolator" or "interpolator,degree".
    default_degree : int, optional
        Default degree to use if not specified in value.

    Returns
    -------
    tuple[str, int]
        Interpolation type and degree.

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
            f"Invalid interpolation type '{interp_type}', must be 'lagrange' or 'hermite'"
        )

    return (interp_type, degree)
