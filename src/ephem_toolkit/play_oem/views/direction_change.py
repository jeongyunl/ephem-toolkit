"""Direction-change time-series view."""

from .legacy_direction_change import LegacyDirectionChangeView
from .orbit_time_series import OrbitTimeSeriesView


class DirectionChangeView(OrbitTimeSeriesView):
    name = "direction-change"
    label = "Direction Change"
    group = "motion"

    def _create_delegate(self, start_time_s: float, object_name: object = ""):
        return LegacyDirectionChangeView(start_time_s, str(object_name))

__all__ = ["DirectionChangeView"]
