"""CLI and scenario defaults for orbit propagation.

Engine constants (SUPPORTED_INTEGRATOR_METHODS, INTEGRATOR_METHOD_DESCRIPTIONS,
DEFAULT_INTEGRATOR_METHOD, DEFAULT_BODIES_TO_CREATE, DEFAULT_GLOBAL_FRAME_ORIGIN,
DEFAULT_GLOBAL_FRAME_ORIENTATION) have moved to
``ephem_toolkit.core.propagator.numerical``.
"""

from __future__ import annotations

import ephem_toolkit.core.time_utils as time_utils

KILOMETERS_TO_METERS: float = 1e3
"""Conversion factor from kilometers to meters."""

# ===================================================================
# CLI and scenario defaults
# ===================================================================

DEFAULT_SATELLITE_NAME: str = "Satellite"
"""Default satellite body name used in the Tudat environment."""

DEFAULT_SATELLITE_DRAG_COEFFICIENT: float = 2.2
"""Default aerodynamic drag coefficient (Cd)."""

DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT: float = 1.2
"""Default solar radiation pressure coefficient (Cr)."""

DEFAULT_SATELLITE_MASS_KG: float = 30.0
"""Default satellite mass in kilograms."""

# ===================================================================
# 3U CubeSat geometry
# ===================================================================

DEFAULT_CUBESAT_LENGTH_M: float = 0.45
"""Default 3U CubeSat length in meters."""

DEFAULT_CUBESAT_WIDTH_M: float = 0.3
"""Default 3U CubeSat width in meters."""

DEFAULT_CUBESAT_HEIGHT_M: float = 0.3
"""Default 3U CubeSat height in meters."""

DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2: float = (
    4 * DEFAULT_CUBESAT_LENGTH_M * DEFAULT_CUBESAT_WIDTH_M
    + 2 * DEFAULT_CUBESAT_WIDTH_M * DEFAULT_CUBESAT_HEIGHT_M
) / 4
"""Default average projection area of a 3U CubeSat in m²."""

# ===================================================================
# Propagation scenario defaults
# ===================================================================

DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_DEGREE: int = 5
"""Default degree for Earth's spherical harmonic gravity field."""

DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_ORDER: int = 5
"""Default order for Earth's spherical harmonic gravity field."""

DEFAULT_SIMULATION_DURATION_S: float = time_utils.SECONDS_PER_DAY
"""Default simulation duration in seconds (1 day)."""

DEFAULT_INTEGRATOR_STEP_SIZE_S: tuple[float, ...] = (10.0, 1.0, 300.0)
"""Default integrator step sizes in seconds: ``(initial, minimum, maximum)``."""
