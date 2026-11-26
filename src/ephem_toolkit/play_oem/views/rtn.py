"""RTN-delta time-series view."""

from .legacy_rtn import LegacyRtnDeltaView
from .orbit_time_series import OrbitTimeSeriesView


class RtnDeltaView(OrbitTimeSeriesView):
    name = "rtn"
    label = "RTN Deltas"
    group = "motion"

    def _create_delegate(self, start_time_s: float, object_name: object = ""):
        return LegacyRtnDeltaView(start_time_s, str(object_name))

__all__ = ["RtnDeltaView"]
