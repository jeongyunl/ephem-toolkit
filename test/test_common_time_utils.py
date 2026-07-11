"""Tests for common.time_utils module.

This test file verifies that the time-related functions work correctly
when imported directly from the common.time_utils module (not through the
backward-compatibility re-exports in common.common).
"""

from datetime import datetime, timezone

import pytest

import common.time_utils as time_utils

# ===================================================================
# Time conversion tests
# ===================================================================


def test_datetime_to_tdb_j2000_epoch():
    """Should return approximately 64.184 seconds for J2000 epoch (TDB-UTC offset)."""
    j2000_epoch = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    tdb_seconds = time_utils.datetime_to_tdb_s(j2000_epoch)
    # TDB-UTC offset at J2000 is approximately 64.184 seconds
    assert tdb_seconds == pytest.approx(64.184, abs=1.0)


def test_datetime_to_tdb_future_date():
    """Should return positive TDB seconds for dates after J2000."""
    future_date = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
    tdb_seconds = time_utils.datetime_to_tdb_s(future_date)
    # Should be a large positive number (roughly 26.4 years * 365.25 * 86400 seconds)
    assert tdb_seconds > 0.0
    assert tdb_seconds > 26 * 365.25 * 86400


def test_datetime_to_tdb_past_date():
    """Should convert a past date to negative TDB seconds."""
    past_date = datetime(1990, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    tdb_seconds = time_utils.datetime_to_tdb_s(past_date)
    # Should be a large negative number (roughly -10 years * 365.25 * 86400 seconds)
    assert tdb_seconds < 0.0
    # The value should be approximately -10 years worth of seconds (within 1%)
    expected_approx = -10 * 365.25 * 86400
    assert abs(tdb_seconds - expected_approx) / abs(expected_approx) < 0.01


def test_tdb_to_datetime_j2000_epoch():
    """Should return UTC time corresponding to TDB = 0.0 (slightly before J2000)."""
    # TDB = 0.0 corresponds to UTC slightly before J2000 due to TDB-UTC offset
    result_dt = time_utils.tdb_s_to_datetime(0.0)
    j2000_epoch = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    # Result should be about 64 seconds before J2000
    time_diff = (j2000_epoch - result_dt).total_seconds()
    assert time_diff == pytest.approx(64.184, abs=1.0)


def test_datetime_tdb_round_trip():
    """Should preserve datetime through TDB conversion round trip."""
    original_dt = datetime(2026, 5, 20, 12, 30, 45, tzinfo=timezone.utc)
    tdb_seconds = time_utils.datetime_to_tdb_s(original_dt)
    result_dt = time_utils.tdb_s_to_datetime(tdb_seconds)
    assert result_dt == pytest.approx(original_dt, abs=1e-6)


# ===================================================================
# ISO 8601 parsing tests
# ===================================================================


@pytest.mark.parametrize(
    "epoch_str,expected_year,expected_month,expected_day,expected_hour,expected_minute,expected_second,expected_microsecond",
    [
        ("2000-01-01T12:00:00", 2000, 1, 1, 12, 0, 0, 0),
        ("2000-01-01 12:00:00", 2000, 1, 1, 12, 0, 0, 0),
        ("2000-01-01T12:00:00Z", 2000, 1, 1, 12, 0, 0, 0),
        ("2000-01-01 12:00:00Z", 2000, 1, 1, 12, 0, 0, 0),
        ("2026-05-20T12:30:45", 2026, 5, 20, 12, 30, 45, 0),
        ("2026-05-20 12:30:45", 2026, 5, 20, 12, 30, 45, 0),
        ("1999-12-31T23:59:59", 1999, 12, 31, 23, 59, 59, 0),
        ("2000-01-01T00:00:00", 2000, 1, 1, 0, 0, 0, 0),
    ],
)
def test_iso8601_to_datetime_valid_formats(
    epoch_str,
    expected_year,
    expected_month,
    expected_day,
    expected_hour,
    expected_minute,
    expected_second,
    expected_microsecond,
):
    """Should parse various ISO 8601 formats."""
    result = time_utils.iso8601_to_datetime(epoch_str)
    assert result.year == expected_year
    assert result.month == expected_month
    assert result.day == expected_day
    assert result.hour == expected_hour
    assert result.minute == expected_minute
    assert result.second == expected_second
    assert result.microsecond == expected_microsecond


@pytest.mark.parametrize(
    "epoch_str,expected_microseconds",
    [
        ("2000-01-01T12:00:00.1", 100000),
        ("2000-01-01T12:00:00.12", 120000),
        ("2000-01-01T12:00:00.123", 123000),
        ("2000-01-01T12:00:00.1234", 123400),
        ("2000-01-01T12:00:00.12345", 123450),
        ("2000-01-01T12:00:00.123456", 123456),
        ("2000-01-01 12:00:00.123", 123000),
        ("2000-01-01T12:00:00.123Z", 123000),
        ("2000-01-01 12:00:00.123Z", 123000),
        ("2026-05-20T12:30:45.999999", 999999),
        ("2000-01-01T00:00:00.000001", 1),
    ],
)
def test_iso8601_to_datetime_fractional_seconds(epoch_str, expected_microseconds):
    """Should correctly parse fractional seconds."""
    result = time_utils.iso8601_to_datetime(epoch_str)
    assert result.microsecond == expected_microseconds


def test_datetime_to_iso8601_default_format():
    """Should format datetime with default settings (T separator, 3 decimal places)."""
    dt = datetime(2000, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
    result = time_utils.datetime_to_iso8601(dt)
    assert result == "2000-01-01T12:00:00.123"


def test_datetime_to_iso8601_space_separator():
    """Should use space separator when requested."""
    dt = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    result = time_utils.datetime_to_iso8601(dt, use_t_separator=False)
    assert result == "2000-01-01 12:00:00.000"


def test_datetime_to_iso8601_no_fractional():
    """Should omit fractional seconds when requested."""
    dt = datetime(2000, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
    result = time_utils.datetime_to_iso8601(dt, fractional_second_places=0)
    assert result == "2000-01-01T12:00:00"


def test_datetime_to_iso8601_six_decimal_places():
    """Should format with 6 decimal places when requested."""
    dt = datetime(2000, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
    result = time_utils.datetime_to_iso8601(dt, fractional_second_places=6)
    assert result == "2000-01-01T12:00:00.123456"


def test_iso8601_to_datetime_invalid_raises():
    """Should raise ValueError for invalid ISO 8601 strings."""
    invalid_strings = [
        "",
        "   ",
        "2000-01-01",
        "12:00:00",
        "2000-1-1T12:00:00",
        "2000-01-01T12:00",
        "2000-01-01T12:00:00.123.456",
        "2000-01-01X12:00:00",
        "2000-01-01T12:00:00.123X",
        "not-a-date",
        "2000-13-01T12:00:00",
        "2000-01-32T12:00:00",
        "2000-01-01T25:00:00",
        "2000-01-01T12:60:00",
        "2000-01-01T12:00:60",
    ]
    for epoch_str in invalid_strings:
        with pytest.raises(ValueError, match="Unable to parse epoch string"):
            time_utils.iso8601_to_datetime(epoch_str)


def test_iso8601_to_datetime_with_leading_trailing_whitespace():
    """Should handle leading and trailing whitespace."""
    result = time_utils.iso8601_to_datetime("  2000-01-01T12:00:00  ")
    assert result.year == 2000
    assert result.month == 1
    assert result.day == 1
    assert result.hour == 12
    assert result.minute == 0
    assert result.second == 0


def test_iso8601_to_datetime_z_suffix_stripped():
    """Should correctly strip 'Z' timezone indicator."""
    result_with_z = time_utils.iso8601_to_datetime("2000-01-01T12:00:00Z")
    result_without_z = time_utils.iso8601_to_datetime("2000-01-01T12:00:00")
    assert result_with_z == result_without_z


# ===================================================================
# Duration parsing tests
# ===================================================================


@pytest.mark.parametrize(
    "token,expected_seconds",
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
)
def test_parse_duration_to_seconds_valid(token, expected_seconds):
    """Should correctly convert duration tokens with all supported units."""
    result = time_utils.parse_duration_to_seconds(token)
    assert result == pytest.approx(expected_seconds)


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
)
def test_parse_duration_to_seconds_invalid(token):
    """Should raise ArgumentTypeError for invalid duration tokens."""
    with pytest.raises(ValueError):
        time_utils.parse_duration_to_seconds(token)


@pytest.mark.parametrize(
    "token,expected_seconds",
    [
        ("60", 60.0),
        ("60s", 60.0),
        ("60S", 60.0),
        ("1m", 60.0),
        ("1M", 60.0),
        ("2.5m", 150.0),
        ("  30s  ", 30.0),
        (".5m", 30.0),
        ("1h", 3600.0),
        ("1d", 86400.0),
    ],
)
def test_parse_duration_to_seconds_valid(token, expected_seconds):
    """Should correctly convert step-size tokens with supported units (s, m, h, d)."""
    result = time_utils.parse_duration_to_seconds(token)
    assert result == pytest.approx(expected_seconds)


@pytest.mark.parametrize(
    "token",
    [
        "",
        "abc",
        "10x",
        "-5s",
        "0s",
        "0",
        "  ",
    ],
)
def test_parse_duration_to_seconds_invalid(token):
    """Should raise ArgumentTypeError for invalid step-size tokens."""
    with pytest.raises(ValueError):
        time_utils.parse_duration_to_seconds(token)


@pytest.mark.parametrize(
    "token,kwargs",
    [
        ("", {}),
        ("abc", {}),
        ("10x", {}),
        ("-5s", {}),
        ("0s", {}),
        ("0", {}),
        ("  ", {}),
        ("1.2.3s", {}),
    ],
)
def test_parse_duration_invalid(token, kwargs):
    """Should raise ArgumentTypeError for invalid inputs."""
    with pytest.raises(ValueError):
        time_utils.parse_duration_to_seconds(token, **kwargs)


def test_parse_duration_negative_rejected_by_default():
    """Should reject negative durations by default."""
    with pytest.raises(ValueError):
        time_utils.parse_duration_to_seconds("-5s")


def test_parse_duration_zero_rejected_by_default():
    """Should reject zero duration by default."""
    with pytest.raises(ValueError):
        time_utils.parse_duration_to_seconds("0s")


# ===================================================================
# Constants tests
# ===================================================================


def test_time_constants():
    """Should have correct time conversion constants."""
    assert time_utils.SECONDS_PER_MINUTE == 60.0
    assert time_utils.SECONDS_PER_HOUR == 3600.0
    assert time_utils.SECONDS_PER_DAY == 86400.0
