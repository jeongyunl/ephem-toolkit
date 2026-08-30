"""Physical constants for Earth and orbital mechanics.

All constants use SI units (meters, seconds) with WGS-84 values where applicable.

References:
    https://en.wikipedia.org/wiki/World_Geodetic_System#WGS84
    https://en.wikipedia.org/wiki/Earth_radius
    https://en.wikipedia.org/wiki/Geopotential_model
    https://earth-info.nga.mil/index.php?dir=wgs84&action=wgs84 (NGA WGS-84 specification)
"""

from __future__ import annotations

EARTH_GRAVITATIONAL_PARAMETER_M3_S2: float = 3.986004418e14
"""Earth gravitational parameter (m³/s²), WGS-84."""

EARTH_EQUATORIAL_RADIUS_M: float = 6378136.3
"""Earth equatorial radius (m), WGS-84."""

EARTH_MEAN_RADIUS_M: float = 6371000.0
"""Earth mean radius (m), approximately 6371 km."""

EARTH_J2: float = 1.08262668e-3
"""Earth J2 zonal harmonic coefficient (dimensionless), WGS-84."""

EARTH_J3: float = -2.53265648e-6
"""Earth J3 zonal harmonic coefficient (dimensionless), WGS-84."""

EARTH_J4: float = -1.61962159e-6
"""Earth J4 zonal harmonic coefficient (dimensionless), WGS-84."""
