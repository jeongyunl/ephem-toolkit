"""Tests for :mod:`common.common` — OEM parsing, duration/step parsing utilities."""

from __future__ import annotations

import argparse

import numpy as np
import pytest

import common.common as common

# ===================================================================
# 1. parse_duration_to_seconds — valid conversions
# ===================================================================


@pytest.mark.parametrize(
    "token, expected_seconds",
    [
        ("90", 90.0),
        ("90s", 90.0),
        ("90S", 90.0),
        ("2m", 120.0),
        ("2M", 120.0),
        ("1.5h", 5400.0),
        ("1.5H", 5400.0),
        ("1d", 86400.0),
        ("1D", 86400.0),
        ("0.5d", 43200.0),
        ("  3600s  ", 3600.0),
        (".5h", 1800.0),
    ],
    ids=[
        "bare-number-seconds",
        "explicit-s",
        "uppercase-S",
        "minutes",
        "uppercase-M",
        "fractional-hours",
        "uppercase-H",
        "one-day",
        "uppercase-D",
        "half-day",
        "whitespace-padded",
        "leading-dot-fraction",
    ],
)
def test_parse_duration_valid_conversions(token: str, expected_seconds: float) -> None:
    """Should correctly convert duration tokens with all supported units."""
    result = common.parse_duration_to_seconds(token)
    assert result == pytest.approx(expected_seconds)


# ===================================================================
# 2. parse_duration_to_seconds — invalid inputs
# ===================================================================


@pytest.mark.parametrize(
    "token",
    [
        "",
        "abc",
        "10x",
        "-5s",
        "0s",
        "0",
        "0d",
        "  ",
        "1.2.3s",
    ],
    ids=[
        "empty-string",
        "non-numeric",
        "invalid-unit-x",
        "negative-value",
        "zero-seconds",
        "zero-bare",
        "zero-days",
        "whitespace-only",
        "malformed-number",
    ],
)
def test_parse_duration_invalid_raises(token: str) -> None:
    """Should raise ArgumentTypeError for invalid or zero/negative durations."""
    with pytest.raises(argparse.ArgumentTypeError):
        common.parse_duration_to_seconds(token)


# ===================================================================
# 3. parse_step_to_seconds — valid conversions
# ===================================================================


@pytest.mark.parametrize(
    "token, expected_seconds",
    [
        ("60", 60.0),
        ("60s", 60.0),
        ("60S", 60.0),
        ("1m", 60.0),
        ("1M", 60.0),
        ("2.5m", 150.0),
        ("  30s  ", 30.0),
        (".5m", 30.0),
    ],
    ids=[
        "bare-number-seconds",
        "explicit-s",
        "uppercase-S",
        "one-minute",
        "uppercase-M",
        "fractional-minutes",
        "whitespace-padded",
        "leading-dot-fraction",
    ],
)
def test_parse_step_valid_conversions(token: str, expected_seconds: float) -> None:
    """Should correctly convert step-size tokens with supported units (s, m)."""
    result = common.parse_step_to_seconds(token)
    assert result == pytest.approx(expected_seconds)


# ===================================================================
# 4. parse_step_to_seconds — invalid inputs
# ===================================================================


@pytest.mark.parametrize(
    "token",
    [
        "",
        "abc",
        "10h",
        "1d",
        "-5s",
        "0s",
        "0",
        "  ",
    ],
    ids=[
        "empty-string",
        "non-numeric",
        "hours-not-supported",
        "days-not-supported",
        "negative-value",
        "zero-seconds",
        "zero-bare",
        "whitespace-only",
    ],
)
def test_parse_step_invalid_raises(token: str) -> None:
    """Should raise ArgumentTypeError for invalid units (h, d) or non-positive values."""
    with pytest.raises(argparse.ArgumentTypeError):
        common.parse_step_to_seconds(token)


# ===================================================================
# 5. parse_oem_state_line — valid and edge-case inputs
# ===================================================================


def test_parse_oem_state_line_valid() -> None:
    """Should parse a valid OEM-style state line into epoch, position, velocity."""
    line = "2026-05-20T12:00:00.000 -2345.678 4567.890 1234.567 -1.234 5.678 -3.456"
    result = common.parse_oem_state_line(line)

    assert result is not None
    epoch_dt, position_km, velocity_km_s = result

    from datetime import datetime

    assert epoch_dt == datetime(2026, 5, 20, 12, 0, 0)
    np.testing.assert_allclose(position_km, [-2345.678, 4567.890, 1234.567])
    np.testing.assert_allclose(velocity_km_s, [-1.234, 5.678, -3.456])


def test_parse_oem_state_line_with_trailing_z() -> None:
    """Should strip trailing Z from epoch before parsing."""
    line = "2026-05-20T12:00:00.000Z -2345.678 4567.890 1234.567 -1.234 5.678 -3.456"
    result = common.parse_oem_state_line(line)
    assert result is not None
    epoch_dt, _, _ = result
    from datetime import datetime

    assert epoch_dt == datetime(2026, 5, 20, 12, 0, 0)


def test_parse_oem_state_line_blank_returns_none() -> None:
    """Should return None for blank lines."""
    assert common.parse_oem_state_line("") is None
    assert common.parse_oem_state_line("   ") is None
    assert common.parse_oem_state_line("\n") is None


def test_parse_oem_state_line_comment_returns_none() -> None:
    """Should return None for comment lines starting with #."""
    assert common.parse_oem_state_line("# this is a comment") is None
    assert common.parse_oem_state_line("  # indented comment") is None


def test_parse_oem_state_line_too_few_fields_raises() -> None:
    """Should raise ValueError when line has fewer than 7 fields."""
    with pytest.raises(ValueError, match="does not contain 7 fields"):
        common.parse_oem_state_line("2026-05-20T12:00:00.000 1.0 2.0 3.0")


# ===================================================================
# 6. datetime_to_tdb and tdb_to_datetime — round-trip conversions
# ===================================================================


def test_datetime_to_tdb_j2000_epoch() -> None:
    """Should convert J2000 epoch (2000-01-01 12:00:00 UTC) to approximately 64.184 TDB seconds."""
    from datetime import datetime

    j2000_epoch = datetime(2000, 1, 1, 12, 0, 0)
    tdb_seconds = common.datetime_to_tdb(j2000_epoch)

    # J2000 epoch should be approximately 64.184 TDB seconds (UTC/TDB offset at J2000)
    assert tdb_seconds == pytest.approx(64.184, rel=0.01)


def test_datetime_to_tdb_future_date() -> None:
    """Should convert a future date to positive TDB seconds."""
    from datetime import datetime

    future_date = datetime(2026, 5, 20, 12, 0, 0)
    tdb_seconds = common.datetime_to_tdb(future_date)

    # Should be a large positive number (roughly 26.4 years * 365.25 * 86400 seconds)
    assert tdb_seconds > 0.0
    assert tdb_seconds > 26 * 365.25 * 86400


def test_tdb_to_datetime_j2000_epoch() -> None:
    """Should convert approximately 0 TDB seconds to J2000 epoch."""
    from datetime import datetime

    j2000_epoch = datetime(2000, 1, 1, 12, 0, 0)
    result_dt = common.tdb_to_datetime(0.0)

    # Should be very close to J2000 epoch (within ~65 seconds due to UTC/TDB offset)
    assert (
        result_dt == j2000_epoch
        or abs((result_dt - j2000_epoch).total_seconds()) < 65.0
    )


def test_datetime_tdb_round_trip() -> None:
    """Should preserve datetime through datetime -> TDB -> datetime conversion."""
    from datetime import datetime

    original_dt = datetime(2026, 5, 20, 12, 30, 45)
    tdb_seconds = common.datetime_to_tdb(original_dt)
    result_dt = common.tdb_to_datetime(tdb_seconds)

    # Should match to within a second (due to floating-point precision)
    assert (
        result_dt == original_dt or abs((result_dt - original_dt).total_seconds()) < 1.0
    )


def test_datetime_to_tdb_past_date() -> None:
    """Should convert a past date to negative TDB seconds."""
    from datetime import datetime

    past_date = datetime(1990, 1, 1, 12, 0, 0)
    tdb_seconds = common.datetime_to_tdb(past_date)

    # Should be a large negative number (roughly -10 years * 365.25 * 86400 seconds)
    assert tdb_seconds < 0.0
    # The value should be approximately -10 years worth of seconds (within 1%)
    expected_approx = -10 * 365.25 * 86400
    assert abs(tdb_seconds - expected_approx) / abs(expected_approx) < 0.01
