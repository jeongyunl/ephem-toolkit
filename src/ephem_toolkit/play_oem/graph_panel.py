"""Reusable graph-panel host for embedded playback plots."""

from __future__ import annotations

from collections.abc import Callable
import math
import time
from typing import cast
from uuid import uuid4

import wx

from .tooltips import dismiss_all_tooltips, set_tooltip

from matplotlib.backend_bases import DrawEvent
from matplotlib.backends.backend_wxagg import (
    FigureCanvasWxAgg,
    NavigationToolbar2WxAgg,
)
from matplotlib.figure import Figure

MATPLOTLIB_REDRAW_INTERVAL_S: float = 0.033
"""Minimum interval between requested Matplotlib redraws per graph panel."""
WHEEL_SCROLL_UNITS_PER_NOTCH: int = 3
"""Graph-stack scroll units moved per standard mouse-wheel notch."""
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
    """Host one graph panel with independently scrollable content."""

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
        on_show: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, wx.ID_ANY)
        if panel_id == "":
            raise ValueError("panel_id cannot be empty")
        self.panel_id = panel_id or uuid4().hex
        self._on_close = on_close
        self._is_visible = is_visible or self.IsShownOnScreen
        self._on_redraw_request = on_redraw_request
        self._on_show_callback = on_show
        self._redraw_throttle: _RedrawThrottle | None = None
        self._canvas: FigureCanvasWxAgg | None = None
        self._toolbar: NavigationToolbar2WxAgg | None = None
        self._native_content: wx.Window | None = None
        self._uses_constrained_layout = False
        self.graph_scroller = wx.ScrolledWindow(
            self,
            wx.ID_ANY,
            style=wx.HSCROLL | wx.VSCROLL | wx.TAB_TRAVERSAL,
        )
        self.graph_scroller.SetName(f"{title} graph content")
        self.graph_scroller.SetScrollRate(10, 10)
        self.graph_scroller.Bind(wx.EVT_MOUSEWHEEL, self._on_content_mousewheel)

        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Retain the header sizer so natural height includes its controls and borders.
        self._header_sizer = header_sizer
        self.graph_title_label: wx.StaticText | None = None
        self.graph_view_selector: wx.Choice | None = None
        if view_choices:
            self.graph_view_selector = wx.Choice(
                self,
                wx.ID_ANY,
                choices=[label for _name, label in view_choices],
            )
            # Keep the selector compact so it matches the smaller header actions.
            self.graph_view_selector.SetMinSize(wx.Size(-1, 26))
            self.graph_view_selector.SetName(f"{title} view selector")
            # Keep wheel input from changing the selection while forwarding its
            # scrolling effect to the containing graph stack.
            self.graph_view_selector.Bind(
                wx.EVT_MOUSEWHEEL, self._on_selector_mousewheel
            )
            set_tooltip(self.graph_view_selector, f"Select a view for {title}")
            if selected_view is not None:
                self.graph_view_selector.SetSelection(
                    next(
                        index
                        for index, (name, _label) in enumerate(view_choices)
                        if name == selected_view
                    )
                )
            if on_view_selected is not None:
                self.graph_view_selector.Bind(
                    wx.EVT_CHOICE,
                    # Replacing the panel destroys this choice; defer until GTK
                    # has finished dispatching its selection event.
                    lambda event: wx.CallAfter(
                        on_view_selected,
                        view_choices[event.GetSelection()][0],
                    ),
                )
            header_sizer.Add(self.graph_view_selector, 1, wx.EXPAND | wx.ALL, 2)
        else:
            self.graph_title_label = wx.StaticText(self, wx.ID_ANY, title)
            header_sizer.Add(
                self.graph_title_label,
                1,
                wx.ALIGN_CENTER_VERTICAL | wx.ALL,
                4,
            )
        self.graph_close_button = wx.Button(self, wx.ID_ANY, "Close")
        # A fixed compact height reduces header space while preserving native width.
        self.graph_close_button.SetMinSize(wx.Size(-1, 26))
        self.graph_close_button.SetName(f"Close {title} graph")
        set_tooltip(self.graph_close_button, f"Close {title} graph")
        self.graph_close_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_close())
        self.graph_actions_button = wx.Button(self, wx.ID_ANY, "Actions")
        # Match the Close control so the header buttons have consistent proportions.
        self.graph_actions_button.SetMinSize(wx.Size(-1, 26))
        self.graph_actions_button.SetName(f"{title} panel actions")
        # Keep the tooltip handle so menu activation can dismiss it explicitly.
        self._actions_tooltip = set_tooltip(
            self.graph_actions_button, f"Actions for {title} graph"
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
        self.graph_actions_button.Bind(
            wx.EVT_BUTTON,
            self._on_actions_button,
        )
        header_sizer.Add(self.graph_actions_button, 0, wx.ALL, 2)
        header_sizer.Add(self.graph_close_button, 0, wx.ALL, 2)
        panel_sizer.Add(header_sizer, 0, wx.EXPAND)
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)
        self.graph_scroller.SetSizer(self.content_sizer)
        panel_sizer.Add(self.graph_scroller, 1, wx.EXPAND)
        self.SetSizer(panel_sizer)
        self.SetMinSize(GRAPH_PANEL_MIN_SIZE)
        self.Bind(wx.EVT_SHOW, self._on_show)

    def _on_actions_button(self, _event: wx.CommandEvent) -> None:
        # GTK requires the tooltip popup to be unmapped before opening a menu
        # with the graph panel as parent, including keyboard activation.
        dismiss_all_tooltips()
        self.PopupMenu(self._actions_menu)

    def set_matplotlib_content(
        self, toolbar: NavigationToolbar2WxAgg, canvas: FigureCanvasWxAgg
    ) -> None:
        """Install a Matplotlib toolbar and canvas in this panel."""
        if self._native_content is not None:
            raise RuntimeError("graph panel already has native content")
        self.content_sizer.Add(toolbar, 0, wx.EXPAND)
        self.content_sizer.Add(canvas, 1, wx.EXPAND)
        toolbar.Bind(wx.EVT_MOUSEWHEEL, self._on_content_mousewheel)
        canvas.Bind(wx.EVT_MOUSEWHEEL, self._on_content_mousewheel)
        self._canvas = canvas
        # Keep both references to measure the full plot height, including its toolbar.
        self._toolbar = toolbar
        self._redraw_throttle = _RedrawThrottle(self._is_visible, canvas.draw_idle)
        if _canvas_figure(canvas).get_layout_engine() is not None:
            self._uses_constrained_layout = True
            canvas.mpl_connect("draw_event", self._disable_constrained_layout)
            canvas.Bind(wx.EVT_SIZE, self._on_canvas_size)
        self.graph_scroller.FitInside()
        self.Layout()

    def _on_content_mousewheel(self, event: wx.MouseEvent) -> None:
        """Scroll panel content first, handing wheel input to its stack at an edge."""
        rotation = event.GetWheelRotation()
        if rotation == 0:
            event.Skip()
            return

        content_position = self.graph_scroller.GetViewStart()
        content_limit = max(
            0,
            self.graph_scroller.GetScrollRange(wx.VERTICAL)
            - self.graph_scroller.GetScrollThumb(wx.VERTICAL),
        )
        if (rotation > 0 and content_position[1] > 0) or (
            rotation < 0 and content_position[1] < content_limit
        ):
            event.Skip()
            return

        if not GraphPanelHost._scroll_stack_from_mousewheel(self, event):
            event.Skip()

    def _on_selector_mousewheel(self, event: wx.MouseEvent) -> None:
        """Scroll the graph stack without changing the selected graph type."""
        GraphPanelHost._scroll_stack_from_mousewheel(self, event)

    def _scroll_stack_from_mousewheel(self, event: wx.MouseEvent) -> bool:
        """Apply a wheel rotation to the containing graph stack."""
        rotation = event.GetWheelRotation()
        if rotation == 0:
            return True
        stack_scroller = self._parent_stack_scroller()
        if stack_scroller is None:
            return False

        stack_position = stack_scroller.GetViewStart()
        stack_limit = max(
            0,
            stack_scroller.GetScrollRange(wx.VERTICAL)
            - stack_scroller.GetScrollThumb(wx.VERTICAL),
        )
        wheel_delta = max(1, event.GetWheelDelta())
        lines = max(
            1,
            round(abs(rotation) / wheel_delta * WHEEL_SCROLL_UNITS_PER_NOTCH),
        )
        direction = -1 if rotation > 0 else 1
        next_position = min(
            max(stack_position[1] + direction * lines, 0),
            stack_limit,
        )
        if next_position == stack_position[1]:
            return True
        stack_scroller.Scroll(stack_position[0], next_position)
        return True

    def _parent_stack_scroller(self) -> wx.ScrolledWindow | None:
        parent = self.GetParent()
        while parent is not None:
            if isinstance(parent, wx.ScrolledWindow):
                return parent
            parent = parent.GetParent()
        return None

    def set_native_content(self, content: wx.Window) -> None:
        """Install native wx plot content in this panel."""
        if self._canvas is not None or self._native_content is not None:
            raise RuntimeError("graph panel already has content")
        self.content_sizer.Add(content, 1, wx.EXPAND)
        self._native_content = content
        self.graph_scroller.FitInside()
        self.Layout()

    def natural_content_height(self) -> int:
        """Return the height needed to show the header and content without scrolling."""
        content_height = self.content_sizer.CalcMin().height
        if self._canvas is not None and self._toolbar is not None:
            figure = _canvas_figure(self._canvas)
            # A canvas can report its clipped first-layout size; the figure's
            # inches and DPI give the intended plot height before layout settles.
            inches_high = float(figure.get_size_inches()[1])
            canvas_height = math.ceil(inches_high * figure.dpi)
            content_height = max(
                content_height,
                canvas_height + self._toolbar.GetBestSize().height,
            )
        elif self._native_content is not None:
            # Native views expose their preferred height through wx directly.
            content_height = max(
                content_height, self._native_content.GetBestSize().height
            )
        return self._header_sizer.CalcMin().height + content_height

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
            if self._on_show_callback is not None:
                self._on_show_callback()
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
