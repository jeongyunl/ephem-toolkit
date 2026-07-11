"""Tests for :mod:`oem_to_tle` — OEM to TLE conversion and estimation.

Validates the OEM-to-TLE conversion workflow including:
- Command-line argument parsing
- Input reading from files and stdin
- OEM dataset parsing
- TLE element estimation via least-squares regression
- B* drag term estimation
- State-match and Keplerian-match refinement
- TLE output formatting
- Accuracy verification
"""

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

import oem_to_tle.oem_to_tle as oem_to_tle
import oem_to_tle.io_utils as io_utils
import oem_to_tle.estimation as estimation
import oem_to_tle.models as models
import oem_to_tle.orbital_mechanics as orbital_mechanics
import oem_to_tle.tle_builder as tle_builder
import oem_to_tle.constants as constants
import common.tle as tle
import common.consts as consts

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test files."""

TEST_DATA_DIR: Path = TEST_DIR / "data"
"""Directory containing test data files (OEM, TLE, OMM samples)."""

ISS_OEM_PATH: Path = TEST_DATA_DIR / "ISS_2026-05-20.OEM"
"""Path to ISS OEM test file for 2026-05-20."""

JPSS1_OEM_PATH: Path = TEST_DATA_DIR / "JPSS-1.oem"
"""Path to JPSS-1 OEM test file."""


# ===================================================================
# 1. Command-line argument parsing
# ===================================================================


def test_parse_arguments_with_defaults() -> None:
    """Should parse arguments with default values when no args provided."""
    with patch("sys.argv", ["oem_to_tle.py"]):
        args = io_utils.parse_arguments()

    assert args.input == "-"
    assert args.output == "-"
    assert args.satellite_number == 99999
    assert args.classification == "U"
    assert args.int_designator_year == 0
    assert args.int_designator_launch_number == 0
    assert args.int_designator_piece == "A"
    assert args.ephemeris_type == 0
    assert args.element_set_number == 1
    assert args.bstar == "00000+0"
    assert args.mean_motion_second_derivative == "00000+0"
    assert args.revolution_number_at_epoch == 0
    assert args.refinement == "cartesian"


def test_parse_arguments_with_input_file() -> None:
    """Should parse input file path correctly."""
    with patch("sys.argv", ["oem_to_tle.py", "test.oem"]):
        args = io_utils.parse_arguments()

    assert args.input == "test.oem"


def test_parse_arguments_with_output_file() -> None:
    """Should parse output file path with -o flag."""
    with patch("sys.argv", ["oem_to_tle.py", "-o", "output.tle"]):
        args = io_utils.parse_arguments()

    assert args.output == "output.tle"


def test_parse_arguments_with_satellite_metadata() -> None:
    """Should parse satellite metadata fields."""
    with patch(
        "sys.argv",
        [
            "oem_to_tle.py",
            "--name",
            "TEST SAT",
            "--satellite-number",
            "12345",
            "--classification",
            "C",
            "--int-designator-year",
            "23",
            "--int-designator-launch-number",
            "100",
            "--int-designator-piece",
            "B",
        ],
    ):
        args = io_utils.parse_arguments()

    assert args.name == "TEST SAT"
    assert args.satellite_number == 12345
    assert args.classification == "C"
    assert args.int_designator_year == 23
    assert args.int_designator_launch_number == 100
    assert args.int_designator_piece == "B"


def test_parse_arguments_with_tle_parameters() -> None:
    """Should parse TLE-specific parameters."""
    with patch(
        "sys.argv",
        [
            "oem_to_tle.py",
            "--bstar",
            "12345-3",
            "--mean-motion-second-derivative",
            "00000+0",
            "--ephemeris-type",
            "4",
            "--element-set-number",
            "999",
            "--revolution-number-at-epoch",
            "12345",
        ],
    ):
        args = io_utils.parse_arguments()

    assert args.bstar == "12345-3"
    assert args.mean_motion_second_derivative == "00000+0"
    assert args.ephemeris_type == 4
    assert args.element_set_number == 999
    assert args.revolution_number_at_epoch == 12345


def test_parse_arguments_with_refinement_methods() -> None:
    """Should parse different refinement method options."""
    for method in ["none", "cartesian", "keplerian"]:
        with patch("sys.argv", ["oem_to_tle.py", "--refinement", method]):
            args = io_utils.parse_arguments()
            assert args.refinement == method


# ===================================================================
# 2. Input reading from file and stdin
# ===================================================================


def test_read_input_text_from_file() -> None:
    """Should read input text from an existing OEM file."""
    content = io_utils.read_input_text(str(ISS_OEM_PATH))

    assert isinstance(content, str)
    assert len(content) > 0
    assert "CCSDS_OEM_VERS" in content or "2026-05-20" in content


def test_read_input_text_from_stdin() -> None:
    """Should read input text from stdin when source is '-'."""
    test_content = "Test OEM content\n2026-05-20T00:00:00 1000 2000 3000 4 5 6"

    with patch("sys.stdin", io.StringIO(test_content)):
        content = io_utils.read_input_text("-")

    assert content == test_content


def test_read_input_text_raises_on_empty_stdin() -> None:
    """Should raise ValueError when stdin is empty."""
    with patch("sys.stdin", io.StringIO("")):
        with pytest.raises(ValueError, match="No input from stdin"):
            io_utils.read_input_text("-")


def test_read_input_text_raises_on_nonexistent_file() -> None:
    """Should raise ValueError when file does not exist."""
    with pytest.raises(ValueError, match="Could not read input file"):
        io_utils.read_input_text("/nonexistent/file.oem")


def test_read_input_text_raises_on_empty_file(tmp_path: Path) -> None:
    """Should raise ValueError when file is empty."""
    empty_file = tmp_path / "empty.oem"
    empty_file.write_text("")

    with pytest.raises(ValueError, match="empty"):
        io_utils.read_input_text(str(empty_file))


# ===================================================================
# 3. OEM dataset parsing
# ===================================================================


def test_parse_dataset_from_oem_file() -> None:
    """Should parse OEM file into list of (timestamp, state_vector) tuples."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = io_utils.parse_dataset(content)

    assert isinstance(records, list)
    assert len(records) >= 2

    # Check first record structure: timestamp is a float, state_vector is (6,)
    ts, state_vector_m = records[0]
    assert isinstance(ts, float)
    assert isinstance(state_vector_m, np.ndarray)
    assert state_vector_m.shape == (6,)


def test_parse_dataset_from_oem_returns_6_element_state_vectors() -> None:
    """Should parse OEM file into list of (timestamp, state_vector) tuples with 6-element state vectors."""
    import io as io_module

    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = io_utils.parse_dataset_from_oem(io_module.StringIO(content))

    assert records is not None
    assert isinstance(records, list)
    assert len(records) >= 2

    # Check first record structure: timestamp is a float, state_vector is (6,)
    ts, state_vector_m = records[0]
    assert isinstance(ts, float)
    assert isinstance(state_vector_m, np.ndarray)
    assert state_vector_m.shape == (6,)

    # Verify position and velocity components are accessible by slice
    position_m = state_vector_m[:3]
    velocity_m_s = state_vector_m[3:6]

    # ISS orbit should have position magnitude around 6700-7000 km (6.7e6 - 7e6 m)
    pos_magnitude = np.linalg.norm(position_m)
    assert 6.0e6 < pos_magnitude < 8.0e6  # meters

    # Velocity should be reasonable for LEO orbit (~7-8 km/s)
    vel_magnitude = np.linalg.norm(velocity_m_s)
    assert 6000.0 < vel_magnitude < 9000.0  # m/s


def test_parse_dataset_converts_km_to_m() -> None:
    """Should convert OEM data from km to meters."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = io_utils.parse_dataset(content)

    # ISS orbit should have position magnitude around 6700-7000 km (6.7e6 - 7e6 m)
    epoch, state_vector_m = records[0]
    position_m = state_vector_m[:3]
    pos_magnitude = np.linalg.norm(position_m)
    assert 6.0e6 < pos_magnitude < 8.0e6  # meters


def test_parse_dataset_raises_on_insufficient_records() -> None:
    """Should raise ValueError when fewer than 2 state vectors found."""
    invalid_content = "# Comment line\n# Another comment\n"

    with pytest.raises(ValueError, match="at least 2"):
        io_utils.parse_dataset(invalid_content)


def test_parse_dataset_handles_line_by_line_format() -> None:
    """Should parse simple line-by-line state vector format."""
    content = (
        "2026-05-20T00:00:00.000000 1000.0 2000.0 3000.0 4.0 5.0 6.0\n"
        "2026-05-20T00:01:00.000000 1100.0 2100.0 3100.0 4.1 5.1 6.1\n"
    )

    records = io_utils.parse_dataset(content)

    assert len(records) == 2
    epoch1, state_vector_m1 = records[0]
    # Values should be converted from km to m
    assert state_vector_m1[0] == pytest.approx(1000.0 * 1000.0)  # x position
    assert state_vector_m1[3] == pytest.approx(4.0 * 1000.0)  # x velocity


# ===================================================================
# 4. Orbital mechanics utilities
# ===================================================================


def test_state_to_orbital_elements_returns_valid_elements() -> None:
    """Should convert Cartesian state to orbital elements."""
    # Simple circular orbit at 7000 km altitude
    state_vector_m = np.array(
        [7000000.0, 0.0, 0.0, 0.0, 7546.0, 0.0]
    )  # [x, y, z, vx, vy, vz]

    elements = orbital_mechanics.state_to_orbital_elements(state_vector_m)

    assert isinstance(elements, models.OrbitalElements)
    assert elements.semi_major_axis_m > 0
    assert 0 <= elements.eccentricity < 1
    assert 0 <= elements.inclination_deg <= 180
    assert 0 <= elements.raan_deg < 360
    assert 0 <= elements.arg_perigee_deg < 360
    assert 0 <= elements.mean_anomaly_deg < 360
    assert elements.mean_motion_rev_per_day > 0


def test_datetime_to_tle_epoch_conversion() -> None:
    """Should convert datetime to TLE epoch format (year, day)."""
    dt = datetime(2026, 5, 20, 12, 30, 45, tzinfo=timezone.utc)
    year, day = orbital_mechanics.datetime_to_tle_epoch(dt)

    assert year == 26  # Two-digit year
    assert 140.0 < day < 141.0  # Day 140 of 2026 + fractional day


def test_linear_regression_slope_and_intercept() -> None:
    """Should compute linear regression slope and intercept correctly."""
    x = [0.0, 1.0, 2.0, 3.0, 4.0]
    y = [1.0, 3.0, 5.0, 7.0, 9.0]  # y = 2x + 1

    slope = orbital_mechanics.linear_regression_slope(x, y)
    intercept = orbital_mechanics.linear_regression_intercept(x, y)

    assert slope == pytest.approx(2.0, abs=1e-10)
    assert intercept == pytest.approx(1.0, abs=1e-10)


# ===================================================================
# 5. TLE element estimation
# ===================================================================


def test_estimate_tle_fields_returns_estimated_dataclass() -> None:
    """Should return Estimated dataclass with all required fields."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = io_utils.parse_dataset(content)

    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    assert isinstance(estimated, models.Estimated)
    assert isinstance(estimated.epoch_datetime, datetime)
    assert isinstance(estimated.epoch_year, int)
    assert isinstance(estimated.epoch_day, float)
    assert 0 <= estimated.inclination_deg <= 180
    assert 0 <= estimated.raan_deg < 360
    assert 0 <= estimated.eccentricity < 1
    assert 0 <= estimated.arg_perigee_deg < 360
    assert 0 <= estimated.mean_anomaly_deg < 360
    assert estimated.mean_motion_rev_per_day > 0


def test_estimate_tle_fields_produces_reasonable_iss_orbit() -> None:
    """Should produce physically reasonable orbital elements for ISS."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = io_utils.parse_dataset(content)

    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    # ISS orbit characteristics
    a_km = estimated.semi_major_axis_m / 1000.0
    assert 6500.0 < a_km < 7200.0  # Semi-major axis
    assert estimated.eccentricity < 0.01  # Nearly circular
    assert 50.0 < estimated.inclination_deg < 52.0  # ISS inclination ~51.6°
    assert 14.0 < estimated.mean_motion_rev_per_day < 16.0  # ~15 orbits/day


def test_estimate_tle_fields_with_state_match_uses_osculating_values() -> None:
    """Should use osculating values as initial guess when use_state_match=True."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = io_utils.parse_dataset(content)

    estimated = estimation.estimate_tle_fields(records, use_state_match=True)

    # With state_match, should use osculating values at epoch
    # These should be close to the osculating_at_epoch fields
    assert abs(estimated.raan_deg - estimated.raan_deg_osculating_at_epoch) < 1.0
    assert (
        abs(estimated.mean_anomaly_deg - estimated.mean_anomaly_deg_osculating_at_epoch)
        < 5.0
    )


def test_estimate_tle_fields_computes_mean_motion_derivative() -> None:
    """Should compute mean motion first derivative from dataset slope."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = io_utils.parse_dataset(content)

    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    # Mean motion derivative should be computed and clamped if necessary
    assert estimated.mean_motion_first_derivative is not None
    assert (
        abs(estimated.mean_motion_first_derivative)
        <= constants.MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE
    )


# ===================================================================
# 6. B* drag term estimation
# ===================================================================


def test_select_bstar_fit_samples_returns_subset() -> None:
    """Should select evenly spaced samples for B* fitting."""
    # Create dummy records with float timestamps and 6-element state vectors
    base_ts = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    records = [(base_ts + i * 60.0, np.zeros(6)) for i in range(20)]

    samples = estimation.select_bstar_fit_samples(records)

    assert len(samples) > 0
    assert len(samples) <= constants.BSTAR_SAMPLE_COUNT
    # First record should not be included (epoch is excluded)
    assert samples[0][0] != records[0][0]


def test_select_bstar_fit_samples_handles_small_dataset() -> None:
    """Should handle datasets smaller than BSTAR_SAMPLE_COUNT."""
    base_ts = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    records = [(base_ts + i * 60.0, np.zeros(6)) for i in range(5)]

    samples = estimation.select_bstar_fit_samples(records)

    # Should return all records except the first (epoch)
    assert len(samples) == 4


def test_select_bstar_fit_samples_returns_empty_for_single_record() -> None:
    """Should return empty list for single record."""
    base_ts = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    records = [(base_ts, np.zeros(6))]

    samples = estimation.select_bstar_fit_samples(records)

    assert len(samples) == 0


def test_estimate_bstar_preserves_user_provided_value() -> None:
    """Should preserve user-provided B* value without estimation."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = io_utils.parse_dataset(content)
    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    # Create args with custom bstar
    args = MagicMock()
    args.bstar = "12345-3"

    result = estimation.estimate_bstar_from_arc(args, estimated, records)

    assert result.bstar == "12345-3"
    assert result.bstar_source == "input"


# ===================================================================
# 7. TLE builder
# ===================================================================


def test_build_tle_data_creates_valid_tle() -> None:
    """Should build valid TLE data structure from estimated elements."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = io_utils.parse_dataset(content)
    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    args = MagicMock()
    args.name = "TEST SAT"
    args.satellite_number = 12345
    args.classification = "U"
    args.int_designator_year = 26
    args.int_designator_launch_number = 100
    args.int_designator_piece = "A"
    args.ephemeris_type = 0
    args.element_set_number = 1
    args.bstar = "00000+0"
    args.mean_motion_second_derivative = "00000+0"
    args.revolution_number_at_epoch = 0

    tle_data = tle_builder.build_tle_data(args, estimated)

    assert isinstance(tle_data, tle.Tle)
    assert tle_data.name == "TEST SAT"
    assert tle_data.satellite_number == 12345
    assert tle_data.classification == "U"
    assert 0 <= tle_data.inclination_deg <= 180
    assert 0 <= tle_data.raan_deg < 360
    assert 0 <= tle_data.eccentricity < 1
    assert 0 <= tle_data.arg_perigee_deg < 360
    assert 0 <= tle_data.mean_anomaly_deg < 360
    assert tle_data.mean_motion_rev_per_day > 0


def test_format_tle_exponential_from_float() -> None:
    """Should format float as TLE exponential notation."""
    # Test positive value (0.00012345 = 1.2345e-4, TLE format uses exponent+1)
    result = tle_builder.format_tle_exponential_from_float(0.00012345)
    assert result == "12345-3"

    # Test negative value
    result = tle_builder.format_tle_exponential_from_float(-0.00012345)
    assert result == "-12345-3"

    # Test zero
    result = tle_builder.format_tle_exponential_from_float(0.0)
    assert result == "00000+0"

    # Test larger value
    result = tle_builder.format_tle_exponential_from_float(0.12345)
    assert result == "12345+0"


# ===================================================================
# 8. Accuracy verification
# ===================================================================


def test_verify_accuracy_keplerian_returns_accuracy_dataclass() -> None:
    """Should return KeplerianAccuracy dataclass with element-wise errors."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = io_utils.parse_dataset(content)
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
# 9. Models and data structures
# ===================================================================


def test_orbital_elements_dataclass() -> None:
    """Should create OrbitalElements dataclass with valid fields."""
    elements = models.OrbitalElements(
        semi_major_axis_m=7000000.0,
        eccentricity=0.001,
        inclination_deg=51.6,
        raan_deg=45.0,
        arg_perigee_deg=90.0,
        mean_anomaly_deg=30.0,
        mean_motion_rev_per_day=15.5,
    )

    assert elements.semi_major_axis_m == 7000000.0
    assert elements.eccentricity == 0.001
    assert elements.inclination_deg == 51.6


def test_estimated_dataclass() -> None:
    """Should create Estimated dataclass with all required fields."""
    estimated = models.Estimated(
        epoch_datetime=datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc),
        epoch_year=26,
        epoch_day=140.0,
        inclination_deg=51.6,
        raan_deg=45.0,
        eccentricity=0.001,
        arg_perigee_deg=90.0,
        mean_anomaly_deg=30.0,
        mean_motion_rev_per_day=15.5,
        inclination_deg_osculating_at_epoch=51.6,
        raan_deg_osculating_at_epoch=45.0,
        arg_perigee_deg_osculating_at_epoch=90.0,
        mean_anomaly_deg_osculating_at_epoch=30.0,
        mean_motion_rev_per_day_osculating_at_epoch=15.5,
        mean_motion_rev_per_day_regression_at_epoch=15.5,
        mean_argument_latitude_rate_rev_per_day=15.5,
        phase_match_count=0,
        phase_match_weight=0.0,
        mean_motion_first_derivative=0.0,
        mean_motion_first_derivative_raw=0.0,
        semi_major_axis_m=7000000.0,
        dataset_slope_rev_per_day2=0.0,
    )

    assert estimated.epoch_year == 26
    assert estimated.inclination_deg == 51.6


def test_tle_parameters_from_estimated() -> None:
    """Should create TleParameters from Estimated dataclass."""
    estimated = models.Estimated(
        epoch_datetime=datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc),
        epoch_year=26,
        epoch_day=140.0,
        inclination_deg=51.6,
        raan_deg=45.0,
        eccentricity=0.001,
        arg_perigee_deg=90.0,
        mean_anomaly_deg=30.0,
        mean_motion_rev_per_day=15.5,
        inclination_deg_osculating_at_epoch=51.6,
        raan_deg_osculating_at_epoch=45.0,
        arg_perigee_deg_osculating_at_epoch=90.0,
        mean_anomaly_deg_osculating_at_epoch=30.0,
        mean_motion_rev_per_day_osculating_at_epoch=15.5,
        mean_motion_rev_per_day_regression_at_epoch=15.5,
        mean_argument_latitude_rate_rev_per_day=15.5,
        phase_match_count=0,
        phase_match_weight=0.0,
        mean_motion_first_derivative=0.0,
        mean_motion_first_derivative_raw=0.0,
        semi_major_axis_m=7000000.0,
        dataset_slope_rev_per_day2=0.0,
    )

    params = models.TleParameters.from_estimated(estimated)

    assert params.inclination_deg == 51.6
    assert params.raan_deg == 45.0
    assert params.eccentricity == 0.001


def test_tle_deltas_from_array() -> None:
    """Should create TleDeltas from numpy array."""
    arr = np.array([0.1, 0.2, 0.0001, 0.3, 0.4, 0.01])
    deltas = models.TleDeltas.from_array(arr)

    assert deltas.inclination_deg == pytest.approx(0.1)
    assert deltas.raan_deg == pytest.approx(0.2)
    assert deltas.eccentricity == pytest.approx(0.0001)
    assert deltas.arg_perigee_deg == pytest.approx(0.3)
    assert deltas.mean_anomaly_deg == pytest.approx(0.4)
    assert deltas.mean_motion_rev_per_day == pytest.approx(0.01)


def test_tle_parameters_apply_deltas() -> None:
    """Should apply deltas to TLE parameters."""
    params = models.TleParameters(
        inclination_deg=51.6,
        raan_deg=45.0,
        eccentricity=0.001,
        arg_perigee_deg=90.0,
        mean_anomaly_deg=30.0,
        mean_motion_rev_per_day=15.5,
    )

    deltas = models.TleDeltas(
        inclination_deg=0.1,
        raan_deg=0.2,
        eccentricity=0.0001,
        arg_perigee_deg=0.3,
        mean_anomaly_deg=0.4,
        mean_motion_rev_per_day=0.01,
    )

    new_params = params.apply_deltas(deltas)

    assert new_params.inclination_deg == pytest.approx(51.7)
    assert new_params.raan_deg == pytest.approx(45.2)
    assert new_params.eccentricity == pytest.approx(0.0011)


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
    records = io_utils.parse_dataset(content)
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
    records = io_utils.parse_dataset(content)
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
