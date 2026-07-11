"""Tests for the OEM slice CLI helper."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

import common.oem as oem
import common.slice_oem as slice_oem

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test modules."""

PROJECT_ROOT: Path = TEST_DIR.parent
"""Repository root path."""

# ===================================================================
# Test helpers
# ===================================================================


def _build_env() -> dict[str, str]:
    """Build a test PYTHONPATH environment for running the helper script."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + existing if existing else "")
    return env


def test_time_slice_prints_start_stop_step(tmp_path: Path) -> None:
    script: Path = PROJECT_ROOT / "bin" / "slice_oem.py"
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            str(script),
            "--interpolate",
            "--time-slice",
            "2026-05-20T12:00:00,2026-05-20T12:10:00,5m",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )

    assert result.returncode == 0, f"slice_oem.py failed: {result.stderr}"
    lines: list[str] = result.stdout.strip().splitlines()
    assert lines == [
        "2026-05-20T12:00:00.000",
        "2026-05-20T12:10:00.000",
        "5m",
    ]


def test_time_slice_default_step_unit_is_minutes() -> None:
    script: Path = PROJECT_ROOT / "bin" / "slice_oem.py"
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            str(script),
            "--interpolate",
            "--time-slice",
            "2026-05-20T12:00:00,2026-05-20T12:10:00,5",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )

    assert result.returncode == 0, f"slice_oem.py failed: {result.stderr}"
    lines: list[str] = result.stdout.strip().splitlines()
    assert lines == [
        "2026-05-20T12:00:00.000",
        "2026-05-20T12:10:00.000",
        "5m",
    ]


def test_time_slice_prints_empty_components_for_missing_values() -> None:
    script: Path = PROJECT_ROOT / "bin" / "slice_oem.py"
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            str(script),
            "--time-slice",
            ",2026-05-20T12:10:00",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )

    assert result.returncode == 0, f"slice_oem.py failed: {result.stderr}"
    lines: list[str] = result.stdout.splitlines()
    assert lines == ["", "2026-05-20T12:10:00.000", ""]


def test_time_slice_missing_stop_returns_one_state_only() -> None:
    sample_oem: Path = TEST_DIR / "data" / "ISS_2026-05-20.OEM"
    script: Path = PROJECT_ROOT / "bin" / "slice_oem.py"
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            str(script),
            str(sample_oem),
            "--time-slice",
            "2026-05-20T12:00:00,",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )

    assert result.returncode == 0, f"slice_oem.py failed: {result.stderr}"
    lines: list[str] = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1


def test_slice_states_by_time_dict_ordered_and_filtered() -> None:
    ts1: float = 5.0
    ts2: float = 10.0
    ts3: float = 20.0

    # states now uses float POSIX timestamps as keys
    states: dict[float, np.ndarray] = {
        ts2: np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0]),
        ts1: np.array([5.0, 4.0, 3.0, 2.0, 1.0, 0.0]),
        ts3: np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
    }

    options: slice_oem.TimeSliceOptions = slice_oem.TimeSliceOptions(
        start_time=datetime.fromtimestamp(5.0, tz=timezone.utc),
        stop_time=datetime.fromtimestamp(15.0, tz=timezone.utc),
    )
    sliced: list[tuple[float, np.ndarray]] = slice_oem.slice_states(states, options)

    assert len(sliced) == 2
    assert sliced[0][0] == ts1
    assert sliced[1][0] == ts2
    assert np.allclose(sliced[0][1], states[ts1], atol=1e-12, rtol=0.0)
    assert np.allclose(sliced[1][1], states[ts2], atol=1e-12, rtol=0.0)


def test_slice_states_with_slice_object() -> None:
    ts1: float = 5.0
    ts2: float = 10.0
    ts3: float = 20.0
    states: dict[float, np.ndarray] = {
        ts1: np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        ts2: np.array([2.0, 2.0, 2.0, 2.0, 2.0, 2.0]),
        ts3: np.array([3.0, 3.0, 3.0, 3.0, 3.0, 3.0]),
    }

    sliced: list[tuple[float, np.ndarray]] = slice_oem.slice_states(states, slice(1, 3))

    assert len(sliced) == 2
    assert sliced[0][0] == ts2
    assert sliced[1][0] == ts3


def test_slice_states_with_time_slice_options() -> None:
    ts1: float = 5.0
    ts2: float = 10.0
    ts3: float = 20.0
    states: dict[float, np.ndarray] = {
        ts1: np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        ts2: np.array([2.0, 2.0, 2.0, 2.0, 2.0, 2.0]),
        ts3: np.array([3.0, 3.0, 3.0, 3.0, 3.0, 3.0]),
    }

    options: slice_oem.TimeSliceOptions = slice_oem.TimeSliceOptions(
        start_time=datetime.fromtimestamp(10.0, tz=timezone.utc),
        stop_time=datetime.fromtimestamp(20.0, tz=timezone.utc),
    )
    sliced: list[tuple[float, np.ndarray]] = slice_oem.slice_states(states, options)

    assert len(sliced) == 2
    assert sliced[0][0] == ts2
    assert sliced[1][0] == ts3


def test_slice_states_by_time_accepts_time_slice_options() -> None:
    ts1: float = 5.0
    ts2: float = 10.0
    ts3: float = 20.0
    states: dict[float, np.ndarray] = {
        ts1: np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        ts2: np.array([2.0, 2.0, 2.0, 2.0, 2.0, 2.0]),
        ts3: np.array([3.0, 3.0, 3.0, 3.0, 3.0, 3.0]),
    }

    options: slice_oem.TimeSliceOptions = slice_oem.TimeSliceOptions(
        start_time=datetime.fromtimestamp(10.0, tz=timezone.utc),
        stop_time=datetime.fromtimestamp(20.0, tz=timezone.utc),
    )
    sliced: list[tuple[float, np.ndarray]] = slice_oem.slice_states_by_time(
        states, options
    )

    assert len(sliced) == 2
    assert sliced[0][0] == ts2
    assert sliced[1][0] == ts3


def test_parse_slice_single_index_returns_slice() -> None:
    assert slice_oem.parse_slice_args("5") == slice(5, 6)
    assert slice_oem.parse_slice_args("-2") == slice(-2, -1)
    assert slice_oem.parse_slice_args("-1") == slice(-1, None)
