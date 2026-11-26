"""Speed/altitude time-series view."""

from .legacy_speed_altitude import LegacySpeedAltitudeView
from .orbit_time_series import OrbitTimeSeriesView


class SpeedAltitudeView(OrbitTimeSeriesView):
    name = "speed-altitude"
    label = "Speed / Altitude"
    group = "overview"

    def _create_delegate(self, start_time_s: float, *_delegate_args: object):
        return LegacySpeedAltitudeView(start_time_s)

__all__ = ["SpeedAltitudeView"]
