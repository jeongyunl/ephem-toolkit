"""Tests for shared CCSDS Orbit Data Message definitions."""

from __future__ import annotations

import re

import pytest

import core.ccsds.odm as odm


def test_ccsds_timecode_matches_supported_format() -> None:
    """The shared CCSDS timecode regex accepts the documented ODM timestamp form."""
    valid = " 2024-07-09T01:02:03.45  "
    match = re.fullmatch(odm.CCSDS_TIMECODE_PATTERN, valid)
    assert match is not None
    assert match.groupdict() == {
        "yr": "2024",
        "mo": "07",
        "dy": "09",
        "hr": "01",
        "mn": "02",
        "sc": "03.45",
    }

    invalid = "2024-07-09 01:02:03"
    assert re.fullmatch(odm.CCSDS_TIMECODE_PATTERN, invalid) is None
    assert re.fullmatch(odm.CCSDS_TIMECODE_PATTERN, "2024-7-9T1:2:3") is None


def test_non_decimal_string_matches_named_groups() -> None:
    """The value regex captures the field name and non-decimal string value."""
    valid = "   ISS-1"
    match = re.fullmatch(odm.CCSDS_NON_DECIMAL_STRING_PATTERN, valid)
    assert match is not None
    assert match.groupdict() == {"value": "ISS-1"}

    invalid = "ISS:1"
    assert re.fullmatch(odm.CCSDS_NON_DECIMAL_STRING_PATTERN, invalid) is None


def test_free_text_string_matches_named_groups() -> None:
    """The free-text kevalue regex captures the field name and free-text value."""
    valid = "  THIS.IS-A_TEST"
    match = re.fullmatch(odm.CCSDS_FREE_TEXT_STRING_PATTERN, valid)
    assert match is not None
    assert match.groupdict() == {"value": "THIS.IS-A_TEST"}

    invalid = "This:is:not:free"
    assert re.fullmatch(odm.CCSDS_FREE_TEXT_STRING_PATTERN, invalid) is None


def test_numerical_value_with_optional_units_matches_named_groups() -> None:
    """The numeric value regex captures the numeric value and optional unit."""
    valid = "  -1.23e-4 [rad/s]"
    match = re.fullmatch(odm.CCSDS_NUMERICAL_VALUE_WITH_OPTIONAL_UNITS_PATTERN, valid)
    assert match is not None
    assert match.groupdict() == {
        "value": "-1.23e-4",
        "unit": "rad/s",
    }

    valid_without_unit = "42"
    match = re.fullmatch(
        odm.CCSDS_NUMERICAL_VALUE_WITH_OPTIONAL_UNITS_PATTERN,
        valid_without_unit,
    )
    assert match is not None
    assert match.groupdict() == {"value": "42", "unit": None}

    invalid = "abc"
    assert (
        re.fullmatch(odm.CCSDS_NUMERICAL_VALUE_WITH_OPTIONAL_UNITS_PATTERN, invalid)
        is None
    )
    assert (
        re.fullmatch(odm.CCSDS_NUMERICAL_VALUE_WITH_OPTIONAL_UNITS_PATTERN, "1.")
        is None
    )
    assert (
        re.fullmatch(odm.CCSDS_NUMERICAL_VALUE_WITH_OPTIONAL_UNITS_PATTERN, "1 [km")
        is None
    )
    assert (
        re.fullmatch(odm.CCSDS_NUMERICAL_VALUE_WITH_OPTIONAL_UNITS_PATTERN, "1[km]")
        is None
    )


def test_ccsds_multipartite_numerical_values_matches_named_groups() -> None:
    """The multipartite numeric regex captures three values in sequence."""
    valid = "  1.0 2.5e-3 -7 "
    match = re.fullmatch(odm.CCSDS_3VALUE_NUMERICAL_PATTERN, valid)
    assert match is not None
    assert match.groupdict() == {
        "value1": "1.0",
        "value2": "2.5e-3",
        "value3": "-7",
    }

    invalid = "1.0 2.5 abc"
    assert re.fullmatch(odm.CCSDS_3VALUE_NUMERICAL_PATTERN, invalid) is None
    assert re.fullmatch(odm.CCSDS_3VALUE_NUMERICAL_PATTERN, "1.0  2.0") is None
    assert re.fullmatch(odm.CCSDS_3VALUE_NUMERICAL_PATTERN, "1.0 . 2.0") is None


def test_parse_kvn_assignment_and_shared_comment_tokens() -> None:
    assert odm.parse_kvn_assignment("  OBJECT_NAME  =  ISS  ") == (
        "OBJECT_NAME",
        "ISS",
    )
    assert odm.parse_kvn_assignment("COMMENT text") is None
    assert odm.parse_kvn_assignment("KEY = value = extra") is None
    assert odm.CCSDS_COMMENT_KEYWORD == "COMMENT"
    assert odm.CCSDS_COMMENT_PREFIX == "COMMENT "


def test_validate_odm_line_enforces_common_length_and_ascii_rules() -> None:
    odm.validate_odm_line("COMMENT text", "ODM")

    with pytest.raises(ValueError, match="254-character"):
        odm.validate_odm_line("x" * 255, "ODM")
    with pytest.raises(ValueError, match="printable ASCII"):
        odm.validate_odm_line("COMMENT café", "ODM")


def test_validate_odm_units_and_numeric_forms() -> None:
    units = {"X": "km"}
    assert odm.validate_odm_unit("X", "1 [km]", units, "OPM") == "1"
    assert odm.validate_odm_numeric("X", "1.25E+2", "OPM") == ("1.25E+2", False)
    assert odm.validate_odm_numeric("X", ".25", "OMM", allow_leading_decimal=True) == (
        "0.25",
        True,
    )

    with pytest.raises(ValueError, match="Invalid unit"):
        odm.validate_odm_unit("X", "1 [m]", units, "OPM")
    with pytest.raises(ValueError, match="significant digits"):
        odm.validate_odm_numeric("X", "12345678901234567", "OPM")


@pytest.mark.parametrize(
    "value",
    [
        "2024-99-99T99:99:99",
        "2024-02-30T12:00:00",
        "2023-366T12:00:00",
        "2024-01-01T24:00:00",
    ],
)
def test_validate_odm_datetime_rejects_invalid_dates_and_times(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid"):
        odm.validate_odm_datetime(value, "EPOCH", "ODM")


def test_validate_odm_datetime_accepts_calendar_ordinal_and_leap_second() -> None:
    odm.validate_odm_datetime("2024-02-29T23:59:60.123Z", "EPOCH", "ODM")
    odm.validate_odm_datetime("2024-060T23:59:59", "EPOCH", "ODM")


def test_ref_frame_values_match_ccsds_odm_frames() -> None:
    """The shared frame set contains all supported OEM and OMM identifiers."""
    expected = {
        "EME2000",
        "GCRF",
        "GRC",
        "ICRF",
        "ITRF",
        "ITRF2000",
        "ITRF1993",
        "ITRF1997",
        "MCI",
        "TDR",
        "TEME",
        "TOD",
    }

    assert odm.REF_FRAME_VALUES == frozenset(expected)
    assert odm.REF_FRAMES is odm.REF_FRAME_VALUES
    assert odm.REF_FRAME_DESCRIPTIONS["TEME"].endswith("(only used in OMMs)")


def test_time_system_values_match_ccsds_odm_time_systems() -> None:
    """The shared time-system set contains all supported OEM and OMM identifiers."""
    expected = {
        "GMST",
        "GPS",
        "MET",
        "MRT",
        "SCLK",
        "TAI",
        "TCB",
        "TDB",
        "TCG",
        "TT",
        "UT1",
        "UTC",
    }

    assert odm.TIME_SYSTEM_VALUES == frozenset(expected)
    assert odm.TIME_SYSTEMS is odm.TIME_SYSTEM_VALUES
    assert odm.TIME_SYSTEM_DESCRIPTIONS["SCLK"].endswith("in ICD)")


@pytest.mark.parametrize("ref_frame", ["J2000", "ITRF93", "ICRF"])
def test_validate_odm_context_accepts_supported_frames(ref_frame: str) -> None:
    odm.validate_odm_context("Earth", ref_frame, "UTC")


@pytest.mark.parametrize(
    ("center_name", "ref_frame", "time_system", "message"),
    [
        ("Earth", "UNKNOWN", "UTC", "REF_FRAME"),
        ("Earth", "ICRF", "UNKNOWN", "TIME_SYSTEM"),
        ("   ", "ICRF", "UTC", "CENTER_NAME"),
    ],
)
def test_validate_odm_context_rejects_invalid_values(
    center_name: str, ref_frame: str, time_system: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        odm.validate_odm_context(center_name, ref_frame, time_system)
