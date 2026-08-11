"""Data models for TLE estimation.

Provides dataclasses for representing orbital elements, TLE parameters,
refinement results, and diagnostic quantities computed during the TLE
estimation process.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime

import numpy as np

from . import constants


@dataclass
class OrbitalElements:
    """Osculating Keplerian orbital elements computed from a Cartesian state.

    Angular quantities are in degrees and mean motion in revolutions per day,
    matching the native TLE representation.
    """

    semi_major_axis_m: float
    """Semi-major axis in m."""
    eccentricity: float
    """Eccentricity (dimensionless, 0 to <1)."""
    inclination_deg: float
    """Inclination in degrees."""
    raan_deg: float
    """Right ascension of ascending node in degrees."""
    arg_perigee_deg: float
    """Argument of perigee in degrees."""
    mean_anomaly_deg: float
    """Mean anomaly in degrees."""
    mean_motion_rev_per_day: float
    """Mean motion in revolutions per day."""

    def __repr__(self) -> str:
        return (
            f"OrbitalElements(semi_major_axis_m={self.semi_major_axis_m}, "
            f"eccentricity={self.eccentricity}, "
            f"inclination_deg={self.inclination_deg})"
        )


@dataclass
class KeplerianMatchErrors:
    """Element-wise Keplerian residuals from :func:`compute_keplerian_match_score`.

    All angular quantities are in degrees; semi-major axis in km.
    """

    semi_major_axis_error_m: float
    """Semi-major axis error in m (TLE minus reference)."""
    eccentricity_error: float
    """Eccentricity error (dimensionless)."""
    inclination_error_deg: float
    """Inclination error in degrees."""
    raan_error_deg: float
    """RAAN error in degrees."""
    arg_perigee_error_deg: float
    """Argument of perigee error in degrees."""
    true_anomaly_error_deg: float
    """True anomaly error in degrees."""
    arg_latitude_error_deg: float
    """Argument of latitude (ω+θ) error in degrees."""

    def __repr__(self) -> str:
        return (
            f"KeplerianMatchErrors(semi_major_axis_error_m={self.semi_major_axis_error_m}, "
            f"eccentricity_error={self.eccentricity_error}, "
            f"inclination_error_deg={self.inclination_error_deg})"
        )


@dataclass
class TleDeltas:
    """Per-element update vector for :class:`TleParameters` refinement.

    Holds one delta value per optimized orbital element, in the same field
    order as :class:`TleParameters`.  Produced by the Gauss-Newton solver and
    consumed by :meth:`TleParameters.apply_deltas`.
    """

    inclination_deg: float
    """Delta for inclination (degrees)."""
    raan_deg: float
    """Delta for RAAN (degrees)."""
    eccentricity: float
    """Delta for eccentricity (dimensionless)."""
    arg_perigee_deg: float
    """Delta for argument of perigee (degrees)."""
    mean_anomaly_deg: float
    """Delta for mean anomaly (degrees)."""
    mean_motion_rev_per_day: float
    """Delta for mean motion (revolutions per day)."""

    @classmethod
    def from_array(cls, arr: np.ndarray) -> TleDeltas:
        """Create from a 6-element numpy array in field declaration order.

        Parameters
        ----------
        arr : np.ndarray
            Array of shape (6,) with deltas in field order.

        Returns
        -------
        TleDeltas
            New instance populated from *arr*.
        """
        return cls(
            inclination_deg=float(arr[0]),
            raan_deg=float(arr[1]),
            eccentricity=float(arr[2]),
            arg_perigee_deg=float(arr[3]),
            mean_anomaly_deg=float(arr[4]),
            mean_motion_rev_per_day=float(arr[5]),
        )

    def __repr__(self) -> str:
        return (
            f"TleDeltas(inclination_deg={self.inclination_deg}, "
            f"raan_deg={self.raan_deg}, "
            f"eccentricity={self.eccentricity})"
        )


@dataclass
class TleParameters:
    """Partial TLE orbital element parameters used during refinement.

    This dataclass holds only the 6 orbital elements that are optimized
    during the refinement process, without the full TLE metadata.
    """

    inclination_deg: float
    """Inclination in degrees."""
    raan_deg: float
    """Right ascension of ascending node in degrees."""
    eccentricity: float
    """Eccentricity (dimensionless, 0 to <1)."""
    arg_perigee_deg: float
    """Argument of perigee in degrees."""
    mean_anomaly_deg: float
    """Mean anomaly in degrees."""
    mean_motion_rev_per_day: float
    """Mean motion in revolutions per day."""

    @classmethod
    def from_estimated(cls, estimated: Estimated) -> TleParameters:
        """Create from Estimated dataclass."""
        return cls(
            inclination_deg=estimated.inclination_deg,
            raan_deg=estimated.raan_deg,
            eccentricity=estimated.eccentricity,
            arg_perigee_deg=estimated.arg_perigee_deg,
            mean_anomaly_deg=estimated.mean_anomaly_deg,
            mean_motion_rev_per_day=estimated.mean_motion_rev_per_day,
        )

    def copy(self) -> TleParameters:
        """Create a copy of this TleParameters instance."""
        return replace(self)

    def perturb(self, field: str, delta: float) -> TleParameters:
        """Return a new instance with one field shifted by *delta*.

        Parameters
        ----------
        field : str
            Name of the field to perturb.
        delta : float
            Amount to add to the field value.

        Returns
        -------
        TleParameters
            New instance with the perturbed field.
        """
        return replace(self, **{field: getattr(self, field) + delta})

    def apply_to_estimated(self, estimated: Estimated) -> Estimated:
        """Return a copy of *estimated* with the 6 orbital element fields replaced.

        Parameters
        ----------
        estimated : Estimated
            Source dataclass whose non-orbital fields are preserved.

        Returns
        -------
        Estimated
            New instance with orbital elements taken from this :class:`TleParameters`.
        """
        return replace(
            estimated,
            inclination_deg=self.inclination_deg,
            raan_deg=self.raan_deg,
            eccentricity=self.eccentricity,
            arg_perigee_deg=self.arg_perigee_deg,
            mean_anomaly_deg=self.mean_anomaly_deg,
            mean_motion_rev_per_day=self.mean_motion_rev_per_day,
        )

    def write_back(self, estimated: Estimated) -> None:
        """Write the 6 orbital element fields back into *estimated* in-place.

        Parameters
        ----------
        estimated : Estimated
            Dataclass to update.
        """
        estimated.inclination_deg = self.inclination_deg
        estimated.raan_deg = self.raan_deg
        estimated.eccentricity = self.eccentricity
        estimated.arg_perigee_deg = self.arg_perigee_deg
        estimated.mean_anomaly_deg = self.mean_anomaly_deg
        estimated.mean_motion_rev_per_day = self.mean_motion_rev_per_day

    def apply_deltas(self, deltas: TleDeltas, scale: float = 1.0) -> TleParameters:
        """Return a new instance with fields shifted by a :class:`TleDeltas`.

        Parameters
        ----------
        deltas : TleDeltas
            Per-field delta values.
        scale : float
            Scalar multiplier applied to every delta (default: 1.0).

        Returns
        -------
        TleParameters
            New instance with all perturbed fields.
        """
        return TleParameters(
            inclination_deg=self.inclination_deg + deltas.inclination_deg * scale,
            raan_deg=self.raan_deg + deltas.raan_deg * scale,
            eccentricity=self.eccentricity + deltas.eccentricity * scale,
            arg_perigee_deg=self.arg_perigee_deg + deltas.arg_perigee_deg * scale,
            mean_anomaly_deg=self.mean_anomaly_deg + deltas.mean_anomaly_deg * scale,
            mean_motion_rev_per_day=self.mean_motion_rev_per_day
            + deltas.mean_motion_rev_per_day * scale,
        )

    def __repr__(self) -> str:
        return (
            f"TleParameters(inclination_deg={self.inclination_deg}, "
            f"raan_deg={self.raan_deg}, "
            f"eccentricity={self.eccentricity})"
        )


@dataclass
class OrbitalRecord:
    """Orbital element data for a single time point.

    This dataclass holds osculating orbital elements computed from a Cartesian
    state at a specific time, used for phase matching and element averaging.
    """

    t_day: float
    """Time offset from epoch in days."""
    raan_rad: float
    """Right ascension of ascending node in radians."""
    arg_perigee_rad: float
    """Argument of perigee in radians."""
    mean_anomaly_rad: float
    """Mean anomaly in radians."""
    mean_argument_latitude_rad: float
    """Mean argument of latitude (ω+M) in radians."""

    def __repr__(self) -> str:
        return (
            f"OrbitalRecord(t_day={self.t_day}, "
            f"raan_rad={self.raan_rad}, "
            f"arg_perigee_rad={self.arg_perigee_rad})"
        )


@dataclass
class PhaseMatchResult:
    """Result of phase matching at repeated orbital phases.

    This dataclass holds the averaged osculating angles and match statistics
    from the phase matching process.
    """

    count: int
    """Number of matched records."""
    raan_rad: float
    """Averaged right ascension of ascending node in radians."""
    arg_perigee_rad: float
    """Averaged argument of perigee in radians."""
    mean_anomaly_rad: float
    """Averaged mean anomaly in radians."""

    def __repr__(self) -> str:
        return (
            f"PhaseMatchResult(count={self.count}, "
            f"raan_rad={self.raan_rad}, "
            f"arg_perigee_rad={self.arg_perigee_rad})"
        )


@dataclass
class KeplerianAccuracy:
    """Osculating Keplerian element residuals from :func:`verify_accuracy_keplerian`.

    Holds element-wise errors (TLE minus reference), the reference osculating
    elements, and the TLE-derived osculating elements, all in consistent units
    (km for semi-major axis, degrees for angles).
    """

    # Element-wise errors (TLE minus reference)
    semi_major_axis_error_m: float
    """Semi-major axis error in m."""
    eccentricity_error: float
    """Eccentricity error (dimensionless)."""
    inclination_error_deg: float
    """Inclination error in degrees."""
    raan_error_deg: float
    """RAAN error in degrees."""
    arg_perigee_error_deg: float
    """Argument of perigee error in degrees."""
    true_anomaly_error_deg: float
    """True anomaly error in degrees."""
    arg_latitude_error_deg: float
    """Argument of latitude (ω+θ) error in degrees."""

    # Reference osculating elements
    ref_semi_major_axis_m: float
    """Reference semi-major axis in m."""
    ref_eccentricity: float
    """Reference eccentricity (dimensionless)."""
    ref_inclination_deg: float
    """Reference inclination in degrees."""
    ref_raan_deg: float
    """Reference RAAN in degrees."""
    ref_arg_perigee_deg: float
    """Reference argument of perigee in degrees."""
    ref_true_anomaly_deg: float
    """Reference true anomaly in degrees."""

    # TLE-derived osculating elements
    tle_semi_major_axis_m: float
    """TLE-derived semi-major axis in m."""
    tle_eccentricity: float
    """TLE-derived eccentricity (dimensionless)."""
    tle_inclination_deg: float
    """TLE-derived inclination in degrees."""
    tle_raan_deg: float
    """TLE-derived RAAN in degrees."""
    tle_arg_perigee_deg: float
    """TLE-derived argument of perigee in degrees."""
    tle_true_anomaly_deg: float
    """TLE-derived true anomaly in degrees."""

    def __repr__(self) -> str:
        return (
            f"KeplerianAccuracy(semi_major_axis_error_m={self.semi_major_axis_error_m}, "
            f"eccentricity_error={self.eccentricity_error}, "
            f"inclination_error_deg={self.inclination_error_deg})"
        )


@dataclass
class Estimated:
    """Estimated TLE elements and diagnostic quantities.

    This dataclass holds the estimated orbital elements and various diagnostic
    metrics computed during the TLE estimation process.
    """

    # Core TLE epoch fields
    epoch_datetime: datetime
    epoch_year: int
    epoch_day: float

    # Orbital elements
    inclination_deg: float
    raan_deg: float
    eccentricity: float
    arg_perigee_deg: float
    mean_anomaly_deg: float
    mean_motion_rev_per_day: float

    # Osculating values at epoch (for comparison)
    inclination_deg_osculating_at_epoch: float
    raan_deg_osculating_at_epoch: float
    arg_perigee_deg_osculating_at_epoch: float
    mean_anomaly_deg_osculating_at_epoch: float
    mean_motion_rev_per_day_osculating_at_epoch: float

    # Regression and rate estimates
    mean_motion_rev_per_day_regression_at_epoch: float
    mean_argument_latitude_rate_rev_per_day: float

    # Phase matching statistics
    phase_match_count: int
    phase_match_weight: float

    # Mean motion derivatives
    mean_motion_first_derivative: float
    mean_motion_first_derivative_raw: float

    # Orbital characteristics
    semi_major_axis_m: float
    dataset_slope_rev_per_day2: float

    # Optional B* drag term fields
    bstar: str | None = None
    bstar_source: str | None = None
    bstar_float: float | None = None
    bstar_fit_score: float | None = None

    # Optional state-match refinement fields
    state_match_refinement_used: bool | None = None
    state_match_iterations: int | None = None
    state_match_position_error_m: float | None = None
    state_match_velocity_error_m_s: float | None = None

    # Optional Keplerian-match refinement fields
    keplerian_match_refinement_used: bool | None = None
    keplerian_match_iterations: int | None = None
    keplerian_match_score: float | None = None
    keplerian_match_errors: KeplerianMatchErrors | None = None

    def __repr__(self) -> str:
        return (
            f"Estimated(epoch_year={self.epoch_year}, "
            f"epoch_day={self.epoch_day}, "
            f"inclination_deg={self.inclination_deg})"
        )
