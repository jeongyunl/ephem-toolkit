"""Tests for oem_to_omm/estimation.py — TLE parameter estimation from OEM data."""

from __future__ import annotations

import io
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pytest
from unittest.mock import MagicMock

import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.oem_to_omm.fit_tle.estimation as estimation
import ephem_toolkit.oem_to_omm.fit_tle.models as models
import ephem_toolkit.oem_to_omm.fit_tle.constants as constants
import ephem_toolkit.oem_to_omm.fit_tle.refinement as refinement

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test files."""

TEST_DATA_DIR: Path = TEST_DIR.parents[2] / "data"
"""Directory containing test data files."""

ISS_OEM_PATH: Path = TEST_DATA_DIR / "ISS_2026-05-20_small.OEM"
"""Path to ISS OEM test data file."""

# ===================================================================
# 5. TLE element estimation
# ===================================================================


def test_estimate_tle_fields_returns_estimated_dataclass() -> None:
    """Should return Estimated dataclass with all required fields."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states

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
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states

    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    # ISS orbit characteristics: convert semi-major axis from m to km for validation
    semi_major_axis_km = estimated.semi_major_axis_m / 1000.0
    assert 6500.0 < semi_major_axis_km < 7200.0  # Semi-major axis range for ISS
    assert estimated.eccentricity < 0.01  # Nearly circular
    assert 50.0 < estimated.inclination_deg < 52.0  # ISS inclination ~51.6°
    assert 14.0 < estimated.mean_motion_rev_per_day < 16.0  # ~15 orbits/day


def test_estimate_tle_fields_with_state_match_uses_osculating_values() -> None:
    """Should use osculating values as initial guess when use_state_match=True."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states

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
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states

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
    base_timestamp = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    records = [(base_timestamp + i * 60.0, np.zeros(6)) for i in range(20)]

    samples = estimation.select_bstar_fit_samples(records)

    assert len(samples) > 0
    assert len(samples) <= constants.BSTAR_SAMPLE_COUNT
    # First record should not be included (epoch is excluded)
    assert samples[0][0] != records[0][0]


def test_select_bstar_fit_samples_handles_small_dataset() -> None:
    """Should handle datasets smaller than BSTAR_SAMPLE_COUNT."""
    base_timestamp = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    records = [(base_timestamp + i * 60.0, np.zeros(6)) for i in range(5)]

    samples = estimation.select_bstar_fit_samples(records)

    # Should return all records except the first (epoch)
    assert len(samples) == 4


def test_select_bstar_fit_samples_returns_empty_for_single_record() -> None:
    """Should return empty list for single record."""
    base_timestamp = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    records = [(base_timestamp, np.zeros(6))]

    samples = estimation.select_bstar_fit_samples(records)

    assert len(samples) == 0


def test_estimate_bstar_preserves_user_provided_value() -> None:
    """Should preserve user-provided B* value without estimation."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states
    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    # Create args with custom bstar
    args = MagicMock()
    args.bstar = "12345-3"

    result = estimation.estimate_bstar_from_arc(args, estimated, records)

    assert result.bstar == "12345-3"
    assert result.bstar_source == "input"


def test_estimate_bstar_uses_default_when_arc_has_no_fit_samples() -> None:
    args = MagicMock()
    args.bstar = "00000+0"
    estimated = MagicMock()

    result = estimation.estimate_bstar_from_arc(args, estimated, [(0.0, np.zeros(6))])

    assert result is estimated
    assert estimated.bstar == "00000+0"
    assert estimated.bstar_source == "default"


def test_verify_accuracy_keplerian_returns_element_errors(monkeypatch) -> None:
    reference = np.array([7_000_000.0, 0.01, 0.5, 0.2, 0.3, 0.4])
    candidate = np.array([7_001_000.0, 0.02, 0.51, 0.25, 0.4, 0.5])
    monkeypatch.setattr(
        estimation.kepler, "cartesian_to_keplerian", lambda *_args: reference
    )
    monkeypatch.setattr(
        estimation.tle_builder, "build_tle_data", lambda *_args: object()
    )
    monkeypatch.setattr(
        estimation.convert_tle,
        "tle_to_osculating_keplerian",
        lambda *_args: candidate,
    )

    accuracy = estimation.verify_accuracy_keplerian(
        MagicMock(), MagicMock(), [(0.0, np.ones(6))]
    )

    assert isinstance(accuracy, models.KeplerianAccuracy)
    assert accuracy.semi_major_axis_error_m == 1_000.0
    assert accuracy.eccentricity_error == pytest.approx(0.01)


@pytest.mark.parametrize("failure", ["reference", "candidate"])
def test_verify_accuracy_keplerian_returns_none_on_conversion_failure(
    monkeypatch, failure: str
) -> None:
    estimated = MagicMock()
    monkeypatch.setattr(
        estimation.tle_builder, "build_tle_data", lambda *_args: object()
    )
    if failure == "reference":
        monkeypatch.setattr(
            estimation.kepler,
            "cartesian_to_keplerian",
            lambda *_args: (_ for _ in ()).throw(ValueError("invalid state")),
        )
    else:
        monkeypatch.setattr(
            estimation.kepler,
            "cartesian_to_keplerian",
            lambda *_args: np.ones(6),
        )
        monkeypatch.setattr(
            estimation.convert_tle,
            "tle_to_osculating_keplerian",
            lambda *_args: (_ for _ in ()).throw(RuntimeError("invalid TLE")),
        )

    assert (
        estimation.verify_accuracy_keplerian(
            MagicMock(), estimated, [(0.0, np.ones(6))]
        )
        is None
    )


def test_estimate_bstar_fits_sampled_arc(monkeypatch) -> None:
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem.CcsdsOem.read(io.StringIO(content)).states
    estimated = estimation.estimate_tle_fields(records, use_state_match=False)
    sampled_states = estimation.select_bstar_fit_samples(records)
    args = MagicMock()
    args.bstar = "00000+0"
    monkeypatch.setattr(
        estimation.tle_builder, "format_tle_exponential_from_float", str
    )
    monkeypatch.setattr(
        estimation.tle_builder,
        "build_tle_lines",
        lambda _args, trial: (trial.bstar, ""),
    )
    monkeypatch.setattr(
        refinement,
        "evaluate_tle_states_for_offsets_m",
        lambda line1, _line2, _offsets: [
            state if float(line1) != 0.0 else np.zeros(6) for _, state in sampled_states
        ],
    )

    result = estimation.estimate_bstar_from_arc(args, estimated, records)

    assert result is estimated
    assert estimated.bstar_source == "estimated"
    assert estimated.bstar_float > 0.0
    assert estimated.bstar_fit_score == 0.0


def test_estimate_bstar_falls_back_when_trial_propagation_fails(monkeypatch) -> None:
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    records = oem.CcsdsOem.read(io.StringIO(content)).states
    estimated = estimation.estimate_tle_fields(records, use_state_match=False)
    args = MagicMock()
    args.bstar = "00000+0"
    monkeypatch.setattr(
        estimation.tle_builder, "build_tle_lines", lambda *_args: ("line1", "line2")
    )
    monkeypatch.setattr(
        refinement, "evaluate_tle_states_for_offsets_m", lambda *_args: None
    )

    result = estimation.estimate_bstar_from_arc(args, estimated, records)

    assert result is estimated
    assert estimated.bstar == "00000+0"
    assert estimated.bstar_source == "default"
