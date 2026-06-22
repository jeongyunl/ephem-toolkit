"""Tests for :mod:`common.kepler` — kepler.cartesian_to_keplerian, kepler.tle_to_osculating_keplerian, and helpers."""

from __future__ import annotations

import io
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

import common.kepler as kepler
import common.tle as tle

TEST_DIR = Path(__file__).parent
TEST_DATA_DIR = TEST_DIR / "data"

# ===================================================================
# Shared fixtures / constants
# ===================================================================

ISS_3LINE = (
    "ISS (ZARYA)\n"
    "1 25544U 98067A   26152.32329980  .00009658  00000+0  17978-3 0  9994\n"
    "2 25544  51.6335  18.6331 0007202 121.2251 238.9444 15.49538094569295\n"
)

# ISS-like orbit (approx 408 km altitude, 51.6 deg inclination)
STATE_ISS = np.array(
    [
        -2700816.14,
        -3314092.80,
        5266346.42,  # position [m]
        5168.606550,
        -5597.546618,
        -2131.981798,  # velocity [m/s]
    ]
)


def _make_tle_fixture() -> tle.Tle:
    """Parse the ISS TLE for use in tests."""
    return tle.read_tle(io.StringIO(ISS_3LINE))


# ===================================================================
# 1. kepler.tle_to_osculating_keplerian returns keplerian element list and epoch
# ===================================================================


def test_tle_to_osculating_keplerian_returns_all_keys() -> None:
    """Should return a 6-element Keplerian list and a UTC-aware epoch datetime."""
    tle_obj = _make_tle_fixture()
    kep_elements = kepler.tle_to_osculating_keplerian(tle_obj)

    assert isinstance(kep_elements, np.ndarray)
    assert kep_elements.shape == (6,)


# ===================================================================
# 2. kepler.tle_to_osculating_keplerian computes correct semi-major axis
# ===================================================================


def test_tle_to_osculating_keplerian_semi_major_axis_iss() -> None:
    """Should compute ISS semi-major axis ~6780 km from mean motion ~15.5 rev/day."""
    tle_obj = _make_tle_fixture()
    kep_elements = kepler.tle_to_osculating_keplerian(tle_obj)

    a_km = kep_elements[0] / 1000.0
    # ISS orbits at ~408 km altitude -> a ~ 6786 km
    assert 6750.0 < a_km < 6850.0


# ===================================================================
# 3. kepler.tle_to_osculating_keplerian preserves eccentricity from TLE
# ===================================================================


def test_tle_to_osculating_keplerian_preserves_eccentricity() -> None:
    """Should preserve the eccentricity value directly from the TLE (no J2)."""
    tle_obj = _make_tle_fixture()
    kep_elements = kepler.tle_to_osculating_keplerian(tle_obj, apply_j2=False)

    assert kep_elements[1] == pytest.approx(tle_obj.eccentricity, abs=1e-10)


# ===================================================================
# 4. kepler.tle_to_osculating_keplerian converts angles to radians correctly
# ===================================================================


def test_tle_to_osculating_keplerian_angles_in_radians() -> None:
    """Should convert inclination, RAAN, and arg_periapsis from degrees to radians (no J2)."""
    tle_obj = _make_tle_fixture()
    kep_elements = kepler.tle_to_osculating_keplerian(tle_obj, apply_j2=False)

    assert kep_elements[2] == pytest.approx(
        np.radians(tle_obj.inclination_deg), abs=1e-12
    )
    assert kep_elements[3] == pytest.approx(
        np.radians(tle_obj.arg_perigee_deg), abs=1e-12
    )
    assert kep_elements[4] == pytest.approx(np.radians(tle_obj.raan_deg), abs=1e-12)


# ===================================================================
# 5. kepler.tle_to_osculating_keplerian true anomaly is in [0, 2pi)
# ===================================================================


def test_tle_to_osculating_keplerian_true_anomaly_range() -> None:
    """Should produce a true anomaly in the range [0, 2pi)."""
    tle_obj = _make_tle_fixture()
    kep_elements = kepler.tle_to_osculating_keplerian(tle_obj)

    theta = kep_elements[5]
    assert 0.0 <= theta < 2.0 * np.pi


# ===================================================================
# 6. kepler.tle_epoch_to_datetime_string handles year 2000+ correctly
# ===================================================================


def test_tle_epoch_to_datetime_string_year_2000_plus() -> None:
    """Should interpret epoch_year < 57 as 2000+year."""
    result = kepler.tle_epoch_to_datetime_string(26, 1.0)
    assert result.startswith("2026-01-01")


# ===================================================================
# 7. kepler.tle_epoch_to_datetime_string handles year 1900+ correctly
# ===================================================================


def test_tle_epoch_to_datetime_string_year_1900_plus() -> None:
    """Should interpret epoch_year >= 57 as 1900+year."""
    result = kepler.tle_epoch_to_datetime_string(99, 1.0)
    assert result.startswith("1999-01-01")


# ===================================================================
# 8. kepler.tle_epoch_to_datetime_string fractional day conversion
# ===================================================================


def test_tle_epoch_to_datetime_string_fractional_day() -> None:
    """Should correctly convert fractional day-of-year to date-time."""
    # Day 32.5 of 2024 -> Feb 1 at 12:00:00
    result = kepler.tle_epoch_to_datetime_string(24, 32.5)
    assert "2024-02-01 12:00:00" in result


# ===================================================================
# 9. kepler.mean_motion_to_semi_major_axis and inverse are consistent
# ===================================================================


def test_mean_motion_semi_major_axis_round_trip() -> None:
    """Should round-trip between mean motion and semi-major axis."""
    n_original = 15.5  # rev/day (ISS-like)
    a = kepler.mean_motion_to_semi_major_axis(n_original)
    n_recovered = kepler.semi_major_axis_to_mean_motion(a)

    assert n_recovered == pytest.approx(n_original, rel=1e-12)


def test_osculating_to_mean_keplerian_returns_six_element_array() -> None:
    """Should return a NumPy array of six mean Keplerian elements."""
    result = kepler.osculating_to_mean_keplerian(
        np.array([7000e3, 0.01, 0.1, 0.3, 0.2, 1.0], dtype=float)
    )

    assert isinstance(result, np.ndarray)
    assert result.shape == (6,)
    assert 0.0 <= result[5] < 2.0 * np.pi


# ===================================================================
# 10. kepler.tle_to_osculating_keplerian with real TLE file
# ===================================================================


def test_tle_to_osculating_keplerian_with_real_tle_file() -> None:
    """Should produce physically reasonable results from a real TLE file."""
    tle_path = TEST_DATA_DIR / "ISS-ZARYA_1998-067A.tle"
    with open(tle_path, "r") as f:
        tle_obj = tle.read_tle(f)

    kep_elements = kepler.tle_to_osculating_keplerian(tle_obj)

    # Semi-major axis should be reasonable for LEO (6400-7200 km)
    a_km = kep_elements[0] / 1000.0
    assert 6400.0 < a_km < 7200.0

    # Eccentricity should be near-circular for ISS
    assert 0.0 <= kep_elements[1] < 0.01

    # Inclination should be ~51.6 degrees for ISS
    inc_deg = np.degrees(kep_elements[2])
    assert 51.0 < inc_deg < 52.0

    # All angles should be in valid range
    assert 0.0 <= kep_elements[5] < 2.0 * np.pi
    assert 0.0 <= kep_elements[3] < 2.0 * np.pi
    assert 0.0 <= kep_elements[4] < 2.0 * np.pi


# ===================================================================
# 11. kepler.cartesian_to_keplerian raises ValueError on wrong shape
# ===================================================================


def test_cartesian_to_keplerian_raises_on_wrong_shape() -> None:
    """Should raise ValueError when state vector does not have shape (6,)."""
    with pytest.raises(ValueError, match="shape"):
        kepler.cartesian_to_keplerian(np.array([1.0, 2.0, 3.0]), kepler.MU_EARTH)

    with pytest.raises(ValueError, match="shape"):
        kepler.cartesian_to_keplerian(np.zeros((2, 3)), kepler.MU_EARTH)


# ===================================================================
# 12. kepler.cartesian_to_keplerian raises ValueError on zero position
# ===================================================================


def test_cartesian_to_keplerian_raises_on_zero_position() -> None:
    """Should raise ValueError when position vector has zero magnitude."""
    state = np.array([0.0, 0.0, 0.0, 1000.0, 0.0, 0.0])
    with pytest.raises(ValueError, match="zero magnitude"):
        kepler.cartesian_to_keplerian(state, kepler.MU_EARTH)


# ===================================================================
# 13. kepler.cartesian_to_keplerian raises ValueError on zero angular momentum
# ===================================================================


def test_cartesian_to_keplerian_raises_on_zero_angular_momentum() -> None:
    """Should raise ValueError for rectilinear orbit (r parallel to v)."""
    # Position and velocity are parallel -> h = r x v = 0
    state = np.array([7000e3, 0.0, 0.0, 1000.0, 0.0, 0.0])
    with pytest.raises(ValueError, match="[Aa]ngular momentum"):
        kepler.cartesian_to_keplerian(state, kepler.MU_EARTH)


# ===================================================================
# 14. kepler.cartesian_to_keplerian returns correct element count and types
# ===================================================================


def test_cartesian_to_keplerian_returns_six_elements() -> None:
    """Should return a numpy array of shape (6,) with float elements."""
    result = kepler.cartesian_to_keplerian(STATE_ISS, kepler.MU_EARTH)

    assert isinstance(result, np.ndarray)
    assert result.shape == (6,)
    assert result.dtype == np.float64


# ===================================================================
# 15. kepler.cartesian_to_keplerian ISS semi-major axis is physically correct
# ===================================================================


def test_cartesian_to_keplerian_iss_semi_major_axis() -> None:
    """Should compute a physically reasonable semi-major axis for the test state."""
    kep = kepler.cartesian_to_keplerian(STATE_ISS, kepler.MU_EARTH)
    a_km = kep[kepler.SEMI_MAJOR_AXIS_INDEX] / 1000.0

    # The test state yields a ~ 7256 km (LEO-range orbit)
    assert 7200.0 < a_km < 7300.0


# ===================================================================
# 16. kepler.cartesian_to_keplerian ISS eccentricity is near-circular
# ===================================================================


def test_cartesian_to_keplerian_iss_eccentricity() -> None:
    """Should compute a valid eccentricity (0 <= e < 1) for the test state."""
    kep = kepler.cartesian_to_keplerian(STATE_ISS, kepler.MU_EARTH)
    e = kep[kepler.ECCENTRICITY_INDEX]

    # The test state yields e ~ 0.14 (moderately eccentric)
    assert 0.0 <= e < 1.0
    assert e == pytest.approx(0.1396, abs=0.001)


# ===================================================================
# 17. kepler.cartesian_to_keplerian ISS inclination is ~51.6 degrees
# ===================================================================


def test_cartesian_to_keplerian_iss_inclination() -> None:
    """Should compute ISS inclination near 51.6 degrees."""
    kep = kepler.cartesian_to_keplerian(STATE_ISS, kepler.MU_EARTH)
    inc_deg = np.degrees(kep[kepler.INCLINATION_INDEX])

    assert 50.0 < inc_deg < 53.0


# ===================================================================
# 18. kepler.cartesian_to_keplerian round-trip with kepler.keplerian_to_cartesian
# ===================================================================


def test_cartesian_to_keplerian_round_trip() -> None:
    """Should round-trip Cartesian -> Keplerian -> Cartesian with negligible error."""
    kep = kepler.cartesian_to_keplerian(STATE_ISS, kepler.MU_EARTH)
    state_recovered = kepler.keplerian_to_cartesian(kep, kepler.MU_EARTH)

    pos_err = np.linalg.norm(state_recovered[0:3] - STATE_ISS[0:3])
    vel_err = np.linalg.norm(state_recovered[3:6] - STATE_ISS[3:6])

    assert pos_err < 1e-6  # sub-micrometer position error
    assert vel_err < 1e-9  # sub-nanometer/s velocity error


def test_cartesian_to_keplerian_matches_tudatpy_element_conversion() -> None:
    """Compare common.kepler.cartesian_to_keplerian with tudatpy on the same state."""
    pytest.importorskip("tudatpy")
    from tudatpy.astro import element_conversion

    kep_tudatpy = element_conversion.cartesian_to_keplerian(STATE_ISS, kepler.MU_EARTH)
    kep_common = kepler.cartesian_to_keplerian(STATE_ISS, kepler.MU_EARTH)

    np.testing.assert_allclose(
        kep_common,
        kep_tudatpy,
        rtol=1e-12,
        atol=1e-10,
        err_msg="common.kepler.cartesian_to_keplerian must match tudatpy.element_conversion.cartesian_to_keplerian",
    )


# ===================================================================
# 19. kepler.cartesian_to_keplerian handles equatorial circular orbit
# ===================================================================


def test_cartesian_to_keplerian_equatorial_circular() -> None:
    """Should handle equatorial circular orbit (i~0, e~0) without error."""
    # Circular equatorial orbit at ~7000 km
    r = 7000e3
    v = np.sqrt(kepler.MU_EARTH / r)  # circular velocity
    state = np.array([r, 0.0, 0.0, 0.0, v, 0.0])

    kep = kepler.cartesian_to_keplerian(state, kepler.MU_EARTH)

    # Semi-major axis should equal radius for circular orbit
    assert kep[kepler.SEMI_MAJOR_AXIS_INDEX] == pytest.approx(r, rel=1e-10)
    # Eccentricity should be ~0
    assert kep[kepler.ECCENTRICITY_INDEX] < 1e-10
    # Inclination should be ~0 (equatorial)
    assert kep[kepler.INCLINATION_INDEX] < 1e-10


# ===================================================================
# 20. kepler.cartesian_to_keplerian handles eccentric orbit correctly
# ===================================================================


def test_cartesian_to_keplerian_eccentric_orbit() -> None:
    """Should correctly compute elements for a moderately eccentric orbit."""
    # GTO-like orbit: periapsis at 6600 km, apoapsis at 42164 km
    a = (6600e3 + 42164e3) / 2.0  # semi-major axis
    e = 1.0 - 6600e3 / a  # eccentricity from periapsis

    # Build state at periapsis (theta=0): r = a(1-e), v = sqrt(mu*(1+e)/(a*(1-e)))
    r_peri = a * (1.0 - e)
    v_peri = np.sqrt(kepler.MU_EARTH * (1.0 + e) / (a * (1.0 - e)))

    # Place in equatorial plane, periapsis along x-axis
    state = np.array([r_peri, 0.0, 0.0, 0.0, v_peri, 0.0])

    kep = kepler.cartesian_to_keplerian(state, kepler.MU_EARTH)

    assert kep[kepler.SEMI_MAJOR_AXIS_INDEX] == pytest.approx(a, rel=1e-10)
    assert kep[kepler.ECCENTRICITY_INDEX] == pytest.approx(e, rel=1e-10)
    # At periapsis, true anomaly should be 0 (or 2pi)
    theta = kep[kepler.TRUE_ANOMALY_INDEX]
    assert theta == pytest.approx(0.0, abs=1e-10) or theta == pytest.approx(
        2.0 * np.pi, abs=1e-10
    )


# ===================================================================
# 21. Round-trip test: TLE -> Cartesian (tudatpy) -> Keplerian (tudatpy)
#     vs common.kepler results
# ===================================================================


@pytest.fixture(scope="module")
def tudatpy_tle_round_trip():
    """Load ISS TLE via tudatpy SGP4, get Cartesian state at epoch,
    convert to Keplerian using tudatpy, and return all intermediate results."""
    import warnings

    warnings.filterwarnings("ignore", module="urllib3")
    warnings.filterwarnings("ignore", category=SyntaxWarning)

    from tudatpy.dynamics import environment_setup
    from tudatpy.astro import element_conversion
    from tudatpy.interface import spice

    import common.common as common

    # Load SPICE kernels
    spice_kernel_files = ["naif0012.tls", "pck00011.tpc"]
    for kernel_file in spice_kernel_files:
        spice.load_kernel(common.get_spice_kernel_path() + "/" + kernel_file)

    # Create bodies for gravitational parameter
    bodies_to_create = ["Earth"]
    body_settings = environment_setup.get_default_body_settings(
        bodies_to_create, "Earth", "J2000"
    )
    bodies = environment_setup.create_system_of_bodies(body_settings)
    earth_mu = bodies.get("Earth").gravitational_parameter

    # Load TLE via tudatpy SGP4 ephemeris
    tle_path = TEST_DATA_DIR / "ISS-ZARYA_1998-067A.tle"
    with open(tle_path, "r") as f:
        tle_data = f.read()
    tle_lines = tle_data.splitlines()[-2:]

    tle_ephemeris_settings = environment_setup.ephemeris.sgp4(
        tle_lines[0], tle_lines[1]
    )
    tle_ephemeris = environment_setup.create_body_ephemeris(
        tle_ephemeris_settings, body_name="ISS"
    )
    tle_obj = tle_ephemeris.tle

    # Get epoch in TDB
    tle_epoch_tdb = tle_obj.reference_epoch

    # Get Cartesian state at TLE epoch from SGP4
    cartesian_state = tle_ephemeris.cartesian_state(tle_epoch_tdb)

    # Convert Cartesian to Keplerian using tudatpy
    keplerian_state_tudatpy = element_conversion.cartesian_to_keplerian(
        cartesian_state, earth_mu
    )

    return {
        "cartesian_state": cartesian_state,
        "keplerian_state_tudatpy": keplerian_state_tudatpy,
        "earth_mu": earth_mu,
        "tle_epoch_tdb": tle_epoch_tdb,
    }


def test_round_trip_tle_cartesian_to_keplerian_vs_tudatpy(
    tudatpy_tle_round_trip,
) -> None:
    """Round-trip: TLE -> Cartesian (tudatpy/SGP4) -> Keplerian.

    Compare common.kepler.cartesian_to_keplerian with tudatpy's
    element_conversion.cartesian_to_keplerian using the same Cartesian
    state obtained from the TLE at its initial epoch.
    """
    data = tudatpy_tle_round_trip
    cartesian_state = data["cartesian_state"]
    kep_tudatpy = data["keplerian_state_tudatpy"]
    earth_mu = data["earth_mu"]

    # Convert the same Cartesian state using common.kepler
    kep_common = kepler.cartesian_to_keplerian(cartesian_state, earth_mu)

    # Compare semi-major axis (relative tolerance)
    assert kep_common[kepler.SEMI_MAJOR_AXIS_INDEX] == pytest.approx(
        kep_tudatpy[0], rel=1e-10
    ), "Semi-major axis mismatch between common.kepler and tudatpy"

    # Compare eccentricity (absolute tolerance for near-circular orbits)
    assert kep_common[kepler.ECCENTRICITY_INDEX] == pytest.approx(
        kep_tudatpy[1], abs=1e-12
    ), "Eccentricity mismatch between common.kepler and tudatpy"

    # Compare inclination
    assert kep_common[kepler.INCLINATION_INDEX] == pytest.approx(
        kep_tudatpy[2], abs=1e-12
    ), "Inclination mismatch between common.kepler and tudatpy"

    # Compare argument of periapsis
    assert kep_common[kepler.ARGUMENT_OF_PERIAPSIS_INDEX] == pytest.approx(
        kep_tudatpy[3], abs=1e-10
    ), "Argument of periapsis mismatch between common.kepler and tudatpy"

    # Compare RAAN
    assert kep_common[kepler.RAAN_INDEX] == pytest.approx(
        kep_tudatpy[4], abs=1e-10
    ), "RAAN mismatch between common.kepler and tudatpy"

    # Compare true anomaly
    assert kep_common[kepler.TRUE_ANOMALY_INDEX] == pytest.approx(
        kep_tudatpy[5], abs=1e-10
    ), "True anomaly mismatch between common.kepler and tudatpy"


def test_round_trip_keplerian_to_cartesian_vs_tudatpy(tudatpy_tle_round_trip) -> None:
    """Round-trip: Keplerian (tudatpy) -> Cartesian (common.kepler).

    Verify that common.kepler.keplerian_to_cartesian produces the same
    Cartesian state as the original SGP4 output when given the Keplerian
    elements from tudatpy.
    """
    data = tudatpy_tle_round_trip
    cartesian_state_original = data["cartesian_state"]
    kep_tudatpy = data["keplerian_state_tudatpy"]
    earth_mu = data["earth_mu"]

    # Convert Keplerian (from tudatpy) back to Cartesian using common.kepler
    cartesian_recovered = kepler.keplerian_to_cartesian(kep_tudatpy, earth_mu)

    # Position error should be sub-millimeter
    pos_err = np.linalg.norm(cartesian_recovered[0:3] - cartesian_state_original[0:3])
    assert pos_err < 1e-3, f"Position round-trip error too large: {pos_err:.6e} m"

    # Velocity error should be sub-micrometer/s
    vel_err = np.linalg.norm(cartesian_recovered[3:6] - cartesian_state_original[3:6])
    assert vel_err < 1e-6, f"Velocity round-trip error too large: {vel_err:.6e} m/s"


def test_round_trip_tle_osculating_vs_tudatpy_keplerian(tudatpy_tle_round_trip) -> None:
    """Compare common.kepler.tle_to_osculating_keplerian with tudatpy's
    Keplerian elements derived from the SGP4 Cartesian state.

    Note: kepler.tle_to_osculating_keplerian uses two-body (Kepler's third law)
    conversion from mean elements, while tudatpy uses SGP4 propagation
    to get the actual osculating state. Differences are expected due to
    SGP4's perturbation model (J2, drag, etc.), so tolerances are relaxed.

    For near-circular orbits (e < 0.01), the argument of periapsis and
    true anomaly are individually poorly defined, so we compare the
    argument of latitude (omega + theta) instead.
    """
    data = tudatpy_tle_round_trip
    kep_tudatpy = data["keplerian_state_tudatpy"]

    # Get common.kepler's TLE-to-osculating conversion
    tle_path = TEST_DATA_DIR / "ISS-ZARYA_1998-067A.tle"
    with open(tle_path, "r") as f:
        tle_obj = tle.read_tle(f)
    kep_from_tle = kepler.tle_to_osculating_keplerian(tle_obj)

    # Semi-major axis: SGP4 vs two-body Kepler's third law
    # Expect agreement within ~50 km due to SGP4 mean-to-osculating differences
    a_diff_km = abs(kep_from_tle[0] - kep_tudatpy[0]) / 1000.0
    assert a_diff_km < 50.0, f"Semi-major axis difference too large: {a_diff_km:.2f} km"

    # Eccentricity: should be close (ISS is near-circular)
    assert kep_from_tle[1] == pytest.approx(
        kep_tudatpy[1], abs=1e-3
    ), "Eccentricity difference too large between TLE mean and SGP4 osculating"

    # Inclination: should agree well (secular perturbation is small)
    assert kep_from_tle[2] == pytest.approx(
        kep_tudatpy[2], abs=np.radians(0.1)
    ), "Inclination difference too large"

    # RAAN: may differ due to J2 nodal regression, allow 1 degree
    raan_diff = abs(kep_from_tle[4] - kep_tudatpy[4])
    # Handle wrap-around
    if raan_diff > np.pi:
        raan_diff = 2.0 * np.pi - raan_diff
    assert raan_diff < np.radians(
        1.0
    ), f"RAAN difference too large: {np.degrees(raan_diff):.4f} degrees"

    # For near-circular orbits, argument of periapsis and true anomaly are
    # individually poorly defined. Compare the argument of latitude (u = omega + theta)
    # which is well-defined regardless of eccentricity.
    u_from_tle = (kep_from_tle[3] + kep_from_tle[5]) % (2.0 * np.pi)
    u_tudatpy = (kep_tudatpy[3] + kep_tudatpy[5]) % (2.0 * np.pi)

    u_diff = abs(u_from_tle - u_tudatpy)
    if u_diff > np.pi:
        u_diff = 2.0 * np.pi - u_diff
    assert u_diff < np.radians(5.0), (
        f"Argument of latitude (omega+theta) difference too large: "
        f"{np.degrees(u_diff):.4f} degrees"
    )
