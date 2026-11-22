"""Tests for the shared play-oem tooltip setup."""

from __future__ import annotations

from types import SimpleNamespace
import weakref

import pytest

from ephem_toolkit.play_oem import tooltips


class FakeToolTip:
    def __init__(self, message: str) -> None:
        self.message = message

    def SetBodyImage(self, _image) -> None:
        pass

    def SetMessageFont(self, _font) -> None:
        self.message_font = _font

    def SetStartDelay(self, delay: int) -> None:
        self.start_delay = delay

    def SetTarget(self, _window) -> None:
        pass


class FakeBitmap:
    @staticmethod
    def FromRGBA(*_args):
        return None


def test_set_tooltip_uses_positive_start_delay(monkeypatch) -> None:
    monkeypatch.setattr(tooltips, "_PlayOemSuperToolTip", FakeToolTip)
    monkeypatch.setattr(tooltips.wx, "Bitmap", FakeBitmap)
    system_font = object()

    class FakeSystemSettings:
        @staticmethod
        def GetFont(font_id):
            assert font_id == tooltips.wx.SYS_DEFAULT_GUI_FONT
            return system_font

    monkeypatch.setattr(tooltips.wx, "SystemSettings", FakeSystemSettings)
    window = type("FakeWindow", (), {})()

    tooltip = tooltips.set_tooltip(window, "Button tooltip")

    assert tooltip.start_delay == 1
    assert tooltip.message == "Button tooltip"
    assert tooltip.message_font is system_font


def test_tooltip_dimensions_scale_padding_and_height_with_content() -> None:
    assert tooltips._tooltip_dimensions([120, 80], 20) == (140, 70, 10, 10)
    assert tooltips._tooltip_dimensions([120], 30) == (150, 60, 15, 15)


@pytest.mark.parametrize(
    ("above_track", "expected_y"),
    [(True, 79), (False, 130)],
)
def test_pointer_tooltip_positioning_is_scoped_to_opted_in_widgets(
    monkeypatch, above_track: bool, expected_y: int
) -> None:
    monkeypatch.setattr(tooltips.wx, "ClientDisplayRect", lambda: (0, 0, 500, 500))
    positions = []
    tooltip = SimpleNamespace(
        _pointer_screen_position=tooltips.wx.Point(200, 150),
        _position_above_track=above_track,
        _positioned_for_pointer=False,
        _widget=SimpleNamespace(GetScreenRect=lambda: SimpleNamespace(y=100)),
    )
    tooltip._widget.GetClientSize = lambda: SimpleNamespace(height=58)
    tip_window = SimpleNamespace(
        GetSize=lambda: (100, 40),
        SetPosition=positions.append,
    )

    tooltips._PlayOemSuperToolTip._position_window(tooltip, tip_window)

    assert positions == [(214, expected_y)]


def test_active_slider_tooltip_follows_pointer_horizontally(monkeypatch) -> None:
    positions = []
    tip_window = SimpleNamespace(GetSize=lambda: (100, 40))

    class FakePlayOemToolTip:
        def GetTipWindow(self):
            return tip_window

        def SetPointerScreenPosition(self, position) -> None:
            self.pointer_position = position

        def _position_window(self, _tip_window) -> None:
            positions.append(self.pointer_position.x)

    monkeypatch.setattr(tooltips, "_PlayOemSuperToolTip", FakePlayOemToolTip)
    tooltip = FakePlayOemToolTip()
    window = SimpleNamespace(ClientToScreen=lambda position: position)

    tooltips.position_tooltip_at_pointer(
        tooltip, window, tooltips.wx.Point(100, 50), above_track=True
    )
    tooltips.position_tooltip_at_pointer(
        tooltip, window, tooltips.wx.Point(125, 50), above_track=True
    )

    assert positions == [100, 125]


def test_dismiss_tooltip_hides_attached_popup() -> None:
    dismissed = []
    window = SimpleNamespace(
        _play_oem_tooltip=SimpleNamespace(DoHideNow=lambda: dismissed.append(True))
    )

    tooltips.dismiss_tooltip(window)

    assert dismissed == [True]


def test_dismiss_tooltip_without_attached_popup_is_safe() -> None:
    tooltips.dismiss_tooltip(SimpleNamespace())


def test_dismiss_all_tooltips_hides_visible_and_pending_popups(monkeypatch) -> None:
    class ActiveTooltip:
        dismissed = False

        def DoHideNow(self) -> None:
            self.dismissed = True

    active = ActiveTooltip()
    pending = ActiveTooltip()
    monkeypatch.setattr(
        tooltips, "_all_tooltips", weakref.WeakSet((active, pending))
    )

    tooltips.dismiss_all_tooltips()

    assert active.dismissed
    assert pending.dismissed


def test_suppressed_tooltip_enter_cancels_start_timer() -> None:
    class Timer:
        stopped = False

        def Stop(self) -> None:
            self.stopped = True

    class Event:
        skipped = False

        def Skip(self) -> None:
            self.skipped = True

    timer, event = Timer(), Event()
    tooltip = SimpleNamespace(_startTimer=timer)
    with tooltips.suppress_tooltips():
        tooltips._PlayOemSuperToolTip.OnWidgetEnter(tooltip, event)

    assert timer.stopped
    assert event.skipped


def test_suppressed_tooltip_cannot_open_from_a_pending_callback() -> None:
    hidden = []
    tooltip = SimpleNamespace(DoHideNow=lambda: hidden.append(True))

    with tooltips.suppress_tooltips():
        tooltips._PlayOemSuperToolTip._show_tooltip(tooltip)

    assert hidden == [True]
