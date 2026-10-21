"""Shared application constants and graph-panel state models."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
import sys

import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg, NavigationToolbar2WxAgg

from .. import series, time_unit
from ..graph_panel import GraphPanelHost
from ..views import base

DEFAULT_TICK_INTERVAL_MS: int = 33
"""Default interval between playback timer events (ms)."""

ELAPSED_TIME_DECIMAL_PLACES: int = 3
"""Number of decimal places shown in the elapsed-time readout."""

PLAYER_FRAME_MIN_SIZE: tuple[int, int] = (920, 480)
"""Minimum dashboard frame size (pixels)."""

PLAYER_FRAME_SIZE: tuple[int, int] = (1100, 760)
"""Initial dashboard frame size (pixels)."""

EMPTY_GRAPH_VIEW: str = "empty"
"""Sentinel name for a graph panel with no selected view."""

EMPTY_GRAPH_LABEL: str = "Empty"
"""Selector label for an unconfigured graph panel."""


def _configure_settings_backend_without_session_bus() -> None:
    """Avoid dconf warnings when Linux GUI apps have no usable session bus."""
    if not sys.platform.startswith("linux") or "GSETTINGS_BACKEND" in os.environ:
        return

    bus_address = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
    socket_path = next(
        (
            address.partition("path=")[2].split(",", 1)[0]
            for address in bus_address.split(";")
            if address.startswith("unix:path=")
        ),
        None,
    )
    if not bus_address or (socket_path is not None and not os.path.exists(socket_path)):
        # GTK's dconf backend writes through D-Bus; the in-memory backend keeps
        # file dialogs usable in shells without a working desktop session bus.
        os.environ["GSETTINGS_BACKEND"] = "memory"


class _EmptyGraphView:
    """View placeholder shown before a graph type is selected."""

    name = EMPTY_GRAPH_VIEW

    def __init__(self, parent: wx.Window) -> None:
        self._parent = parent

    def build(
        self, _series: series.OrbitSeries, _time_unit: time_unit.TimeUnit
    ) -> wx.Window:
        empty_graph_prompt = wx.StaticText(
            self._parent, wx.ID_ANY, "Select a graph view above"
        )
        empty_graph_prompt.SetName("Empty graph prompt")
        return empty_graph_prompt

    def update(self, _t_s: float) -> None:
        pass

    def close(self) -> None:
        pass


@dataclass
class _OpenView:
    """Track one graph-panel instance and its clock subscription."""

    panel_id: str
    """Stable identity independent of the registered view type."""

    view_name: str
    """Registered view type hosted by this panel instance."""

    stack: str
    """Graph stack containing this panel instance."""

    panel: GraphPanelHost
    """Embedded graph-panel host."""

    view: base.View
    """Plot view rendered in the frame."""

    unsubscribe: Callable[[], None]
    """Callback that removes this view from clock notifications."""

    canvas: FigureCanvasWxAgg | None
    """Wx canvas hosting a Matplotlib figure, if this view uses one."""

    toolbar: NavigationToolbar2WxAgg | None
    """Wx navigation toolbar associated with a Matplotlib canvas."""

    click_callback_id: int | None
    """Matplotlib event identifier used to disconnect plot seeking, if connected."""
