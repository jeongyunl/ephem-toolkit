"""Data structures for orbit propagation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np


@dataclass
class PropagationInputs:
    """Container for propagation input options and parsed initial-state data."""

    satellite_name: str
    """Name of the propagated vehicle body added to the Tudat environment"""
    satellite_mass_kg: float
    """Spacecraft mass (kg) used by dynamics propagation"""

    integrator_method: str
    """Numerical integrator method identifier used by propagation settings"""
    integrator_step_size_values_s: tuple[float, ...]
    """Step-size input (seconds) from CLI; one value = fixed step, three values (initial, min, max) = variable step"""

    earth_spherical_harmonic_gravity_degree: int
    """Degree used for Earth's spherical harmonic gravity field"""
    earth_spherical_harmonic_gravity_order: int
    """Order used for Earth's spherical harmonic gravity field"""

    satellite_drag_area_m2: float
    """Effective drag/reference area (m²) used for aerodynamic drag and SRP cannonball model"""

    is_srp_on: bool
    """Whether solar radiation pressure acceleration is enabled"""
    srp_coefficient: float
    """Dimensionless solar radiation pressure coefficient (Cr) used when SRP is enabled"""

    is_earth_drag_on: bool
    """Whether aerodynamic drag acceleration from Earth's atmosphere is enabled"""
    satellite_drag_coefficient: float
    """Dimensionless aerodynamic drag coefficient (Cd) used when drag is enabled"""

    is_moon_gravity_on: bool
    """Whether Moon point-mass gravity perturbation is enabled"""
    is_sun_gravity_on: bool
    """Whether Sun point-mass gravity perturbation is enabled"""
    is_venus_gravity_on: bool
    """Whether Venus point-mass gravity perturbation is enabled"""
    is_mars_gravity_on: bool
    """Whether Mars point-mass gravity perturbation is enabled"""

    initial_epoch_datetime_utc: datetime
    """Start epoch parsed from OEM input, represented as a UTC datetime"""
    initial_state_m_m_s: np.ndarray
    """Initial translational state vector [x, y, z, vx, vy, vz] in SI units (m, m/s)"""

    simulation_duration_s: float
    """Total propagation duration (seconds)"""
