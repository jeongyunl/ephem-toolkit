"""Angular-velocity time-series view."""

from .orbit_time_series import OrbitTimeSeriesView
from .angular_velocity_impl import AngularVelocityImpl


class AngularVelocityView(OrbitTimeSeriesView):
    name = "angular-velocity"
    label = "Angular Velocity"
    group = "motion"

    def _create_delegate(self, start_time_s: float, object_name: object = ""):
        return AngularVelocityImpl(start_time_s, str(object_name))

__all__ = ["AngularVelocityView"]
