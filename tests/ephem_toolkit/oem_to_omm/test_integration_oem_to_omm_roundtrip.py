"""Tests for integration workflow: OEM → TLE → propagation round-trip."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest

import ephem_toolkit.core.convert_tle as convert_tle
import ephem_toolkit.core.ccsds.omm as omm
import ephem_toolkit.core.propagator.sgp4 as tle
import ephem_toolkit.propagate_tle.__main__ as propagate_tle_main
import ephem_toolkit.oem_to_omm.__main__ as oem_to_omm_main

TEST_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = TEST_DIR.parent.parent.parent
TEST_DATA_DIR: Path = TEST_DIR.parent.parent / "data"

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


def run_propagate_tle(tle_path: Path) -> str:
    """Run propagate_tle main function and return output.

    Parameters
    ----------
    tle_path : Path
        Path to TLE file to propagate.

    Returns
    -------
    str
        Standard output from propagate_tle.
    """
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        propagate_tle_main.main([str(tle_path), "-s", "15m", "--output", "-"])
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    assert output.strip(), f"propagate_tle produced no output for {tle_path.name}"
    return output


def run_oem_to_tle(
    oem_text: str, original: tle.Tle, refinement: str = "cartesian"
) -> str:
    """Run oem_to_omm main function and return output.

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
        Standard output from oem_to_omm.
    """
    # Build object_id from international designator
    object_id = f"{original.int_designator_year:02d}-{original.int_designator_launch_number:03d}{original.int_designator_piece or 'A'}"

    args: list[str] = [
        "--mode",
        "tle",
        "-",
        "--output",
        "-",
        "--object-name",
        original.object_name if original.object_name else "",
        "--object-id",
        object_id,
        "--tle-norad-cat-id",
        str(original.norad_cat_id),
        "--tle-classification-type",
        original.classification,
        "--tle-rev-at-epoch",
        str(original.revolution_number_at_epoch),
        "--tle-refinement",
        refinement,
    ]

    # Capture stdin and stdout
    old_stdin = sys.stdin
    old_stdout = sys.stdout
    sys.stdin = io.StringIO(oem_text)
    sys.stdout = io.StringIO()

    try:
        oem_to_omm_main.main(args)
        output = sys.stdout.getvalue()
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout

    return output


def parse_generated_tle_from_output(output: str) -> tle.Tle:
    """Parse TLE from oem_to_omm script output (OMM format).

    Parameters
    ----------
    output : str
        Standard output from oem_to_omm script (CCSDS OMM text).

    Returns
    -------
    tle.Tle
        Parsed TLE dataclass instance.
    """
    assert output.strip(), "oem_to_omm.py produced no output"
    assert (
        "CCSDS_OMM_VERS" in output
    ), f"Expected OMM output from oem_to_omm.py:\n{output[-500:]}"
    omm_obj: omm.CcsdsOmm = omm.CcsdsOmm.from_source(io.StringIO(output))
    tle_partial: tle.Tle = convert_tle.omm_to_tle(omm_obj)
    line1, line2 = tle.format_tle_strings(tle_partial)
    name: str = tle_partial.object_name or ""
    tle_text: str = f"{name}\n{line1}\n{line2}\n" if name else f"{line1}\n{line2}\n"
    return tle.read_tle(io.StringIO(tle_text))


def test_oem_to_omm_help_uses_command_name_and_format_aware_output() -> None:
    """The CLI help should use the canonical command name and output placeholder."""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        try:
            oem_to_omm_main.main(["--help"])
        except SystemExit as e:
            exit_code = e.code
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    assert exit_code == 0
    assert "usage: oem-to-omm" in output
    assert "--output <output_omm|->" in output
    assert "--mode <mean-kepler|tle>" in output


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
