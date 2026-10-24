"""Shared styling for play-oem hover tooltips."""

from __future__ import annotations

from typing import Any
import weakref

import wx
from wx.lib.agw import supertooltip as _agw_supertooltip
from wx.lib.agw.supertooltip import SuperToolTip

TOOLTIP_HORIZONTAL_PADDING: int = 8
"""Horizontal inner padding used by play-oem tooltip windows, in pixels."""


def _tooltip_dimensions(
    line_widths: list[int], line_height: int
) -> tuple[int, int, int, int]:
    """Size a tooltip to its text using font-scaled, balanced padding."""
    padding = max(1, line_height // 2)
    line_count = len(line_widths)
    width = max(line_widths, default=0) + 2 * padding
    height = line_count * line_height + (line_count + 1) * padding
    return width, height, padding, padding


if wx.Platform == "__WXMAC__":

    class _PlayOemToolTipWindow(wx.Frame, _agw_supertooltip.ToolTipWindowBase):
        def __init__(
            self, parent: wx.Window, class_parent: _PlayOemSuperToolTip
        ) -> None:
            # A normal Cocoa tooltip frame becomes key and deactivates the parent,
            # changing the slider's active appearance; tool windows avoid activation.
            wx.Frame.__init__(
                self,
                parent,
                style=wx.NO_BORDER
                | wx.FRAME_FLOAT_ON_PARENT
                | wx.FRAME_NO_TASKBAR
                | wx.POPUP_WINDOW
                | wx.FRAME_TOOL_WINDOW,
            )
            _agw_supertooltip.ToolTipWindowBase.__init__(self, parent, class_parent)

else:
    _PlayOemToolTipWindow = _agw_supertooltip.ToolTipWindow


class _VerticallyCenteredToolTipWindow(_PlayOemToolTipWindow):
    """Draw plain-text messages with equal padding between and around lines."""

    def __init__(self, parent: wx.Window, class_parent: _PlayOemSuperToolTip) -> None:
        super().__init__(parent, class_parent)
        self._line_height = 0
        self._horizontal_padding = 0
        self._vertical_spacing = 0

    def CalculateBestSize(self) -> None:
        dc = wx.ClientDC(self)
        dc.SetFont(self._classParent.GetMessageFont())
        lines = self._classParent.GetMessage().split("\n")
        self._line_height = dc.GetTextExtent("Ag")[1]
        widths = [dc.GetTextExtent(line or " ")[0] for line in lines]
        (
            width,
            height,
            self._horizontal_padding,
            self._vertical_spacing,
        ) = _tooltip_dimensions(widths, self._line_height)
        self.SetSize((width, height))

    def OnPaint(self, event: wx.PaintEvent | None) -> tuple[int, int] | None:
        dc = wx.ClientDC(self) if event is None else wx.BufferedPaintDC(self)
        rect = self.GetClientRect()
        middle_y = rect.y + rect.height // 2
        dc.GradientFillLinear(
            wx.Rect(rect.x, rect.y, rect.width, middle_y - rect.y),
            self._classParent.GetTopGradientColour(),
            self._classParent.GetMiddleGradientColour(),
            wx.SOUTH,
        )
        dc.GradientFillLinear(
            wx.Rect(rect.x, middle_y, rect.width, rect.y + rect.height - middle_y),
            self._classParent.GetMiddleGradientColour(),
            self._classParent.GetBottomGradientColour(),
            wx.SOUTH,
        )
        dc.SetFont(self._classParent.GetMessageFont())
        dc.SetTextForeground(self._classParent.GetTextColour())
        x = rect.x + self._horizontal_padding
        y = rect.y + self._vertical_spacing
        for line in self._classParent.GetMessage().split("\n"):
            dc.DrawText(line, x, y)
            y += self._line_height + self._vertical_spacing
        if event is None:
            return rect.width, rect.height
        return None


class _PlayOemSuperToolTip(SuperToolTip):
    """Clear SuperToolTip's stale popup reference after wx destroys it."""

    _center_message: bool = False
    _pointer_screen_position: wx.Point | None = None
    _positioned_for_pointer: bool = False

    def SetTarget(self, widget: wx.Window) -> None:
        super().SetTarget(widget)
        # Dismiss hover popups before controls open native menus or dropdowns.
        for event_type in (wx.EVT_LEFT_DOWN, wx.EVT_RIGHT_DOWN, wx.EVT_KEY_DOWN):
            widget.Bind(event_type, self._on_widget_interaction)

    def _on_widget_interaction(self, event: wx.Event) -> None:
        dismiss_all_tooltips()
        # Let the control process its normal click or key after dismissal.
        event.Skip()

    def DoHideNow(self) -> None:
        # Cancel pending hover creation so the tooltip cannot reopen over a menu.
        self._startTimer.Stop()
        self._endTimer.Stop()
        _clear_active_tooltip(self)
        tip_window = self._superToolTip
        # Drop the cached wrapper before destroying its native window.
        self._superToolTip = None
        if tip_window:
            # Destroy() is deferred; Hide() removes the native popup from
            # GTK's popup stack before another menu is mapped.
            tip_window.Hide()
            tip_window.Destroy()

    def SetPointerScreenPosition(self, position: wx.Point) -> None:
        self._pointer_screen_position = position

    def _position_window(self, tip_window: Any) -> None:
        if self._pointer_screen_position is None:
            tip_window.CalculateBestPosition(self._widget)
            self._positioned_for_pointer = False
            return

        pointer_x, pointer_y = self._pointer_screen_position
        tip_width, tip_height = tip_window.GetSize()
        screen_x, screen_y, screen_width, screen_height = wx.ClientDisplayRect()
        x = pointer_x + 14
        y = pointer_y - tip_height // 2
        if x + tip_width > screen_x + screen_width:
            x = pointer_x - tip_width - 14
        x = min(max(x, screen_x), screen_x + screen_width - tip_width)
        y = min(max(y, screen_y), screen_y + screen_height - tip_height)
        tip_window.SetPosition((x, y))
        self._positioned_for_pointer = True

    def PositionPopupNearPointer(self, tip_window: Any) -> None:
        if not self._positioned_for_pointer:
            self._position_window(tip_window)

    def _show_tooltip(self) -> None:
        active_tooltip = _active_tooltip_instance()
        if active_tooltip is not None and active_tooltip is not self:
            active_tooltip.DoHideNow()
        if self._superToolTip is not None:
            try:
                self._superToolTip.Destroy()
            except RuntimeError:
                pass

        if self._center_message:
            tip_window = _VerticallyCenteredToolTipWindow(self._widget, self)
        else:
            tip_window = _PlayOemToolTipWindow(self._widget, self)
        self._superToolTip = tip_window
        tip_window.CalculateBestSize()
        self._position_window(tip_window)
        tip_window.DropShadow(self.GetDropShadow())
        self._startTimer.Stop()
        self._endTimer.Stop()
        if self.GetUseFade():
            tip_window.StartAlpha(True)
        else:
            tip_window.Show()
        _set_active_tooltip(self)
        # Some popup backends reset their native position when first shown.
        self._position_window(tip_window)
        self._endTimer.Start(self._endDelayTime * 1000)

    def OnStartTimer(self) -> None:
        self._show_tooltip()

    def DoShowNow(self) -> None:
        self._show_tooltip()

    def OnWidgetLeave(self, event: wx.MouseEvent) -> None:
        try:
            super().OnWidgetLeave(event)
        except RuntimeError:
            # The popup can already be gone if wx delivered leave late.
            pass
        _clear_active_tooltip(self)
        self._superToolTip = None
        event.Skip()

    def OnEndTimer(self) -> None:
        try:
            super().OnEndTimer()
        except RuntimeError:
            pass
        _clear_active_tooltip(self)
        self._superToolTip = None


_active_tooltip: weakref.ReferenceType[_PlayOemSuperToolTip] | None = None


def _active_tooltip_instance() -> _PlayOemSuperToolTip | None:
    return _active_tooltip() if _active_tooltip is not None else None


def _clear_active_tooltip(tooltip: _PlayOemSuperToolTip) -> None:
    global _active_tooltip
    if _active_tooltip_instance() is tooltip:
        _active_tooltip = None


def _set_active_tooltip(tooltip: _PlayOemSuperToolTip) -> None:
    global _active_tooltip
    _active_tooltip = weakref.ref(tooltip)


def dismiss_all_tooltips() -> None:
    """Immediately hide the currently visible play-oem hover tooltip."""
    tooltip = _active_tooltip_instance()
    if tooltip is not None:
        tooltip.DoHideNow()


def set_tooltip(
    window: wx.Window, message: str, *, center_message: bool = True
) -> SuperToolTip:
    """Attach a platform-sized SuperToolTip, updating it if one already exists."""
    tooltip = getattr(window, "_play_oem_tooltip", None)
    if tooltip is None:
        tooltip = _PlayOemSuperToolTip(message)
        tooltip._center_message = center_message
        tooltip.SetBodyImage(
            wx.Bitmap.FromRGBA(TOOLTIP_HORIZONTAL_PADDING, 1, 0, 0, 0, 0)
        )
        tooltip.SetMessageFont(wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT))
        # wxPython truncates this delay to whole seconds; zero fails to start its timer.
        tooltip.SetStartDelay(1)
        tooltip.SetTarget(window)
        setattr(window, "_play_oem_tooltip", tooltip)
    else:
        tooltip.SetMessage(message)
    return tooltip


def dismiss_tooltip(window: wx.Window) -> None:
    """Immediately hide this window's play-oem tooltip, if one is attached."""
    tooltip = getattr(window, "_play_oem_tooltip", None)
    dismiss = getattr(tooltip, "DoHideNow", None)
    if callable(dismiss):
        dismiss()


def position_tooltip_at_pointer(
    tooltip: SuperToolTip, window: wx.Window, pointer_position: wx.Point
) -> None:
    """Create a tooltip beside the pointer, keeping it inside the display."""
    tip_window = tooltip.GetTipWindow()
    try:
        if tip_window is not None:
            tip_window.GetSize()
    except RuntimeError:
        # SuperToolTip may retain its Python wrapper after wx destroys the
        # underlying popup when the pointer leaves the target widget.
        tooltip._superToolTip = None
        tip_window = None

    if isinstance(tooltip, _PlayOemSuperToolTip):
        tooltip.SetPointerScreenPosition(window.ClientToScreen(pointer_position))
    if tip_window is None:
        tooltip.DoShowNow()
    elif isinstance(tooltip, _PlayOemSuperToolTip):
        tooltip.PositionPopupNearPointer(tip_window)
