"""Tests for :mod:`oem_to_kepler.oem_to_kepler` — OEM to Keplerian element fitting.

Validates the OEM-to-Keplerian conversion workflow including:
- Command-line argument parsing
- Input reading from files and stdin
- OEM dataset parsing
- Mean Keplerian element fitting via least-squares
- Output formatting and unit conversion
- Propagation accuracy computation
"""

from __future__ import annotations

import io
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import oem_to_kepler.oem_to_kepler as oem_to_kepler
import common.kepler as kepler
import common.consts as consts

TEST_DIR = Path(__file__).parent
TEST_DATA_DIR = TEST_DIR / "data"
ISS_OEM_PATH = TEST_DATA_DIR / "ISS_2026-05-20.OEM"


# ===================================================================
# 1. Command-line argument parsing
# ===================================================================


def test_parse_arguments_with_defaults() -> None:
    """Should parse arguments with default values when no args provided."""
    with patch("sys.argv", ["oem_to_kepler.py"]):
        args = oem_to_kepler.parse_arguments()

    assert args.input == "-"
    assert args.output == "-"
    assert args.mu_m3_s2 == pytest.approx(consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2)
    assert args.fit_span_hours == pytest.approx(2.0)


def test_parse_arguments_with_input_file() -> None:
    """Should parse input file path correctly."""
    with patch("sys.argv", ["oem_to_kepler.py", "test.oem"]):
        args = oem_to_kepler.parse_arguments()

    assert args.input == "test.oem"


def test_parse_arguments_with_output_file() -> None:
    """Should parse output file path with -o flag."""
    with patch("sys.argv", ["oem_to_kepler.py", "-o", "output.txt"]):
        args = oem_to_kepler.parse_arguments()

    assert args.output == "output.txt"


def test_parse_arguments_with_custom_mu() -> None:
    """Should parse custom gravitational parameter."""
    custom_mu = 3.986e14
    with patch("sys.argv", ["oem_to_kepler.py", "--mu", str(custom_mu)]):
        args = oem_to_kepler.parse_arguments()

    assert args.mu_m3_s2 == pytest.approx(custom_mu)


def test_parse_arguments_with_custom_fit_span() -> None:
    """Should parse custom fit span in hours."""
    with patch("sys.argv", ["oem_to_kepler.py", "--fit-span", "1.5"]):
        args = oem_to_kepler.parse_arguments()

    assert args.fit_span_hours == pytest.approx(1.5)


# ===================================================================
# 2. Input reading from file and stdin
# ===================================================================


def test_read_input_text_from_file() -> None:
    """Should read input text from an existing OEM file."""
    content = oem_to_kepler.read_input_text(str(ISS_OEM_PATH))

    assert isinstance(content, str)
    assert len(content) > 0
    assert "CCSDS_OEM_VERS" in content


def test_read_input_text_from_stdin() -> None:
    """Should read input text from stdin when source is '-'."""
    test_content = "Test OEM content\n2026-05-20T00:00:00 1000 2000 3000 4 5 6"

    with patch("sys.stdin", io.StringIO(test_content)):
        content = oem_to_kepler.read_input_text("-")

    assert content == test_content


def test_read_input_text_raises_on_empty_stdin() -> None:
    """Should raise ValueError when stdin is empty."""
    with patch("sys.stdin", io.StringIO("")):
        with pytest.raises(ValueError, match="No input from stdin"):
            oem_to_kepler.read_input_text("-")


def test_read_input_text_raises_on_nonexistent_file() -> None:
    """Should raise ValueError when file does not exist."""
    with pytest.raises(ValueError, match="Could not read input file"):
        oem_to_kepler.read_input_text("/nonexistent/file.oem")


def test_read_input_text_raises_on_empty_file(tmp_path: Path) -> None:
    """Should raise ValueError when file is empty."""
    empty_file = tmp_path / "empty.oem"
    empty_file.write_text("")

    with pytest.raises(ValueError, match="empty"):
        oem_to_kepler.read_input_text(str(empty_file))


# ===================================================================
# 3. OEM dataset parsing
# ===================================================================


def test_parse_dataset_from_oem_file() -> None:
    """Should parse OEM file into list of (timestamp, state_vector) tuples."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    assert isinstance(records, list)
    assert len(records) > 0

    # Check first record structure
    timestamp, state_vector = records[0]
    assert isinstance(timestamp, float)
    assert isinstance(state_vector, np.ndarray)
    assert state_vector.shape == (6,)


def test_parse_dataset_converts_km_to_m() -> None:
    """Should convert OEM data from km to meters."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    # ISS orbit should have position magnitude around 6700-7000 km (6.7e6 - 7e6 m)
    epoch, state_vector = records[0]
    pos_magnitude = np.linalg.norm(state_vector[:3])
    assert 6.0e6 < pos_magnitude < 8.0e6  # meters


def test_parse_dataset_raises_on_no_valid_states() -> None:
    """Should raise ValueError when no valid state vectors found."""
    # Use content that won't trigger parse errors but has no valid states
    invalid_content = "# Comment line\n# Another comment\n"

    with pytest.raises(ValueError, match="No valid state vectors found"):
        oem_to_kepler.parse_dataset(invalid_content)


def test_parse_dataset_handles_line_by_line_format() -> None:
    """Should parse simple line-by-line state vector format."""
    content = (
        "2026-05-20T00:00:00.000000 1000.0 2000.0 3000.0 4.0 5.0 6.0\n"
        "2026-05-20T00:01:00.000000 1100.0 2100.0 3100.0 4.1 5.1 6.1\n"
    )

    records = oem_to_kepler.parse_dataset(content)

    assert len(records) == 2
    epoch1, state_vector1 = records[0]
    # Values should be converted from km to m
    assert state_vector1[0] == pytest.approx(1000.0 * 1000.0)
    assert state_vector1[3] == pytest.approx(4.0 * 1000.0)


# ===================================================================
# 4. Keplerian element formatting
# ===================================================================


def test_format_keplerian_line_km_deg_units() -> None:
    """Should format Keplerian elements with km and degree units."""
    epoch = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc)
    # Elements in SI units (m, rad)
    kep_elements = np.array(
        [
            7000000.0,  # a in meters
            0.001,  # e
            np.radians(51.6),  # i in radians
            np.radians(45.0),  # omega in radians
            np.radians(90.0),  # RAAN in radians
            np.radians(30.0),  # theta in radians
        ]
    )

    line = oem_to_kepler.format_keplerian_line(epoch, kep_elements, "km-deg")

    assert "2026-05-20T00:00:00" in line
    assert "7000.000000" in line  # a in km
    assert "0.0010000000" in line  # e
    assert "51.600000" in line  # i in degrees
    assert "45.000000" in line  # omega in degrees
    assert "90.000000" in line  # RAAN in degrees
    assert "30.000000" in line  # theta in degrees


def test_format_keplerian_line_m_rad_units() -> None:
    """Should format Keplerian elements with meter and radian units."""
    epoch = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc)
    kep_elements = np.array([7000000.0, 0.001, 0.9, 0.785, 1.571, 0.524])

    line = oem_to_kepler.format_keplerian_line(epoch, kep_elements, "m-rad")

    assert "2026-05-20T00:00:00" in line
    assert "7000000.000000" in line  # a in meters
    assert "0.9000000000" in line  # i in radians


# ===================================================================
# 5. Mean element fitting
# ===================================================================


def test_fit_mean_elements_returns_six_elements() -> None:
    """Should return fitted mean Keplerian elements with shape (6,)."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    fitted_elements, diagnostics = oem_to_kepler.fit_mean_elements(
        records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )

    assert isinstance(fitted_elements, np.ndarray)
    assert fitted_elements.shape == (6,)


def test_fit_mean_elements_returns_diagnostics() -> None:
    """Should return diagnostics dictionary with fit statistics."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    fitted_elements, diagnostics = oem_to_kepler.fit_mean_elements(
        records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )

    assert "rms_position_m" in diagnostics
    assert "iterations" in diagnostics
    assert "n_records" in diagnostics
    assert "span_s" in diagnostics
    assert diagnostics["n_records"] > 0
    assert diagnostics["iterations"] > 0


def test_fit_mean_elements_produces_reasonable_semi_major_axis() -> None:
    """Should produce physically reasonable semi-major axis for ISS orbit."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    fitted_elements, _ = oem_to_kepler.fit_mean_elements(
        records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )

    a_km = fitted_elements[kepler.SEMI_MAJOR_AXIS_INDEX] / 1000.0
    # ISS orbit: ~6700-7000 km
    assert 6500.0 < a_km < 7200.0


def test_fit_mean_elements_produces_valid_eccentricity() -> None:
    """Should produce valid eccentricity (0 <= e < 1)."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    fitted_elements, _ = oem_to_kepler.fit_mean_elements(
        records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )

    e = fitted_elements[kepler.ECCENTRICITY_INDEX]
    assert 0.0 <= e < 1.0


def test_fit_mean_elements_filters_to_fit_span() -> None:
    """Should only use records within the specified fit span."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    # Use very short fit span (60 seconds)
    fitted_elements, diagnostics = oem_to_kepler.fit_mean_elements(
        records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2, fit_span_s=60.0
    )

    # Should have used fewer records
    assert diagnostics["n_records"] < len(records)
    assert diagnostics["span_s"] <= 60.0


def test_fit_mean_elements_converges_with_low_rms() -> None:
    """Should converge to a solution with reasonable RMS error."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    fitted_elements, diagnostics = oem_to_kepler.fit_mean_elements(
        records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )

    # RMS position error should be reasonable (< 100 km for J2 model)
    rms_km = diagnostics["rms_position_m"] / 1000.0
    assert rms_km < 100.0


# ===================================================================
# 6. Residual computation
# ===================================================================


def test_compute_fit_residuals_returns_correct_shape() -> None:
    """Should return residuals with shape (N*3,) for N time samples."""
    mean_elements = np.array([7000e3, 0.001, 0.9, 0.785, 1.571, 0.524])
    time_offsets = np.array([0.0, 100.0, 200.0])
    target_positions = np.random.randn(3, 3) * 1e6

    residuals = oem_to_kepler.compute_fit_residuals(
        mean_elements,
        time_offsets,
        target_positions,
        consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    )

    assert residuals.shape == (9,)  # 3 samples * 3 components


def test_compute_fit_residuals_zero_at_epoch() -> None:
    """Should produce near-zero residuals at epoch (t=0) for self-consistent state."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    fitted_elements, _ = oem_to_kepler.fit_mean_elements(
        records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )

    # Compute residual at epoch only
    time_offsets = np.array([0.0])
    target_positions = np.array([records[0][1][:3]])  # Only position part

    residuals = oem_to_kepler.compute_fit_residuals(
        fitted_elements,
        time_offsets,
        target_positions,
        consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    )

    # Should be small (within a few km)
    residual_magnitude = np.linalg.norm(residuals)
    assert residual_magnitude < 10000.0  # < 10 km


# ===================================================================
# 7. Propagation accuracy computation
# ===================================================================


def test_compute_all_differences_returns_statistics() -> None:
    """Should return dictionary with min/max/avg position and velocity errors."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    fitted_elements, _ = oem_to_kepler.fit_mean_elements(
        records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )

    stats = oem_to_kepler.compute_all_differences(
        fitted_elements, records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2, 7200.0
    )

    assert "n_compared" in stats
    assert "min_pos_km" in stats
    assert "max_pos_km" in stats
    assert "avg_pos_km" in stats
    assert "min_vel_km_s" in stats
    assert "max_vel_km_s" in stats
    assert "avg_vel_km_s" in stats
    assert stats["n_compared"] > 0


def test_compute_all_differences_filters_to_fit_span() -> None:
    """Should only compare states within the fit span."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    fitted_elements, _ = oem_to_kepler.fit_mean_elements(
        records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )

    # Use short fit span
    stats = oem_to_kepler.compute_all_differences(
        fitted_elements, records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2, 60.0
    )

    # Should compare fewer records than total
    assert stats["n_compared"] < len(records)


def test_compute_all_differences_produces_reasonable_errors() -> None:
    """Should produce reasonable position and velocity errors for J2 model."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    fitted_elements, _ = oem_to_kepler.fit_mean_elements(
        records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )

    stats = oem_to_kepler.compute_all_differences(
        fitted_elements, records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2, 7200.0
    )

    # Errors should be non-negative
    assert stats["min_pos_km"] >= 0.0
    assert stats["min_vel_km_s"] >= 0.0
    # Max should be >= min
    assert stats["max_pos_km"] >= stats["min_pos_km"]
    assert stats["max_vel_km_s"] >= stats["min_vel_km_s"]


# ===================================================================
# 8. Output formatting
# ===================================================================


def test_format_fit_output_contains_key_sections() -> None:
    """Should format output with all key sections."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    fitted_elements, diagnostics = oem_to_kepler.fit_mean_elements(
        records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )

    # Convert timestamp to datetime for output formatting
    first_epoch = datetime.fromtimestamp(records[0][0], tz=timezone.utc)
    output = oem_to_kepler.format_fit_output(
        first_epoch, fitted_elements, diagnostics, "km-deg"
    )

    assert "Fitted mean Keplerian elements" in output
    assert "epoch:" in output
    assert "records used:" in output
    assert "arc span:" in output
    assert "iterations:" in output
    assert "RMS position error:" in output
    assert "semi-major axis:" in output
    assert "eccentricity:" in output
    assert "inclination:" in output
    assert "arg of periapsis:" in output
    assert "RAAN:" in output
    assert "mean anomaly:" in output
    assert "mean motion:" in output
    assert "orbital period:" in output


def test_format_fit_output_includes_propagation_accuracy() -> None:
    """Should include propagation accuracy section when difference_summary provided."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem_to_kepler.parse_dataset(content)

    fitted_elements, diagnostics = oem_to_kepler.fit_mean_elements(
        records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )

    diff_summary = oem_to_kepler.compute_all_differences(
        fitted_elements, records, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2, 7200.0
    )

    # Convert timestamp to datetime for output formatting
    first_epoch = datetime.fromtimestamp(records[0][0], tz=timezone.utc)
    output = oem_to_kepler.format_fit_output(
        first_epoch, fitted_elements, diagnostics, "km-deg", diff_summary
    )

    assert "Propagation accuracy" in output
    assert "position |Δr|:" in output
    assert "velocity |Δv|:" in output


def test_format_fit_output_km_deg_units() -> None:
    """Should format output with km and degree units when specified."""
    epoch = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc)
    fitted_elements = np.array(
        [7000000.0, 0.001, np.radians(51.6), 0.785, 1.571, 0.524]
    )
    diagnostics = {
        "rms_position_m": 1000.0,
        "iterations": 10,
        "n_records": 100,
        "span_s": 7200.0,
    }

    output = oem_to_kepler.format_fit_output(
        epoch, fitted_elements, diagnostics, "km-deg"
    )

    assert "km, degrees" in output
    assert "7000.000000 km" in output  # semi-major axis
    assert "51.600000 deg" in output  # inclination


def test_format_fit_output_m_rad_units() -> None:
    """Should format output with meter and radian units when specified."""
    epoch = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc)
    fitted_elements = np.array([7000000.0, 0.001, 0.9, 0.785, 1.571, 0.524])
    diagnostics = {
        "rms_position_m": 1000.0,
        "iterations": 10,
        "n_records": 100,
        "span_s": 7200.0,
    }

    output = oem_to_kepler.format_fit_output(
        epoch, fitted_elements, diagnostics, "m-rad"
    )

    assert "m, radians" in output
    assert "7000000.000000 m" in output  # semi-major axis
    assert "0.9000000000 rad" in output  # inclination


# ===================================================================
# 9. Integration test: full workflow
# ===================================================================


def test_main_workflow_with_file_input(tmp_path: Path) -> None:
    """Should execute full workflow from OEM file to formatted output."""
    output_file = tmp_path / "output.txt"

    with patch(
        "sys.argv",
        [
            "oem_to_kepler.py",
            str(ISS_OEM_PATH),
            "-o",
            str(output_file),
            "--fit-span",
            "0.5",
        ],
    ):
        oem_to_kepler.main()

    # Check output file was created
    assert output_file.exists()
    content = output_file.read_text()

    # Verify key content
    assert "Fitted mean Keplerian elements" in content
    assert "semi-major axis:" in content
    assert "eccentricity:" in content
    assert "Propagation accuracy" in content


def test_main_workflow_with_stdout(capsys) -> None:
    """Should write output to stdout when output is '-'."""
    with patch(
        "sys.argv",
        ["oem_to_kepler.py", str(ISS_OEM_PATH), "-o", "-", "--fit-span", "0.5"],
    ):
        oem_to_kepler.main()

    captured = capsys.readouterr()
    assert "Fitted mean Keplerian elements" in captured.out
    assert "semi-major axis:" in captured.out


def test_main_exits_on_invalid_input() -> None:
    """Should exit with error code when input is invalid."""
    with patch("sys.argv", ["oem_to_kepler.py", "/nonexistent/file.oem"]):
        with pytest.raises(SystemExit) as exc_info:
            oem_to_kepler.main()

    assert exc_info.value.code == 1


def test_main_exits_on_insufficient_records(tmp_path: Path) -> None:
    """Should exit with error when fewer than 2 state vectors provided."""
    # Create OEM file with only 1 state vector
    single_state_oem = tmp_path / "single.oem"
    single_state_oem.write_text(
        "CCSDS_OEM_VERS = 2.0\n"
        "META_START\n"
        "OBJECT_NAME = TEST\n"
        "OBJECT_ID = 2000-001A\n"
        "CENTER_NAME = Earth\n"
        "REF_FRAME = EME2000\n"
        "TIME_SYSTEM = UTC\n"
        "META_STOP\n"
        "2026-05-20T00:00:00.000000 1000.0 2000.0 3000.0 4.0 5.0 6.0\n"
    )

    with patch("sys.argv", ["oem_to_kepler.py", str(single_state_oem)]):
        with pytest.raises(SystemExit) as exc_info:
            oem_to_kepler.main()

    assert exc_info.value.code == 1
