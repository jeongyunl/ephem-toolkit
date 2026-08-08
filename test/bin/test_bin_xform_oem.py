"""Tests for bin/xform_oem.py — OEM transformation utility script."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test modules."""

PROJECT_ROOT: Path = TEST_DIR.parent.parent
"""Repository root path."""

XFORM_OEM_SCRIPT: Path = PROJECT_ROOT / "bin" / "xform_oem.py"
"""Path to xform_oem.py script."""


def _build_env() -> dict[str, str]:
    """Build a test PYTHONPATH environment for running the helper script."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + existing if existing else "")
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
