"""Tests for src/xform_oem/xform_oem.py — OEM transformation utility script."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

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
