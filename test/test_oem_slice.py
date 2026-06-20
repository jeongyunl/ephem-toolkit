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
from oem.oem_slice import slice_states_by_time

TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PROJECT_ROOT) + ((":" + existing) if existing else "")
    return env


def test_time_slice_prints_start_stop_step(tmp_path: Path) -> None:
    script = PROJECT_ROOT / "oem" / "oem_slice.py"
    result = subprocess.run(
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

    assert result.returncode == 0, f"oem_slice.py failed: {result.stderr}"
    lines = result.stdout.strip().splitlines()
    assert lines == [
        "2026-05-20T12:00:00",
        "2026-05-20T12:10:00",
        "5m",
    ]


def test_time_slice_default_step_unit_is_minutes() -> None:
    script = PROJECT_ROOT / "oem" / "oem_slice.py"
    result = subprocess.run(
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

    assert result.returncode == 0, f"oem_slice.py failed: {result.stderr}"
    lines = result.stdout.strip().splitlines()
    assert lines == [
        "2026-05-20T12:00:00",
        "2026-05-20T12:10:00",
        "5m",
    ]


def test_time_slice_prints_empty_components_for_missing_values() -> None:
    script = PROJECT_ROOT / "oem" / "oem_slice.py"
    result = subprocess.run(
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

    assert result.returncode == 0, f"oem_slice.py failed: {result.stderr}"
    lines = result.stdout.splitlines()
    assert lines == ["", "2026-05-20T12:10:00", ""]


def test_time_slice_missing_stop_returns_one_state_only() -> None:
    sample_oem = TEST_DIR / "data" / "ISS_2026-05-20.OEM"
    script = PROJECT_ROOT / "oem" / "oem_slice.py"
    result = subprocess.run(
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

    assert result.returncode == 0, f"oem_slice.py failed: {result.stderr}"
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1


def test_slice_states_by_time_dict_ordered_and_filtered() -> None:
    states = {
        10.0: np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0]),
        5.0: np.array([5.0, 4.0, 3.0, 2.0, 1.0, 0.0]),
        20.0: np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
    }

    sliced = slice_states_by_time(
        states,
        start_time=datetime.fromtimestamp(5.0, tz=timezone.utc),
        stop_time=datetime.fromtimestamp(15.0, tz=timezone.utc),
    )

    assert len(sliced) == 2
    assert sliced[0][0] == 5.0
    assert sliced[1][0] == 10.0
    assert np.allclose(sliced[0][1], states[5.0], atol=1e-12, rtol=0.0)
    assert np.allclose(sliced[1][1], states[10.0], atol=1e-12, rtol=0.0)
