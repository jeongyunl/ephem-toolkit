"""Behavioral tests for the wx-native playback dashboard."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pytest

from ephem_toolkit.play_oem import control_window


class FakeEvent:
    def __init__(self, value: int = 0) -> None:
        self.value = value
        self.skipped = False

    def GetInt(self) -> int:
        return self.value

    def Skip(self) -> None:
        self.skipped = True


class FakeWidget:
    def __init__(self, _parent, _id: int, label: str = "", **_kwargs) -> None:
        self.parent = _parent
        self.label = label
        self.enabled = True
        self.name = ""
        self.hint = ""
        self.bindings: dict[object, Callable[..., object]] = {}
        self.wrap_width = None
        self.position = FakeSize(0, 0)
        self.size = FakeSize(84, 24)

    def Bind(self, event_type, callback) -> None:
        self.bindings[event_type] = callback

    def SetLabel(self, label: str) -> None:
        self.label = label

    def Enable(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def SetName(self, name: str) -> None:
        self.name = name

    def SetToolTip(self, tooltip: str) -> None:
        self.tooltip = tooltip

    def SetHint(self, hint: str) -> None:
        self.hint = hint

    def SetForegroundColour(self, _colour) -> None:
        pass

    def Wrap(self, width: int) -> None:
        self.wrap_width = width

    def GetPosition(self):
        if isinstance(self.parent, FakeScrolledWindow):
            return FakeSize(
                self.position.x,
                self.position.y
                - self.parent.view_start.y * self.parent.scroll_pixels_per_unit.y,
            )
        return self.position

    def GetSize(self):
        return self.size

    def trigger(self, event_type, event=None) -> None:
        self.bindings[event_type](FakeEvent() if event is None else event)


class FakeButton(FakeWidget):
    def __init__(self, parent, _id: int, label: str = "", **kwargs) -> None:
        super().__init__(parent, _id, label, **kwargs)
        self.value = False

    def SetValue(self, value: bool) -> None:
        self.value = value


class FakeTextCtrl(FakeWidget):
    def __init__(self, parent, _id: int, value: str = "", **kwargs) -> None:
        super().__init__(parent, _id, value, **kwargs)
        self.value = value

    def GetValue(self) -> str:
        return self.value

    def SetValue(self, value: str) -> None:
        self.value = value


class FakeSlider(FakeWidget):
    def __init__(
        self,
        parent,
        _id: int,
        value: int,
        minimum: int,
        maximum: int,
        **_kwargs,
    ) -> None:
        super().__init__(parent, _id)
        self.value = value
        self.minimum = minimum
        self.maximum = maximum
        self.emit_event_on_set = False

    def SetValue(self, value: int) -> None:
        self.value = value
        if self.emit_event_on_set and control_window.wx.EVT_SLIDER in self.bindings:
            self.bindings[control_window.wx.EVT_SLIDER](FakeEvent(value))


class FakeSizer:
    def __init__(self, orientation: int) -> None:
        self.orientation = orientation
        self.items = []

    def Add(self, item, proportion: int, flags: int = 0, border: int = 0) -> None:
        self.items.append((item, proportion, flags, border))


class FakePanel:
    def __init__(self, parent, _id: int) -> None:
        self.parent = parent
        self.sizer = None

    def SetName(self, name: str) -> None:
        self.name = name

    def SetSizer(self, sizer) -> None:
        self.sizer = sizer


class FakeScrolledWindow(FakePanel):
    def __init__(self, parent, _id: int, **kwargs) -> None:
        super().__init__(parent, _id)
        self.style = kwargs.get("style", 0)
        self.bindings: dict[object, Callable[..., object]] = {}
        self.scroll_rate = None
        self.fit_inside_count = 0
        self.layout_count = 0
        self.scroll_pixels_per_unit = FakeSize(0, 10)
        self.view_start = FakeSize(0, 0)
        self.scroll_position = None

    def GetClientSize(self):
        return FakeSize(190, 400)

    def GetViewStart(self):
        return self.view_start.x, self.view_start.y

    def GetScrollPixelsPerUnit(self):
        return self.scroll_pixels_per_unit.x, self.scroll_pixels_per_unit.y

    def Scroll(self, x: int, y: int) -> None:
        self.scroll_position = (x, y)
        self.view_start = FakeSize(x, y)

    def Bind(self, event_type, callback) -> None:
        self.bindings[event_type] = callback

    def SetScrollRate(self, x_step: int, y_step: int) -> None:
        self.scroll_rate = (x_step, y_step)

    def FitInside(self) -> None:
        self.fit_inside_count += 1

    def Layout(self) -> None:
        self.layout_count += 1


class FakeSize:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.x = width
        self.y = height


class FakeOwner:
    def __init__(self) -> None:
        self.bindings: dict[tuple[object, int], Callable[..., object]] = {}
        self.accelerator_table = FakeAcceleratorTable()

    def Bind(self, event_type, callback, *, id: int) -> None:
        self.bindings[(event_type, id)] = callback

    def SetAcceleratorTable(self, table) -> None:
        self.accelerator_table = table


class FakeAcceleratorEntry:
    def __init__(self, flags: int, key_code: int, command_id: int) -> None:
        self.flags = flags
        self.key_code = key_code
        self.command_id = command_id


class FakeAcceleratorTable:
    def __init__(self, entries=()) -> None:
        self.entries = tuple(entries)


def configure_fake_wx(monkeypatch: pytest.MonkeyPatch) -> None:
    wx = control_window.wx
    monkeypatch.setattr(
        control_window,
        "set_tooltip",
        lambda widget, message: widget.SetToolTip(message),
    )
    for name, value in {
        "Panel": FakePanel,
        "ScrolledWindow": FakeScrolledWindow,
        "BoxSizer": FakeSizer,
        "StaticText": FakeWidget,
        "Button": FakeButton,
        "ToggleButton": FakeButton,
        "TextCtrl": FakeTextCtrl,
        "Slider": FakeSlider,
        "AcceleratorEntry": FakeAcceleratorEntry,
        "AcceleratorTable": FakeAcceleratorTable,
        "Colour": lambda *values: values,
        "NewIdRef": iter(range(1000, 1010)).__next__,
        "ID_ANY": -1,
        "VERTICAL": 1,
        "HORIZONTAL": 2,
        "VSCROLL": 2048,
        "TAB_TRAVERSAL": 4096,
        "EXPAND": 4,
        "LEFT": 8,
        "RIGHT": 16,
        "TOP": 32,
        "BOTTOM": 64,
        "ALL": 128,
        "ALIGN_CENTER_VERTICAL": 256,
        "SL_HORIZONTAL": 512,
        "TE_PROCESS_ENTER": 1024,
        "EVT_BUTTON": "button",
        "EVT_TOGGLEBUTTON": "toggle-button",
        "EVT_SIZE": "size",
        "EVT_SLIDER": "slider",
        "EVT_TEXT_ENTER": "text-enter",
        "EVT_SET_FOCUS": "set-focus",
        "EVT_KILL_FOCUS": "kill-focus",
        "EVT_MENU": "menu",
        "ACCEL_NORMAL": 0,
        "ACCEL_SHIFT": 1,
        "WXK_SPACE": 32,
        "WXK_LEFT": 314,
        "WXK_RIGHT": 316,
        "WXK_HOME": 313,
        "WXK_END": 312,
    }.items():
        monkeypatch.setattr(wx, name, value)


def make_window(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Any, FakeOwner, dict[str, list[object]]]:
    configure_fake_wx(monkeypatch)
    calls: dict[str, list[object]] = {
        "toggle": [],
        "speed": [],
        "reverse": [],
        "step_samples": [],
        "step_seconds": [],
        "start": [],
        "end": [],
    }
    owner = FakeOwner()
    # The monkeypatched wx constructors produce fakes with test-only attributes.
    window_factory = cast(Callable[..., Any], control_window.ControlWindow)
    window = window_factory(
        owner,
        lambda: calls["toggle"].append(True),
        calls["speed"].append,
        lambda: calls["reverse"].append(True),
        on_step_samples=calls["step_samples"].append,
        on_step_seconds=calls["step_seconds"].append,
        on_jump_to_start=lambda: calls["start"].append(True),
        on_jump_to_end=lambda: calls["end"].append(True),
        accelerator_parent=owner,
    )
    return window, owner, calls


def test_native_controls_dispatch_playback_and_navigation_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _owner, calls = make_window(monkeypatch)

    window.play_pause_button.trigger(control_window.wx.EVT_BUTTON)
    window.reverse_toggle_button.trigger(control_window.wx.EVT_TOGGLEBUTTON)
    for button in window.navigation_buttons:
        button.trigger(control_window.wx.EVT_BUTTON)

    assert calls["toggle"] == [True]
    assert calls["reverse"] == [True]
    assert calls["speed"] == []
    assert calls["start"] == [True]
    assert calls["step_samples"] == [-1, 1]
    assert calls["step_seconds"] == [-60.0, 60.0]
    assert calls["end"] == [True]
    assert [button.label for button in window.navigation_buttons] == [
        "Start",
        "Previous sample",
        "-1 min",
        "+1 min",
        "Next sample",
        "End",
    ]


def test_playback_controls_remain_reachable_in_scrollable_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _owner, _calls = make_window(monkeypatch)

    assert window.playback_scroller.scroll_rate == (0, 10)
    playback_row = window.playback_scroller.sizer.items[2][0]
    assert playback_row.orientation == control_window.wx.VERTICAL
    playback_controls = [item[0] for item in playback_row.items]
    assert window.playback_heading_label in playback_controls
    assert window.speed_slider in playback_controls
    navigation_group = window.playback_scroller.sizer.items[3][0]
    assert window.navigation_heading_label in [
        item[0] for item in navigation_group.items
    ]
    assert not hasattr(window, "time_entry")
    assert not hasattr(window, "seek_button")
    navigation_row = navigation_group.items[1][0]
    assert all(
        button in [item[0] for item in navigation_row.items]
        for button in window.navigation_buttons
    )
    assert window.navigation_buttons[1].parent is window.playback_scroller
    assert "100 slider steps per decade" in window.speed_slider.tooltip
    assert not hasattr(window, "view_groups_pane")
    assert not hasattr(window, "group_buttons")
    assert not hasattr(window, "view_choice")
    assert not hasattr(window, "open_view_button")
    assert window.playback_scroller.fit_inside_count == 1

    window.playback_scroller.bindings[control_window.wx.EVT_SIZE](FakeEvent())

    assert window.playback_scroller.layout_count == 2
    assert window.playback_scroller.fit_inside_count == 4


def test_utc_timestamp_wraps_at_the_date_time_separator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _owner, _calls = make_window(monkeypatch)

    window.update_time("Elapsed: 0 s\nUTC: 2026-07-06T00:00:00.000")

    assert window.utc_time_label.label == "UTC: 2026-07-06T\n00:00:00.000"


@pytest.mark.parametrize("control_name", ("last_navigation_button",))
def test_keyboard_focus_scrolls_offscreen_playback_controls_into_view(
    monkeypatch: pytest.MonkeyPatch,
    control_name: str,
) -> None:
    window, _owner, _calls = make_window(monkeypatch)
    control = {
        "last_navigation_button": window.navigation_buttons[-1],
    }[control_name]
    control.position = FakeSize(0, 540)

    control.trigger(control_window.wx.EVT_SET_FOCUS)

    assert window.playback_scroller.scroll_position == (0, 17)
    control.trigger(control_window.wx.EVT_SET_FOCUS)
    assert window.playback_scroller.scroll_position == (0, 17)


def test_dashboard_formats_state_and_missing_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ephem_toolkit.play_oem.cursor import CursorState, CursorStatus
    import numpy as np

    window, _owner, _calls = make_window(monkeypatch)
    assert all(
        label.parent is window.state_scroller
        for label in (
            window.state_position_label,
            window.state_velocity_label,
            window.state_derived_label,
            window.state_cursor_status_label,
        )
    )
    assert len(window.state_scroller.sizer.items) == 4
    assert window.state_scroller.name == "Current state readout"
    assert window.state_scroller.scroll_rate == (0, 10)
    assert window.state_position_label.name == "Position components (kilometers)"
    assert (
        window.state_velocity_label.name
        == "Velocity components (kilometers per second)"
    )
    assert window.state_derived_label.name == "Derived speed and altitude"
    assert window.state_cursor_status_label.name == "Cursor data status"
    assert all(
        label not in [item[0] for item in window.playback_scroller.sizer.items]
        for label in (
            window.state_position_label,
            window.state_velocity_label,
            window.state_derived_label,
            window.state_cursor_status_label,
        )
    )
    window.update_current_state(
        CursorState(
            1.0,
            np.zeros(6),
            np.array([1.0, 2.0, 3.0]),
            np.array([0.1, 0.2, 0.3]),
            0.374166,
            4.5,
            6378.0,
            CursorStatus.INTERPOLATED,
        )
    )
    assert window.state_position_label.label == (
        "Position (km)\nX: 1.000\nY: 2.000\nZ: 3.000"
    )
    assert (
        window.state_velocity_label.label
        == "Velocity (km/s)\nVx: 0.100000\nVy: 0.200000\nVz: 0.300000"
    )
    assert "0.374166 km/s" in window.state_derived_label.label
    assert window.state_derived_label.label == (
        "Derived values\nSpeed:\n0.374166 km/s\nAltitude:\n4.500 km"
    )
    assert window.state_cursor_status_label.label == "Cursor status: interpolated"

    window.update_current_state(
        CursorState(2.0, None, None, None, None, None, None, CursorStatus.OUT_OF_RANGE)
    )
    assert "X: unavailable" in window.state_position_label.label
    assert "Vx: unavailable" in window.state_velocity_label.label
    assert window.state_cursor_status_label.label == "Cursor status: out of range"
    window.update_current_state(
        CursorState(50.0, None, None, None, None, None, None, CursorStatus.GAP)
    )
    assert (
        window.state_cursor_status_label.label
        == "Cursor status: data gap; no state available"
    )


def test_state_readout_preserves_component_precision_and_scroll_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ephem_toolkit.play_oem.cursor import CursorState, CursorStatus
    import numpy as np

    window, _owner, _calls = make_window(monkeypatch)
    window.state_scroller.Scroll(0, 7)
    window.update_current_state(
        CursorState(
            3.0,
            np.zeros(6),
            np.array([123456789.1234, -98765432.1111, 0.0]),
            np.array([123456.12345678, -98765.123456789, 0.0]),
            123456.12345678,
            987654321.1234,
            6378.0,
            CursorStatus.EXACT_SAMPLE,
        )
    )

    assert "X: 123456789.123" in window.state_position_label.label
    assert "Y: -98765432.111" in window.state_position_label.label
    assert "Vx: 123456.123457" in window.state_velocity_label.label
    assert "Vy: -98765.123457" in window.state_velocity_label.label
    assert "Altitude:\n987654321.123 km" in window.state_derived_label.label
    assert window.state_cursor_status_label.label == "Cursor status: sampled"
    assert window.state_scroller.GetViewStart() == (0, 7)

    window.update_current_state(
        CursorState(
            4.0,
            np.zeros(6),
            None,
            np.array([1.0, 2.0, 3.0]),
            None,
            None,
            None,
            CursorStatus.UNAVAILABLE,
        )
    )
    assert window.state_position_label.label == (
        "Position (km)\nX: unavailable\nY: unavailable\nZ: unavailable"
    )
    assert "Vx: 1.000000" in window.state_velocity_label.label
    assert window.state_cursor_status_label.label == "Cursor status: unavailable"


@pytest.mark.parametrize(
    ("position", "expected"),
    [(0, 1.0), (100, 10.0), (200, 100.0), (300, 1000.0)],
)
def test_log_speed_slider_maps_integer_values_to_speed(
    monkeypatch: pytest.MonkeyPatch,
    position: int,
    expected: float,
) -> None:
    window, _owner, calls = make_window(monkeypatch)

    window.speed_slider.trigger(
        control_window.wx.EVT_SLIDER,
        FakeEvent(position),
    )

    assert calls["speed"][-1] == pytest.approx(expected)


def test_playback_state_updates_readouts_and_speed_without_seeking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _owner, calls = make_window(monkeypatch)
    window.speed_slider.emit_event_on_set = True

    window.update_playback_state("Elapsed: 25 s\nUTC: example", True, -10.0)

    assert window.speed_slider.value == 100
    assert window.elapsed_time_label.label == "Elapsed: 25 s"
    assert window.utc_time_label.label == "UTC: example"
    assert window.play_pause_button.label == "Pause"
    assert window.speed_readout_label.label == "Speed: -10x"
    assert window.speed_scale_label.label == (
        "Speed slider: -10x (log scale, 1x to 9000x)"
    )
    assert window.reverse_toggle_button.label == "Forward"
    assert window.reverse_toggle_button.value
    assert window.utc_time_label.wrap_width == 166
    assert window.speed_scale_label.wrap_width == 166
    assert not calls["speed"]

    window.update_playback_state("Elapsed: 25 s\nUTC: example", False, 1.0)

    assert window.speed_scale_label.label == (
        "Speed slider: +1x (log scale, 1x to 9000x)"
    )
    assert not window.reverse_toggle_button.value
    assert not calls["speed"]


def test_accelerators_cover_playback_navigation_and_disable_for_time_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, owner, calls = make_window(monkeypatch)

    keys = {(entry.flags, entry.key_code) for entry in owner.accelerator_table.entries}
    assert keys == {
        (control_window.wx.ACCEL_NORMAL, control_window.wx.WXK_SPACE),
        (control_window.wx.ACCEL_NORMAL, ord("R")),
        (control_window.wx.ACCEL_NORMAL, control_window.wx.WXK_LEFT),
        (control_window.wx.ACCEL_NORMAL, control_window.wx.WXK_RIGHT),
        (control_window.wx.ACCEL_SHIFT, control_window.wx.WXK_LEFT),
        (control_window.wx.ACCEL_SHIFT, control_window.wx.WXK_RIGHT),
        (control_window.wx.ACCEL_NORMAL, control_window.wx.WXK_HOME),
        (control_window.wx.ACCEL_NORMAL, control_window.wx.WXK_END),
    }
    for entry in owner.accelerator_table.entries:
        owner.bindings[(control_window.wx.EVT_MENU, entry.command_id)](FakeEvent())

    assert calls["toggle"] == [True]
    assert calls["reverse"] == [True]
    assert calls["step_samples"] == [-1, 1]
    assert calls["step_seconds"] == [-60.0, 60.0]
    assert calls["start"] == [True]
    assert calls["end"] == [True]

    time_entry = FakeTextCtrl(window.playback_scroller, -1, "")
    window.bind_time_entry(time_entry)
    focus_event = FakeEvent()
    time_entry.trigger(control_window.wx.EVT_SET_FOCUS, focus_event)
    assert focus_event.skipped
    assert owner.accelerator_table.entries == ()

    blur_event = FakeEvent()
    time_entry.trigger(control_window.wx.EVT_KILL_FOCUS, blur_event)
    assert blur_event.skipped
    assert keys == {
        (entry.flags, entry.key_code) for entry in owner.accelerator_table.entries
    }
