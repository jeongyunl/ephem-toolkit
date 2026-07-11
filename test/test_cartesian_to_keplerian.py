"""Tests for :mod:`bin.cartesian_to_keplerian` — CLI and stream processing.

Tests the :func:`process_stream`, :func:`print_usage`, and :func:`main`
functions for converting between Cartesian and Keplerian orbital elements.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pytest

import bin.cartesian_to_keplerian as script
import common.kepler as kepler
import common.mean_kepler as mean_kepler
import common.consts as consts

TEST_DIR = Path(__file__).parent
TEST_DATA_DIR = TEST_DIR / "data"


# ===================================================================
# Shared fixtures / constants
# ===================================================================

ISS_CARTESIAN_KM: str = (
    "2026-06-21T00:00:00  -2700.816  -3314.093  5266.346  5.168607  -5.597547  -2.131982"
)
"""ISS-like Cartesian state in km and km/s."""

ISS_CARTESIAN_STATE_KM: np.ndarray = np.array(
    [-2700.816, -3314.093, 5266.346, 5.168607, -5.597547, -2.131982]
)
"""ISS-like Cartesian state vector (km and km/s)."""

ISS_CARTESIAN_STATE_M: np.ndarray = ISS_CARTESIAN_STATE_KM * np.array(
    [1e3, 1e3, 1e3, 1e3, 1e3, 1e3]
)
"""ISS-like Cartesian state vector (m and m/s)."""


# ===================================================================
# 1. process_stream: Cartesian to Keplerian conversion
# ===================================================================


def test_process_stream_cartesian_to_keplerian_basic(capsys) -> None:
    """Should convert a single Cartesian state to Keplerian elements."""
    input_stream = io.StringIO(ISS_CARTESIAN_KM + "\n")

    script.process_stream(input_stream, reverse=False, mean=False)

    captured = capsys.readouterr()
    output_lines = captured.out.strip().split("\n")
    assert len(output_lines) == 1

    output_values = output_lines[0].split()
    assert len(output_values) == 7  # epoch + 6 Keplerian elements

    # Parse output
    epoch_str = output_values[0]
    a_km = float(output_values[1])
    e = float(output_values[2])
    i_rad = float(output_values[3])
    omega_rad = float(output_values[4])
    raan_rad = float(output_values[5])
    theta_rad = float(output_values[6])

    # Verify epoch is preserved (format: YYYY-MM-DDTHH:MM:SS.ffffff)
    assert "2026-06-21T00:00:00" in epoch_str

    # Verify Keplerian elements are physically reasonable
    assert a_km > 0.0  # semi-major axis must be positive
    assert 0.0 <= e < 1.0  # eccentricity must be in [0, 1)
    assert 0.0 <= i_rad <= np.pi  # inclination must be in [0, pi]
    assert 0.0 <= omega_rad < 2.0 * np.pi  # argument of periapsis
    assert 0.0 <= raan_rad < 2.0 * np.pi  # RAAN
    assert 0.0 <= theta_rad < 2.0 * np.pi  # true anomaly


def test_process_stream_cartesian_to_keplerian_multiple_lines(capsys) -> None:
    """Should process multiple Cartesian state lines."""
    input_data = (
        "2026-06-21T00:00:00Z  -2700.816  -3314.093  5266.346  5.168607  -5.597547  -2.131982\n"
        "2026-06-21T00:01:00Z  -2700.816  -3314.093  5266.346  5.168607  -5.597547  -2.131982\n"
        "2026-06-21T00:02:00Z  -2700.816  -3314.093  5266.346  5.168607  -5.597547  -2.131982\n"
    )
    input_stream = io.StringIO(input_data)

    script.process_stream(input_stream, reverse=False, mean=False)

    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) == 3


def test_process_stream_cartesian_to_keplerian_skips_blank_lines(capsys) -> None:
    """Should skip blank lines without error."""
    input_data = (
        "2026-06-21T00:00:00Z  -2700.816  -3314.093  5266.346  5.168607  -5.597547  -2.131982\n"
        "\n"
        "2026-06-21T00:01:00Z  -2700.816  -3314.093  5266.346  5.168607  -5.597547  -2.131982\n"
    )
    input_stream = io.StringIO(input_data)

    script.process_stream(input_stream, reverse=False, mean=False)

    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) == 2


def test_process_stream_cartesian_to_keplerian_skips_comment_lines(capsys) -> None:
    """Should skip lines starting with '#' without error."""
    input_data = (
        "# This is a comment\n"
        "2026-06-21T00:00:00Z  -2700.816  -3314.093  5266.346  5.168607  -5.597547  -2.131982\n"
        "# Another comment\n"
    )
    input_stream = io.StringIO(input_data)

    script.process_stream(input_stream, reverse=False, mean=False)

    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) == 1


def test_process_stream_cartesian_to_keplerian_handles_parse_error(capsys) -> None:
    """Should skip lines with parse errors and print a warning."""
    input_data = (
        "2026-06-21T00:00:00Z  -2700.816  -3314.093  5266.346  5.168607  -5.597547  -2.131982\n"
        "invalid line with not enough fields\n"
        "2026-06-21T00:02:00Z  -2700.816  -3314.093  5266.346  5.168607  -5.597547  -2.131982\n"
    )
    input_stream = io.StringIO(input_data)

    script.process_stream(input_stream, reverse=False, mean=False)

    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) == 2  # Only valid lines produce output
    assert "Skipping line" in captured.err  # Error message printed


# ===================================================================
# 2. process_stream: Keplerian to Cartesian conversion (reverse)
# ===================================================================


def test_process_stream_keplerian_to_cartesian_basic(capsys) -> None:
    """Should convert a single Keplerian state to Cartesian elements."""
    # First convert Cartesian to Keplerian to get valid Keplerian elements
    kep = kepler.cartesian_to_keplerian(
        ISS_CARTESIAN_STATE_M, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )
    kep_km = kep.copy()
    kep_km[0] *= 1e-3  # Convert semi-major axis to km

    # Format as input line
    epoch_str = "2026-06-21T00:00:00"
    epoch_str_expected = "2026-06-21T00:00:00.000"  # Expected output without 'Z'
    keplerian_line = f"{epoch_str}  {kep_km[0]}  {kep_km[1]}  {kep_km[2]}  {kep_km[3]}  {kep_km[4]}  {kep_km[5]}"
    input_stream = io.StringIO(keplerian_line + "\n")

    script.process_stream(input_stream, reverse=True, mean=False)

    captured = capsys.readouterr()
    output_lines = captured.out.strip().split("\n")
    assert len(output_lines) == 1

    output_values = output_lines[0].split()
    assert len(output_values) == 7  # epoch + 6 Cartesian elements

    # Parse output
    epoch_str_out = output_values[0]
    x_km = float(output_values[1])
    y_km = float(output_values[2])
    z_km = float(output_values[3])
    vx_km_s = float(output_values[4])
    vy_km_s = float(output_values[5])
    vz_km_s = float(output_values[6])

    # Verify epoch is preserved (without 'Z' suffix)
    assert epoch_str_out == epoch_str_expected

    # Verify Cartesian elements are physically reasonable
    r_km = np.sqrt(x_km**2 + y_km**2 + z_km**2)
    assert 6300.0 < r_km < 7500.0  # LEO altitude range
    v_km_s = np.sqrt(vx_km_s**2 + vy_km_s**2 + vz_km_s**2)
    assert 6.0 < v_km_s < 8.0  # LEO velocity range


def test_process_stream_keplerian_to_cartesian_round_trip(capsys) -> None:
    """Should round-trip Cartesian -> Keplerian -> Cartesian with small error."""
    input_stream = io.StringIO(ISS_CARTESIAN_KM + "\n")

    # First pass: Cartesian to Keplerian
    script.process_stream(input_stream, reverse=False, mean=False)
    captured1 = capsys.readouterr()
    keplerian_output = captured1.out.strip()

    # Second pass: Keplerian to Cartesian
    input_stream2 = io.StringIO(keplerian_output + "\n")
    script.process_stream(input_stream2, reverse=True, mean=False)
    captured2 = capsys.readouterr()
    cartesian_output = captured2.out.strip()

    # Parse final Cartesian output
    output_values = cartesian_output.split()
    x_km_final = float(output_values[1])
    y_km_final = float(output_values[2])
    z_km_final = float(output_values[3])
    vx_km_s_final = float(output_values[4])
    vy_km_s_final = float(output_values[5])
    vz_km_s_final = float(output_values[6])

    # Compare with original
    pos_err_km = np.sqrt(
        (x_km_final - ISS_CARTESIAN_STATE_KM[0]) ** 2
        + (y_km_final - ISS_CARTESIAN_STATE_KM[1]) ** 2
        + (z_km_final - ISS_CARTESIAN_STATE_KM[2]) ** 2
    )
    vel_err_km_s = np.sqrt(
        (vx_km_s_final - ISS_CARTESIAN_STATE_KM[3]) ** 2
        + (vy_km_s_final - ISS_CARTESIAN_STATE_KM[4]) ** 2
        + (vz_km_s_final - ISS_CARTESIAN_STATE_KM[5]) ** 2
    )

    # Allow for numerical precision loss in round-trip
    assert pos_err_km < 1e-6  # sub-micrometer error
    assert vel_err_km_s < 1e-9  # sub-nanometer/s error


# ===================================================================
# 3. process_stream: Mean Keplerian conversion
# ===================================================================


def test_process_stream_cartesian_to_mean_keplerian(capsys) -> None:
    """Should convert Cartesian to mean Keplerian elements with --mean flag."""
    input_stream = io.StringIO(ISS_CARTESIAN_KM + "\n")

    script.process_stream(input_stream, reverse=False, mean=True)

    captured = capsys.readouterr()
    output_lines = captured.out.strip().split("\n")
    assert len(output_lines) == 1

    output_values = output_lines[0].split()
    assert len(output_values) == 7

    # Parse output
    a_km = float(output_values[1])
    e = float(output_values[2])
    i_rad = float(output_values[3])
    omega_rad = float(output_values[4])
    raan_rad = float(output_values[5])
    m_rad = float(output_values[6])  # Mean anomaly instead of true anomaly

    # Verify elements are physically reasonable
    assert a_km > 0.0
    assert 0.0 <= e < 1.0
    assert 0.0 <= i_rad <= np.pi
    assert 0.0 <= omega_rad < 2.0 * np.pi
    assert 0.0 <= raan_rad < 2.0 * np.pi
    assert 0.0 <= m_rad < 2.0 * np.pi


def test_process_stream_mean_flag_ignored_with_reverse(capsys) -> None:
    """Should ignore --mean flag when reverse=True (enforced by main)."""
    # This test verifies that process_stream doesn't crash if mean=True and reverse=True
    # (though main() should prevent this combination)
    kep = kepler.cartesian_to_keplerian(
        ISS_CARTESIAN_STATE_M, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )
    kep_km = kep.copy()
    kep_km[0] *= 1e-3

    epoch_str = "2026-06-21T00:00:00"
    keplerian_line = f"{epoch_str}  {kep_km[0]}  {kep_km[1]}  {kep_km[2]}  {kep_km[3]}  {kep_km[4]}  {kep_km[5]}"
    input_stream = io.StringIO(keplerian_line + "\n")

    # process_stream should handle this without crashing
    script.process_stream(input_stream, reverse=True, mean=True)

    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) == 1


# ===================================================================
# 4. print_usage: Help message
# ===================================================================


def test_print_usage_outputs_to_stdout(capsys) -> None:
    """Should print usage message to stdout."""
    script.print_usage()

    captured = capsys.readouterr()
    assert "Usage:" in captured.out
    assert "cartesian_to_keplerian.py" in captured.out


def test_print_usage_contains_required_sections(capsys) -> None:
    """Should include all required sections in usage message."""
    script.print_usage()

    captured = capsys.readouterr()
    usage_text = captured.out

    assert "Positional arguments:" in usage_text
    assert "Options:" in usage_text
    assert "Input format:" in usage_text
    assert "Output format:" in usage_text
    assert "-h, --help" in usage_text
    assert "-r" in usage_text
    assert "--mean" in usage_text


def test_print_usage_describes_input_format(capsys) -> None:
    """Should describe the input format (OEM-style)."""
    script.print_usage()

    captured = capsys.readouterr()
    assert "ISO-8601 epoch" in captured.out
    assert "km" in captured.out
    assert "km/s" in captured.out


def test_print_usage_describes_output_format(capsys) -> None:
    """Should describe the output format (Keplerian elements)."""
    script.print_usage()

    captured = capsys.readouterr()
    assert "semi-major axis" in captured.out
    assert "eccentricity" in captured.out
    assert "inclination" in captured.out
    assert "argument of periapsis" in captured.out
    assert "longitude of ascending node" in captured.out


# ===================================================================
# 5. main: CLI argument parsing
# ===================================================================


def test_main_help_flag_prints_usage_and_exits(capsys) -> None:
    """Should print usage and exit with code 0 when -h is provided."""
    exit_code = script.main(["-h"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Usage:" in captured.out


def test_main_help_flag_long_form(capsys) -> None:
    """Should print usage and exit with code 0 when --help is provided."""
    exit_code = script.main(["--help"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Usage:" in captured.out


def test_main_no_arguments_reads_from_stdin(capsys, monkeypatch) -> None:
    """Should read from stdin when no input file is provided."""
    stdin_data = ISS_CARTESIAN_KM + "\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_data))

    exit_code = script.main([])

    assert exit_code == 0
    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) == 1


def test_main_with_input_file(capsys, tmp_path) -> None:
    """Should read from input file when provided."""
    input_file = tmp_path / "input.oem"
    input_file.write_text(ISS_CARTESIAN_KM + "\n")

    exit_code = script.main([str(input_file)])

    assert exit_code == 0
    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) == 1


def test_main_reverse_flag(capsys, tmp_path) -> None:
    """Should convert Keplerian to Cartesian with -r flag."""
    # Create Keplerian input
    kep = kepler.cartesian_to_keplerian(
        ISS_CARTESIAN_STATE_M, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )
    kep_km = kep.copy()
    kep_km[0] *= 1e-3

    epoch_str = "2026-06-21T00:00:00"
    keplerian_line = f"{epoch_str}  {kep_km[0]}  {kep_km[1]}  {kep_km[2]}  {kep_km[3]}  {kep_km[4]}  {kep_km[5]}"

    input_file = tmp_path / "input.oem"
    input_file.write_text(keplerian_line + "\n")

    exit_code = script.main(["-r", str(input_file)])

    assert exit_code == 0
    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) == 1


def test_main_mean_flag(capsys, tmp_path) -> None:
    """Should convert to mean Keplerian elements with --mean flag."""
    input_file = tmp_path / "input.oem"
    input_file.write_text(ISS_CARTESIAN_KM + "\n")

    exit_code = script.main(["--mean", str(input_file)])

    assert exit_code == 0
    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) == 1


def test_main_rejects_mean_with_reverse(capsys) -> None:
    """Should reject using --mean together with -r/--reverse."""
    exit_code = script.main(["-r", "--mean"])

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "cannot be used" in captured.err.lower()


def test_main_multiple_flags(capsys, tmp_path) -> None:
    """Should handle multiple flags in any order."""
    input_file = tmp_path / "input.oem"
    input_file.write_text(ISS_CARTESIAN_KM + "\n")

    # Test --mean with input file
    exit_code = script.main(["--mean", str(input_file)])
    assert exit_code == 0

    # Test input file with --mean
    exit_code = script.main([str(input_file), "--mean"])
    assert exit_code == 0


def test_main_default_argv_uses_sys_argv(capsys, monkeypatch, tmp_path) -> None:
    """Should use sys.argv[1:] when argv is None."""
    input_file = tmp_path / "input.oem"
    input_file.write_text(ISS_CARTESIAN_KM + "\n")

    # Mock sys.argv
    monkeypatch.setattr("sys.argv", ["cartesian_to_keplerian.py", str(input_file)])

    exit_code = script.main(None)

    assert exit_code == 0
    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) == 1


# ===================================================================
# 6. Integration tests
# ===================================================================


def test_integration_cartesian_to_keplerian_to_cartesian(capsys, tmp_path) -> None:
    """Full integration: Cartesian -> Keplerian -> Cartesian round-trip."""
    input_file = tmp_path / "input.oem"
    input_file.write_text(ISS_CARTESIAN_KM + "\n")

    # First pass: Cartesian to Keplerian
    exit_code1 = script.main([str(input_file)])
    assert exit_code1 == 0
    captured1 = capsys.readouterr()
    keplerian_output = captured1.out.strip()

    # Second pass: Keplerian to Cartesian
    keplerian_file = tmp_path / "keplerian.oem"
    keplerian_file.write_text(keplerian_output + "\n")
    exit_code2 = script.main(["-r", str(keplerian_file)])
    assert exit_code2 == 0
    captured2 = capsys.readouterr()
    cartesian_output = captured2.out.strip()

    # Verify round-trip accuracy
    output_values = cartesian_output.split()
    x_km_final = float(output_values[1])
    y_km_final = float(output_values[2])
    z_km_final = float(output_values[3])
    vx_km_s_final = float(output_values[4])
    vy_km_s_final = float(output_values[5])
    vz_km_s_final = float(output_values[6])

    pos_err_km = np.sqrt(
        (x_km_final - ISS_CARTESIAN_STATE_KM[0]) ** 2
        + (y_km_final - ISS_CARTESIAN_STATE_KM[1]) ** 2
        + (z_km_final - ISS_CARTESIAN_STATE_KM[2]) ** 2
    )
    vel_err_km_s = np.sqrt(
        (vx_km_s_final - ISS_CARTESIAN_STATE_KM[3]) ** 2
        + (vy_km_s_final - ISS_CARTESIAN_STATE_KM[4]) ** 2
        + (vz_km_s_final - ISS_CARTESIAN_STATE_KM[5]) ** 2
    )

    assert pos_err_km < 1e-6
    assert vel_err_km_s < 1e-9


def test_integration_with_real_oem_file(capsys) -> None:
    """Should process a real OEM file if available."""
    oem_file = TEST_DATA_DIR / "ISS_2026-05-20.OEM"
    if not oem_file.exists():
        pytest.skip(f"Test OEM file not found: {oem_file}")

    exit_code = script.main([str(oem_file)])

    assert exit_code == 0
    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) > 0


def test_integration_cartesian_to_mean_keplerian_to_cartesian(capsys, tmp_path) -> None:
    """Full integration: Cartesian -> mean Keplerian -> Cartesian."""
    input_file = tmp_path / "input.oem"
    input_file.write_text(ISS_CARTESIAN_KM + "\n")

    # First pass: Cartesian to mean Keplerian
    exit_code1 = script.main(["--mean", str(input_file)])
    assert exit_code1 == 0
    captured1 = capsys.readouterr()
    mean_keplerian_output = captured1.out.strip()

    # Second pass: mean Keplerian to Cartesian
    mean_keplerian_file = tmp_path / "mean_keplerian.oem"
    mean_keplerian_file.write_text(mean_keplerian_output + "\n")
    exit_code2 = script.main(["-r", str(mean_keplerian_file)])
    assert exit_code2 == 0
    captured2 = capsys.readouterr()
    cartesian_output = captured2.out.strip()

    # Verify output is valid Cartesian
    output_values = cartesian_output.split()
    assert len(output_values) == 7
    r_km = np.sqrt(
        float(output_values[1]) ** 2
        + float(output_values[2]) ** 2
        + float(output_values[3]) ** 2
    )
    assert 6300.0 < r_km < 7500.0  # LEO altitude range


# ===================================================================
# 7. Edge cases and error handling
# ===================================================================


def test_process_stream_with_comma_separated_values(capsys) -> None:
    """Should handle comma-separated input values."""
    input_data = "2026-06-21T00:00:00Z,-2700.816,-3314.093,5266.346,5.168607,-5.597547,-2.131982\n"
    input_stream = io.StringIO(input_data)

    script.process_stream(input_stream, reverse=False, mean=False)

    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) == 1


def test_process_stream_with_mixed_separators(capsys) -> None:
    """Should handle mixed whitespace and comma separators."""
    input_data = "2026-06-21T00:00:00Z  -2700.816,-3314.093  5266.346,5.168607  -5.597547,-2.131982\n"
    input_stream = io.StringIO(input_data)

    script.process_stream(input_stream, reverse=False, mean=False)

    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) == 1


def test_main_with_nonexistent_file(capsys) -> None:
    """Should handle nonexistent input file gracefully."""
    with pytest.raises(FileNotFoundError):
        script.main(["/nonexistent/path/to/file.oem"])


def test_process_stream_preserves_epoch_precision(capsys) -> None:
    """Should preserve epoch timestamp precision in output."""
    input_data = "2026-06-21T12:34:56.789Z  -2700.816  -3314.093  5266.346  5.168607  -5.597547  -2.131982\n"
    input_stream = io.StringIO(input_data)

    script.process_stream(input_stream, reverse=False, mean=False)

    captured = capsys.readouterr()
    output_lines = captured.out.strip().split("\n")
    output_epoch = output_lines[0].split()[0]

    assert "2026-06-21T12:34:56" in output_epoch


def test_process_stream_handles_scientific_notation(capsys) -> None:
    """Should handle scientific notation in input values."""
    input_data = "2026-06-21T00:00:00Z  -2.700816e3  -3.314093e3  5.266346e3  5.168607e0  -5.597547e0  -2.131982e0\n"
    input_stream = io.StringIO(input_data)

    script.process_stream(input_stream, reverse=False, mean=False)

    captured = capsys.readouterr()
    output_lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(output_lines) == 1


# ===================================================================
# 8. Output format validation
# ===================================================================


def test_output_format_has_correct_number_of_fields(capsys) -> None:
    """Output should have exactly 7 fields (epoch + 6 elements)."""
    input_stream = io.StringIO(ISS_CARTESIAN_KM + "\n")

    script.process_stream(input_stream, reverse=False, mean=False)

    captured = capsys.readouterr()
    output_values = captured.out.strip().split()
    assert len(output_values) == 7


def test_output_format_epoch_is_iso8601(capsys) -> None:
    """Output epoch should be in ISO 8601 format."""
    input_stream = io.StringIO(ISS_CARTESIAN_KM + "\n")

    script.process_stream(input_stream, reverse=False, mean=False)

    captured = capsys.readouterr()
    output_epoch = captured.out.strip().split()[0]

    # ISO 8601 format: YYYY-MM-DDTHH:MM:SS[.ffffff]
    assert "T" in output_epoch
    assert "-" in output_epoch
    assert ":" in output_epoch


def test_output_format_elements_are_numeric(capsys) -> None:
    """Output elements should be numeric (float) values."""
    input_stream = io.StringIO(ISS_CARTESIAN_KM + "\n")

    script.process_stream(input_stream, reverse=False, mean=False)

    captured = capsys.readouterr()
    output_values = captured.out.strip().split()

    # Skip epoch (index 0), check remaining 6 values are numeric
    for i in range(1, 7):
        try:
            float(output_values[i])
        except ValueError:
            pytest.fail(f"Output value {i} is not numeric: {output_values[i]}")


def test_output_format_uses_double_space_separator(capsys) -> None:
    """Output should use double-space separator between fields."""
    input_stream = io.StringIO(ISS_CARTESIAN_KM + "\n")

    script.process_stream(input_stream, reverse=False, mean=False)

    captured = capsys.readouterr()
    output_line = captured.out.strip()

    # Check for double-space separator
    assert "  " in output_line
