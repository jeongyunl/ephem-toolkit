"""Tests for src/xform_oem/xform_oem.py — OEM transformation utility script."""

from __future__ import annotations

import io
import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

import ephem_toolkit.xform_oem.operations as operations
import ephem_toolkit.xform_oem.xform_oem_cli as xform_oem_cli
from ephem_toolkit.xform_oem import main

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test modules."""

PROJECT_ROOT: Path = TEST_DIR.parent.parent.parent
"""Repository root path."""


class CliResult:
    """Mock subprocess.CompletedProcess for direct function calls."""

    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _run_xform_oem(args: list[str], input_data: str | None = None) -> CliResult:
    """Run xform_oem main function with given arguments."""
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    with (
        patch("sys.stdout", stdout_capture),
        patch("sys.stderr", stderr_capture),
        patch("sys.stdin", io.StringIO(input_data or "")),
    ):
        try:
            main(args)
            returncode = 0
        except SystemExit as e:
            returncode = e.code if isinstance(e.code, int) else (1 if e.code else 0)
        except Exception:
            returncode = 1

    return CliResult(returncode, stdout_capture.getvalue(), stderr_capture.getvalue())


def test_debug_override_messages_show_original_values() -> None:
    """Show original header and metadata values in verbose override messages."""
    input_oem = """CCSDS_OEM_VERS = 2.0
CREATION_DATE = 2024-01-01T00:00:00.000
ORIGINATOR = ORIGINAL_ORIGINATOR
META_START
OBJECT_NAME = ORIGINAL_OBJECT
OBJECT_ID = 1998-067A
CENTER_NAME = EARTH
REF_FRAME = GCRF
TIME_SYSTEM = UTC
START_TIME = 2024-01-01T00:00:00.000
STOP_TIME = 2024-01-01T00:00:00.000
META_STOP
2024-01-01T00:00:00.000 7000 0 0 0 7.5 0
"""
    result = _run_xform_oem(
        [
            "-",
            "--output",
            "-",
            "--verbose",
            "--set-meta",
            "OBJECT_NAME=UPDATED_OBJECT",
            "--set-header",
            "ORIGINATOR=UPDATED_ORIGINATOR",
        ],
        input_oem,
    )

    assert result.returncode == 0
    assert "OBJECT_NAME: ORIGINAL_OBJECT -> UPDATED_OBJECT" in result.stderr
    assert "ORIGINATOR: ORIGINAL_ORIGINATOR -> UPDATED_ORIGINATOR" in result.stderr


def test_csv_output_flag_writes_csv_state_header() -> None:
    """Write state data as CSV when --x-csv is provided."""
    input_oem = """CCSDS_OEM_VERS = 2.0
CREATION_DATE = 2024-01-01T00:00:00.000
ORIGINATOR = TEST
META_START
OBJECT_NAME = TEST_OBJECT
REF_FRAME = GCRF
TIME_SYSTEM = UTC
META_STOP
2024-01-01T00:00:00.000 7000 0 0 0 7.5 0
"""
    result = _run_xform_oem(["-", "--output", "-", "--x-csv"], input_oem)

    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert lines[-2] == "epoch,x_km,y_km,z_km,vx_km_s,vy_km_s,vz_km_s"
    assert lines[-1].count(",") == 6


def test_data_only_output_omits_oem_header_and_metadata() -> None:
    """Write only OEM-format state rows when --data-only is provided."""
    input_oem = """CCSDS_OEM_VERS = 2.0
CREATION_DATE = 2024-01-01T00:00:00.000
ORIGINATOR = TEST
META_START
OBJECT_NAME = TEST_OBJECT
REF_FRAME = GCRF
TIME_SYSTEM = UTC
META_STOP
2024-01-01T00:00:00.000 7000 0 0 0 7.5 0
"""
    result = _run_xform_oem(["-", "--output", "-", "--data-only"], input_oem)

    assert result.returncode == 0
    assert result.stdout == ("2024-01-01T00:00:00.000000 7000 0 0 0 7.5 0\n")


def test_help_uses_command_name_and_project_output_metavar() -> None:
    """The xform-oem help text should follow the project command naming conventions."""
    result = _run_xform_oem(["--help"])

    assert result.returncode == 0
    assert "usage: xform-oem" in result.stdout
    assert "--output <output_oem|->" in result.stdout


def test_x_arguments_are_mutually_exclusive() -> None:
    """Reject combinations of the --x-* options."""
    result = _run_xform_oem(["-", "--x-ref-frame", "J2000", "--x-aer", "40,-74,10"])

    assert result.returncode != 0
    assert "not allowed with argument" in result.stderr


def test_parse_metadata_and_header_overrides_converts_typed_values() -> None:
    parser = argparse.ArgumentParser()

    metadata = operations.parse_metadata_overrides(
        ["object_name=Updated", "INTERPOLATION_DEGREE=9"], parser
    )
    header = operations.parse_header_overrides(
        ["originator=tool", "CCSDS_OEM_VERS=3.0"], parser
    )

    assert metadata == [("object_name", "Updated"), ("interpolation_degree", 9)]
    assert header == [("originator", "tool"), ("version", 3.0)]


@pytest.mark.parametrize(
    ("parser_function", "value", "message"),
    [
        (operations.parse_metadata_overrides, "OBJECT_NAME", "requires KEY=VALUE"),
        (
            operations.parse_metadata_overrides,
            "UNKNOWN=value",
            "unknown --set-meta key",
        ),
        (
            operations.parse_metadata_overrides,
            "INTERPOLATION_DEGREE=high",
            "must be an integer",
        ),
        (operations.parse_header_overrides, "ORIGINATOR", "requires KEY=VALUE"),
        (
            operations.parse_header_overrides,
            "UNKNOWN=value",
            "unknown --set-header key",
        ),
        (
            operations.parse_header_overrides,
            "CCSDS_OEM_VERS=latest",
            "must be numeric",
        ),
    ],
)
def test_override_parsers_reject_invalid_values(
    parser_function, value, message
) -> None:
    with pytest.raises(SystemExit):
        parser_function([value], argparse.ArgumentParser())


def test_convert_ref_frame_mutates_states_and_returns_canonical_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_state = np.arange(6, dtype=float)
    oem_data = SimpleNamespace(
        meta=SimpleNamespace(ref_frame="GCRF"),
        states=[(123.0, original_state.copy())],
    )
    converted_state = original_state + 10.0
    monkeypatch.setattr(
        operations.frame_utils,
        "convert_frame",
        lambda **_kwargs: converted_state,
    )

    result = operations.convert_ref_frame(oem_data, "itrf")

    assert result == "ITRF"
    np.testing.assert_array_equal(oem_data.states[0][1], converted_state)


def test_convert_ref_frame_leaves_state_unchanged_when_conversion_fails(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    original_state = np.arange(6, dtype=float)
    oem_data = SimpleNamespace(
        meta=SimpleNamespace(ref_frame="GCRF"),
        states=[(123.0, original_state.copy())],
    )
    monkeypatch.setattr(operations.frame_utils, "convert_frame", lambda **_kwargs: None)

    assert operations.convert_ref_frame(oem_data, "ITRF") is None
    np.testing.assert_array_equal(oem_data.states[0][1], original_state)
    assert "Leaving state unchanged" in capsys.readouterr().err


@pytest.mark.parametrize("ref_frame", ["ITRF", "ITRF2020", "GCRF"])
def test_convert_to_aer_formats_states_and_reports_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    ref_frame: str,
) -> None:
    oem_data = SimpleNamespace(
        meta=SimpleNamespace(ref_frame=ref_frame),
        states=[(123.0, np.arange(6, dtype=float))],
    )
    monkeypatch.setattr(
        operations.aer,
        "ecef_to_aer",
        lambda position, reference: np.array([np.pi, np.pi / 4.0, 1234.5]),
    )
    monkeypatch.setattr(operations.time_utils, "tt_s_to_datetime", lambda _epoch: None)
    monkeypatch.setattr(
        operations.time_utils,
        "datetime_to_iso8601",
        lambda _datetime: "2026-01-02T03:04:05.000000",
    )
    output = io.StringIO()

    operations.convert_to_aer(oem_data, 40.0, -74.0, 10.0, output, verbose=True)

    assert output.getvalue().startswith("2026-01-02T03:04:05.000000")
    assert "180.000000" in output.getvalue()
    assert "45.000000" in output.getvalue()
    assert "1234.500" in output.getvalue()
    diagnostics = capsys.readouterr()
    assert "Ground station" in diagnostics.err
    if ref_frame == "GCRF":
        assert "may not be ECEF" in diagnostics.err
    else:
        assert "may not be ECEF" not in diagnostics.err


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--x-ref-frame", "J2000,", "requires <frame>"),
        ("--x-aer", "40,-74", "exactly 3 comma-separated values"),
        ("--x-aer", "north,-74,10", "values must be numeric"),
        ("--set-meta", "OBJECT_NAME", "requires KEY=VALUE"),
        ("--set-meta", "UNKNOWN=value", "unknown --set-meta key"),
        ("--set-meta", "INTERPOLATION_DEGREE=high", "must be an integer"),
        ("--set-header", "ORIGINATOR", "requires KEY=VALUE"),
        ("--set-header", "UNKNOWN=value", "unknown --set-header key"),
        ("--set-header", "CCSDS_OEM_VERS=latest", "must be numeric"),
    ],
)
def test_xform_cli_rejects_invalid_transform_and_override_values(
    option: str,
    value: str,
    message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = xform_oem_cli.build_arg_parser()
    with pytest.raises(SystemExit):
        xform_oem_cli.parse_arguments(
            parser, ["input.oem", "--output", "-", option, value]
        )
    assert message in capsys.readouterr().err


def test_main_runs_aer_conversion_to_file_and_closes_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_oem = """CCSDS_OEM_VERS = 2.0
CREATION_DATE = 2024-01-01T00:00:00.000
ORIGINATOR = TEST
META_START
OBJECT_NAME = TEST_OBJECT
REF_FRAME = GCRF
TIME_SYSTEM = UTC
START_TIME = 2024-01-01T00:00:00.000
STOP_TIME = 2024-01-01T00:00:00.000
META_STOP
2024-01-01T00:00:00.000 7000 0 0 0 7.5 0
"""
    output_path = tmp_path / "aer.txt"
    conversion_calls = []

    def convert(_oem_data, latitude, longitude, altitude, output_file, verbose):
        conversion_calls.append((latitude, longitude, altitude, verbose))
        output_file.write("AER output\n")

    monkeypatch.setattr(operations, "convert_to_aer", convert)
    result = _run_xform_oem(
        [
            "-",
            "--x-aer",
            "40,-74,10",
            "--output",
            str(output_path),
            "--verbose",
        ],
        input_oem,
    )

    assert result.returncode == 0
    assert conversion_calls == [(40.0, -74.0, 10.0, True)]
    assert output_path.read_text(encoding="utf-8") == "AER output\n"
    assert "Total States: 1" in result.stderr


def test_main_converts_frame_and_applies_metadata_and_header_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_oem = """CCSDS_OEM_VERS = 2.0
CREATION_DATE = 2024-01-01T00:00:00.000
ORIGINATOR = TEST
META_START
OBJECT_NAME = TEST_OBJECT
REF_FRAME = GCRF
TIME_SYSTEM = UTC
START_TIME = 2024-01-01T00:00:00.000
STOP_TIME = 2024-01-01T00:00:00.000
META_STOP
2024-01-01T00:00:00.000 7000 0 0 0 7.5 0
"""
    conversion_calls = []
    monkeypatch.setattr(
        operations,
        "convert_ref_frame",
        lambda data, target, source: conversion_calls.append((source, target))
        or "ITRF",
    )

    result = _run_xform_oem(
        [
            "-",
            "--x-ref-frame",
            "GCRF,ITRF",
            "--set-meta",
            "OBJECT_NAME=RENAMED",
            "--set-header",
            "ORIGINATOR=UPDATED",
            "--output",
            "-",
        ],
        input_oem,
    )

    assert result.returncode == 0
    assert conversion_calls == [("GCRF", "ITRF")]
    assert "OBJECT_NAME = RENAMED" in result.stdout
    assert "ITRF" in result.stdout
    assert "GCRF" not in result.stdout
    assert "ORIGINATOR     = UPDATED" in result.stdout
