"""Tests for :mod:`common.tle` — Tle dataclass, read_tle, write_tle."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

import common.tle as tle

TEST_DIR = Path(__file__).parent

# ===================================================================
# Shared fixtures / constants
# ===================================================================

# ISS-like 3-line TLE (name + line1 + line2)
ISS_NAME = "ISS (ZARYA)"
ISS_LINE1 = "1 25544U 98067A   26152.32329980  .00009658  00000+0  17978-3 0  9994"
ISS_LINE2 = "2 25544  51.6335  18.6331 0007202 121.2251 238.9444 15.49538094569295"
ISS_3LINE = f"{ISS_NAME}\n{ISS_LINE1}\n{ISS_LINE2}\n"
ISS_2LINE = f"{ISS_LINE1}\n{ISS_LINE2}\n"

# LEO satellite 2-line TLE (from project file LEO-3_2023-100G.tle)
LEO_LINE1 = "1 57392U 23100G   26152.32106577 -.00000025  00000+0  23090-4 0  9994"
LEO_LINE2 = "2 57392  99.5618 276.7913 0018935  58.5750 301.7244 13.68420246143473"
LEO_2LINE = f"{LEO_LINE1}\n{LEO_LINE2}\n"


# ===================================================================
# 1. Parse 3-line TLE and return Tle dataclass
# ===================================================================


def test_read_tle_three_line_returns_tle_dataclass() -> None:
    """Should parse a 3-line TLE and return a Tle with all fields populated."""
    t = tle.read_tle(io.StringIO(ISS_3LINE))

    assert isinstance(t, tle.Tle)
    assert t.name == ISS_NAME
    assert t.satellite_number == 25544
    assert t.classification == "U"
    assert t.int_designator_year == 98
    assert t.int_designator_launch_number == 67
    assert t.int_designator_piece == "A"
    assert t.epoch_year == 26
    assert t.epoch_day == pytest.approx(152.32329980, abs=1e-8)
    assert t.mean_motion_first_derivative == pytest.approx(0.00009658, abs=1e-10)
    assert t.ephemeris_type == 0
    assert t.element_set_number == 999
    assert t.inclination_deg == pytest.approx(51.6335, abs=1e-4)
    assert t.raan_deg == pytest.approx(18.6331, abs=1e-4)
    assert t.eccentricity == pytest.approx(0.0007202, abs=1e-7)
    assert t.arg_perigee_deg == pytest.approx(121.2251, abs=1e-4)
    assert t.mean_anomaly_deg == pytest.approx(238.9444, abs=1e-4)
    assert t.mean_motion_rev_per_day == pytest.approx(15.49538094, abs=1e-8)
    assert t.revolution_number_at_epoch == 56929


# ===================================================================
# 2. Parse 2-line TLE (no name)
# ===================================================================


def test_read_tle_two_line_sets_empty_name() -> None:
    """Should parse a 2-line TLE and set name to empty string."""
    t = tle.read_tle(io.StringIO(LEO_2LINE))

    assert isinstance(t, tle.Tle)
    assert t.name == ""
    assert t.satellite_number == 57392
    assert t.inclination_deg == pytest.approx(99.5618, abs=1e-4)
    assert t.mean_motion_first_derivative == pytest.approx(-0.00000025, abs=1e-10)


# ===================================================================
# 3. Raise ValueError on insufficient lines
# ===================================================================


def test_read_tle_raises_on_single_line() -> None:
    """Should raise ValueError when fewer than 2 non-empty lines are given."""
    with pytest.raises(ValueError, match="at least 2 non-empty lines"):
        tle.read_tle(io.StringIO("1 25544U 98067A   24001.50000000\n"))


def test_read_tle_raises_on_empty_stream() -> None:
    """Should raise ValueError on an empty stream."""
    with pytest.raises(ValueError, match="at least 2 non-empty lines"):
        tle.read_tle(io.StringIO(""))


# ===================================================================
# 4. Raise ValueError on short TLE lines
# ===================================================================


def test_read_tle_raises_on_short_lines() -> None:
    """Should raise ValueError when TLE lines are shorter than 69 chars."""
    short_line1 = ISS_LINE1[:50]
    short_line2 = ISS_LINE2[:50]
    with pytest.raises(ValueError, match="at least 69 characters"):
        tle.read_tle(io.StringIO(f"{short_line1}\n{short_line2}\n"))


# ===================================================================
# 5. Compute correct TLE checksums
# ===================================================================


def test_compute_tle_checksum_digits_and_minus() -> None:
    """Should sum digit values and count minus signs, return mod-10."""
    # "1-2" → 1 + 1(minus) + 2 = 4
    assert tle.compute_tle_checksum("1-2") == "4"
    # All zeros
    assert tle.compute_tle_checksum("0000") == "0"
    # Letters are ignored
    assert tle.compute_tle_checksum("ABC") == "0"
    # Mixed
    assert tle.compute_tle_checksum("9-9") == "9"  # 9+1+9 = 19 → 9


def test_read_tle_checksums_match() -> None:
    """Parsed checksum fields should match the expected computed values."""
    t = tle.read_tle(io.StringIO(ISS_3LINE))
    assert t.line1_checksum == t.line1_checksum_expected
    assert t.line2_checksum == t.line2_checksum_expected


# ===================================================================
# 6. Dict-style backward compatibility on Tle dataclass
# ===================================================================


def test_tle_getitem() -> None:
    """Should support tle['field'] dict-style access."""
    t = tle.read_tle(io.StringIO(ISS_3LINE))
    assert t["satellite_number"] == 25544
    assert t["name"] == ISS_NAME


def test_tle_getitem_raises_keyerror_for_missing() -> None:
    """Should raise KeyError for non-existent fields via __getitem__."""
    t = tle.read_tle(io.StringIO(ISS_3LINE))
    with pytest.raises(KeyError):
        _ = t["nonexistent_field"]


def test_tle_contains() -> None:
    """Should support 'field in tle' membership test."""
    t = tle.read_tle(io.StringIO(ISS_3LINE))
    assert "satellite_number" in t
    assert "nonexistent_field" not in t


def test_tle_get_with_default() -> None:
    """Should return default for missing keys via .get()."""
    t = tle.read_tle(io.StringIO(ISS_3LINE))
    assert t.get("satellite_number") == 25544
    assert t.get("nonexistent", "fallback") == "fallback"


def test_tle_to_dict() -> None:
    """Should convert to a plain dict with all fields."""
    t = tle.read_tle(io.StringIO(ISS_3LINE))
    d = t.to_dict()
    assert isinstance(d, dict)
    assert d["satellite_number"] == 25544
    assert d["name"] == ISS_NAME
    assert d["eccentricity"] == pytest.approx(0.0007202, abs=1e-7)


# ===================================================================
# 7. Write TLE from Tle dataclass — valid lines with checksums
# ===================================================================


def test_write_tle_from_dataclass_produces_valid_lines() -> None:
    """Should write 69-char lines with correct checksums from a Tle."""
    t = tle.read_tle(io.StringIO(ISS_3LINE))
    buf = io.StringIO()
    line1, line2 = tle.write_tle(buf, t)

    assert len(line1) == 69
    assert len(line2) == 69
    assert line1[0] == "1"
    assert line2[0] == "2"
    # Verify checksums
    assert line1[68] == tle.compute_tle_checksum(line1[:68])
    assert line2[68] == tle.compute_tle_checksum(line2[:68])


# ===================================================================
# 8. Write TLE from plain dict (Mapping backward compatibility)
# ===================================================================


def test_write_tle_from_dict() -> None:
    """Should accept a plain dict and produce valid TLE lines."""
    tle_dict = {
        "name": "",
        "satellite_number": 57392,
        "classification": "U",
        "int_designator_year": 23,
        "int_designator_launch_number": 100,
        "int_designator_piece": "G",
        "epoch_year": 26,
        "epoch_day": 100.26300651,
        "mean_motion_first_derivative": -0.00000007,
        "mean_motion_second_derivative": "00000+0",
        "bstar": "44009-4",
        "ephemeris_type": 0,
        "element_set_number": 999,
        "inclination_deg": 99.5524,
        "raan_deg": 225.2487,
        "eccentricity": 0.0018285,
        "arg_perigee_deg": 187.8494,
        "mean_anomaly_deg": 172.2367,
        "mean_motion_rev_per_day": 13.68419075,
        "revolution_number_at_epoch": 13635,
    }
    buf = io.StringIO()
    line1, line2 = tle.write_tle(buf, tle_dict)

    assert len(line1) == 69
    assert len(line2) == 69
    assert line1[68] == tle.compute_tle_checksum(line1[:68])
    assert line2[68] == tle.compute_tle_checksum(line2[:68])


# ===================================================================
# 9. Read → write → read round-trip preserves values
# ===================================================================


TLE_FILES = sorted(TEST_DIR.glob("*.tle"))


@pytest.mark.parametrize("tle_path", TLE_FILES, ids=[p.name for p in TLE_FILES])
def test_round_trip_preserves_elements(tle_path: Path) -> None:
    """Should preserve all element values through a read→write→read cycle."""
    with open(tle_path, encoding="utf-8") as fh:
        tle1 = tle.read_tle(fh)

    buf = io.StringIO()
    tle.write_tle(buf, tle1)
    buf.seek(0)

    tle2 = tle.read_tle(buf)

    assert tle2.name == tle1.name
    assert tle2.satellite_number == tle1.satellite_number
    assert tle2.classification == tle1.classification
    assert tle2.int_designator_year == tle1.int_designator_year
    assert tle2.int_designator_launch_number == tle1.int_designator_launch_number
    assert tle2.int_designator_piece == tle1.int_designator_piece
    assert tle2.epoch_year == tle1.epoch_year
    assert tle2.epoch_day == pytest.approx(tle1.epoch_day, abs=1e-8)
    assert tle2.mean_motion_first_derivative == pytest.approx(
        tle1.mean_motion_first_derivative, abs=1e-10
    )
    assert tle2.ephemeris_type == tle1.ephemeris_type
    assert tle2.element_set_number == tle1.element_set_number
    assert tle2.inclination_deg == pytest.approx(tle1.inclination_deg, abs=1e-4)
    assert tle2.raan_deg == pytest.approx(tle1.raan_deg, abs=1e-4)
    assert tle2.eccentricity == pytest.approx(tle1.eccentricity, abs=1e-7)
    assert tle2.arg_perigee_deg == pytest.approx(tle1.arg_perigee_deg, abs=1e-4)
    assert tle2.mean_anomaly_deg == pytest.approx(tle1.mean_anomaly_deg, abs=1e-4)
    assert tle2.mean_motion_rev_per_day == pytest.approx(tle1.mean_motion_rev_per_day, abs=1e-8)
    assert tle2.revolution_number_at_epoch == tle1.revolution_number_at_epoch
    # Checksums should still be valid
    assert tle2.line1_checksum == tle2.line1_checksum_expected
    assert tle2.line2_checksum == tle2.line2_checksum_expected


# ===================================================================
# 10. Write TLE to a file path (str / Path)
# ===================================================================


def test_write_tle_to_file_path(tmp_path: Path) -> None:
    """Should write a TLE file when dest is a str or Path."""
    t = tle.read_tle(io.StringIO(LEO_2LINE))
    out_path = tmp_path / "output.tle"

    line1, line2 = tle.write_tle(out_path, t)

    text = out_path.read_text(encoding="utf-8")
    lines = text.strip().splitlines()
    # 2-line TLE (no name) → exactly 2 lines
    assert len(lines) == 2
    assert lines[0] == line1
    assert lines[1] == line2


def test_write_tle_to_file_path_with_name(tmp_path: Path) -> None:
    """Should include the name line when writing a named TLE to a file."""
    t = tle.read_tle(io.StringIO(ISS_3LINE))
    out_path = tmp_path / "named.tle"

    tle.write_tle(str(out_path), t)

    text = out_path.read_text(encoding="utf-8")
    lines = text.strip().splitlines()
    # 3-line TLE (name + line1 + line2)
    assert len(lines) == 3
    assert lines[0] == ISS_NAME
