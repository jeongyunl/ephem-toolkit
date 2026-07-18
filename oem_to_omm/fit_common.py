from dataclasses import dataclass


@dataclass
class PropagationComparison:
    """Single propagation comparison record.

    Attributes
    ----------
    elapsed_s : float
        Elapsed time from epoch in seconds.
    elapsed_min : float
        Elapsed time from epoch in minutes.
    pos_err_km : float
        Position error magnitude in kilometers.
    vel_err_m_s : float
        Velocity error magnitude in meters per second.
    dx_km : float
        Position error in x-component in kilometers.
    dy_km : float
        Position error in y-component in kilometers.
    dz_km : float
        Position error in z-component in kilometers.
    dvx_m_s : float
        Velocity error in x-component in meters per second.
    dvy_m_s : float
        Velocity error in y-component in meters per second.
    dvz_m_s : float
        Velocity error in z-component in meters per second.
    """

    elapsed_s: float
    elapsed_min: float
    pos_err_km: float
    vel_err_m_s: float
    dx_km: float
    dy_km: float
    dz_km: float
    dvx_m_s: float
    dvy_m_s: float
    dvz_m_s: float


@dataclass
class FitDiagnostics:
    """Diagnostics from orbital element fitting.

    Attributes
    ----------
    rms_position_m : float
        Root mean square position error in meters.
    iterations : int
        Number of iterations performed during fitting.
    n_records : int
        Number of state records used in the fit.
    span_s : float
        Time span of the fit arc in seconds.
    epoch_pos_delta_m : float | None
        Position delta at epoch in meters (optional).
    epoch_vel_delta_m_s : float | None
        Velocity delta at epoch in m/s (optional).
    fit_method : str | None
        Fitting method used (optional, e.g., "mean_kepler_j2_velocity_fit").
    """

    rms_position_m: float
    iterations: int
    n_records: int
    span_s: float
    epoch_pos_delta_m: float | None = None
    epoch_vel_delta_m_s: float | None = None
    fit_method: str | None = None
