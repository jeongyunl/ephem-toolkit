"""Tests for shared CCSDS Orbit Data Message definitions."""

from __future__ import annotations

import core.ccsds.odm as odm


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