"""Command-line interface for OEM comparison.

Usage:
    python3 -m tudatpy_utils.diff_oem <reference_oem.oem> <comparison_oem.oem> [options]
"""

from __future__ import annotations

import argparse
from functools import partial
import sys

import tudatpy_utils.core.cli as cli
from tudatpy_utils.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)
from .utils import parse_rotation_fit_span

ROTATION_FIT_DURATION_S: float = 3600.0
"""Duration of the state history used by the optional rotation fit."""

DEFAULT_INTERPOLATION_TYPE: str = "hermite"
"""Default interpolation method."""

DEFAULT_INTERPOLATION_DEGREE: int = 5
"""Default polynomial degree for interpolation (Hermite default)."""

DEFAULT_INTERPOLATION_SPEC: InterpolationSpec = InterpolationSpec(
    interp_type=InterpolationType.HERMITE,
    degree=DEFAULT_INTERPOLATION_DEGREE,
)
"""Default interpolation specification."""

TRANSFORM_STAGE_OPTIONS: dict[str, str] = {
    "--rot": "rot",
    "--rot-xy": "rot_xy",
    "--rot-z": "rot_z",
    "--time-shift": "time_shift",
}
"""Supported transformation-stage options mapped to internal stage keys."""


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments with attributes ``reference_oem``,
        ``comparison_oem``, ``verbose``, ``debug``, ``interpolate_ref``, and
        ``interpolate_data``. The ``--interpolate`` convenience option enables
        both interpolation flags, and is represented by the parsed interpolation
        attributes. ``stage_sequence`` records transformation stage order as
        requested in the CLI.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Compare two OEM files and report differences in time, "
            "position, and velocity."
        )
    )
    parser.add_argument(
        "reference_oem",
        metavar="<reference_oem.oem>",
        help="Reference OEM file path (use '-' to read from stdin)",
    )
    parser.add_argument(
        "comparison_oem",
        metavar="<comparison_oem.oem>",
        help="Comparison OEM file path (use '-' to read from stdin)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed component-wise differences",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print time-range determination details to stderr",
    )
    parser.add_argument(
        "--interpolate-ref",
        action="store_true",
        help="Interpolate reference OEM at each comparison state timestamp",
    )
    parser.add_argument(
        "--interpolate-data",
        action="store_true",
        default=True,
        help="Interpolate comparison data at each reference state timestamp (enabled by default)",
    )
    parser.add_argument(
        "--interpolate",
        action="store_true",
        help="Interpolate both reference and comparison OEM data",
    )
    parser.add_argument(
        "--interpolate-type",
        type=partial(
            cli.parse_interpolate_type, default_degree=DEFAULT_INTERPOLATION_DEGREE
        ),
        default=DEFAULT_INTERPOLATION_SPEC,
        metavar="TYPE[,DEGREE]",
        help=f"Interpolation method: 'hermite[,degree]' or 'lagrange[,degree]' (default: {DEFAULT_INTERPOLATION_TYPE},{DEFAULT_INTERPOLATION_DEGREE}). Degree must be > 0",
    )
    parser.add_argument(
        "--rtn",
        action="store_true",
        help="Include comparison state coordinates in reference RTN frame",
    )
    parser.add_argument(
        "--rot",
        action="store_true",
        help="Fit fixed rotation from initial comparison state span and apply before reporting differences (may be repeated)",
    )
    parser.add_argument(
        "--rot-xy",
        action="store_true",
        help="Fit fixed rotation around X and Y axes from initial comparison state span (may be repeated)",
    )
    parser.add_argument(
        "--rot-z",
        action="store_true",
        help="Fit fixed rotation around Z axis from initial comparison state span (may be repeated)",
    )
    parser.add_argument(
        "--time-shift",
        action="store_true",
        help="Fit constant comparison epoch bias and shift comparison timestamps before reporting differences (may be repeated)",
    )
    parser.add_argument(
        "--rot-fit-span",
        type=parse_rotation_fit_span,
        default=ROTATION_FIT_DURATION_S,
        metavar="<duration>",
        help=f"Duration of initial state span used for --rot fitting (default: {ROTATION_FIT_DURATION_S:g}s)",
    )
    parser.add_argument(
        "--start",
        metavar="<iso8601|duration>",
        default=None,
        help="Start epoch as ISO 8601 timestamp or duration relative to first reference epoch",
    )
    parser.add_argument(
        "--stop",
        metavar="<iso8601|duration>",
        default=None,
        help="Stop epoch as ISO 8601 timestamp or duration relative to first reference epoch",
    )
    args = parser.parse_args()
    args.stage_sequence = extract_stage_sequence(sys.argv[1:])
    if args.interpolate:
        args.interpolate_ref = True
        args.interpolate_data = True
    if args.reference_oem == "-" and args.comparison_oem == "-":
        parser.error("reference_oem and comparison_oem cannot both be '-'")
    return args


def extract_stage_sequence(argv: list[str]) -> list[str]:
    """Return transformation stage keys in order of CLI appearance.

    Parameters
    ----------
    argv : list[str]
        Command-line argument list to extract stage sequence from.

    Returns
    -------
    list[str]
        Transformation stage keys in order of appearance.
    """
    stage_sequence: list[str] = []
    for token in argv:
        option = token.split("=", maxsplit=1)[0]
        stage_key = TRANSFORM_STAGE_OPTIONS.get(option)
        if stage_key is not None:
            stage_sequence.append(stage_key)
    return stage_sequence
