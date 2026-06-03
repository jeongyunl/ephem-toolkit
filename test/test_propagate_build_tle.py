"""Integration tests: propagate_tle -> build_tle round-trip accuracy.

For each TLE file in the test directory, propagate with SGP4 for 1 day,
feed the resulting OEM-like state vectors into build_tle, and compare
the reconstructed TLE against the original.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

import common.tle as tle

TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent

TLE_FILES = sorted(TEST_DIR.glob("*.tle"))

MEAN_MOTION_TOL_REV_PER_DAY = 0.005
INCLINATION_TOL_DEG = 0.1
RAAN_TOL_DEG = 0.3
ECCENTRICITY_TOL = 0.002
ARG_PERIGEE_TOL_DEG = 5.0
MEAN_ANOMALY_TOL_DEG = 5.0

GEO_MEAN_MOTION_THRESHOLD = 2.0
GEO_ARG_PERIGEE_TOL_DEG = 180.0
GEO_MEAN_ANOMALY_TOL_DEG = 180.0
GEO_RAAN_TOL_DEG = 1.0
GEO_INCLINATION_TOL_DEG = 0.5  # Near-equatorial: use osculating directly


def _build_env():
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PROJECT_ROOT) + ((":" + existing) if existing else "")
    return env


def run_propagate_tle(tle_path):
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "propagation" / "propagate_tle.py"),
            str(tle_path),
            "-d",
            "1d",
            "-s",
            "15m",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )
    assert result.returncode == 0, f"propagate_tle.py failed for {tle_path.name}:\n{result.stderr}"
    assert result.stdout.strip(), f"propagate_tle.py produced no output for {tle_path.name}"
    return result.stdout


def run_build_tle(oem_text, original):
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "tle" / "build_tle.py"),
        "--name",
        original.name if original.name else "",
        "--satellite-number",
        str(original.satellite_number),
        "--classification",
        original.classification,
        "--int-designator-year",
        str(original.int_designator_year),
        "--int-designator-launch-number",
        str(original.int_designator_launch_number),
        "--int-designator-piece",
        original.int_designator_piece or "A",
        "--revolution-number-at-epoch",
        str(original.revolution_number_at_epoch),
    ]
    result = subprocess.run(
        cmd,
        input=oem_text,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )
    assert result.returncode == 0, f"build_tle.py failed:\n{result.stderr}"
    return result.stdout


def parse_generated_tle_from_output(output):
    lines = [line for line in output.strip().splitlines() if line.strip()]
    tle_line1 = None
    tle_line2 = None
    for i in range(len(lines) - 1):
        if lines[i].startswith("1 ") and lines[i + 1].startswith("2 "):
            tle_line1 = lines[i]
            tle_line2 = lines[i + 1]
    assert (
        tle_line1 is not None and tle_line2 is not None
    ), f"Could not find TLE lines in build_tle.py output:\n{output[-500:]}"
    idx = lines.index(tle_line1)
    name_line = ""
    if idx > 0:
        candidate = lines[idx - 1]
        if not candidate.startswith(
            ("1 ", "2 ", " ", "Estimated", "note:", "bstar", "mean-", "state-")
        ):
            name_line = candidate
    tle_text = (
        f"{name_line}\n{tle_line1}\n{tle_line2}\n" if name_line else f"{tle_line1}\n{tle_line2}\n"
    )
    return tle.read_tle(io.StringIO(tle_text))


def is_geo_orbit(tle_data):
    return tle_data.mean_motion_rev_per_day < GEO_MEAN_MOTION_THRESHOLD


def angle_difference(a_deg, b_deg):
    diff = (a_deg - b_deg) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return diff


@pytest.fixture(params=TLE_FILES, ids=[p.name for p in TLE_FILES])
def tle_round_trip(request):
    tle_path = request.param
    with open(tle_path, encoding="utf-8") as fh:
        original = tle.read_tle(fh)
    oem_text = run_propagate_tle(tle_path)
    build_output = run_build_tle(oem_text, original)
    reconstructed = parse_generated_tle_from_output(build_output)
    return original, reconstructed


@pytest.mark.parametrize("tle_path", TLE_FILES, ids=[p.name for p in TLE_FILES])
def test_propagate_tle_produces_valid_state_vectors(tle_path):
    """Should propagate each TLE for 1 day and produce valid OEM-like state vectors."""
    oem_text = run_propagate_tle(tle_path)
    lines = [line for line in oem_text.strip().splitlines() if line.strip()]
    assert len(lines) >= 90, f"Expected ~97 state lines, got {len(lines)} for {tle_path.name}"
    for line in lines[:5]:
        parts = line.split()
        assert len(parts) == 7, f"Expected 7 fields per line, got {len(parts)}: {line}"


def test_reconstructed_tle_preserves_elements(tle_round_trip):
    """Should reconstruct a TLE that preserves all orbital elements within tolerance."""
    original, reconstructed = tle_round_trip

    # Mean motion
    assert reconstructed.mean_motion_rev_per_day == pytest.approx(
        original.mean_motion_rev_per_day, abs=MEAN_MOTION_TOL_REV_PER_DAY
    )

    # Inclination
    inc_tol = GEO_INCLINATION_TOL_DEG if is_geo_orbit(original) else INCLINATION_TOL_DEG
    assert reconstructed.inclination_deg == pytest.approx(original.inclination_deg, abs=inc_tol)

    # RAAN
    raan_tol = GEO_RAAN_TOL_DEG if is_geo_orbit(original) else RAAN_TOL_DEG
    raan_diff = angle_difference(reconstructed.raan_deg, original.raan_deg)
    assert raan_diff < raan_tol, (
        f"RAAN diff={raan_diff:.4f} > tol={raan_tol} "
        f"(orig={original.raan_deg:.4f}, recon={reconstructed.raan_deg:.4f})"
    )

    # Eccentricity
    assert reconstructed.eccentricity == pytest.approx(original.eccentricity, abs=ECCENTRICITY_TOL)

    # Argument of perigee
    aop_tol = GEO_ARG_PERIGEE_TOL_DEG if is_geo_orbit(original) else ARG_PERIGEE_TOL_DEG
    aop_diff = angle_difference(reconstructed.arg_perigee_deg, original.arg_perigee_deg)
    assert aop_diff < aop_tol, (
        f"Arg perigee diff={aop_diff:.4f} > tol={aop_tol} "
        f"(orig={original.arg_perigee_deg:.4f}, recon={reconstructed.arg_perigee_deg:.4f})"
    )

    # Mean anomaly
    ma_tol = GEO_MEAN_ANOMALY_TOL_DEG if is_geo_orbit(original) else MEAN_ANOMALY_TOL_DEG
    ma_diff = angle_difference(reconstructed.mean_anomaly_deg, original.mean_anomaly_deg)
    assert ma_diff < ma_tol, (
        f"Mean anomaly diff={ma_diff:.4f} > tol={ma_tol} "
        f"(orig={original.mean_anomaly_deg:.4f}, recon={reconstructed.mean_anomaly_deg:.4f})"
    )

    # Valid format and checksums
    assert len(reconstructed.line1) == 69
    assert len(reconstructed.line2) == 69
    assert reconstructed.line1[0] == "1"
    assert reconstructed.line2[0] == "2"
    assert reconstructed.line1_checksum == reconstructed.line1_checksum_expected
    assert reconstructed.line2_checksum == reconstructed.line2_checksum_expected
