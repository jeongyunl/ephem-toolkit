"""Integration tests: propagate_tle -> oem_to_tle round-trip accuracy.

For each TLE file in the test directory, propagate with SGP4 for 1 day,
feed the resulting OEM-like state vectors into oem_to_tle, and compare
the reconstructed TLE against the original.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common.tle as tle

TEST_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = TEST_DIR.parent
TEST_DATA_DIR: Path = TEST_DIR / "data"

TLE_FILES: list[Path] = sorted(TEST_DATA_DIR.glob("*.tle"))

MEAN_MOTION_TOL_REV_PER_DAY: float = 0.005
INCLINATION_TOL_DEG: float = 0.1
RAAN_TOL_DEG: float = 0.3
ECCENTRICITY_TOL: float = 0.002
ARG_PERIGEE_TOL_DEG: float = 5.0
MEAN_ANOMALY_TOL_DEG: float = 5.0

GEO_MEAN_MOTION_THRESHOLD: float = 2.0
GEO_ARG_PERIGEE_TOL_DEG: float = 180.0
GEO_MEAN_ANOMALY_TOL_DEG: float = 180.0
GEO_RAAN_TOL_DEG: float = 1.0
GEO_INCLINATION_TOL_DEG: float = 0.5
"""GEO inclination tolerance in degrees (relaxed for near-equatorial orbits)."""


def _build_env() -> dict[str, str]:
    """Build environment dictionary with PYTHONPATH set to project root.

    Returns
    -------
    dict[str, str]
        Environment dictionary with updated PYTHONPATH.
    """
    env: dict[str, str] = os.environ.copy()
    existing: str = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PROJECT_ROOT) + ((":" + existing) if existing else "")
    return env


def run_propagate_tle(tle_path: Path) -> str:
    """Run propagate_tle.py script and return output.

    Parameters
    ----------
    tle_path : Path
        Path to TLE file to propagate.

    Returns
    -------
    str
        Standard output from propagate_tle.py script.
    """
    result: subprocess.CompletedProcess[str] = subprocess.run(
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
    assert (
        result.returncode == 0
    ), f"propagate_tle.py failed for {tle_path.name}:\n{result.stderr}"
    assert (
        result.stdout.strip()
    ), f"propagate_tle.py produced no output for {tle_path.name}"
    return result.stdout


def run_oem_to_tle(
    oem_text: str, original: tle.Tle, refinement: str = "cartesian"
) -> str:
    """Run oem_to_tle script and return output.

    Parameters
    ----------
    oem_text : str
        OEM-like state vector text input.
    original : tle.Tle
        Original TLE data for metadata.
    refinement : str
        Refinement method (default: "cartesian").

    Returns
    -------
    str
        Standard output from oem_to_tle script.
    """
    cmd: list[str] = [
        sys.executable,
        "-m",
        "oem_to_tle.oem_to_tle",
        "-",
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
        "--refinement",
        refinement,
    ]
    result: subprocess.CompletedProcess[str] = subprocess.run(
        cmd,
        input=oem_text,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )
    assert result.returncode == 0, f"oem_to_tle.py failed:\n{result.stderr}"
    return result.stdout


def parse_generated_tle_from_output(output: str) -> tle.Tle:
    """Parse TLE from oem_to_tle script output.

    Parameters
    ----------
    output : str
        Standard output from oem_to_tle script.

    Returns
    -------
    tle.Tle
        Parsed TLE dataclass instance.
    """
    lines: list[str] = [line for line in output.strip().splitlines() if line.strip()]
    tle_line1: str | None = None
    tle_line2: str | None = None
    for i in range(len(lines) - 1):
        if lines[i].startswith("1 ") and lines[i + 1].startswith("2 "):
            tle_line1 = lines[i]
            tle_line2 = lines[i + 1]
    assert (
        tle_line1 is not None and tle_line2 is not None
    ), f"Could not find TLE lines in oem_to_tle.py output:\n{output[-500:]}"
    idx: int = lines.index(tle_line1)
    name_line: str = ""
    if idx > 0:
        candidate: str = lines[idx - 1]
        if not candidate.startswith(
            ("1 ", "2 ", " ", "Estimated", "note:", "bstar", "mean-", "state-")
        ):
            name_line = candidate
    tle_text: str = (
        f"{name_line}\n{tle_line1}\n{tle_line2}\n"
        if name_line
        else f"{tle_line1}\n{tle_line2}\n"
    )
    return tle.read_tle(io.StringIO(tle_text))


def is_geo_orbit(tle_data: tle.Tle) -> bool:
    """Check if TLE represents a geostationary orbit.

    Parameters
    ----------
    tle_data : tle.Tle
        TLE dataclass instance.

    Returns
    -------
    bool
        True if mean motion indicates geostationary orbit.
    """
    return tle_data.mean_motion_rev_per_day < GEO_MEAN_MOTION_THRESHOLD


def angle_difference(a_deg: float, b_deg: float) -> float:
    """Compute minimum angular difference between two angles in degrees.

    Parameters
    ----------
    a_deg : float
        First angle in degrees.
    b_deg : float
        Second angle in degrees.

    Returns
    -------
    float
        Minimum angular difference in degrees (0 to 180).
    """
    diff: float = (a_deg - b_deg) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return diff


@pytest.fixture(params=TLE_FILES, ids=[p.name for p in TLE_FILES])
def tle_round_trip(request) -> tuple[tle.Tle, tle.Tle]:
    """Fixture providing original and reconstructed TLE pair.

    Parameters
    ----------
    request : pytest.FixtureRequest
        Pytest fixture request object.

    Returns
    -------
    tuple[tle.Tle, tle.Tle]
        Tuple of (original TLE, reconstructed TLE).
    """
    tle_path: Path = request.param
    with open(tle_path, encoding="utf-8") as fh:
        original: tle.Tle = tle.read_tle(fh)
    oem_text: str = run_propagate_tle(tle_path)
    build_output: str = run_oem_to_tle(oem_text, original)
    reconstructed: tle.Tle = parse_generated_tle_from_output(build_output)
    return original, reconstructed


@pytest.mark.parametrize("tle_path", TLE_FILES, ids=[p.name for p in TLE_FILES])
def test_propagate_tle_produces_valid_state_vectors(tle_path: Path) -> None:
    """Should propagate each TLE for 1 day and produce valid OEM-like state vectors.

    Parameters
    ----------
    tle_path : Path
        Path to TLE file to test.
    """
    oem_text: str = run_propagate_tle(tle_path)
    lines: list[str] = [line for line in oem_text.strip().splitlines() if line.strip()]
    assert (
        len(lines) >= 90
    ), f"Expected ~97 state lines, got {len(lines)} for {tle_path.name}"
    for line in lines[:5]:
        parts: list[str] = line.split()
        assert len(parts) == 7, f"Expected 7 fields per line, got {len(parts)}: {line}"


def test_reconstructed_tle_preserves_elements(
    tle_round_trip: tuple[tle.Tle, tle.Tle],
) -> None:
    """Should reconstruct a TLE that preserves all orbital elements within tolerance.

    Parameters
    ----------
    tle_round_trip : tuple[tle.Tle, tle.Tle]
        Tuple of (original TLE, reconstructed TLE).
    """
    original: tle.Tle
    reconstructed: tle.Tle
    original, reconstructed = tle_round_trip

    # Mean motion
    assert reconstructed.mean_motion_rev_per_day == pytest.approx(
        original.mean_motion_rev_per_day, abs=MEAN_MOTION_TOL_REV_PER_DAY
    )

    # Inclination
    inc_tol: float = (
        GEO_INCLINATION_TOL_DEG if is_geo_orbit(original) else INCLINATION_TOL_DEG
    )
    assert reconstructed.inclination_deg == pytest.approx(
        original.inclination_deg, abs=inc_tol
    )

    # RAAN
    raan_tol: float = GEO_RAAN_TOL_DEG if is_geo_orbit(original) else RAAN_TOL_DEG
    raan_diff: float = angle_difference(reconstructed.raan_deg, original.raan_deg)
    assert raan_diff < raan_tol, (
        f"RAAN diff={raan_diff:.4f} > tol={raan_tol} "
        f"(orig={original.raan_deg:.4f}, recon={reconstructed.raan_deg:.4f})"
    )

    # Eccentricity
    assert reconstructed.eccentricity == pytest.approx(
        original.eccentricity, abs=ECCENTRICITY_TOL
    )

    # Argument of perigee
    aop_tol: float = (
        GEO_ARG_PERIGEE_TOL_DEG if is_geo_orbit(original) else ARG_PERIGEE_TOL_DEG
    )
    aop_diff: float = angle_difference(
        reconstructed.arg_perigee_deg, original.arg_perigee_deg
    )
    assert aop_diff < aop_tol, (
        f"Arg perigee diff={aop_diff:.4f} > tol={aop_tol} "
        f"(orig={original.arg_perigee_deg:.4f}, recon={reconstructed.arg_perigee_deg:.4f})"
    )

    # Mean anomaly
    ma_tol: float = (
        GEO_MEAN_ANOMALY_TOL_DEG if is_geo_orbit(original) else MEAN_ANOMALY_TOL_DEG
    )
    ma_diff: float = angle_difference(
        reconstructed.mean_anomaly_deg, original.mean_anomaly_deg
    )
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
