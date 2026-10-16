"""Command-line entry point for OEM playback."""

from __future__ import annotations

from collections.abc import Sequence

from .play_oem_cli import build_arg_parser


def main(argv: Sequence[str] | None = None) -> None:
    """Parse the play-oem command line."""
    parser = build_arg_parser()
    parser.parse_args(argv)
    parser.error(
        "play-oem is not implemented yet; OEM loading and playback are not available."
    )


def cli(argv: Sequence[str] | None = None) -> int:
    """Run the CLI entry point and report unexpected errors consistently."""
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
