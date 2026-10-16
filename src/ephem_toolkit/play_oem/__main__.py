"""Command-line entry point for OEM playback."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
import math
from pathlib import Path

from .play_oem_cli import build_arg_parser, parse_arguments, PlayOemArgs


def main(argv: Sequence[str] | None = None) -> None:
    """Load an OEM and prepare its derived playback series."""
    cli_args: PlayOemArgs = parse_arguments(build_arg_parser(), argv)

    import sys

    import ephem_toolkit.core.time_utils as time_utils

    from .data import filter_states_by_duration, read_oem_states
    from .app import PlayerApp
    from .clock import PlaybackClock
    from .cursor import OemCursor
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
    oem_data, timestamps_s, states_m = read_oem_states(cli_args.input_oem)
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
    rate = -cli_args.speed if cli_args.reverse else cli_args.speed
    clock = PlaybackClock(
        timestamps_s[0],
        timestamps_s[-1],
        t_now=timestamps_s[-1] if rate < 0.0 else timestamps_s[0],
        rate=rate,
        playing=cli_args.autoplay,
        loop=cli_args.loop,
        sample_times=timestamps_s,
    )
    if cli_args.start is not None:
        try:
            parsed_start = time_utils.parse_time_or_duration(cli_args.start)
            if isinstance(parsed_start, timedelta):
                start_time_s = timestamps_s[0] + parsed_start.total_seconds()
            else:
                start_time_s = time_utils.datetime_to_tt_s(parsed_start)
            if not timestamps_s[0] <= start_time_s <= timestamps_s[-1]:
                raise ValueError("start time is outside the selected OEM timeline")
            clock.seek(start_time_s)
        except ValueError as exception:
            print(
                f"Error: failed to parse start time '{cli_args.start}': {exception}",
                file=sys.stderr,
            )
            raise SystemExit(1) from exception

    cursor = OemCursor(
        timestamps_s,
        states_m,
        interpolation=oem_data.meta.interpolation,
        interpolation_degree=oem_data.meta.interpolation_degree,
    )
    frame_context = (
        " / ".join(
            value
            for value in (
                oem_data.meta.ref_frame.strip(),
                oem_data.meta.center_name.strip(),
            )
            if value
        )
        or "Frame metadata unavailable"
    )
    object_name = oem_data.meta.object_name.strip() or Path(cli_args.input_oem).name
    PlayerApp(
        clock,
        series,
        time_unit,
        cursor,
        object_name,
        frame_context,
        tick_interval_ms=math.ceil(1000 / cli_args.fps),
    ).run()


def cli(argv: Sequence[str] | None = None) -> int:
    """Run the CLI entry point and report unexpected errors consistently."""
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
