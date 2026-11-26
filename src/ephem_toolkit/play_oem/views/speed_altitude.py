"""Speed/altitude time-series view."""

from .orbit_time_series import OrbitTimeSeriesView
from .speed_altitude_impl import SpeedAltitudeImpl


class SpeedAltitudeView(OrbitTimeSeriesView):
    name = "speed-altitude"
    label = "Speed / Altitude"
    group = "overview"

    def _create_delegate(self, start_time_s: float, *_delegate_args: object):
        return SpeedAltitudeImpl(start_time_s)

__all__ = ["SpeedAltitudeView"]
