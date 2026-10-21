"""Command-line entry point for OEM playback."""

from __future__ import annotations

from collections.abc import Sequence
import math

from .play_oem_cli import build_arg_parser, parse_arguments, PlayOemArgs


def main(argv: Sequence[str] | None = None) -> None:
    """Load an OEM and prepare its derived playback series."""
    cli_args: PlayOemArgs = parse_arguments(build_arg_parser(), argv)

    import sys

    import ephem_toolkit.core.time_utils as time_utils

    from .playback_data import empty_playback_data, load_playback_data
    from .time_unit import TimeUnit

    try:
        from .app import PlayerApp
    except ModuleNotFoundError as exception:
        if exception.name != "wx" and not (exception.name or "").startswith("wx."):
            raise
        raise ImportError(
            'wxPython is required to run "play-oem". Install it with '
            '`pip install "ephem-toolkit[playback]"`.'
        ) from exception

    try:
        duration_s = (
            None
            if cli_args.duration is None
            else time_utils.parse_duration_to_seconds(cli_args.duration)
        )
    except ValueError as exception:
        print(
            f"Error: failed to parse duration '{cli_args.duration}': {exception}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exception

    selected_time_unit = TimeUnit.from_string(cli_args.time_unit)

    def load_file(input_oem: str):
        print(f"Reading OEM orbit from {input_oem}...")
        loaded = load_playback_data(
            input_oem,
            duration_s=duration_s,
            selected_time_unit=selected_time_unit,
            speed=cli_args.speed,
            reverse=cli_args.reverse,
            autoplay=cli_args.autoplay,
            loop=cli_args.loop,
            start=cli_args.start,
        )
        print(f"Loaded {loaded.source_sample_count} states")
        print(f"Using {loaded.selected_sample_count} states after duration filtering")
        print(
            f"Prepared orbit series with {len(loaded.series.elapsed_time)} samples "
            f"using {loaded.time_unit.value}."
        )
        return loaded

    try:
        initial_data = (
            load_file(cli_args.input_oem) if cli_args.input_oem is not None else None
        )
    except ValueError as exception:
        if cli_args.start is None:
            raise
        print(
            f"Error: failed to parse start time '{cli_args.start}': {exception}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exception
    if initial_data is None:
        initial_data = empty_playback_data(selected_time_unit, cli_args.speed)
    player = PlayerApp(
        initial_data.clock,
        initial_data.series,
        initial_data.time_unit,
        initial_data.cursor,
        initial_data.object_name,
        initial_data.frame_context,
        dashboard_context=initial_data.dashboard_context,
        metadata_details=initial_data.metadata_details,
        plots=cli_args.plots,
        three_d_backend=cli_args.three_d_backend,
        tick_interval_ms=math.ceil(1000 / cli_args.fps),
        on_open_file=load_file,
        oem_loaded=cli_args.input_oem is not None,
    )

    player.run()


def cli(argv: Sequence[str] | None = None) -> int:
    """Run the CLI entry point and report unexpected errors consistently."""
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
