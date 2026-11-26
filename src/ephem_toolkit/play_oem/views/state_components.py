"""State-components time-series view."""

from typing import cast

from .orbit_time_series import OrbitTimeSeriesView
from .state_components_impl import StateComponentsImpl


class StateComponentsView(OrbitTimeSeriesView):
    name = "state-components"
    label = "State Components"
    group = "state"

    def _create_delegate(self, start_time_s: float, frame_context: object = ""):
        return StateComponentsImpl(start_time_s, cast(str, frame_context))

__all__ = ["StateComponentsView"]
