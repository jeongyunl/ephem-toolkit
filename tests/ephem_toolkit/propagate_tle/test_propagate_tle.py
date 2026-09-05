"""Tests for the TLE propagation utility script."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from ephem_toolkit.propagate_tle import main as propagate_tle_main

TEST_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = TEST_DIR.parent.parent.parent
TEST_DATA_DIR: Path = TEST_DIR.parent.parent / "data"

TLE_FILES: list[Path] = sorted(TEST_DATA_DIR.glob("*.tle"))


def run_propagate_tle(tle_path: Path) -> str:
    """Run propagate_tle.py script and return output.

    Parameters
    ----------
    tle_path : Path
        Path to TLE file to propagate.

    Returns
    -------
    str
        Standard output from propagate_tle.py script.
    """
    old_stdout = sys.stdout
    captured_output = io.StringIO()
    sys.stdout = captured_output

    try:
        result = propagate_tle_main(
            [
                str(tle_path),
                "--data-only",
                "-s",
                "15m",
                "--output",
                "-",
            ]
        )
        assert result == 0, f"propagate_tle.py failed for {tle_path.name}"
    finally:
        sys.stdout = old_stdout

    output = captured_output.getvalue()
    assert output.strip(), f"propagate_tle.py produced no output for {tle_path.name}"
    return output


@pytest.mark.parametrize("tle_path", TLE_FILES, ids=[p.name for p in TLE_FILES])
def test_propagate_tle_produces_valid_state_vectors(tle_path: Path) -> None:
    """Should propagate each TLE for 1 day and produce valid OEM-like state vectors.

    Parameters
    ----------
    tle_path : Path
        Path to TLE file to test.
    """
    oem_text: str = run_propagate_tle(tle_path)
    lines: list[str] = [line for line in oem_text.strip().splitlines() if line.strip()]
    assert (
        len(lines) >= 90
    ), f"Expected ~97 state lines, got {len(lines)} for {tle_path.name}"
    for line in lines[:5]:
        parts: list[str] = line.split()
        assert len(parts) == 7, f"Expected 7 fields per line, got {len(parts)}: {line}"


def test_propagate_tle_oem_records_sgp4_provenance(tmp_path: Path) -> None:
    output = tmp_path / "propagated.oem"
    propagate_tle_main(
        [
            str(TEST_DATA_DIR / "ISS-ZARYA_1998-067A.tle"),
            "--duration",
            "15m",
            "--step",
            "15m",
            "--output",
            str(output),
        ]
    )

    assert (
        "EPHEMERIS_PROVENANCE: source=TLE; transformation=propagation; "
        "target_model=SGP4"
        in output.read_text(encoding="utf-8")
    )
