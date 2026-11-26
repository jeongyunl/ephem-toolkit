"""Geocentric-distance time-series view."""

from .orbit_time_series import OrbitTimeSeriesView
from .distance_impl import GeocentricDistanceImpl


class GeocentricDistanceView(OrbitTimeSeriesView):
    name = "distance"
    label = "Geocentric Distance"
    group = "motion"

    def _create_delegate(self, start_time_s: float, object_name: object = ""):
        return GeocentricDistanceImpl(start_time_s, str(object_name))

__all__ = ["GeocentricDistanceView"]
