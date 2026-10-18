"""Behavioral tests for the wx-native playback dashboard."""

from __future__ import annotations

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
        self.bindings: dict[object, object] = {}
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

    def SetSizer(self, sizer) -> None:
        self.sizer = sizer


class FakeScrolledWindow(FakePanel):
    def __init__(self, parent, _id: int, **_kwargs) -> None:
        super().__init__(parent, _id)
        self.bindings: dict[object, object] = {}
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
        self.bindings: dict[tuple[object, int], object] = {}
        self.accelerator_table = None

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
) -> tuple[control_window.ControlWindow, FakeOwner, dict[str, list[object]]]:
    configure_fake_wx(monkeypatch)
    calls: dict[str, list[object]] = {
        "toggle": [],
        "speed": [],
        "reverse": [],
        "seek_time": [],
        "step_samples": [],
        "step_seconds": [],
        "start": [],
        "end": [],
    }
    owner = FakeOwner()
    window = control_window.ControlWindow(
        owner,
        lambda: calls["toggle"].append(True),
        calls["speed"].append,
        lambda: calls["reverse"].append(True),
        on_seek_to_time=calls["seek_time"].append,
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
    window.direction_button.trigger(control_window.wx.EVT_TOGGLEBUTTON)
    window.speed_preset_buttons[10.0].trigger(control_window.wx.EVT_TOGGLEBUTTON)
    for button in window.navigation_buttons:
        button.trigger(control_window.wx.EVT_BUTTON)

    assert calls["toggle"] == [True]
    assert calls["reverse"] == [True]
    assert calls["speed"] == [10.0]
    assert calls["start"] == [True]
    assert calls["step_samples"] == [-1, 1]
    assert calls["step_seconds"] == [-60.0, 60.0]
    assert calls["end"] == [True]


def test_playback_controls_remain_reachable_in_scrollable_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _owner, _calls = make_window(monkeypatch)

    assert window.panel.scroll_rate == (0, 10)
    playback_row = window.panel.sizer.items[2][0]
    assert playback_row.orientation == control_window.wx.VERTICAL
    assert window.time_entry.parent is window.panel
    assert window.seek_button.parent is window.panel
    assert window.panel.sizer.items[4][0].orientation == control_window.wx.VERTICAL
    assert window.navigation_buttons[1].parent is window.panel
    assert window.speed_preset_buttons[100.0].parent is window.panel
    assert not hasattr(window, "view_groups_pane")
    assert not hasattr(window, "group_buttons")
    assert not hasattr(window, "view_choice")
    assert not hasattr(window, "open_view_button")
    assert window.panel.fit_inside_count == 1

    window.panel.bindings[control_window.wx.EVT_SIZE](FakeEvent())

    assert window.panel.layout_count == 1
    assert window.panel.fit_inside_count == 2


@pytest.mark.parametrize(
    "control_name", ("time_entry", "seek_button", "last_navigation_button")
)
def test_keyboard_focus_scrolls_offscreen_playback_controls_into_view(
    monkeypatch: pytest.MonkeyPatch,
    control_name: str,
) -> None:
    window, _owner, _calls = make_window(monkeypatch)
    control = {
        "time_entry": window.time_entry,
        "seek_button": window.seek_button,
        "last_navigation_button": window.navigation_buttons[-1],
    }[control_name]
    control.position = FakeSize(0, 540)

    control.trigger(control_window.wx.EVT_SET_FOCUS)

    assert window.panel.scroll_position == (0, 17)
    control.trigger(control_window.wx.EVT_SET_FOCUS)
    assert window.panel.scroll_position == (0, 17)


def test_dashboard_formats_state_and_missing_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ephem_toolkit.play_oem.cursor import CursorState, CursorStatus
    import numpy as np

    window, _owner, _calls = make_window(monkeypatch)
    assert all(
        label.parent is window.state_panel
        for label in (
            window.position_label,
            window.velocity_label,
            window.speed_altitude_label,
            window.cursor_status_label,
        )
    )
    assert len(window.state_panel.sizer.items) == 4
    assert all(
        label not in [item[0] for item in window.panel.sizer.items]
        for label in (
            window.position_label,
            window.velocity_label,
            window.speed_altitude_label,
            window.cursor_status_label,
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
    assert "Position (km): 1.000, 2.000, 3.000" == window.position_label.label
    assert (
        "Velocity (km/s): 0.100000, 0.200000, 0.300000" == window.velocity_label.label
    )
    assert "0.374166 km/s" in window.speed_altitude_label.label
    assert window.cursor_status_label.label == "State: interpolated"

    window.update_current_state(
        CursorState(2.0, None, None, None, None, None, None, CursorStatus.OUT_OF_RANGE)
    )
    assert "unavailable" in window.position_label.label
    assert "unavailable" in window.velocity_label.label
    assert window.cursor_status_label.label == "State: out of range"
    window.update_current_state(
        CursorState(50.0, None, None, None, None, None, None, CursorStatus.GAP)
    )
    assert window.cursor_status_label.label == "State: data gap; no state available"


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
    assert window.elapsed_label.label == "Elapsed: 25 s"
    assert window.utc_label.label == "UTC: example"
    assert window.play_pause_button.label == "Pause"
    assert window.speed_label.label == "Speed: -10x"
    assert window.direction_button.label == "Forward"
    assert window.direction_button.value
    assert window.speed_preset_buttons[10.0].value
    assert window.utc_label.wrap_width == 166
    assert window.speed_scale_label.wrap_width == 166
    assert window.seek_label.wrap_width == 166
    assert not calls["speed"]

    window.update_playback_state("Elapsed: 25 s\nUTC: example", False, 1.0)

    assert not window.direction_button.value
    assert window.speed_preset_buttons[1.0].value
    assert not window.speed_preset_buttons[10.0].value
    assert not calls["speed"]


def test_time_entry_dispatches_text_and_errors_are_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _owner, calls = make_window(monkeypatch)
    window.time_entry.value = "1h30m"

    window.time_entry.trigger(control_window.wx.EVT_TEXT_ENTER)
    window.seek_button.trigger(control_window.wx.EVT_BUTTON)
    window.show_time_error("invalid time")
    assert window.time_error_label.label == "invalid time"
    window.clear_time_error()

    assert calls["seek_time"] == ["1h30m", "1h30m"]
    assert window.time_error_label.label == ""
    assert window.time_entry.name == "Seek time"
    assert "UTC" in window.time_entry.hint


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

    focus_event = FakeEvent()
    window.time_entry.trigger(control_window.wx.EVT_SET_FOCUS, focus_event)
    assert focus_event.skipped
    assert owner.accelerator_table.entries == ()

    blur_event = FakeEvent()
    window.time_entry.trigger(control_window.wx.EVT_KILL_FOCUS, blur_event)
    assert blur_event.skipped
    assert keys == {
        (entry.flags, entry.key_code) for entry in owner.accelerator_table.entries
    }
