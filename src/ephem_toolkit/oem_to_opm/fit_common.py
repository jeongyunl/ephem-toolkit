"""Common data structures for orbital element fitting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PropagationComparison:
    """Single propagation comparison record."""

    elapsed_s: float
    """Elapsed time from epoch in seconds."""
    elapsed_min: float
    """Elapsed time from epoch in minutes."""
    pos_err_km: float
    """Position error magnitude in kilometers."""
    vel_err_m_s: float
    """Velocity error magnitude in meters per second."""
    dx_km: float
    """Position error in the x-component in kilometers."""
    dy_km: float
    """Position error in the y-component in kilometers."""
    dz_km: float
    """Position error in the z-component in kilometers."""
    dvx_m_s: float
    """Velocity error in the x-component in meters per second."""
    dvy_m_s: float
    """Velocity error in the y-component in meters per second."""
    dvz_m_s: float
    """Velocity error in the z-component in meters per second."""


@dataclass
class FitDiagnostics:
    """Diagnostics from orbital element fitting."""

    rms_position_m: float
    """Root mean square position error in meters."""
    iterations: int
    """Number of iterations performed during fitting."""
    n_records: int
    """Number of state records used in the fit."""
    span_s: float
    """Time span of the fit arc in seconds."""
    epoch_pos_delta_m: float | None = None
    """Position delta at epoch in meters, if available."""
    epoch_vel_delta_m_s: float | None = None
    """Velocity delta at epoch in meters per second, if available."""
    fit_method: str | None = None
    """Fitting method used, if available."""
    initial_position_rms_m: float | None = None
    """Position RMS before fitting, if available."""
