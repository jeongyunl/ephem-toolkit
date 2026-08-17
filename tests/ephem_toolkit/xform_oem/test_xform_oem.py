"""Tests for src/xform_oem/xform_oem.py — OEM transformation utility script."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test modules."""

PROJECT_ROOT: Path = TEST_DIR.parent.parent.parent
"""Repository root path."""

XFORM_OEM_SCRIPT: Path = (
    PROJECT_ROOT / "src" / "ephem_toolkit" / "xform_oem" / "xform_oem.py"
)
"""Path to xform_oem.py script."""


def _build_env() -> dict[str, str]:
    """Build a test PYTHONPATH environment for running the helper script."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    source_paths = [
        PROJECT_ROOT / "src",
        PROJECT_ROOT / "src" / "ephem_toolkit",
    ]
    env["PYTHONPATH"] = os.pathsep.join(
        [*(str(path) for path in source_paths), existing]
        if existing
        else [*(str(path) for path in source_paths)]
    )
    return env


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
    env = _build_env()

    result = subprocess.run(
        [
            sys.executable,
            str(XFORM_OEM_SCRIPT),
            "-",
            "--verbose",
            "--set-meta",
            "OBJECT_NAME=UPDATED_OBJECT",
            "--set-header",
            "ORIGINATOR=UPDATED_ORIGINATOR",
        ],
        capture_output=True,
        text=True,
        input=input_oem,
        env=env,
        check=False,
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
    result = subprocess.run(
        [sys.executable, str(XFORM_OEM_SCRIPT), "-", "--x-csv"],
        capture_output=True,
        text=True,
        input=input_oem,
        env=_build_env(),
        check=False,
    )

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
    result = subprocess.run(
        [sys.executable, str(XFORM_OEM_SCRIPT), "-", "--data-only"],
        capture_output=True,
        text=True,
        input=input_oem,
        env=_build_env(),
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == ("2024-01-01T00:00:00.000000 7000 0 0 0 7.5 0\n")


def test_x_arguments_are_mutually_exclusive() -> None:
    """Reject combinations of the --x-* options."""
    result = subprocess.run(
        [
            sys.executable,
            str(XFORM_OEM_SCRIPT),
            "-",
            "--x-ref-frame",
            "J2000",
            "--x-aer",
            "40,-74,10",
        ],
        capture_output=True,
        text=True,
        env=_build_env(),
        check=False,
    )

    assert result.returncode != 0
    assert "not allowed with argument" in result.stderr
