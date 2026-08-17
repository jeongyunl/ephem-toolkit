"""Common CLI utilities."""

from __future__ import annotations

import argparse

from ephem_toolkit.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)

VALID_INTERPOLATION_TYPES: list[str] = [
    "hermite",
    "hermite_sliding",
    "chebyshev",
    "lagrange",
]
"""Valid interpolation type names for CLI arguments."""

VALID_INTERPOLATION_TYPES_MESSAGE: str = ", ".join(
    f"'{value}'" for value in VALID_INTERPOLATION_TYPES
)
"""Human-readable list of supported interpolation types for CLI errors."""


class CliHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawDescriptionHelpFormatter,
):
    """Preserve paragraph breaks while showing argument defaults."""


def create_parser(
    description: str,
    *,
    epilog: str | None = None,
    formatter_class: type[argparse.HelpFormatter] | None = None,
) -> argparse.ArgumentParser:
    """Create a project-standard CLI parser.

    Parameters
    ----------
    description : str
        One-sentence description shown near the top of the help output.
    epilog : str | None, optional
        Additional help text appended after the options block.
    formatter_class : type[argparse.HelpFormatter] | None, optional
        Custom formatter for custom help output. Defaults to argparse's default
        formatter with visible defaults in help strings.
    """
    if formatter_class is None:
        formatter_class = CliHelpFormatter

    return argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=formatter_class,
    )


def add_common_arguments(
    parser: argparse.ArgumentParser,
    *,
    positional_name: str = "input_file",
    positional_help: str = "Input file path; '-' reads from stdin.",
    positional_nargs: str | None = None,
    output_name: str = "output",
) -> argparse.ArgumentParser:
    """Add shared CLI arguments to an argparse parser.

    The standard project convention is to keep input paths positional when the
    format is known or otherwise use ``input_file``. Output arguments prefer a
    format-aware destination name such as ``output_omm`` or ``output_tle`` when
    the target format is known. All option descriptions use sentence-style
    capitalization and the value placeholders use descriptive names like
    ``<path|->`` and ``<timestamp|duration>``. The ``-`` sentinel is accepted for
    both stdin and stdout input/output flows.
    """
    parser.add_argument(
        positional_name,
        metavar=f"<{positional_name}|->",
        nargs=positional_nargs,
        help=positional_help,
    )
    parser.add_argument(
        "-o",
        "--output",
        dest=output_name,
        metavar="<path|->",
        help="Output file path; '-' writes to stdout.",
    )
    parser.add_argument(
        "--duration",
        metavar="<duration>",
        help="Duration of the requested interval; equivalent to --stop = --start + duration.",
    )
    parser.add_argument(
        "--start",
        metavar="<timestamp|duration>",
        help="Start time in ISO-8601 format (for example, 2001-11-06T11:17:33 or 2001-11-06T11:17:33.1234) or as a relative duration.",
    )
    parser.add_argument(
        "--stop",
        metavar="<timestamp|duration>",
        help="Stop time in ISO-8601 format (for example, 2001-11-06T11:17:33 or 2001-11-06T11:17:33.1234) or as a duration offset from --start.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print extra diagnostic output.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print low-level debug details.",
    )
    return parser


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
