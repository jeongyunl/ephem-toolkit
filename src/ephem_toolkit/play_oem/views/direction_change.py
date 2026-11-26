"""Direction-change time-series view."""

from .orbit_time_series import OrbitTimeSeriesView
from .direction_change_impl import DirectionChangeImpl


class DirectionChangeView(OrbitTimeSeriesView):
    name = "direction-change"
    label = "Direction Change"
    group = "motion"

    def _create_delegate(self, start_time_s: float, object_name: object = ""):
        return DirectionChangeImpl(start_time_s, str(object_name))

__all__ = ["DirectionChangeView"]
