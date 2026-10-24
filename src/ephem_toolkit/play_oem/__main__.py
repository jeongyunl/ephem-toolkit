"""Command-line entry point for OEM playback."""

from __future__ import annotations

from collections.abc import Sequence
import math
from pathlib import Path

from .play_oem_cli import build_arg_parser, parse_arguments, PlayOemArgs


def main(argv: Sequence[str] | None = None) -> None:
    """Load an OEM and prepare its derived playback series."""
    cli_args: PlayOemArgs = parse_arguments(build_arg_parser(), argv)

    from .config import load_config
    from .playback_data import empty_playback_data, load_playback_data
    from .saved_state import load_saved_state

    user_config = load_config(cli_args.config)
    saved_state = load_saved_state()
    initial_render_rate_fps = user_config.render_rate_fps
    if "plots" in cli_args.provided_options:
        selected_plots = cli_args.plots
    elif user_config.plots_configured:
        selected_plots = user_config.plots
    elif saved_state.open_plots:
        selected_plots = saved_state.open_plots
    else:
        selected_plots = user_config.plots
    selected_backend = (
        cli_args.three_d_backend
        if "three_d_backend" in cli_args.provided_options
        else user_config.three_d_backend
    )
    try:
        from .app import PlayerApp
    except ModuleNotFoundError as exception:
        if exception.name != "wx" and not (exception.name or "").startswith("wx."):
            raise
        raise ImportError(
            'wxPython is required to run "play-oem". Install it with '
            '`pip install "ephem-toolkit[playback]"`.'
        ) from exception

    def load_file(input_oem: str):
        print(f"Reading OEM orbit from {input_oem}...")
        # Initial and subsequent file loads both prepare the entire OEM timeline.
        loaded = load_playback_data(input_oem)
        print(f"Loaded {loaded.source_sample_count} states")
        print(
            f"Prepared orbit series with {len(loaded.series.elapsed_time)} samples "
            f"using {loaded.time_unit.value}."
        )
        return loaded

    initial_data = (
        load_file(cli_args.input_oem) if cli_args.input_oem is not None else None
    )
    if initial_data is None:
        initial_data = empty_playback_data()
    initial_data.clock.set_speed(user_config.speed)
    initial_data.clock.set_direction(-1 if user_config.reverse else 1)
    if user_config.reverse and cli_args.input_oem is not None:
        initial_data.clock.seek(initial_data.clock.t_end)

    player_options: dict[str, str] = {}
    if cli_args.config is not None:
        player_options["config_path"] = cli_args.config

    player = PlayerApp(
        initial_data.clock,
        initial_data.series,
        initial_data.time_unit,
        initial_data.cursor,
        initial_data.object_name,
        initial_data.frame_context,
        dashboard_context=initial_data.dashboard_context,
        metadata_details=initial_data.metadata_details,
        plots=selected_plots,
        three_d_backend=selected_backend,
        tick_interval_ms=math.ceil(1000 / initial_render_rate_fps),
        render_rate_fps=initial_render_rate_fps,
        on_open_file=load_file,
        saved_state=saved_state,
        ground_track_source=initial_data.ground_track_source,
        initial_file_path=cli_args.input_oem,
        oem_loaded=cli_args.input_oem is not None,
        loaded_file_name=(
            Path(cli_args.input_oem).name if cli_args.input_oem is not None else None
        ),
        **player_options,
    )

    player.run()


def cli(argv: Sequence[str] | None = None) -> int:
    """Run the CLI entry point and report unexpected errors consistently."""
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
