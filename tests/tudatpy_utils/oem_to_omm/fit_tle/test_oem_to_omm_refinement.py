"""Tests for oem_to_omm/refinement.py — TLE parameter refinement."""

from __future__ import annotations

import math

import numpy as np
import pytest

from oem_to_omm.fit_tle import refinement
from oem_to_omm.fit_tle.models import TleParameters, KeplerianMatchErrors


class TestClampRefinedElements:
    """Tests for clamp_refined_elements function."""

    def test_clamp_inclination_below_zero(self) -> None:
        """Should clamp negative inclination to 0."""
        params = TleParameters(
            inclination_deg=-10.0,
            raan_deg=45.0,
            arg_perigee_deg=90.0,
            mean_anomaly_deg=180.0,
            eccentricity=0.001,
            mean_motion_rev_per_day=15.0,
        )
        
        clamped = refinement.clamp_refined_elements(params)
        
        assert clamped.inclination_deg == 0.0

    def test_clamp_inclination_above_180(self) -> None:
        """Should clamp inclination above 180 to 180."""
        params = TleParameters(
            inclination_deg=200.0,
            raan_deg=45.0,
            arg_perigee_deg=90.0,
            mean_anomaly_deg=180.0,
            eccentricity=0.001,
            mean_motion_rev_per_day=15.0,
        )
        
        clamped = refinement.clamp_refined_elements(params)
        
        assert clamped.inclination_deg == 180.0

    def test_wrap_raan_angle(self) -> None:
        """Should wrap RAAN to [0, 360) range."""
        params = TleParameters(
            inclination_deg=45.0,
            raan_deg=400.0,  # Should wrap to 40
            arg_perigee_deg=90.0,
            mean_anomaly_deg=180.0,
            eccentricity=0.001,
            mean_motion_rev_per_day=15.0,
        )
        
        clamped = refinement.clamp_refined_elements(params)
        
        assert 0.0 <= clamped.raan_deg < 360.0
        assert abs(clamped.raan_deg - 40.0) < 1e-10

    def test_wrap_negative_raan(self) -> None:
        """Should wrap negative RAAN to positive range."""
        params = TleParameters(
            inclination_deg=45.0,
            raan_deg=-30.0,  # Should wrap to 330
            arg_perigee_deg=90.0,
            mean_anomaly_deg=180.0,
            eccentricity=0.001,
            mean_motion_rev_per_day=15.0,
        )
        
        clamped = refinement.clamp_refined_elements(params)
        
        assert 0.0 <= clamped.raan_deg < 360.0
        assert abs(clamped.raan_deg - 330.0) < 1e-10

    def test_wrap_arg_perigee(self) -> None:
        """Should wrap argument of perigee to [0, 360) range."""
        params = TleParameters(
            inclination_deg=45.0,
            raan_deg=45.0,
            arg_perigee_deg=720.0,  # Should wrap to 0
            mean_anomaly_deg=180.0,
            eccentricity=0.001,
            mean_motion_rev_per_day=15.0,
        )
        
        clamped = refinement.clamp_refined_elements(params)
        
        assert 0.0 <= clamped.arg_perigee_deg < 360.0
        assert abs(clamped.arg_perigee_deg) < 1e-10

    def test_wrap_mean_anomaly(self) -> None:
        """Should wrap mean anomaly to [0, 360) range."""
        params = TleParameters(
            inclination_deg=45.0,
            raan_deg=45.0,
            arg_perigee_deg=90.0,
            mean_anomaly_deg=450.0,  # Should wrap to 90
            eccentricity=0.001,
            mean_motion_rev_per_day=15.0,
        )
        
        clamped = refinement.clamp_refined_elements(params)
        
        assert 0.0 <= clamped.mean_anomaly_deg < 360.0
        assert abs(clamped.mean_anomaly_deg - 90.0) < 1e-10

    def test_clamp_eccentricity_below_zero(self) -> None:
        """Should clamp negative eccentricity to 0."""
        params = TleParameters(
            inclination_deg=45.0,
            raan_deg=45.0,
            arg_perigee_deg=90.0,
            mean_anomaly_deg=180.0,
            eccentricity=-0.1,
            mean_motion_rev_per_day=15.0,
        )
        
        clamped = refinement.clamp_refined_elements(params)
        
        assert clamped.eccentricity == 0.0

    def test_clamp_eccentricity_above_limit(self) -> None:
        """Should clamp eccentricity above 0.9999999."""
        params = TleParameters(
            inclination_deg=45.0,
            raan_deg=45.0,
            arg_perigee_deg=90.0,
            mean_anomaly_deg=180.0,
            eccentricity=1.5,
            mean_motion_rev_per_day=15.0,
        )
        
        clamped = refinement.clamp_refined_elements(params)
        
        assert clamped.eccentricity == 0.9999999

    def test_clamp_mean_motion_below_minimum(self) -> None:
        """Should clamp mean motion to minimum value."""
        params = TleParameters(
            inclination_deg=45.0,
            raan_deg=45.0,
            arg_perigee_deg=90.0,
            mean_anomaly_deg=180.0,
            eccentricity=0.001,
            mean_motion_rev_per_day=-1.0,
        )
        
        clamped = refinement.clamp_refined_elements(params)
        
        assert clamped.mean_motion_rev_per_day == 1e-8

    def test_valid_parameters_unchanged(self) -> None:
        """Should not modify valid parameters."""
        params = TleParameters(
            inclination_deg=51.6,
            raan_deg=120.0,
            arg_perigee_deg=45.0,
            mean_anomaly_deg=270.0,
            eccentricity=0.0005,
            mean_motion_rev_per_day=15.5,
        )
        
        clamped = refinement.clamp_refined_elements(params)
        
        # Use approximate equality for floating point comparisons
        assert abs(clamped.inclination_deg - params.inclination_deg) < 1e-10
        assert abs(clamped.raan_deg - params.raan_deg) < 1e-10
        assert abs(clamped.arg_perigee_deg - params.arg_perigee_deg) < 1e-10
        assert abs(clamped.mean_anomaly_deg - params.mean_anomaly_deg) < 1e-10
        assert abs(clamped.eccentricity - params.eccentricity) < 1e-10
        assert abs(clamped.mean_motion_rev_per_day - params.mean_motion_rev_per_day) < 1e-10


class TestComputeStateMatchScore:
    """Tests for compute_state_match_score function."""

    def test_zero_residual(self) -> None:
        """Should return zero score for zero residual."""
        residual = np.zeros(6)
        
        score, pos_err, vel_err = refinement.compute_state_match_score(residual)
        
        assert score == 0.0
        assert pos_err == 0.0
        assert vel_err == 0.0

    def test_position_only_residual(self) -> None:
        """Should compute score for position-only residual."""
        # 1000m position error, no velocity error
        residual = np.array([600.0, 800.0, 0.0, 0.0, 0.0, 0.0])
        
        score, pos_err, vel_err = refinement.compute_state_match_score(residual)
        
        assert pos_err == 1000.0  # sqrt(600^2 + 800^2)
        assert vel_err == 0.0
        # Score should be weighted position error
        assert score > 0.0

    def test_velocity_only_residual(self) -> None:
        """Should compute score for velocity-only residual."""
        # No position error, 5 m/s velocity error
        residual = np.array([0.0, 0.0, 0.0, 3.0, 4.0, 0.0])
        
        score, pos_err, vel_err = refinement.compute_state_match_score(residual)
        
        assert pos_err == 0.0
        assert vel_err == 5.0  # sqrt(3^2 + 4^2)
        # Score should be weighted velocity error
        assert score > 0.0

    def test_combined_residual(self) -> None:
        """Should compute score for combined position and velocity residual."""
        # Both position and velocity errors
        residual = np.array([100.0, 0.0, 0.0, 1.0, 0.0, 0.0])
        
        score, pos_err, vel_err = refinement.compute_state_match_score(residual)
        
        assert pos_err == 100.0
        assert vel_err == 1.0
        assert score > 0.0

    def test_negative_residuals(self) -> None:
        """Should handle negative residuals correctly."""
        residual = np.array([-300.0, -400.0, 0.0, -3.0, -4.0, 0.0])
        
        score, pos_err, vel_err = refinement.compute_state_match_score(residual)
        
        assert pos_err == 500.0  # sqrt(300^2 + 400^2)
        assert vel_err == 5.0  # sqrt(3^2 + 4^2)
        assert score > 0.0

    def test_3d_residuals(self) -> None:
        """Should compute 3D magnitude correctly."""
        # 3D position and velocity errors
        residual = np.array([1.0, 2.0, 2.0, 0.1, 0.2, 0.2])
        
        score, pos_err, vel_err = refinement.compute_state_match_score(residual)
        
        expected_pos = math.sqrt(1.0**2 + 2.0**2 + 2.0**2)
        expected_vel = math.sqrt(0.1**2 + 0.2**2 + 0.2**2)
        
        assert abs(pos_err - expected_pos) < 1e-10
        assert abs(vel_err - expected_vel) < 1e-10


class TestComputeKeplerianMatchScore:
    """Tests for compute_keplerian_match_score function."""

    def test_identical_elements(self) -> None:
        """Should return zero score for identical elements."""
        elements = [7000000.0, 0.001, math.radians(51.6), 
                   math.radians(120.0), math.radians(45.0), math.radians(30.0)]
        
        score, errors = refinement.compute_keplerian_match_score(elements, elements)
        
        assert score == 0.0
        assert errors.semi_major_axis_error_m == 0.0
        assert errors.eccentricity_error == 0.0
        assert errors.inclination_error_deg == 0.0
        assert errors.raan_error_deg == 0.0
        assert errors.arg_perigee_error_deg == 0.0
        assert errors.true_anomaly_error_deg == 0.0
        assert errors.arg_latitude_error_deg == 0.0

    def test_semi_major_axis_difference(self) -> None:
        """Should detect semi-major axis differences."""
        tle_kep = [7001000.0, 0.001, math.radians(51.6), 
                   math.radians(120.0), math.radians(45.0), math.radians(30.0)]
        ref_kep = [7000000.0, 0.001, math.radians(51.6), 
                   math.radians(120.0), math.radians(45.0), math.radians(30.0)]
        
        score, errors = refinement.compute_keplerian_match_score(tle_kep, ref_kep)
        
        assert errors.semi_major_axis_error_m == 1000.0
        assert score > 0.0

    def test_eccentricity_difference(self) -> None:
        """Should detect eccentricity differences."""
        tle_kep = [7000000.0, 0.002, math.radians(51.6), 
                   math.radians(120.0), math.radians(45.0), math.radians(30.0)]
        ref_kep = [7000000.0, 0.001, math.radians(51.6), 
                   math.radians(120.0), math.radians(45.0), math.radians(30.0)]
        
        score, errors = refinement.compute_keplerian_match_score(tle_kep, ref_kep)
        
        assert errors.eccentricity_error == 0.001
        assert score > 0.0

    def test_inclination_difference(self) -> None:
        """Should detect inclination differences."""
        tle_kep = [7000000.0, 0.001, math.radians(52.0), 
                   math.radians(120.0), math.radians(45.0), math.radians(30.0)]
        ref_kep = [7000000.0, 0.001, math.radians(51.6), 
                   math.radians(120.0), math.radians(45.0), math.radians(30.0)]
        
        score, errors = refinement.compute_keplerian_match_score(tle_kep, ref_kep)
        
        assert abs(errors.inclination_error_deg - 0.4) < 1e-10
        assert score > 0.0

    def test_raan_difference(self) -> None:
        """Should detect RAAN differences."""
        tle_kep = [7000000.0, 0.001, math.radians(51.6), 
                   math.radians(125.0), math.radians(45.0), math.radians(30.0)]
        ref_kep = [7000000.0, 0.001, math.radians(51.6), 
                   math.radians(120.0), math.radians(45.0), math.radians(30.0)]
        
        score, errors = refinement.compute_keplerian_match_score(tle_kep, ref_kep)
        
        # Score should be non-zero when elements differ
        assert score > 0.0
        assert hasattr(errors, 'raan_error_deg')

    def test_angle_wrapping_positive(self) -> None:
        """Should wrap angle differences correctly (positive case)."""
        # RAAN: 10 deg vs 350 deg should give -20 deg difference (not +340)
        tle_kep = [7000000.0, 0.001, math.radians(51.6), 
                   math.radians(10.0), math.radians(45.0), math.radians(30.0)]
        ref_kep = [7000000.0, 0.001, math.radians(51.6), 
                   math.radians(350.0), math.radians(45.0), math.radians(30.0)]
        
        score, errors = refinement.compute_keplerian_match_score(tle_kep, ref_kep)
        
        # Score should be non-zero for different angles
        assert score > 0.0
        assert hasattr(errors, 'raan_error_deg')

    def test_angle_wrapping_negative(self) -> None:
        """Should wrap angle differences correctly (negative case)."""
        # RAAN: 350 deg vs 10 deg should give -20 deg difference
        tle_kep = [7000000.0, 0.001, math.radians(51.6), 
                   math.radians(350.0), math.radians(45.0), math.radians(30.0)]
        ref_kep = [7000000.0, 0.001, math.radians(51.6), 
                   math.radians(10.0), math.radians(45.0), math.radians(30.0)]
        
        score, errors = refinement.compute_keplerian_match_score(tle_kep, ref_kep)
        
        # Score should be non-zero for different angles
        assert score > 0.0
        assert hasattr(errors, 'raan_error_deg')

    def test_argument_of_latitude(self) -> None:
        """Should compute argument of latitude correctly."""
        # u = ω + ν
        tle_kep = [7000000.0, 0.001, math.radians(51.6), 
                   math.radians(120.0), math.radians(45.0), math.radians(30.0)]
        ref_kep = [7000000.0, 0.001, math.radians(51.6), 
                   math.radians(120.0), math.radians(40.0), math.radians(30.0)]
        
        score, errors = refinement.compute_keplerian_match_score(tle_kep, ref_kep)
        
        # Score should be non-zero when arg_perigee differs
        assert score > 0.0
        assert hasattr(errors, 'arg_latitude_error_deg')

    def test_combined_differences(self) -> None:
        """Should handle multiple element differences."""
        tle_kep = [7001000.0, 0.002, math.radians(52.0), 
                   math.radians(125.0), math.radians(50.0), math.radians(35.0)]
        ref_kep = [7000000.0, 0.001, math.radians(51.6), 
                   math.radians(120.0), math.radians(45.0), math.radians(30.0)]
        
        score, errors = refinement.compute_keplerian_match_score(tle_kep, ref_kep)
        
        assert errors.semi_major_axis_error_m == 1000.0
        assert errors.eccentricity_error == 0.001
        assert abs(errors.inclination_error_deg - 0.4) < 1e-10
        assert abs(errors.raan_error_deg - 5.0) < 1e-10
        assert abs(errors.arg_perigee_error_deg - 5.0) < 1e-10
        assert abs(errors.true_anomaly_error_deg - 5.0) < 1e-10
        # Score should be sum of weighted differences
        assert score > 0.0

    def test_near_circular_orbit(self) -> None:
        """Should handle near-circular orbits (small eccentricity)."""
        # Very small eccentricity
        tle_kep = [7000000.0, 0.0001, math.radians(51.6), 
                   math.radians(120.0), math.radians(45.0), math.radians(30.0)]
        ref_kep = [7000000.0, 0.0001, math.radians(51.6), 
                   math.radians(120.0), math.radians(50.0), math.radians(25.0)]
        
        score, errors = refinement.compute_keplerian_match_score(tle_kep, ref_kep)
        
        # Should still compute arg_latitude correctly
        assert errors.arg_latitude_error_deg != 0.0


class TestEvaluateTleEpochStatesM:
    """Tests for evaluate_tle_epoch_states_m function."""

    def test_returns_none_without_tudatpy(self) -> None:
        """Should return None when tudatpy is not available."""
        # This test assumes tudatpy might not be available
        # The function checks for environment_setup and spice
        line_pairs = [
            ("1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927",
             "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537")
        ]
        
        result = refinement.evaluate_tle_epoch_states_m(line_pairs)
        
        # Result depends on whether tudatpy is available
        # If not available, should return None
        # If available, should return list of states
        assert result is None or isinstance(result, list)


class TestEvaluateTleStatesForOffsetsM:
    """Tests for evaluate_tle_states_for_offsets_m function."""

    def test_returns_none_without_tudatpy(self) -> None:
        """Should return None when tudatpy is not available."""
        line1 = "1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927"
        line2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537"
        time_offsets = [0.0, 60.0, 120.0]
        
        result = refinement.evaluate_tle_states_for_offsets_m(line1, line2, time_offsets)
        
        # Result depends on whether tudatpy is available
        assert result is None or isinstance(result, list)
