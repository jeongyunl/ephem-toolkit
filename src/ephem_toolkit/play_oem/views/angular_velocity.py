"""Angular-velocity time-series view."""

from .legacy_angular_velocity import LegacyAngularVelocityView
from .orbit_time_series import OrbitTimeSeriesView


class AngularVelocityView(OrbitTimeSeriesView):
    name = "angular-velocity"
    label = "Angular Velocity"
    group = "motion"

    def _create_delegate(self, start_time_s: float, object_name: object = ""):
        return LegacyAngularVelocityView(start_time_s, str(object_name))

__all__ = ["AngularVelocityView"]
