"""Shared application constants and data-data-view panel state models."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg, NavigationToolbar2WxAgg
from matplotlib.figure import Figure

from ..data_view_panel import DataViewPanelHost
from ..matplotlib_helpers import create_figure
from ..platform_support import is_linux
from ..time_range import ResolvedTimeRange
from ..views import data_view_base as base

DEFAULT_TICK_INTERVAL_MS: int = 33
"""Default interval between playback timer events (ms)."""

ELAPSED_TIME_DECIMAL_PLACES: int = 3
"""Number of decimal places shown in the elapsed-time readout."""

PLAYER_FRAME_MIN_SIZE: tuple[int, int] = (920, 480)
"""Minimum dashboard frame size (pixels)."""

PLAYER_FRAME_SIZE: tuple[int, int] = (1100, 760)
"""Initial dashboard frame size (pixels)."""

EMPTY_DATA_VIEW: str = "empty"
"""Sentinel name for a data-view panel with no selected view."""

EMPTY_DATA_VIEW_LABEL: str = "Empty"
"""Selector label for an unconfigured data-view panel."""


def _configure_settings_backend_without_session_bus() -> None:
    """Avoid dconf warnings when Linux GUI apps have no usable session bus."""
    if not is_linux() or "GSETTINGS_BACKEND" in os.environ:
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


class _EmptyDataView:
    """DataView placeholder shown before a data-view type is selected."""

    name = EMPTY_DATA_VIEW
    seek_on_click = False

    def __init__(self, parent: wx.Window) -> None:
        self._parent = parent

    def build_placeholder(self) -> wx.Window:
        empty_data_view_prompt = wx.StaticText(
            self._parent, wx.ID_ANY, "Select a data view above"
        )
        empty_data_view_prompt.SetName("Empty data view prompt")
        return empty_data_view_prompt

    def close(self) -> None:
        pass

    def build_from_store(self, _context) -> wx.Window:
        return self.build_placeholder()

    def update_from_store(self, _context) -> None:
        pass

    def set_time_range(self, _bounds, _coverage) -> None:
        pass

    def update(self, _time_s: float) -> None:
        pass


class _PendingDataView:
    """Draw a selected data-view panel while its OEM data is not available yet."""

    name = "pending"
    seek_on_click = False

    def __init__(self, parent: wx.Window, label: str) -> None:
        self._parent = parent
        self._label = label

    def build_placeholder(self) -> Figure:
        figure = create_figure((8.0, 4.5))
        axes = figure.add_subplot(111)
        axes.set_axis_off()
        axes.text(
            0.5,
            0.55,
            self._label,
            ha="center",
            va="center",
            fontsize=12,
            transform=axes.transAxes,
        )
        axes.text(
            0.5,
            0.45,
            "Waiting for OEM data…",
            ha="center",
            va="center",
            color="0.45",
            transform=axes.transAxes,
        )
        return figure


    def close(self) -> None:
        pass

    def build_from_store(self, _context) -> Figure:
        return self.build_placeholder()

    def update_from_store(self, _context) -> None:
        pass

    def set_time_range(self, _bounds, _coverage) -> None:
        pass

    def update(self, _time_s: float) -> None:
        pass


@dataclass
class PanelBuildResources:
    """Resources created while one data-view panel is being opened."""

    panel: DataViewPanelHost | None = None
    """DataData-data-view panel host, when construction reached the host stage."""
    data_view: base.DataView | None = None
    """DataView instance, when construction reached the view stage."""
    canvas: FigureCanvasWxAgg | None = None
    """Matplotlib canvas, when the view uses a Matplotlib figure."""
    toolbar: NavigationToolbar2WxAgg | None = None
    """Matplotlib toolbar associated with the canvas."""
    click_callback_id: int | None = None
    """Matplotlib click callback identifier."""
    unsubscribe: Callable[[], None] | None = None
    """Clock observer unsubscribe callback."""
    panel_inserted: bool = False
    """Whether the panel was inserted into or replaced in a data-view stack."""


@dataclass
class _OpenDataView:
    """Track one data-data-view panel instance and its deferred display state."""

    panel_id: str
    """Stable identity independent of the registered view type."""

    data_view_name: str
    """Registered view type hosted by this panel instance."""

    stack: str
    """DataData-view stack containing this panel instance."""

    panel: DataViewPanelHost
    """Embedded data-view panel host."""

    data_view: base.DataView
    """Plot view rendered in the frame."""

    unsubscribe: Callable[[], None]
    """Callback that removes this view from clock notifications."""

    canvas: FigureCanvasWxAgg | None
    """Wx canvas hosting a Matplotlib figure, if this view uses one."""

    toolbar: NavigationToolbar2WxAgg | None
    """Wx navigation toolbar associated with a Matplotlib canvas."""

    click_callback_id: int | None
    """Matplotlib event identifier used to disconnect plot seeking, if connected."""

    requires_store_rebuild: bool = False
    """Whether this view was opened before an OEM store became available."""

    range_initialized: bool = False
    """Whether the current effective range has been sent to this view."""

    applied_range: ResolvedTimeRange | None = None
    """Effective range last applied to this view, including an empty range."""

    applied_coverage: tuple[float, float] | None = None
    """OEM coverage last applied alongside the effective range."""

    pending_time_s: float | None = None
    """Latest playback time deferred while this panel is hidden."""

    pending_range: ResolvedTimeRange | None = None
    """Latest effective range deferred while this panel is hidden."""

    has_pending_range: bool = False
