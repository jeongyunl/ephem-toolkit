"""Command-line entry point for OEM playback."""

from __future__ import annotations

from collections.abc import Sequence

from .play_oem_cli import build_arg_parser, parse_arguments, PlayOemArgs


def main(argv: Sequence[str] | None = None) -> None:
    """Load an OEM and prepare its derived playback series."""
    cli_args: PlayOemArgs = parse_arguments(build_arg_parser(), argv)

    import sys

    import ephem_toolkit.core.time_utils as time_utils

    from .data import filter_states_by_duration, read_oem_states
    from .series import OrbitSeries, compute_orbit_series
    from .time_unit import TimeUnit

    time_unit = TimeUnit.from_string(cli_args.time_unit)

    duration_s = None
    if cli_args.duration is not None:
        try:
            duration_s = time_utils.parse_duration_to_seconds(cli_args.duration)
        except ValueError as exception:
            print(
                f"Error: failed to parse duration '{cli_args.duration}': {exception}",
                file=sys.stderr,
            )
            raise SystemExit(1) from exception

    print(f"Reading OEM orbit from {cli_args.input_oem}...")
    _, timestamps_s, states_m = read_oem_states(cli_args.input_oem)
    print(f"Loaded {len(states_m)} states")
    timestamps_s, states_m = filter_states_by_duration(
        timestamps_s, states_m, duration_s
    )
    print(f"Using {len(states_m)} states after duration filtering")
    series: OrbitSeries = compute_orbit_series(timestamps_s, states_m, time_unit)
    print(
        f"Prepared orbit series with {len(series.elapsed_time)} samples "
        f"using {time_unit.value}."
    )


def cli(argv: Sequence[str] | None = None) -> int:
    """Run the CLI entry point and report unexpected errors consistently."""
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
