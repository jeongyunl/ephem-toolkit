"""Reusable graph-panel host for embedded playback plots."""

from __future__ import annotations

from collections.abc import Callable
import math
import time
from typing import cast
from uuid import uuid4

import wx

from .tooltips import set_tooltip

from matplotlib.backend_bases import DrawEvent
from matplotlib.backends.backend_wxagg import (
    FigureCanvasWxAgg,
    NavigationToolbar2WxAgg,
)
from matplotlib.figure import Figure

MATPLOTLIB_REDRAW_INTERVAL_S: float = 0.033
"""Minimum interval between requested Matplotlib redraws per graph panel."""
GRAPH_PANEL_MIN_SIZE: tuple[int, int] = (320, 280)
"""Minimum usable graph-panel width and height in pixels."""


def _canvas_figure(canvas: object) -> Figure:
    """Return the Matplotlib figure stored by a canvas backend."""
    return cast(Figure, getattr(canvas, "figure"))


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
    """Host one graph-panel instance within a scrollable graph stack."""

    def __init__(
        self,
        parent: wx.Window,
        title: str,
        on_close: Callable[[], None],
        is_visible: Callable[[], bool] | None = None,
        on_redraw_request: Callable[[GraphPanelHost], None] | None = None,
        panel_id: str | None = None,
        view_choices: tuple[tuple[str, str], ...] = (),
        selected_view: str | None = None,
        on_view_selected: Callable[[str], None] | None = None,
        on_move_up: Callable[[], None] | None = None,
        on_move_down: Callable[[], None] | None = None,
        on_duplicate: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, wx.ID_ANY)
        if panel_id == "":
            raise ValueError("panel_id cannot be empty")
        self.panel_id = panel_id or uuid4().hex
        self._on_close = on_close
        self._is_visible = is_visible or self.IsShownOnScreen
        self._on_redraw_request = on_redraw_request
        self._redraw_throttle: _RedrawThrottle | None = None
        self._canvas: FigureCanvasWxAgg | None = None
        self._native_content: wx.Window | None = None
        self._uses_constrained_layout = False

        layout = wx.BoxSizer(wx.VERTICAL)
        header = wx.BoxSizer(wx.HORIZONTAL)
        self.title_label: wx.StaticText | None = None
        self.view_selector: wx.Choice | None = None
        if view_choices:
            self.view_selector = wx.Choice(
                self,
                wx.ID_ANY,
                choices=[label for _name, label in view_choices],
            )
            # Keep the selector compact so it matches the smaller header actions.
            self.view_selector.SetMinSize(wx.Size(-1, 26))
            self.view_selector.SetName(f"{title} view selector")
            set_tooltip(self.view_selector, f"Select a view for {title}")
            if selected_view is not None:
                self.view_selector.SetSelection(
                    next(
                        index
                        for index, (name, _label) in enumerate(view_choices)
                        if name == selected_view
                    )
                )
            if on_view_selected is not None:
                self.view_selector.Bind(
                    wx.EVT_CHOICE,
                    # Replacing the panel destroys this choice; defer until GTK
                    # has finished dispatching its selection event.
                    lambda event: wx.CallAfter(
                        on_view_selected,
                        view_choices[event.GetSelection()][0],
                    ),
                )
            header.Add(self.view_selector, 1, wx.EXPAND | wx.ALL, 2)
        else:
            self.title_label = wx.StaticText(self, wx.ID_ANY, title)
            header.Add(
                self.title_label,
                1,
                wx.ALIGN_CENTER_VERTICAL | wx.ALL,
                4,
            )
        self.close_button = wx.Button(self, wx.ID_ANY, "Close")
        # A fixed compact height reduces header space while preserving native width.
        self.close_button.SetMinSize(wx.Size(-1, 26))
        self.close_button.SetName(f"Close {title} graph")
        set_tooltip(self.close_button, f"Close {title} graph")
        self.close_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_close())
        self.actions_button = wx.Button(self, wx.ID_ANY, "Actions")
        # Match the Close control so the header buttons have consistent proportions.
        self.actions_button.SetMinSize(wx.Size(-1, 26))
        self.actions_button.SetName(f"{title} panel actions")
        # Keep the tooltip handle so menu activation can dismiss it explicitly.
        self._actions_tooltip = set_tooltip(
            self.actions_button, f"Actions for {title} graph"
        )
        self._actions_menu = wx.Menu()
        for label, callback in (
            ("Move up", on_move_up),
            ("Move down", on_move_down),
            ("Duplicate", on_duplicate),
            ("Close", on_close),
        ):
            if callback is None:
                continue
            item = self._actions_menu.Append(wx.ID_ANY, label)
            self._actions_menu.Bind(
                wx.EVT_MENU,
                lambda _event, action=callback: action(),
                id=item.GetId(),
            )
        # Handle activation centrally so keyboard clicks also dismiss the tooltip.
        self.actions_button.Bind(
            wx.EVT_BUTTON,
            self._on_actions_button,
        )
        header.Add(self.actions_button, 0, wx.ALL, 2)
        header.Add(self.close_button, 0, wx.ALL, 2)
        layout.Add(header, 0, wx.EXPAND)
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)
        layout.Add(self.content_sizer, 1, wx.EXPAND)
        self.SetSizer(layout)
        self.SetMinSize(GRAPH_PANEL_MIN_SIZE)
        self.Bind(wx.EVT_SHOW, self._on_show)

    def _on_actions_button(self, _event: wx.CommandEvent) -> None:
        # GTK requires the tooltip popup to be unmapped before opening a menu
        # with the graph panel as parent, including keyboard activation.
        self._actions_tooltip.DoHideNow()
        self.PopupMenu(self._actions_menu)

    def set_matplotlib_content(
        self, toolbar: NavigationToolbar2WxAgg, canvas: FigureCanvasWxAgg
    ) -> None:
        """Install a Matplotlib toolbar and canvas in this panel."""
        if self._native_content is not None:
            raise RuntimeError("graph panel already has native content")
        self.content_sizer.Add(toolbar, 0, wx.EXPAND)
        self.content_sizer.Add(canvas, 1, wx.EXPAND)
        self._canvas = canvas
        self._redraw_throttle = _RedrawThrottle(self._is_visible, canvas.draw_idle)
        if _canvas_figure(canvas).get_layout_engine() is not None:
            self._uses_constrained_layout = True
            canvas.mpl_connect("draw_event", self._disable_constrained_layout)
            canvas.Bind(wx.EVT_SIZE, self._on_canvas_size)
        self.Layout()

    def set_native_content(self, content: wx.Window) -> None:
        """Install native wx plot content in this panel."""
        if self._canvas is not None or self._native_content is not None:
            raise RuntimeError("graph panel already has content")
        self.content_sizer.Add(content, 1, wx.EXPAND)
        self._native_content = content
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
            elif self._native_content is not None and self._is_visible():
                self._native_content.Refresh()
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
            # Matplotlib accepts None here to disable layout; its type stubs
            # omit that documented sentinel value.
            getattr(_canvas_figure(event.canvas), "set_layout_engine")(None)

    def _on_canvas_size(self, event: wx.SizeEvent) -> None:
        if (
            self._uses_constrained_layout
            and self._canvas is not None
            and _canvas_figure(self._canvas).get_layout_engine() is None
        ):
            _canvas_figure(self._canvas).set_layout_engine("constrained")
        event.Skip()
