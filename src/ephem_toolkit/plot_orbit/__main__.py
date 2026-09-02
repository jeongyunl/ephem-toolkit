#!/usr/bin/env python3
"""Command-line entry point for plotting an OEM orbit."""

from __future__ import annotations

from .plot_orbit_cli import build_arg_parser, parse_arguments, PlotOrbitArgs


def main(argv=None) -> None:
    """Run the CLI workflow to load one OEM and generate requested plots."""
    cli_args: PlotOrbitArgs = parse_arguments(build_arg_parser(), argv)

    import signal
    import sys
    from pathlib import Path
    from types import FrameType
    from typing import Any

    import matplotlib.pyplot as plt

    import ephem_toolkit.core.time_utils as time_utils

    from .plot_orbit import (
        OrbitSeries,
        TimeUnit,
        build_output_filename,
        compute_orbit_series,
        filter_states_by_duration,
        plot_angular_velocity_time_series,
        plot_direction_change_time_series,
        plot_geocentric_distance_with_delta,
        plot_rtn_delta_time_series,
        plot_scalar_time_series,
        plot_state_vectors,
        read_oem_states,
        warn_if_altitude_frame_assumption_is_weak,
    )

    time_unit = TimeUnit.from_string(cli_args.time_unit)

    duration_s = None
    if cli_args.duration is not None:
        try:
            duration_s = time_utils.parse_duration_to_seconds(cli_args.duration)
        except Exception as exception:
            print(
                f"Error: failed to parse duration '{cli_args.duration}': {exception}",
                file=sys.stderr,
            )
            sys.exit(1)

    def handle_sigint(_signum: int, _frame: FrameType | None) -> None:
        plt.close("all")

    previous_sigint_handler: Any = signal.signal(signal.SIGINT, handle_sigint)

    def handle_key_press(event: Any) -> None:
        if event.key in {"ctrl+c", "control+c"}:
            plt.close("all")

    print(f"Reading OEM orbit from {cli_args.input_oem}...")
    oem_data, timestamps_s, states_m = read_oem_states(cli_args.input_oem)
    print(f"Loaded {len(states_m)} states")
    timestamps_s, states_m = filter_states_by_duration(
        timestamps_s, states_m, duration_s
    )
    print(f"Using {len(states_m)} states after duration filtering")
    warn_if_altitude_frame_assumption_is_weak(oem_data)
    orbit_label = Path(cli_args.input_oem).name
    series: OrbitSeries = compute_orbit_series(timestamps_s, states_m, time_unit)

    print("Plotting state-vector trajectory views...")
    plot_state_vectors(
        series.position_km,
        orbit_label,
        build_output_filename(cli_args.output, "state_vectors"),
    )
    print("Plotting RTN deltas versus previous state...")
    plot_rtn_delta_time_series(
        series.rtn_elapsed_time,
        series.rtn_delta_km,
        orbit_label,
        time_unit,
        build_output_filename(cli_args.output, "rtn_deltas"),
    )
    print("Plotting velocity magnitude...")
    plot_scalar_time_series(
        series.elapsed_time,
        series.velocity_magnitude_km_s,
        orbit_label,
        "Velocity Magnitude vs Time",
        "Velocity Magnitude (km/s)",
        time_unit,
        build_output_filename(cli_args.output, "velocity_magnitude"),
    )
    print("Plotting angular velocity / attitude rate...")
    plot_angular_velocity_time_series(
        series.elapsed_time,
        series.angular_velocity_deg_s,
        series.angular_velocity_rad_s,
        orbit_label,
        time_unit,
        build_output_filename(cli_args.output, "angular_velocity"),
    )
    print("Plotting direction change metrics...")
    plot_direction_change_time_series(
        series.elapsed_time,
        series.euler_angles_deg,
        series.euler_angle_rates_deg_s,
        orbit_label,
        time_unit,
        build_output_filename(cli_args.output, "direction_change"),
    )
    print("Plotting geocentric distance...")
    plot_geocentric_distance_with_delta(
        series.elapsed_time,
        series.geocentric_distance_km,
        orbit_label,
        time_unit,
        build_output_filename(cli_args.output, "geocentric_distance"),
    )
    print("Plotting WGS84 altitude...")
    plot_scalar_time_series(
        series.elapsed_time,
        series.altitude_km,
        orbit_label,
        "Altitude above WGS84 Ellipsoid vs Time",
        "Altitude (km)",
        time_unit,
        build_output_filename(cli_args.output, "altitude_wgs84"),
    )

    if cli_args.output is None:
        for figure_number in plt.get_fignums():
            figure = plt.figure(figure_number)
            figure.canvas.mpl_connect("key_press_event", handle_key_press)
        try:
            plt.show()
        except KeyboardInterrupt:
            plt.close("all")
            signal.signal(signal.SIGINT, previous_sigint_handler)
            return

    signal.signal(signal.SIGINT, previous_sigint_handler)
    print("Done!")


def cli(argv=None) -> int:
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
