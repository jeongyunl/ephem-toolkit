"""Tests for src/plot_dep_vars/plot_dependent_variables.py — Dependent variable plotting utility script."""

from __future__ import annotations

import io
import sys
from unittest.mock import Mock

import numpy as np
import pytest

import ephem_toolkit.core.cli as core_cli
import ephem_toolkit.plot_dep_vars.__main__ as plot_dep_vars_entry
import ephem_toolkit.plot_dep_vars.plot_dependent_variables as dep_vars
from ephem_toolkit.plot_dep_vars.plot_dependent_variables_cli import (
    build_arg_parser,
    parse_arguments,
)


def test_plot_dependent_variables_help_uses_command_name() -> None:
    """The CLI help should use the canonical command name."""
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
    assert "usage: plot-dependent-variables" in help_text


def test_plot_dependent_variables_cli_parses_name_and_duration() -> None:
    args = parse_arguments(
        build_arg_parser(),
        ["orbit_dep_vars.csv", "--name", "ISS", "--duration", "90m"],
    )

    assert args.dep_vars_csv == "orbit_dep_vars.csv"
    assert args.name == "ISS"
    assert args.duration == 5_400.0


def test_read_dependent_variables_csv_reads_numeric_data(tmp_path) -> None:
    csv_path = tmp_path / "dep_vars.csv"
    csv_path.write_text(
        "epoch_tt_s,speed//ISS/Earth//\n100,7.5\n160,7.4\n", encoding="utf-8"
    )

    times_s, headers, values = dep_vars.read_dependent_variables_csv(csv_path)

    np.testing.assert_array_equal(times_s, [100.0, 160.0])
    assert headers == ["speed//ISS/Earth//"]
    np.testing.assert_array_equal(values, [[7.5], [7.4]])


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("", "CSV is empty"),
        ("value,speed\n100,7.5\n", "first column must be 'epoch_tt_s'"),
        ("epoch_tt_s,speed\n100\n", "row width"),
        ("epoch_tt_s,speed\n100,fast\n", "numeric value"),
    ],
)
def test_read_dependent_variables_csv_rejects_invalid_input(
    tmp_path, content: str, message: str
) -> None:
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        dep_vars.read_dependent_variables_csv(csv_path)


def test_load_csv_dependent_variable_data_disambiguates_duplicate_headers(
    tmp_path,
) -> None:
    csv_path = tmp_path / "duplicate.csv"
    csv_path.write_text(
        "epoch_tt_s,latitude//ISS/Earth//,latitude//ISS/Earth//\n" "100,0.1,0.2\n",
        encoding="utf-8",
    )

    data = dep_vars.load_csv_dependent_variable_data(csv_path)

    assert list(data.dep_var_columns) == [
        "latitude//ISS/Earth//",
        "latitude//ISS/Earth//#dup1",
    ]
    assert [meta.occurrence_index for meta in data.metadata] == [0, 1]
    np.testing.assert_array_equal(
        data.dep_var_columns["latitude//ISS/Earth//#dup1"], [0.2]
    )


def test_extract_vector_orders_components_by_component_index(tmp_path) -> None:
    csv_path = tmp_path / "vector.csv"
    csv_path.write_text(
        "epoch_tt_s,relative_position//ISS/Earth//2,"
        "relative_position//ISS/Earth//0,relative_position//ISS/Earth//1\n"
        "100,30,10,20\n",
        encoding="utf-8",
    )
    data = dep_vars.load_csv_dependent_variable_data(csv_path)

    vector = dep_vars._extract_vector(
        data, "relative_position", associated_body="ISS", secondary_body="Earth"
    )

    np.testing.assert_array_equal(vector, [[10.0, 20.0, 30.0]])


def test_extract_latitude_longitude_supports_legacy_duplicate_type(tmp_path) -> None:
    csv_path = tmp_path / "ground_track.csv"
    csv_path.write_text(
        "epoch_tt_s,relative_body_aerodynamic_orientation_angle//ISS/Earth//,"
        "relative_body_aerodynamic_orientation_angle//ISS/Earth//#duplicate\n"
        "100,0.25,-0.5\n",
        encoding="utf-8",
    )
    data = dep_vars.load_csv_dependent_variable_data(csv_path)

    latitude_rad, longitude_rad = dep_vars._extract_latitude_longitude(data, "ISS")

    np.testing.assert_array_equal(latitude_rad, [0.25])
    np.testing.assert_array_equal(longitude_rad, [-0.5])


def test_plot_dependent_variables_filters_duration_and_detects_satellite(
    tmp_path, monkeypatch
) -> None:
    csv_path = tmp_path / "orbit_dep_vars.csv"
    csv_path.write_text(
        "epoch_tt_s,relative_position//ISS/Earth//0\n" "100,1\n" "3700,2\n" "7300,3\n",
        encoding="utf-8",
    )
    total_acceleration_plot = Mock()
    monkeypatch.setattr(dep_vars, "plot_total_acceleration", total_acceleration_plot)
    monkeypatch.setattr(dep_vars, "plot_ground_track", Mock())
    monkeypatch.setattr(dep_vars, "plot_kepler_elements", Mock())
    monkeypatch.setattr(dep_vars, "plot_acceleration_components", Mock())
    monkeypatch.setattr(
        dep_vars,
        "plot_satellite_body_fixed_position_history_3d",
        Mock(return_value=None),
    )
    monkeypatch.setattr(
        dep_vars, "plot_satellite_relative_position_history_3d", Mock(return_value=None)
    )

    animations = dep_vars.plot_dependent_variables_from_csv(
        csv_path, satellite_name="Satellite", show=False, duration_s=3_600.0
    )

    call_data, relative_time_h, satellite_name = total_acceleration_plot.call_args.args
    np.testing.assert_array_equal(call_data.time_history_tt_s, [100.0, 3_700.0])
    np.testing.assert_array_equal(relative_time_h, [0.0, 1.0])
    assert satellite_name == "ISS"
    assert animations == [None, None]


def test_main_dispatches_parsed_arguments_and_shows_plots(monkeypatch) -> None:
    plotter = Mock(return_value=[object()])
    show = Mock()
    monkeypatch.setattr(dep_vars, "plot_dependent_variables_from_csv", plotter)
    monkeypatch.setattr("matplotlib.pyplot.show", show)

    plot_dep_vars_entry.main(
        ["orbit_dep_vars.csv", "--name", "ISS", "--duration", "90m"]
    )

    plotter.assert_called_once_with(
        dep_var_csv_path="orbit_dep_vars.csv",
        satellite_name="ISS",
        show=False,
        duration_s=5_400.0,
    )
    show.assert_called_once_with()


def test_main_closes_figures_and_returns_on_keyboard_interrupt(monkeypatch) -> None:
    plotter = Mock(return_value=[])
    close = Mock()
    monkeypatch.setattr(dep_vars, "plot_dependent_variables_from_csv", plotter)
    monkeypatch.setattr("matplotlib.pyplot.show", Mock(side_effect=KeyboardInterrupt))
    monkeypatch.setattr("matplotlib.pyplot.close", close)

    assert plot_dep_vars_entry.main(["orbit_dep_vars.csv"]) is None

    close.assert_called_once_with("all")


def test_main_without_input_connects_figure_callbacks(monkeypatch) -> None:
    import matplotlib.pyplot as plt

    monkeypatch.setattr(
        plot_dep_vars_entry,
        "parse_arguments",
        lambda _parser, _argv: type(
            "Args", (), {"dep_vars_csv": None, "name": None, "duration": None}
        )(),
    )
    callbacks = []
    figure = type(
        "Figure",
        (),
        {
            "canvas": type(
                "Canvas",
                (),
                {
                    "mpl_connect": lambda _self, _event, callback: callbacks.append(
                        callback
                    )
                },
            )(),
        },
    )()
    monkeypatch.setattr(plt, "get_fignums", lambda: [1])
    monkeypatch.setattr(plt, "figure", lambda _number: figure)
    close = Mock()
    monkeypatch.setattr(plt, "close", close)
    monkeypatch.setattr(
        plt,
        "show",
        lambda: callbacks[0](type("Event", (), {"key": "control+c"})()),
    )

    plot_dep_vars_entry.main([])

    close.assert_called_once_with("all")


def test_plot_dependent_variables_cli_uses_shared_runner(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        core_cli,
        "run_cli",
        lambda main_func, argv: calls.append((main_func, argv)) or 11,
    )

    assert plot_dep_vars_entry.cli(["data.csv"]) == 11
    assert calls == [(plot_dep_vars_entry.main, ["data.csv"])]


def test_plot_helpers_render_scalar_vector_and_animation_data() -> None:
    headers = []
    columns = {}

    def add_column(header: str, values: np.ndarray) -> None:
        headers.append(header)
        columns[header] = values

    sample_count = 24
    for component in range(3):
        add_column(
            f"total_acceleration//ISS//{component}",
            np.full(sample_count, component + 1.0),
        )
        add_column(
            f"central_body_fixed_cartesian_position//ISS/Earth/{component}",
            np.linspace(7.0e6, 7.1e6, sample_count) + component,
        )
        add_column(
            f"relative_position//ISS/Earth/{component}",
            np.linspace(component, component + 10.0, sample_count),
        )
    for component in range(6):
        add_column(
            f"keplerian_state//ISS/Earth/{component}",
            np.linspace(component + 1.0, component + 2.0, sample_count),
        )
    add_column("latitude//ISS/Earth", np.linspace(-0.5, 0.5, sample_count))
    add_column("longitude//ISS/Earth", np.linspace(-1.0, 1.0, sample_count))
    add_column(
        "single_acceleration_norm/point_mass_gravity/ISS/Earth",
        np.full(sample_count, 1.0e-3),
    )
    metadata = [
        dep_vars.parse_dep_var_column_metadata(header, header, 0) for header in headers
    ]
    data = dep_vars.CsvDependentVariableData(
        time_history_tt_s=np.arange(sample_count, dtype=float),
        dep_var_columns=columns,
        metadata=metadata,
    )
    relative_time_h = np.arange(sample_count, dtype=float)

    try:
        dep_vars.plot_total_acceleration(data, relative_time_h, "ISS")
        dep_vars.plot_ground_track(data, relative_time_h, "ISS")
        dep_vars.plot_kepler_elements(data, relative_time_h, "ISS")
        dep_vars.plot_acceleration_components(data, relative_time_h, "ISS")
        animations = [
            dep_vars.plot_satellite_body_fixed_position_history_3d(data, "ISS"),
            dep_vars.plot_satellite_relative_position_history_3d(data, "ISS"),
        ]
        for animation in animations:
            assert animation is not None
            animation._init_func()
            animation._func(2)
            animation._draw_was_started = True
    finally:
        dep_vars.plt.close("all")
