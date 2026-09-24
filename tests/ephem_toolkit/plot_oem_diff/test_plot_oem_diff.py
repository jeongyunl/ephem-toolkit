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

import ephem_toolkit.plot_oem_diff.__main__ as plot_oem_diff_entry
import ephem_toolkit.plot_oem_diff.file_io as file_io
import ephem_toolkit.plot_oem_diff.plotting as plotting
from ephem_toolkit.plot_oem_diff import file_io as orbit_file_io
from ephem_toolkit.plot_oem_diff.data_structures import StateHistory
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


def test_relative_plots_show_expected_cartesian_rtn_and_angular_deltas(
    monkeypatch,
) -> None:
    reference_state = np.array([7.0e6, 0.0, 0.0, 0.0, 7_500.0, 0.0])
    comparison_state = np.array([0.0, 7.0e6, 0.0, 10.0, 7_510.0, 20.0])
    reference_history = StateHistory(
        label="reference",
        state_history={
            epoch: reference_state.copy() for epoch in (0.0, 60.0, 120.0)
        },
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
        plotting.plot_relative_cartesian_timeseries(
            reference_history, [comparison_history], time_unit=plotting.TimeUnit.MINUTES
        )
        cartesian_figure = plt.gcf()
        np.testing.assert_allclose(
            cartesian_figure.axes[0].lines[-1].get_xdata(), [1.0, 2.0]
        )
        np.testing.assert_allclose(
            cartesian_figure.axes[0].lines[-1].get_ydata(), [-7_000.0, -7_000.0]
        )

        plotting.plot_relative_rtn_timeseries(
            reference_history, [comparison_history], time_unit=plotting.TimeUnit.MINUTES
        )
        rtn_figure = plt.gcf()
        np.testing.assert_allclose(rtn_figure.axes[0].lines[-1].get_xdata(), [1.0, 2.0])
        np.testing.assert_allclose(rtn_figure.axes[0].lines[-1].get_ydata(), [1.0, 1.0])

        plotting.plot_angular_separation(
            reference_history, [comparison_history], time_unit=plotting.TimeUnit.MINUTES
        )
        angular_figure = plt.gcf()
        np.testing.assert_allclose(
            angular_figure.axes[0].lines[-1].get_ydata(), [90.0, 90.0]
        )
    finally:
        plt.close("all")


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
