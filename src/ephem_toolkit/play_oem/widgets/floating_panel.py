"""Reusable floating panel for playback views."""

from __future__ import annotations

from enum import Enum

import wx


class PanelCorner(str, Enum):
    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_RIGHT = "bottom-right"


class PanelInteraction(str, Enum):
    HOVER = "hover"
    CLICK = "click"


class FloatingPanel(wx.Panel):
    """A compact corner panel that expands on hover or click."""

    def __init__(
        self,
        parent: wx.Window,
        *,
        name: str = "Panel",
        handle_label: str = "≡",
        corner: PanelCorner = PanelCorner.TOP_RIGHT,
        interaction: PanelInteraction = PanelInteraction.HOVER,
        initially_expanded: bool = False,
        content_margin_dip: int = 8,
        popup_border_width_dip: int = 1,
    ) -> None:
        """Create a floating panel anchored to a parent corner.

        ``corner`` defaults to :attr:`PanelCorner.TOP_RIGHT`; ``interaction``
        defaults to :attr:`PanelInteraction.HOVER`. Set ``initially_expanded``
        to open the panel after the current event completes.
        """
        try:
            corner = PanelCorner(corner)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unsupported panel corner: {corner!r}") from error
        try:
            interaction = PanelInteraction(interaction)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Unsupported panel interaction: {interaction!r}"
            ) from error
        if content_margin_dip < 0:
            raise ValueError("content_margin_dip must be non-negative")
        if popup_border_width_dip < 0:
            raise ValueError("popup_border_width_dip must be non-negative")
        super().__init__(
            parent,
            wx.ID_ANY,
            style=wx.BORDER_NONE,
        )
        self._host = parent
        self._corner = corner
        self._interaction = interaction
        self.SetName(name)
        self._expanded = False
        self._collapse_timer: wx.CallLater | None = None
        self._content_sizer: wx.Sizer | None = None
        self._content_body_sizer: wx.Sizer | None = None
        self._content_margin_dip = content_margin_dip
        self._collapsed_screen_rect = wx.Rect()
        self._focus_before_expand: wx.Window | None = None

        self._handle = wx.Panel(self, wx.ID_ANY, style=wx.BORDER_NONE)
        self._handle.SetName(f"{name} handle")
        self._handle.SetBackgroundColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNSHADOW)
        )
        handle_inner = wx.Panel(
            self._handle,
            wx.ID_ANY,
            style=wx.BORDER_NONE,
        )
        handle_inner.SetBackgroundColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
        )
        handle_label_control = wx.StaticText(
            handle_inner,
            wx.ID_ANY,
            handle_label,
            style=wx.ALIGN_CENTRE_HORIZONTAL,
        )
        handle_label_control.SetName(f"{name} handle label")
        handle_inner_sizer = wx.BoxSizer(wx.VERTICAL)
        handle_inner_sizer.Add(
            handle_label_control,
            1,
            wx.EXPAND | wx.ALL,
            1,
        )
        handle_inner.SetSizer(handle_inner_sizer)
        handle_outer_sizer = wx.BoxSizer(wx.VERTICAL)
        handle_outer_sizer.Add(
            handle_inner,
            1,
            wx.EXPAND | wx.ALL,
            self.FromDIP(1),
        )
        self._handle.SetSizer(handle_outer_sizer)

        top_level = wx.GetTopLevelParent(parent)
        self._top_level = top_level
        self._uses_popup_window = "gtk3" in wx.PlatformInfo
        if self._uses_popup_window:
            # GTK popup windows avoid activating a second top-level frame.
            self._popup = wx.PopupWindow(top_level, wx.BORDER_NONE)
        else:
            self._popup = wx.Frame(
                top_level,
                wx.ID_ANY,
                "",
                style=(
                    wx.BORDER_NONE
                    | wx.FRAME_NO_TASKBAR
                    | wx.FRAME_FLOAT_ON_PARENT
                ),
            )
        self._popup_border_width_dip = popup_border_width_dip
        self._popup_border_width = self.FromDIP(
            self._popup_border_width_dip
        )
        popup_background = wx.SystemSettings.GetColour(
            wx.SYS_COLOUR_BTNSHADOW
        )
        content_background = (
            top_level.GetBackgroundColour()
            if self._uses_popup_window
            else wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
        )
        self._popup.SetBackgroundColour(popup_background)
        self._content = wx.ScrolledWindow(
            self._popup,
            wx.ID_ANY,
            style=(
                wx.HSCROLL
                | wx.VSCROLL
            ),
        )
        self._content.SetName(name)
        self._content.SetScrollRate(10, 10)
        self._content.AlwaysShowScrollbars(False, False)
        self._content.ShowScrollbars(False, False)
        self._content.SetBackgroundColour(content_background)
        self._content.SetForegroundColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
        )
        self._collapse_control: wx.StaticText | None = None
        if interaction == PanelInteraction.CLICK:
            self._collapse_control = wx.StaticText(
                self._content,
                wx.ID_ANY,
                handle_label,
            )
            self._collapse_control.SetName(f"{name} collapse")
            self._collapse_control.SetToolTip("Collapse panel")
            self._collapse_control.Bind(
                wx.EVT_LEFT_UP,
                self._on_collapse_control_click,
            )
        popup_sizer = wx.BoxSizer(wx.VERTICAL)
        popup_sizer.Add(
            self._content,
            1,
            wx.EXPAND | wx.ALL,
            self._popup_border_width,
        )
        self._popup.SetSizer(popup_sizer)
        self._popup.SetBackgroundColour(popup_background)
        self._popup.Hide()

        if interaction == PanelInteraction.HOVER:
            self._handle.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
            self._handle.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
            self._content.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
            self._content.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        else:
            self._handle.Bind(wx.EVT_LEFT_UP, self._on_handle_click)
            handle_inner.Bind(wx.EVT_LEFT_UP, self._on_handle_click)
            handle_label_control.Bind(wx.EVT_LEFT_UP, self._on_handle_click)
        parent.Bind(wx.EVT_SIZE, self._on_host_size)
        parent.Bind(wx.EVT_MOVE, self._on_host_move)
        self._top_level.Bind(wx.EVT_MOVE, self._on_host_move)

        self._handle.Show()
        self._content.Hide()
        wx.CallAfter(self.RefreshLayout)
        if initially_expanded:
            wx.CallAfter(self.Expand)

    def GetContentWindow(self) -> wx.ScrolledWindow:
        """Return the scrolled content host for view-specific controls."""
        return self._content

    def _sync_collapse_control_height(self) -> None:
        if self._collapse_control is None or self._content_body_sizer is None:
            return
        height = self._content_body_sizer.CalcMin().height
        if height > 0:
            self._collapse_control.SetMinSize(wx.Size(-1, height))
            self._collapse_control.SetMaxSize(wx.Size(-1, height))

    def SetContentSizer(self, sizer: wx.Sizer) -> None:
        """Populate the expanded panel with a caller-owned content sizer."""
        margin = self.FromDIP(self._content_margin_dip)
        outer_sizer = wx.BoxSizer(wx.VERTICAL)
        body_sizer = wx.BoxSizer(
            wx.HORIZONTAL if self._collapse_control is not None else wx.VERTICAL
        )
        if self._collapse_control is None:
            body_sizer.Add(sizer, 1, wx.EXPAND)
        else:
            alignment = (
                wx.ALIGN_TOP
                if self._corner.value.startswith("top")
                else wx.ALIGN_BOTTOM
            )
            if self._corner.value.endswith("left"):
                body_sizer.Add(
                    self._collapse_control,
                    0,
                    alignment | wx.RIGHT,
                    4,
                )
                body_sizer.Add(sizer, 1, wx.EXPAND)
            else:
                body_sizer.Add(sizer, 1, wx.EXPAND)
                body_sizer.Add(
                    self._collapse_control,
                    0,
                    alignment | wx.LEFT,
                    4,
                )
        outer_sizer.Add(body_sizer, 1, wx.EXPAND | wx.ALL, margin)
        self._content_sizer = outer_sizer
        self._content_body_sizer = sizer
        self._content.SetSizer(outer_sizer)
        self._sync_collapse_control_height()
        outer_sizer.Layout()
        required = outer_sizer.CalcMin()
        self._content.SetVirtualSize(required)
        self.RefreshLayout()

    def AddContent(
        self,
        window: wx.Window,
        proportion: int = 0,
        flags: int = 0,
        border: int = 0,
    ) -> None:
        """Add a control to a default vertical content sizer."""
        sizer = self._content_body_sizer
        if sizer is None:
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetContentSizer(sizer)
        sizer.Add(window, proportion, flags, border)
        self.RefreshLayout()

    def IsExpanded(self) -> bool:
        return self._expanded

    def GetHandleSize(self) -> wx.Size:
        return self._handle.GetSize()

    def GetExpandedBounds(self) -> wx.Rect:
        point, size = self._expanded_position_and_size()
        return wx.Rect(point.x, point.y, size.width, size.height)

    def GetCollapsedScreenRect(self) -> wx.Rect:
        """Return the collapsed handle rectangle in screen coordinates."""
        if self._expanded:
            return self._collapsed_screen_rect
        return self._handle.GetScreenRect()

    def GetExpandedScreenRect(self) -> wx.Rect:
        """Return the expanded popup rectangle in screen coordinates."""
        return self._popup.GetScreenRect()

    def Expand(self) -> None:
        self.CancelCollapse()
        if self._expanded:
            self.RefreshLayout()
            return
        if not self._uses_popup_window:
            self._focus_before_expand = wx.Window.FindFocus()
        self._expanded = True
        self._handle.Hide()
        self._content.Show()
        if self._uses_popup_window:
            # Give GTK's scrolled window its final allocation before mapping
            # the popup; showing it at the default 1x1 size can make its
            # scrollbars receive a negative allocation.
            self.RefreshLayout()
            self._popup.Show()
            # GTK may apply the popup's initial position while mapping it.
            # Reapply the host-relative position once it has a native window.
            self.RefreshLayout()
        else:
            self._popup.Show()
            self.RefreshLayout()
        if not self._uses_popup_window:
            wx.CallAfter(self._focus_expanded_content)

    def Collapse(self) -> None:
        self.CancelCollapse()
        self._expanded = False
        self._content.Hide()
        self._popup.Hide()
        self._handle.Show()
        self.RefreshLayout()
        if not self._uses_popup_window:
            previous_focus = self._focus_before_expand
            self._focus_before_expand = None
            focus_target = previous_focus if previous_focus is not None else self._handle
            wx.CallAfter(self._restore_focus, focus_target)

    def _restore_focus(self, focus_target: wx.Window) -> None:
        being_deleted = getattr(focus_target, "IsBeingDeleted", None)
        if callable(being_deleted) and being_deleted():
            return
        focus_target.SetFocus()

    def _focus_expanded_content(self) -> None:
        if not self._expanded:
            return
        self._content.SetFocus()

    def ScheduleCollapse(self, delay_ms: int = 250) -> None:
        self.CancelCollapse()
        self._collapse_timer = wx.CallLater(
            max(0, delay_ms),
            self._collapse_if_not_hovered,
        )

    def CancelCollapse(self) -> None:
        timer = self._collapse_timer
        self._collapse_timer = None
        if timer is not None:
            stop = getattr(timer, "Stop", None)
            if callable(stop):
                stop()

    def RefreshLayout(self) -> None:
        host_size = self.GetParent().GetClientSize()
        if host_size.width <= 0 or host_size.height <= 0:
            return

        margin = self.FromDIP(8)
        handle_size = self.FromDIP(24)
        handle_x = (
            0
            if self._corner.value.endswith("left")
            else max(0, host_size.width - handle_size)
        )
        handle_y = (
            0
            if self._corner.value.startswith("top")
            else max(0, host_size.height - handle_size)
        )
        handle_rect = wx.Rect(
            handle_x,
            handle_y,
            handle_size,
            handle_size,
        )

        if self._content_sizer is not None:
            for child in self._content.GetChildren():
                child.InvalidateBestSize()
            self._sync_collapse_control_height()
            required = self._content_sizer.CalcMin()
            self._content_sizer.Layout()
        else:
            required = wx.Size(420, 180)

        position, size = self._expanded_position_and_size(
            host_size,
            required,
            margin,
        )
        if self._expanded:
            self._handle.SetSize(0, 0, handle_size, handle_size)
            host_origin = self.GetParent().ClientToScreen(wx.Point(0, 0))
            collapsed_left = host_origin.x + handle_rect.x
            collapsed_right = host_origin.x + handle_rect.x + handle_size
            collapsed_top = host_origin.y + handle_rect.y
            collapsed_bottom = collapsed_top + handle_size
            if self._uses_popup_window:
                frame_origin = self._top_level.ClientToScreen(wx.Point(0, 0))
                frame_size = self._top_level.GetClientSize()
            else:
                frame_rect = self._top_level.GetScreenRect()
                frame_origin = wx.Point(frame_rect.left, frame_rect.top)
                frame_size = wx.Size(frame_rect.width, frame_rect.height)
            edge_margin = self.FromDIP(8)
            popup_width = min(
                size.width,
                max(1, frame_size.width - 2 * edge_margin),
            )
            popup_height = min(
                size.height,
                max(1, frame_size.height - 2 * edge_margin),
            )
            self._popup.SetClientSize(wx.Size(popup_width, popup_height))
            self._popup.Layout()
            actual_popup_size = self._popup.GetSize()
            popup_width = actual_popup_size.width
            popup_height = actual_popup_size.height
            popup_left = (
                collapsed_left
                if self._corner.value.endswith("left")
                else collapsed_right - popup_width
            )
            if popup_left < frame_origin.x:
                popup_left = frame_origin.x
            elif popup_left + popup_width > frame_origin.x + frame_size.width:
                popup_left = frame_origin.x + frame_size.width - popup_width
            popup_top = (
                collapsed_top
                if self._corner.value.startswith("top")
                else collapsed_bottom - popup_height
            )
            if popup_top < frame_origin.y:
                popup_top = frame_origin.y
            elif popup_top + popup_height > frame_origin.y + frame_size.height:
                popup_top = frame_origin.y + frame_size.height - popup_height
            self._popup.SetPosition(wx.Point(popup_left, popup_top))
            self._popup.Layout()
            self._collapsed_screen_rect = wx.Rect(
                collapsed_left,
                collapsed_top,
                handle_size,
                handle_size,
            )
        else:
            self.SetSize(handle_rect.x, handle_rect.y, handle_size, handle_size)
            self._handle.SetSize(0, 0, handle_size, handle_size)
            self._collapsed_screen_rect = self._handle.GetScreenRect()
        self._content.Layout()
        if self._expanded:
            if self._content_sizer is not None:
                required = self._content_sizer.CalcMin()
            client_size = self._content.GetClientSize()
            horizontal_overflow = required.width > client_size.width
            vertical_overflow = required.height > client_size.height
            self._content.ShowScrollbars(
                horizontal_overflow,
                vertical_overflow,
            )
            client_size = self._content.GetClientSize()
            if horizontal_overflow or vertical_overflow:
                virtual_size = wx.Size(
                    max(required.width, client_size.width),
                    max(required.height, client_size.height),
                )
            else:
                virtual_size = client_size
            self._content.SetVirtualSize(
                virtual_size
            )
        else:
            self._content.SetVirtualSize(required)

        if self._expanded:
            self._content.Show()
        else:
            self._handle.Show()

    def Close(self, force: bool = False) -> bool:
        self.CancelCollapse()
        self._host.Unbind(wx.EVT_SIZE, handler=self._on_host_size)
        self._host.Unbind(wx.EVT_MOVE, handler=self._on_host_move)
        self._top_level.Unbind(wx.EVT_MOVE, handler=self._on_host_move)
        if self._interaction == PanelInteraction.HOVER:
            self._handle.Unbind(wx.EVT_ENTER_WINDOW)
            self._handle.Unbind(wx.EVT_LEAVE_WINDOW)
            self._content.Unbind(wx.EVT_ENTER_WINDOW)
            self._content.Unbind(wx.EVT_LEAVE_WINDOW)
        else:
            self._handle.Unbind(wx.EVT_LEFT_UP)
            if self._collapse_control is not None:
                self._collapse_control.Unbind(wx.EVT_LEFT_UP)
        self._popup.Hide()
        self._popup.Destroy()
        self.Destroy()
        return True

    def _on_enter(self, event: wx.MouseEvent) -> None:
        self.CancelCollapse()
        self.Expand()
        event.Skip()

    def _on_handle_click(self, event: wx.MouseEvent) -> None:
        self.Expand()
        event.Skip()

    def _on_collapse_control_click(self, event: wx.MouseEvent) -> None:
        self.Collapse()
        event.Skip()

    def _on_leave(self, event: wx.MouseEvent) -> None:
        if self._expanded:
            self.ScheduleCollapse()
        event.Skip()

    def _on_host_size(self, event: wx.SizeEvent) -> None:
        event.Skip()
        wx.CallAfter(self.RefreshLayout)

    def _on_host_move(self, event: wx.MoveEvent) -> None:
        event.Skip()
        wx.CallAfter(self.RefreshLayout)

    def _collapse_if_not_hovered(self) -> None:
        self._collapse_timer = None
        if not self._expanded:
            return
        pointer = wx.GetMousePosition()
        if self._content.GetScreenRect().Contains(pointer):
            return
        self.Collapse()

    def _expanded_position_and_size(
        self,
        host_size: wx.Size | None = None,
        required: wx.Size | None = None,
        margin: int | None = None,
    ) -> tuple[wx.Point, wx.Size]:
        if host_size is None:
            host_size = self.GetParent().GetClientSize()
        assert host_size is not None
        if margin is None:
            margin = self.FromDIP(8)
        assert margin is not None
        if required is None:
            required = (
                self._content_sizer.CalcMin()
                if self._content_sizer is not None
                else wx.Size(420, 180)
            )

        screen_width = wx.Display().GetClientArea().width
        screen_height = wx.Display().GetClientArea().height
        available_width = max(
            1,
            screen_width - 2 * margin,
        )
        available_height = max(
            1,
            screen_height - 2 * margin,
        )
        desired_width = min(
            required.width + 2 * self._popup_border_width,
            available_width,
        )
        desired_height = min(
            required.height + 2 * self._popup_border_width,
            available_height,
        )
        width = max(0, desired_width)
        height = max(0, desired_height)
        point = wx.Point(
            (
                margin
                if self._corner.value.endswith("left")
                else max(margin, host_size.width - width - margin)
            ),
            (
                margin
                if self._corner.value.startswith("top")
                else max(margin, host_size.height - height - margin)
            ),
        )
        return point, wx.Size(width, height)
