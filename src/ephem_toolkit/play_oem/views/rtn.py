"""RTN-delta time-series view."""

from .orbit_time_series import OrbitTimeSeriesView
from .rtn_impl import RtnDeltaImpl


class RtnDeltaView(OrbitTimeSeriesView):
    name = "rtn"
    label = "RTN Deltas"
    group = "motion"

    def _create_delegate(self, start_time_s: float, object_name: object = ""):
        return RtnDeltaImpl(start_time_s, str(object_name))

__all__ = ["RtnDeltaView"]
