"""Tests for oem_to_tle/oem_to_tle.py — OEM to TLE conversion utility script."""

from __future__ import annotations

import io
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.tle as tle
import common.consts as consts
import common.oem as oem
import oem_to_tle.oem_to_tle as oem_to_tle
import oem_to_tle.models as models
import oem_to_tle.orbital_mechanics as orbital_mechanics
import oem_to_tle.tle_builder as tle_builder
import oem_to_tle.estimation as estimation

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test files."""

TEST_DATA_DIR: Path = TEST_DIR.parent / "data"
"""Directory containing test data files (OEM, TLE, OMM samples)."""

ISS_OEM_PATH: Path = TEST_DATA_DIR / "ISS_2026-05-20.OEM"
"""Path to ISS OEM test file for 2026-05-20."""

JPSS1_OEM_PATH: Path = TEST_DATA_DIR / "JPSS-1.oem"
"""Path to JPSS-1 OEM test file."""


# ===================================================================
# 8. Accuracy verification
# ===================================================================


def test_verify_accuracy_keplerian_returns_accuracy_dataclass() -> None:
    """Should return KeplerianAccuracy dataclass with element-wise errors."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states
    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    args = MagicMock()
    args.name = ""
    args.satellite_number = 99999
    args.classification = "U"
    args.int_designator_year = 0
    args.int_designator_launch_number = 0
    args.int_designator_piece = "A"
    args.ephemeris_type = 0
    args.element_set_number = 1
    args.bstar = "00000+0"
    args.mean_motion_second_derivative = "00000+0"
    args.revolution_number_at_epoch = 0

    accuracy = estimation.verify_accuracy_keplerian(args, estimated, records)

    if accuracy is not None:
        assert isinstance(accuracy, models.KeplerianAccuracy)
        assert hasattr(accuracy, "semi_major_axis_error_m")
        assert hasattr(accuracy, "eccentricity_error")
        assert hasattr(accuracy, "inclination_error_deg")
        assert hasattr(accuracy, "raan_error_deg")
        assert hasattr(accuracy, "arg_perigee_error_deg")
        assert hasattr(accuracy, "true_anomaly_error_deg")


# ===================================================================
# 10. Integration test: full workflow
# ===================================================================


@pytest.mark.skipif(not ISS_OEM_PATH.exists(), reason="ISS OEM test file not available")
def test_main_workflow_with_file_input(tmp_path: Path) -> None:
    """Should execute full workflow from OEM file to TLE output."""
    output_file = tmp_path / "output.tle"

    # Mock SPICE kernel loading to avoid dependency
    with patch("oem_to_tle.oem_to_tle.load_spice_kernels"):
        with patch(
            "sys.argv",
            [
                "oem_to_tle.py",
                str(ISS_OEM_PATH),
                "-o",
                str(output_file),
                "--refinement",
                "none",
                "--name",
                "ISS TEST",
            ],
        ):
            oem_to_tle.main()

    # Check output file was created
    assert output_file.exists()
    content = output_file.read_text()

    # Verify TLE format (should have 2 or 3 lines)
    lines = content.strip().split("\n")
    assert len(lines) >= 2

    # Check for TLE line identifiers
    assert any("1 " in line for line in lines)
    assert any("2 " in line for line in lines)


@pytest.mark.skipif(not ISS_OEM_PATH.exists(), reason="ISS OEM test file not available")
def test_main_workflow_with_stdout(capsys) -> None:
    """Should write TLE output to stdout when output is '-'."""
    with patch("oem_to_tle.oem_to_tle.load_spice_kernels"):
        with patch(
            "sys.argv",
            [
                "oem_to_tle.py",
                str(ISS_OEM_PATH),
                "-o",
                "-",
                "--refinement",
                "none",
            ],
        ):
            oem_to_tle.main()

    captured = capsys.readouterr()
    # Should contain TLE line identifiers
    assert "1 " in captured.out
    assert "2 " in captured.out


def test_main_exits_on_invalid_input() -> None:
    """Should exit with error code when input is invalid."""
    with patch("oem_to_tle.oem_to_tle.load_spice_kernels"):
        with patch("sys.argv", ["oem_to_tle.py", "/nonexistent/file.oem"]):
            with pytest.raises(SystemExit) as exc_info:
                oem_to_tle.main()

    assert exc_info.value.code == 1


def test_main_exits_on_invalid_satellite_number() -> None:
    """Should exit with error when satellite number is out of range."""
    with patch("oem_to_tle.oem_to_tle.load_spice_kernels"):
        with patch(
            "sys.argv",
            ["oem_to_tle.py", str(ISS_OEM_PATH), "--satellite-number", "100000"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                oem_to_tle.main()

    assert exc_info.value.code == 1


def test_main_exits_on_insufficient_records(tmp_path: Path) -> None:
    """Should exit with error when fewer than 2 state vectors provided."""
    # Create OEM file with only 1 state vector
    single_state_oem = tmp_path / "single.oem"
    single_state_oem.write_text(
        "2026-05-20T00:00:00.000000 1000.0 2000.0 3000.0 4.0 5.0 6.0\n"
    )

    with patch("oem_to_tle.oem_to_tle.load_spice_kernels"):
        with patch("sys.argv", ["oem_to_tle.py", str(single_state_oem)]):
            with pytest.raises(SystemExit) as exc_info:
                oem_to_tle.main()

    assert exc_info.value.code == 1


# ===================================================================
# 11. Print summary function
# ===================================================================


def test_print_summary_outputs_key_information(capsys) -> None:
    """Should print summary with all key TLE estimation information."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states
    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    args = MagicMock()
    args.bstar = "00000+0"
    args.mean_motion_second_derivative = "00000+0"

    oem_to_tle.print_summary(records, estimated, args)

    captured = capsys.readouterr()
    assert "Estimated TLE elements" in captured.out
    assert "records:" in captured.out
    assert "epoch range:" in captured.out
    assert "inclination-deg:" in captured.out
    assert "raan-deg:" in captured.out
    assert "eccentricity:" in captured.out
    assert "mean-motion-rev-per-day:" in captured.out


def test_print_summary_includes_keplerian_accuracy(capsys) -> None:
    """Should include Keplerian accuracy section when provided."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states
    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    args = MagicMock()
    args.bstar = "00000+0"
    args.mean_motion_second_derivative = "00000+0"

    keplerian_accuracy = models.KeplerianAccuracy(
        semi_major_axis_error_m=100.0,
        eccentricity_error=0.0001,
        inclination_error_deg=0.01,
        raan_error_deg=0.02,
        arg_perigee_error_deg=0.03,
        true_anomaly_error_deg=0.04,
        arg_latitude_error_deg=0.05,
        ref_semi_major_axis_m=7000000.0,
        ref_eccentricity=0.001,
        ref_inclination_deg=51.6,
        ref_raan_deg=45.0,
        ref_arg_perigee_deg=90.0,
        ref_true_anomaly_deg=30.0,
        tle_semi_major_axis_m=7000100.0,
        tle_eccentricity=0.0011,
        tle_inclination_deg=51.61,
        tle_raan_deg=45.02,
        tle_arg_perigee_deg=90.03,
        tle_true_anomaly_deg=30.04,
    )

    oem_to_tle.print_summary(records, estimated, args, keplerian_accuracy)

    captured = capsys.readouterr()
    assert "Accuracy verification" in captured.out
    assert "semi-major-axis error:" in captured.out
    assert "eccentricity error:" in captured.out
