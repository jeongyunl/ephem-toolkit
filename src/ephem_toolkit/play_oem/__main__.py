"""Command-line entry point for OEM playback."""

from __future__ import annotations

from collections.abc import Sequence
import math
from pathlib import Path

from .play_oem_cli import build_arg_parser, parse_arguments, PlayOemArgs


def main(argv: Sequence[str] | None = None) -> None:
    """Load an OEM and prepare its derived playback series."""
    cli_args: PlayOemArgs = parse_arguments(build_arg_parser(), argv)
    if cli_args.input_oem is not None and not Path(cli_args.input_oem).is_file():
        raise FileNotFoundError(f"File not found: {cli_args.input_oem}")

    from .config import load_config, save_ground_stations
    from .playback_data import empty_playback_data
    from .saved_state import load_saved_state

    user_config = load_config(cli_args.config)
    saved_state = load_saved_state()
    ground_stations = list(user_config.ground_stations)
    if not user_config.ground_stations_configured and saved_state.ground_stations:
        ground_stations = list(saved_state.ground_stations)
        save_ground_stations(ground_stations, cli_args.config)
        saved_state.ground_stations = []
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

    # Display the workspace first. The app starts a background load after showing
    # its frame and installs the first valid state batch when it arrives.
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
        display_time_zone=user_config.display_time_zone,
        use_oem_interpolation=user_config.use_oem_interpolation,
        interpolation_method=user_config.interpolation_method,
        interpolation_degree=user_config.interpolation_degree,
        oem_interpolation=initial_data.oem_interpolation,
        oem_interpolation_degree=initial_data.oem_interpolation_degree,
        on_open_file=None,
        saved_state=saved_state,
        ground_stations=ground_stations,
        ground_track_source=initial_data.ground_track_source,
        initial_file_path=cli_args.input_oem,
        oem_loaded=False,
        loaded_file_name=None,
        **player_options,
    )

    player.run()


def cli(argv: Sequence[str] | None = None) -> int:
    """Run the CLI entry point and report unexpected errors consistently."""
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
