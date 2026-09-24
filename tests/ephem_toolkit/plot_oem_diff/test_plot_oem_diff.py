"""Tests for src/plot_oem_diff/plot_oem_diff.py — Orbit plotting utility script."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import numpy as np
import matplotlib.pyplot as plt
import pytest

import ephem_toolkit.core.cli as core_cli
import ephem_toolkit.plot_oem_diff.__main__ as plot_oem_diff_entry
import ephem_toolkit.plot_oem_diff.file_io as file_io
import ephem_toolkit.plot_oem_diff.plotting as plotting
from ephem_toolkit.plot_oem_diff import file_io as orbit_file_io
from ephem_toolkit.plot_oem_diff.data_structures import StateHistory, TimeUnit
from ephem_toolkit.plot_oem_diff import data_structures
from ephem_toolkit.plot_oem_diff.plot_oem_diff_cli import (
    build_arg_parser,
    parse_arguments,
)
from ephem_toolkit.plot_oem_diff.plotting import plot_orbits


def test_plot_oem_diff_help_uses_command_name_and_output_placeholder() -> None:
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
    assert "usage: plot-oem-diff" in help_text
    assert "--output <output_plot>" in help_text


def test_plot_oem_diff_parse_arguments_sets_input_oem_files() -> None:
    """The positional OEM arguments should populate the expected attribute name."""
    sample_files = ["tmp/leo3_aug_aa.oem", "tmp/leo3_aug_ab.oem"]

    with patch.object(sys, "argv", ["plot-oem-diff", *sample_files]):
        args = parse_arguments(build_arg_parser())

    assert args.input_oem_files == sample_files


def test_plot_orbits_skips_empty_comparison_histories() -> None:
    """Comparison orbits with no valid timestamps should not crash the absolute orbit plot."""
    reference_state_history = StateHistory(
        label="reference",
        state_history={
            0.0: np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            1.0: np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        },
    )
    empty_comparison = StateHistory(label="empty", state_history={})

    plot_orbits(reference_state_history, [empty_comparison], output_file=None)


def test_orbit_plots_write_figures_and_dataset_csvs(
    tmp_path: Path, monkeypatch
) -> None:
    reference_state = np.array([7.0e6, 0.0, 0.0, 0.0, 7_500.0, 0.0])
    comparison_state = np.array([7.0e6, 1_000.0, 500.0, 1.0, 7_501.0, 2.0])
    reference_history = StateHistory(
        label="reference",
        state_history={epoch: reference_state.copy() for epoch in (0.0, 60.0, 120.0)},
    )
    comparison_history = StateHistory(
        label="comparison",
        state_history={epoch: comparison_state.copy() for epoch in (0.0, 60.0, 120.0)},
    )
    monkeypatch.setattr(
        reference_history,
        "get_interpolated_state",
        lambda _epoch: reference_state,
    )
    monkeypatch.setattr(
        plotting.misc,
        "transform_to_rtn",
        lambda *_args: np.array([100.0, 200.0, 300.0, 1.0, 2.0, 3.0]),
    )

    absolute_plot = tmp_path / "absolute.png"
    rtn_orbit_plot = tmp_path / "rtn-orbit.png"
    try:
        plotting.plot_orbits(
            reference_history, [comparison_history], str(absolute_plot)
        )
        plotting.plot_relative_rtn_orbits(
            reference_history, [comparison_history], str(rtn_orbit_plot)
        )

        assert plt.gcf().axes[0].lines[-1].get_label() == "comparison"
    finally:
        plt.close("all")

    assert absolute_plot.stat().st_size > 0
    assert rtn_orbit_plot.stat().st_size > 0
    absolute_csv = tmp_path / "absolute_absolute_orbits_comparison.csv"
    rtn_csv = tmp_path / "rtn-orbit_relative_rtn_orbits_comparison.csv"
    assert "x_km" in absolute_csv.read_text(encoding="utf-8")
    assert "epoch_s" in rtn_csv.read_text(encoding="utf-8")


def test_state_history_lazily_interpolates_only_within_safe_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_interpolators = []

    class FakeInterpolator:
        independent_values = list(range(7))

        def interpolate(self, timestamp_s):
            return np.full(6, timestamp_s)

    fake_interpolator = FakeInterpolator()

    def create_interpolator(**kwargs):
        created_interpolators.append(kwargs)
        return fake_interpolator

    monkeypatch.setattr(
        data_structures.factory.InterpolatorFactory,
        "create",
        create_interpolator,
    )
    history = StateHistory(
        label="orbit",
        state_history={float(epoch): np.zeros(6) for epoch in range(7)},
    )

    assert history.get_interpolated_state(1.9) is None
    np.testing.assert_array_equal(history.get_interpolated_state(2.0), np.full(6, 2.0))
    np.testing.assert_array_equal(history.get_interpolated_state(4.0), np.full(6, 4.0))
    assert history.get_interpolated_state(4.1) is None
    assert history.interpolator is fake_interpolator
    assert len(created_interpolators) == 1
    assert created_interpolators[0]["data"] is history.state_history


def test_state_history_reports_first_and_last_epochs() -> None:
    history = StateHistory(
        label="orbit",
        state_history={5.0: np.zeros(6), 10.0: np.ones(6)},
    )

    assert history.get_start_time() == 5.0
    assert history.get_stop_time() == 10.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("m", TimeUnit.MINUTES),
        ("minutes", TimeUnit.MINUTES),
        ("h", TimeUnit.HOURS),
        ("hours", TimeUnit.HOURS),
    ],
)
def test_time_unit_parses_aliases(value: str, expected: TimeUnit) -> None:
    assert TimeUnit.from_string(value) is expected


def test_time_unit_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="Invalid time unit"):
        TimeUnit.from_string("days")


def test_time_unit_hours_conversion_and_label() -> None:
    assert TimeUnit.HOURS.get_divisor() == 3600.0
    assert TimeUnit.HOURS.get_label() == "Time from Start (hours)"


def test_generate_output_filename_adds_suffix_before_extension() -> None:
    assert plot_oem_diff_entry.generate_output_filename("plots/orbits.png", "rtn") == (
        "plots/orbits_rtn.png"
    )
    assert plot_oem_diff_entry.generate_output_filename(None, "rtn") is None


def test_main_filters_histories_and_routes_plot_outputs(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    histories = {
        "reference.oem": {float(epoch): np.full(6, epoch) for epoch in range(10)},
        "comparison.oem": {
            -1.0: np.full(6, -1.0),
            1.0: np.full(6, 1.0),
            2.0: np.full(6, 2.0),
            3.0: np.full(6, 3.0),
        },
        "empty.oem": {},
    }
    monkeypatch.setattr(file_io, "read_orbit_file", histories.__getitem__)
    plot_functions = [
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
    ]
    for name, plot_function in zip(
        (
            "plot_relative_rtn_timeseries",
            "plot_relative_rtn_orbits",
            "plot_relative_cartesian_timeseries",
            "plot_angular_separation",
            "plot_orbits",
        ),
        plot_functions,
    ):
        monkeypatch.setattr(plotting, name, plot_function)
    output_path = tmp_path / "orbits.png"

    plot_oem_diff_entry.main(
        [
            "reference.oem",
            "comparison.oem",
            "empty.oem",
            "--duration",
            "2s",
            "--output",
            str(output_path),
        ]
    )

    reference_history, comparisons, absolute_output = plot_functions[-1].call_args.args
    assert reference_history.label == "reference.oem"
    assert sorted(reference_history.state_history) == [0.0, 1.0, 2.0, 3.0, 4.0]
    assert len(comparisons) == 1
    assert comparisons[0].label == "comparison.oem"
    assert sorted(comparisons[0].state_history) == [-1.0, 1.0, 2.0]
    assert absolute_output == str(output_path)
    assert "Skipping comparison orbit with no data" in capsys.readouterr().out


def test_main_reports_invalid_duration(monkeypatch, capsys) -> None:
    import signal
    import ephem_toolkit.core.time_utils as time_utils

    monkeypatch.setattr(signal, "signal", lambda *_args: None)
    monkeypatch.setattr(
        time_utils,
        "parse_duration_to_seconds",
        lambda _value: (_ for _ in ()).throw(ValueError("invalid duration")),
    )

    with pytest.raises(SystemExit) as error:
        plot_oem_diff_entry.main(["reference.oem", "--duration", "bad"])

    assert error.value.code == 1
    assert "Error parsing duration: invalid duration" in capsys.readouterr().out


def test_main_shows_plots_when_no_output_file_is_set(monkeypatch) -> None:
    import signal

    histories = {"reference.oem": {float(epoch): np.ones(6) for epoch in range(5)}}
    monkeypatch.setattr(signal, "signal", lambda *_args: None)
    monkeypatch.setattr(file_io, "read_orbit_file", histories.__getitem__)
    monkeypatch.setattr(plt, "get_fignums", lambda: [])
    show = Mock()
    monkeypatch.setattr(plt, "show", show)
    for name in (
        "plot_relative_rtn_timeseries",
        "plot_relative_rtn_orbits",
        "plot_relative_cartesian_timeseries",
        "plot_angular_separation",
        "plot_orbits",
    ):
        monkeypatch.setattr(plotting, name, Mock())

    plot_oem_diff_entry.main(["reference.oem"])

    show.assert_called_once_with()


def test_cli_forwards_to_shared_runner(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        core_cli, "run_cli", lambda main, argv: calls.append((main, argv)) or 4
    )

    assert plot_oem_diff_entry.cli(["reference.oem"]) == 4
    assert calls == [(plot_oem_diff_entry.main, ["reference.oem"])]


def test_relative_plots_show_expected_deltas_and_write_outputs(
    monkeypatch, tmp_path: Path
) -> None:
    reference_state = np.array([7.0e6, 0.0, 0.0, 0.0, 7_500.0, 0.0])
    comparison_state = np.array([0.0, 7.0e6, 0.0, 10.0, 7_510.0, 20.0])
    reference_history = StateHistory(
        label="reference",
        state_history={epoch: reference_state.copy() for epoch in (0.0, 60.0, 120.0)},
    )
    monkeypatch.setattr(
        reference_history,
        "get_interpolated_state",
        lambda _epoch: reference_state,
    )
    comparison_history = StateHistory(
        label="comparison",
        state_history={60.0: comparison_state, 120.0: comparison_state},
    )
    monkeypatch.setattr(
        plotting.misc,
        "transform_to_rtn",
        lambda *_args: np.array([1_000.0, 2_000.0, 3_000.0, 4_000.0, 5_000.0, 6_000.0]),
    )

    try:
        cartesian_plot = tmp_path / "cartesian.png"
        plotting.plot_relative_cartesian_timeseries(
            reference_history,
            [comparison_history],
            output_file=str(cartesian_plot),
            time_unit=plotting.TimeUnit.MINUTES,
        )
        cartesian_figure = plt.gcf()
        np.testing.assert_allclose(
            cartesian_figure.axes[0].lines[-1].get_xdata(), [1.0, 2.0]
        )
        np.testing.assert_allclose(
            cartesian_figure.axes[0].lines[-1].get_ydata(), [-7_000.0, -7_000.0]
        )

        rtn_plot = tmp_path / "rtn.png"
        plotting.plot_relative_rtn_timeseries(
            reference_history,
            [comparison_history],
            output_file=str(rtn_plot),
            time_unit=plotting.TimeUnit.MINUTES,
        )
        rtn_figure = plt.gcf()
        np.testing.assert_allclose(rtn_figure.axes[0].lines[-1].get_xdata(), [1.0, 2.0])
        np.testing.assert_allclose(rtn_figure.axes[0].lines[-1].get_ydata(), [1.0, 1.0])

        angular_plot = tmp_path / "angular.png"
        plotting.plot_angular_separation(
            reference_history,
            [comparison_history],
            output_file=str(angular_plot),
            time_unit=plotting.TimeUnit.MINUTES,
        )
        angular_figure = plt.gcf()
        np.testing.assert_allclose(
            angular_figure.axes[0].lines[-1].get_ydata(), [90.0, 90.0]
        )
        assert cartesian_plot.stat().st_size > 0
        assert rtn_plot.stat().st_size > 0
        assert angular_plot.stat().st_size > 0
    finally:
        plt.close("all")

    assert (
        tmp_path / "cartesian_relative_cartesian_timeseries_comparison.csv"
    ).exists()
    assert (tmp_path / "rtn_relative_rtn_timeseries_comparison.csv").exists()
    assert (tmp_path / "angular_angular_separation_comparison.csv").exists()


def test_read_orbit_file_falls_back_to_raw_state_parsing(
    tmp_path: Path, monkeypatch
) -> None:
    source_path = tmp_path / "states.txt"
    source_path.write_text("header\nstate\nmalformed\n", encoding="utf-8")
    expected_state = np.arange(6, dtype=float)

    def reject_as_oem(_source):
        raise ValueError("not OEM")

    def parse_line(line):
        if line.strip() == "state":
            return 123.0, expected_state
        if line.strip() == "malformed":
            raise ValueError("invalid state")
        return None

    monkeypatch.setattr(orbit_file_io.CcsdsOem, "read", reject_as_oem)
    monkeypatch.setattr(
        orbit_file_io.oem.CcsdsOem,
        "parse_oem_state_line",
        classmethod(lambda _cls, line: parse_line(line)),
    )

    state_history = orbit_file_io.read_orbit_file(source_path)

    assert list(state_history) == [123.0]
    np.testing.assert_array_equal(state_history[123.0], expected_state)


def test_read_orbit_file_rejects_files_without_state_rows(
    tmp_path: Path, monkeypatch
) -> None:
    source_path = tmp_path / "empty.txt"
    source_path.write_text("header\ncomment\n", encoding="utf-8")
    monkeypatch.setattr(
        orbit_file_io.CcsdsOem,
        "read",
        lambda _source: (_ for _ in ()).throw(ValueError("not OEM")),
    )
    monkeypatch.setattr(
        orbit_file_io.oem.CcsdsOem,
        "parse_oem_state_line",
        classmethod(lambda _cls, _line: None),
    )

    with pytest.raises(ValueError, match="Could not parse any state data"):
        orbit_file_io.read_orbit_file(source_path)


def test_read_orbit_file_rejects_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="File not found"):
        orbit_file_io.read_orbit_file(tmp_path / "missing.oem")
