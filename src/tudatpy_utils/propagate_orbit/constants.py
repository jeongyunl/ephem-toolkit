"""Constants and default values for orbit propagation."""

from __future__ import annotations

import tudatpy_utils.core.time_utils as time_utils

KILOMETERS_TO_METERS: float = 1e3
"""Conversion factor from kilometers to meters."""

# ===================================================================
# CLI and model defaults
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
# Propagation settings
# ===================================================================

DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_DEGREE: int = 5
"""Default degree for Earth's spherical harmonic gravity field."""

DEFAULT_EARTH_SPHERICAL_HARMONIC_GRAVITY_ORDER: int = 5
"""Default order for Earth's spherical harmonic gravity field."""

DEFAULT_BODIES_TO_CREATE: list[str] = ["Sun", "Earth"]
"""Default list of celestial bodies always included in the environment."""

DEFAULT_GLOBAL_FRAME_ORIGIN: str = "Earth"
"""Default global frame origin for the Tudat environment."""

DEFAULT_GLOBAL_FRAME_ORIENTATION: str = "J2000"
"""Default global frame orientation for the Tudat environment."""

DEFAULT_SIMULATION_DURATION_S: float = time_utils.SECONDS_PER_DAY
"""Default simulation duration in seconds (1 day)."""

# ===================================================================
# Integrator configuration
# ===================================================================

# Supported integrator method identifiers accepted by the CLI.
# Values should match names in propagation_setup.integrator.CoefficientSets.
# Method descriptions are the single source of truth for supported methods.
INTEGRATOR_METHOD_DESCRIPTIONS: dict[str, str] = {
    "rk_3": "classic RK3",
    "rk_4": "classic RK4",
    "rkf_45": "Fehlberg 4(5)",
    "rkf_56": "Fehlberg 5(6)",
    "rkf_78": "Fehlberg 7(8)",
    "rkf_89": "Fehlberg 8(9)",
    "rkf_108": "Fehlberg 10(8)",
    "rkf_1210": "Fehlberg 12(10)",
    "rkf_1412": "Fehlberg 14(12)",
    "rkdp_87": "Dormand-Prince 8(7)",
    "rkv_89": "Verner 8(9)",
}
"""Mapping of integrator method identifiers to human-readable descriptions."""

SUPPORTED_INTEGRATOR_METHODS: tuple[str, ...] = tuple(INTEGRATOR_METHOD_DESCRIPTIONS)
"""Tuple of all supported integrator method identifier strings."""

DEFAULT_INTEGRATOR_METHOD: str = "rkdp_87"
"""Default numerical integrator method (Dormand-Prince 8(7))."""

DEFAULT_INTEGRATOR_STEP_SIZE_S: tuple[float, ...] = (10.0, 1.0, 300.0)
"""Default integrator step sizes in seconds: ``(initial, minimum, maximum)``."""
