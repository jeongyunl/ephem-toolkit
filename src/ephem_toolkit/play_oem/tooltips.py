"""Shared styling for play-oem hover tooltips."""

from __future__ import annotations

from typing import Any

import wx
from wx.lib.agw import supertooltip as _agw_supertooltip
from wx.lib.agw.supertooltip import SuperToolTip

TOOLTIP_HORIZONTAL_PADDING: int = 8
"""Horizontal inner padding used by play-oem tooltip windows, in pixels."""


class _VerticallyCenteredToolTipWindow(_agw_supertooltip.ToolTipWindow):
    """Balance the extra top padding AGW gives its one-line message body."""

    def __init__(self, parent: wx.Window, class_parent: _PlayOemSuperToolTip) -> None:
        super().__init__(parent, class_parent)
        self._spacing = 0

    def CalculateBestSize(self) -> None:
        super().CalculateBestSize()
        dc = wx.ClientDC(self)
        dc.SetFont(self._classParent.GetMessageFont())
        _message_width, message_height = dc.GetTextExtent(
            self._classParent.GetMessage().split("\n", maxsplit=1)[0] or " "
        )
        width, height = self.GetSize()
        self.SetSize((width + TOOLTIP_HORIZONTAL_PADDING, height + message_height))


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
        self.DoHideNow()
        # Let the control process its normal click or key after dismissal.
        event.Skip()

    def DoHideNow(self) -> None:
        # Cancel pending hover creation so the tooltip cannot reopen over a menu.
        self._startTimer.Stop()
        self._endTimer.Stop()
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
        if self._superToolTip is not None:
            try:
                self._superToolTip.Destroy()
            except RuntimeError:
                pass

        if self._center_message:
            tip_window = _VerticallyCenteredToolTipWindow(self._widget, self)
        else:
            tip_window = _agw_supertooltip.ToolTipWindow(self._widget, self)
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
        self._superToolTip = None
        event.Skip()

    def OnEndTimer(self) -> None:
        try:
            super().OnEndTimer()
        except RuntimeError:
            pass
        self._superToolTip = None


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
