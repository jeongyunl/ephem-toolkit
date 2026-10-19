"""Tests for the shared play-oem tooltip setup."""

from __future__ import annotations

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
