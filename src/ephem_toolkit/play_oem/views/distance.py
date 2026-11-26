"""Geocentric-distance time-series view."""

from .legacy_distance import LegacyGeocentricDistanceView
from .orbit_time_series import OrbitTimeSeriesView


class GeocentricDistanceView(OrbitTimeSeriesView):
    name = "distance"
    label = "Geocentric Distance"
    group = "motion"

    def _create_delegate(self, start_time_s: float, object_name: object = ""):
        return LegacyGeocentricDistanceView(start_time_s, str(object_name))

__all__ = ["GeocentricDistanceView"]
