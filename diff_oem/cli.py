"""Command-line interface for OEM comparison."""

from __future__ import annotations

import argparse
import sys

from .utils import parse_rotation_fit_span

ROTATION_FIT_DURATION_S: float = 3600.0
"""Duration of the state history used by the optional rotation fit."""

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
            "Compare two OEM-like Cartesian states and report differences in time, "
            "position, and velocity."
        )
    )
    parser.add_argument(
        "reference_oem",
        metavar="<reference_oem.oem>",
        help="Reference OEM file path or '-' to read from stdin.",
    )
    parser.add_argument(
        "comparison_oem",
        metavar="<comparison_oem.oem>",
        help="Comparison OEM file path or '-' to read from stdin.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed component-wise differences.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print time-range determination details to stderr.",
    )
    parser.add_argument(
        "--interpolate-ref",
        action="store_true",
        help="Interpolate the reference OEM at each comparison state timestamp.",
    )
    parser.add_argument(
        "--interpolate-data",
        action="store_true",
        default=True,
        help=(
            "Interpolate comparison data at each reference state timestamp "
            "(default)."
        ),
    )
    parser.add_argument(
        "--interpolate",
        action="store_true",
        help="Interpolate both reference and comparison OEM data.",
    )
    parser.add_argument(
        "--rtn",
        action="store_true",
        help="Include comparison state coordinates in the reference RTN frame.",
    )
    parser.add_argument(
        "--rot",
        action="store_true",
        help=(
            "Fit a fixed rotation from the initial comparison state span and "
            "apply it before reporting differences. May be repeated."
        ),
    )
    parser.add_argument(
        "--rot-xy",
        action="store_true",
        help=(
            "Fit a fixed rotation around the X and Y axes from the initial "
            "comparison state span. May be repeated."
        ),
    )
    parser.add_argument(
        "--rot-z",
        action="store_true",
        help=(
            "Fit a fixed rotation around the Z axis from the initial comparison "
            "state span. May be repeated."
        ),
    )
    parser.add_argument(
        "--time-shift",
        action="store_true",
        help=(
            "Fit a constant comparison epoch bias and shift comparison timestamps "
            "before reporting differences. May be repeated."
        ),
    )
    parser.add_argument(
        "--rot-fit-span",
        type=parse_rotation_fit_span,
        default=ROTATION_FIT_DURATION_S,
        metavar="<duration>",
        help=(
            "Duration of the initial state span used for --rot fitting "
            f"(default: {ROTATION_FIT_DURATION_S:g}s)."
        ),
    )
    parser.add_argument(
        "--start",
        metavar="<iso8601|duration>",
        default=None,
        help=(
            "Start epoch as an ISO 8601 timestamp or duration relative to the "
            "first reference epoch."
        ),
    )
    parser.add_argument(
        "--stop",
        metavar="<iso8601|duration>",
        default=None,
        help=(
            "Stop epoch as an ISO 8601 timestamp or duration relative to the "
            "first reference epoch."
        ),
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
    """Return transformation stage keys in order of CLI appearance."""
    stage_sequence: list[str] = []
    for token in argv:
        option = token.split("=", maxsplit=1)[0]
        stage_key = TRANSFORM_STAGE_OPTIONS.get(option)
        if stage_key is not None:
            stage_sequence.append(stage_key)
    return stage_sequence
