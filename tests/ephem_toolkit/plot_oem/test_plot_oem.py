"""Tests for src/plot_oem/plot_oem.py — orbit plotting utility script."""

from __future__ import annotations

import io
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

import ephem_toolkit.plot_oem.__main__ as plot_oem_entry
import ephem_toolkit.plot_oem.plot_oem as plot_oem_module
from ephem_toolkit.plot_oem.plot_oem_cli import build_arg_parser, parse_arguments
from ephem_toolkit.plot_oem.plot_oem import (
    TimeUnit,
    build_output_filename,
    compute_orbit_series,
    filter_states_by_duration,
    save_or_show_figure,
    warn_if_altitude_frame_assumption_is_weak,
)


def test_plot_oem_help_uses_command_name_and_output_placeholder() -> None:
    """The CLI help should use the canonical command name and output placeholder."""
    old_stdout = sys.stdout
    captured_output = io.StringIO()
    sys.stdout = captured_output

    try:
        parse_arguments(build_arg_parser(), ["--help"])
    except SystemExit:
        pass
    finally:
        sys.stdout = old_stdout

    help_text = captured_output.getvalue()
    assert "usage: plot-oem" in help_text
    assert "--output <output_plot>" in help_text


def test_plot_oem_uses_input_oem_attribute_name() -> None:
    """The parser should expose the positional input path under input_oem."""
    original_argv = sys.argv[:]
    try:
        sys.argv = ["plot-oem", "orbit.oem", "-o", "orbit.png", "-d", "1h"]
        args = parse_arguments(build_arg_parser())
    finally:
        sys.argv = original_argv

    assert args.input_oem == "orbit.oem"
    assert args.output == "orbit.png"
    assert args.duration == "1h"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("m", TimeUnit.MINUTES),
        ("Minute", TimeUnit.MINUTES),
        ("hours", TimeUnit.HOURS),
        ("H", TimeUnit.HOURS),
    ],
)
def test_time_unit_from_string_accepts_supported_aliases(
    value: str, expected: TimeUnit
) -> None:
    assert TimeUnit.from_string(value) is expected


def test_time_unit_from_string_rejects_unknown_unit() -> None:
    with pytest.raises(ValueError, match="Invalid time unit: days"):
        TimeUnit.from_string("days")


def test_filter_states_by_duration_includes_stop_time_and_preserves_full_span() -> None:
    timestamps_s = [10.0, 20.0, 30.0]
    states_m = [np.full(6, value) for value in timestamps_s]

    filtered_timestamps_s, filtered_states_m = filter_states_by_duration(
        timestamps_s, states_m, 10.0
    )
    unchanged_timestamps_s, unchanged_states_m = filter_states_by_duration(
        timestamps_s, states_m, None
    )

    assert filtered_timestamps_s == [10.0, 20.0]
    assert all(
        actual is expected for actual, expected in zip(filtered_states_m, states_m)
    )
    assert unchanged_timestamps_s is timestamps_s
    assert unchanged_states_m is states_m


def test_filter_states_by_duration_raises_when_no_samples_remain() -> None:
    with pytest.raises(ValueError, match="No states remain"):
        filter_states_by_duration([10.0, 20.0], [np.zeros(6), np.ones(6)], -1.0)


def test_compute_orbit_series_derives_units_and_angular_rates(monkeypatch) -> None:
    states_m = [
        np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
        np.array([7_000_000.0, 0.0, 0.0, 7_500.0, 0.0, 0.0]),
    ]
    monkeypatch.setattr(
        "ephem_toolkit.plot_oem.plot_oem.wgs.ecef_to_lla",
        lambda positions_m: np.array([[0.0, 0.0, 1_000.0], [0.0, 0.0, 2_000.0]]),
    )
    monkeypatch.setattr(
        "ephem_toolkit.plot_oem.plot_oem.misc.transform_to_rtn",
        lambda current_state, previous_state: np.arange(1.0, 7.0) * 1_000.0,
    )

    series = compute_orbit_series([100.0, 160.0], states_m, TimeUnit.MINUTES)

    np.testing.assert_allclose(series.elapsed_time, [0.0, 1.0])
    np.testing.assert_allclose(series.position_km[:, 0], [7_000.0, 7_000.0])
    np.testing.assert_allclose(series.velocity_km_s[:, 1], [7.5, 0.0])
    np.testing.assert_allclose(series.velocity_magnitude_km_s, [7.5, 7.5])
    np.testing.assert_allclose(series.geocentric_distance_km, [7_000.0, 7_000.0])
    np.testing.assert_allclose(series.altitude_km, [1.0, 2.0])
    np.testing.assert_allclose(series.rtn_elapsed_time, [1.0])
    np.testing.assert_allclose(series.rtn_delta_km, [[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]])
    np.testing.assert_allclose(series.direction_change_angle_deg, [0.0, 90.0])
    np.testing.assert_allclose(series.direction_change_rate_deg_s, [0.0, 1.5])
    np.testing.assert_allclose(series.angular_velocity_rad_s, [0.0, np.pi / 120.0])
    np.testing.assert_allclose(series.euler_angle_rates_deg_s[1], [0.0, 1.5, 0.0])


def test_build_output_filename_adds_suffix_before_extension() -> None:
    assert build_output_filename("plots/orbit.png", "velocity") == (
        "plots/orbit_velocity.png"
    )
    assert build_output_filename(None, "velocity") is None


def test_save_or_show_figure_saves_and_closes_output_figure(monkeypatch) -> None:
    figure = Mock()
    close_figure = Mock()
    monkeypatch.setattr("ephem_toolkit.plot_oem.plot_oem.plt.close", close_figure)

    save_or_show_figure(figure, "orbit.png")

    figure.tight_layout.assert_called_once_with()
    figure.savefig.assert_called_once_with("orbit.png", dpi=150, bbox_inches="tight")
    close_figure.assert_called_once_with(figure)


def test_warn_if_altitude_frame_assumption_is_weak(capsys) -> None:
    earth_fixed_oem = Mock()
    earth_fixed_oem.meta.ref_frame = "ITRF93"
    earth_fixed_oem.meta.center_name = "EARTH"
    warn_if_altitude_frame_assumption_is_weak(earth_fixed_oem)
    assert capsys.readouterr().out == ""

    inertial_oem = Mock()
    inertial_oem.meta.ref_frame = "J2000"
    inertial_oem.meta.center_name = "EARTH"
    warn_if_altitude_frame_assumption_is_weak(inertial_oem)
    assert "Warning: altitude-from-WGS84" in capsys.readouterr().out


def test_main_filters_duration_and_routes_series_to_all_plotters(monkeypatch) -> None:
    oem_data = Mock()
    timestamps_s = [100.0, 1_900.0, 3_700.0]
    states_m = [np.full(6, value) for value in timestamps_s]
    series = SimpleNamespace(
        position_km=np.zeros((2, 3)),
        rtn_elapsed_time=np.array([0.5]),
        rtn_delta_km=np.zeros((1, 6)),
        elapsed_time=np.array([0.0, 0.5]),
        velocity_magnitude_km_s=np.ones(2),
        angular_velocity_deg_s=np.zeros(2),
        angular_velocity_rad_s=np.zeros(2),
        euler_angles_deg=np.zeros((2, 3)),
        euler_angle_rates_deg_s=np.zeros((2, 3)),
        geocentric_distance_km=np.ones(2),
        altitude_km=np.ones(2),
    )
    read_states = Mock(return_value=(oem_data, timestamps_s, states_m))
    compute_series = Mock(return_value=series)
    monkeypatch.setattr(plot_oem_module, "read_oem_states", read_states)
    monkeypatch.setattr(plot_oem_module, "compute_orbit_series", compute_series)
    monkeypatch.setattr(
        plot_oem_module, "warn_if_altitude_frame_assumption_is_weak", Mock()
    )
    plotters = {
        name: Mock()
        for name in (
            "plot_state_vectors",
            "plot_rtn_delta_time_series",
            "plot_scalar_time_series",
            "plot_angular_velocity_time_series",
            "plot_direction_change_time_series",
            "plot_geocentric_distance_with_delta",
        )
    }
    for name, plotter in plotters.items():
        monkeypatch.setattr(plot_oem_module, name, plotter)

    plot_oem_entry.main(
        [
            "orbit.oem",
            "--duration",
            "30m",
            "--time-unit",
            "minutes",
            "--output",
            "plots/orbit.png",
        ]
    )

    read_states.assert_called_once_with("orbit.oem")
    compute_series.assert_called_once_with(
        [100.0, 1_900.0], states_m[:2], TimeUnit.MINUTES
    )
    assert plotters["plot_state_vectors"].call_args.args[2] == (
        "plots/orbit_state_vectors.png"
    )
    assert plotters["plot_scalar_time_series"].call_count == 2


def test_main_reports_invalid_duration(monkeypatch, capsys) -> None:
    with pytest.raises(SystemExit) as error:
        plot_oem_entry.main(["orbit.oem", "--duration", "not-a-duration"])

    assert error.value.code == 1
    assert "failed to parse duration 'not-a-duration'" in capsys.readouterr().err


def test_plot_helpers_render_populated_and_empty_series(monkeypatch) -> None:
    save_figure = Mock()
    monkeypatch.setattr(plot_oem_module, "save_or_show_figure", save_figure)
    elapsed_time = np.array([0.0, 1.0, 2.0])

    try:
        plot_oem_module.plot_state_vectors(
            np.array([[7.0, 0.0, 0.0], [0.0, 7.0, 0.0], [-7.0, 0.0, 0.0]]),
            "ISS",
            None,
        )
        plot_oem_module.plot_rtn_delta_time_series(
            elapsed_time[:2], np.ones((2, 6)), "ISS", TimeUnit.MINUTES, None
        )
        plot_oem_module.plot_rtn_delta_time_series(
            np.array([]), np.empty((0, 6)), "ISS", TimeUnit.HOURS, None
        )
        plot_oem_module.plot_angular_velocity_time_series(
            elapsed_time,
            np.array([0.0, 0.1, 0.2]),
            np.array([0.0, 0.01, 0.02]),
            "ISS",
            TimeUnit.MINUTES,
            None,
        )
        plot_oem_module.plot_angular_velocity_time_series(
            np.array([0.0]),
            np.array([0.0]),
            np.array([0.0]),
            "ISS",
            TimeUnit.HOURS,
            None,
        )
        plot_oem_module.plot_direction_change_time_series(
            elapsed_time,
            np.ones((3, 3)),
            np.ones((3, 3)),
            "ISS",
            TimeUnit.MINUTES,
            None,
        )
        plot_oem_module.plot_direction_change_time_series(
            np.array([]),
            np.empty((0, 3)),
            np.empty((0, 3)),
            "ISS",
            TimeUnit.HOURS,
            None,
        )
        plot_oem_module.plot_scalar_time_series(
            elapsed_time,
            np.array([7.0, 7.1, 7.2]),
            "ISS",
            "Speed",
            "km/s",
            TimeUnit.HOURS,
            None,
        )
        plot_oem_module.plot_geocentric_distance_with_delta(
            elapsed_time,
            np.array([7000.0, 7001.0, 7003.0]),
            "ISS",
            TimeUnit.MINUTES,
            None,
        )
        plot_oem_module.plot_geocentric_distance_with_delta(
            np.array([0.0]), np.array([7000.0]), "ISS", TimeUnit.HOURS, None
        )
    finally:
        plot_oem_module.plt.close("all")

    assert save_figure.call_count == 10
