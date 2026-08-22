"""Tests for shared CCSDS Orbit Data Message definitions."""

from __future__ import annotations

import re

import core.ccsds.odm as odm


def test_ccsds_timecode_matches_supported_format() -> None:
    """The shared CCSDS timecode regex accepts the documented ODM timestamp form."""
    valid = " 2024-7-9T1:2:3.45  "
    match = re.fullmatch(odm.CCSDS_TIMECODE_PATTERN, valid)
    assert match is not None
    assert match.groupdict() == {
        "yr": "2024",
        "mo": "7",
        "dy": "9",
        "hr": "1",
        "mn": "2",
        "sc": "3.45",
    }

    invalid = "2024-07-09 01:02:03"
    assert re.fullmatch(odm.CCSDS_TIMECODE_PATTERN, invalid) is None


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
    match = re.fullmatch(
        odm.CCSDS_NUMERICAL_VALUE_WITH_OPTIONAL_UNITS_PATTERN, valid
    )
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
        re.fullmatch(
            odm.CCSDS_NUMERICAL_VALUE_WITH_OPTIONAL_UNITS_PATTERN, invalid
        )
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
