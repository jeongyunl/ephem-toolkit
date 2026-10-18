"""Reusable graph-panel host for embedded playback plots."""

from __future__ import annotations

from collections.abc import Callable
import math
import time

import wx
from matplotlib.backend_bases import DrawEvent
from matplotlib.backends.backend_wxagg import (
    FigureCanvasWxAgg,
    NavigationToolbar2WxAgg,
)

MATPLOTLIB_REDRAW_INTERVAL_S: float = 0.033
"""Minimum interval between requested Matplotlib redraws per graph panel."""


class _RedrawThrottle:
    """Coalesce redraws and schedule them only while their panel is visible."""

    def __init__(
        self,
        is_visible: Callable[[], bool],
        draw: Callable[[], None],
    ) -> None:
        self._is_visible = is_visible
        self._draw = draw
        self._timer: wx.CallLater | None = None
        self._last_draw_time = float("-inf")
        self._needs_redraw = False

    def request(self) -> None:
        self._needs_redraw = True
        if not self._is_visible():
            return
        if self._timer is not None and self._timer.IsRunning():
            return

        elapsed = time.monotonic() - self._last_draw_time
        delay_s = MATPLOTLIB_REDRAW_INTERVAL_S - elapsed
        if delay_s > 0.0:
            delay_ms = max(1, math.ceil(delay_s * 1000.0))
            self._timer = wx.CallLater(delay_ms, self._draw_if_needed)
            return
        self._draw_if_needed()

    def close(self) -> None:
        if self._timer is not None and self._timer.IsRunning():
            self._timer.Stop()
            self._timer = None

    def _draw_if_needed(self) -> None:
        self._timer = None
        if not self._needs_redraw or not self._is_visible():
            return
        self._needs_redraw = False
        self._last_draw_time = time.monotonic()
        self._draw()


class GraphPanelHost(wx.Panel):
    """Host a plot toolbar and canvas within a scrollable graph stack."""

    def __init__(
        self,
        parent: wx.Window,
        title: str,
        on_close: Callable[[], None],
        is_visible: Callable[[], bool] | None = None,
        on_redraw_request: Callable[[GraphPanelHost], None] | None = None,
    ) -> None:
        super().__init__(parent, wx.ID_ANY)
        self._on_close = on_close
        self._is_visible = is_visible or self.IsShownOnScreen
        self._on_redraw_request = on_redraw_request
        self._redraw_throttle: _RedrawThrottle | None = None
        self._canvas: FigureCanvasWxAgg | None = None
        self._uses_constrained_layout = False

        layout = wx.BoxSizer(wx.VERTICAL)
        header = wx.BoxSizer(wx.HORIZONTAL)
        self.title_label = wx.StaticText(self, wx.ID_ANY, title)
        self.close_button = wx.Button(self, wx.ID_ANY, "Close")
        self.close_button.SetName(f"Close {title} graph")
        self.close_button.SetToolTip(f"Close {title} graph")
        self.close_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_close())
        header.Add(self.title_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        header.Add(self.close_button, 0, wx.ALL, 4)
        layout.Add(header, 0, wx.EXPAND)
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)
        layout.Add(self.content_sizer, 1, wx.EXPAND)
        self.SetSizer(layout)
        self.SetMinSize((320, 280))
        self.Bind(wx.EVT_SHOW, self._on_show)

    def set_matplotlib_content(
        self, toolbar: NavigationToolbar2WxAgg, canvas: FigureCanvasWxAgg
    ) -> None:
        """Install a Matplotlib toolbar and canvas in this panel."""
        self.content_sizer.Add(toolbar, 0, wx.EXPAND)
        self.content_sizer.Add(canvas, 1, wx.EXPAND)
        self._canvas = canvas
        self._redraw_throttle = _RedrawThrottle(self._is_visible, canvas.draw_idle)
        if canvas.figure.get_layout_engine() is not None:
            self._uses_constrained_layout = True
            canvas.mpl_connect("draw_event", self._disable_constrained_layout)
            canvas.Bind(wx.EVT_SIZE, self._on_canvas_size)
        self.Layout()

    def request_redraw(self) -> None:
        """Coalesce redraw requests and defer work for hidden or off-screen panels."""
        if self._on_redraw_request is not None:
            self._on_redraw_request(self)
        else:
            self.draw_if_needed()

    def draw_if_needed(self) -> None:
        """Request a throttled canvas redraw after workspace scheduling."""
        if self._on_redraw_request is not None:
            if self._canvas is not None and self._is_visible():
                self._canvas.draw_idle()
            return
        if self._redraw_throttle is not None:
            self._redraw_throttle.request()

    def draw_initial(self) -> None:
        """Render visible content once so playback starts after first-layout work."""
        if self._canvas is not None and self._is_visible():
            self._canvas.draw()

    def Destroy(self) -> bool:
        """Cancel any deferred redraw before destroying the wx controls."""
        if self._redraw_throttle is not None:
            self._redraw_throttle.close()
        return super().Destroy()

    def _on_show(self, event: wx.ShowEvent) -> None:
        if event.IsShown():
            self.request_redraw()
        event.Skip()

    def _disable_constrained_layout(self, event: DrawEvent) -> None:
        if self._uses_constrained_layout:
            event.canvas.figure.set_layout_engine(None)

    def _on_canvas_size(self, event: wx.SizeEvent) -> None:
        if (
            self._uses_constrained_layout
            and self._canvas is not None
            and self._canvas.figure.get_layout_engine() is None
        ):
            self._canvas.figure.set_layout_engine("constrained")
        event.Skip()
