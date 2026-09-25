"""Shared diagnostic data structures for OEM fitting and comparison."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PropagationComparison:
    """Single propagation comparison record."""

    elapsed_s: float
    """Elapsed time from epoch (s)."""
    elapsed_min: float
    """Elapsed time from epoch (min)."""
    pos_err_km: float
    """Position error magnitude (km)."""
    vel_err_m_s: float
    """Velocity error magnitude (m/s)."""
    dx_km: float
    """Position error in the x-component (km)."""
    dy_km: float
    """Position error in the y-component (km)."""
    dz_km: float
    """Position error in the z-component (km)."""
    dvx_m_s: float
    """Velocity error in the x-component (m/s)."""
    dvy_m_s: float
    """Velocity error in the y-component (m/s)."""
    dvz_m_s: float
    """Velocity error in the z-component (m/s)."""


@dataclass
class FitDiagnostics:
    """Diagnostics from orbital element fitting."""

    rms_position_m: float
    """Root mean square position error (m)."""
    iterations: int
    """Number of iterations performed during fitting."""
    n_records: int
    """Number of state records used in the fit."""
    span_s: float
    """Time span of the fit arc (s)."""
    epoch_pos_delta_m: float | None = None
    """Position delta at epoch (m), if available."""
    epoch_vel_delta_m_s: float | None = None
    """Velocity delta at epoch (m/s), if available."""
    fit_method: str | None = None
    """Fitting method used, if available."""
