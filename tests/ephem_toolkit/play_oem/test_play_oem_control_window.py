"""Behavioral tests for the wx-native playback dashboard."""

from __future__ import annotations

import pytest

from ephem_toolkit.play_oem import control_window
from ephem_toolkit.play_oem.views.registry import ViewRegistry


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

    def Bind(self, event_type, callback) -> None:
        self.bindings[event_type] = callback

    def SetLabel(self, label: str) -> None:
        self.label = label

    def Enable(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def SetName(self, name: str) -> None:
        self.name = name

    def SetHint(self, hint: str) -> None:
        self.hint = hint

    def SetForegroundColour(self, _colour) -> None:
        pass

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
    def __init__(self, _orientation: int) -> None:
        self.items = []

    def Add(self, item, proportion: int, flags: int = 0, border: int = 0) -> None:
        self.items.append((item, proportion, flags, border))


class FakePanel:
    def __init__(self, parent, _id: int) -> None:
        self.parent = parent
        self.sizer = None

    def SetSizer(self, sizer) -> None:
        self.sizer = sizer


class FakeCollapsiblePane(FakeWidget):
    def __init__(self, parent, widget_id: int, label: str) -> None:
        super().__init__(parent, widget_id, label)
        self.pane = FakePanel(parent, widget_id)

    def GetPane(self):
        return self.pane


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
        "CollapsiblePane": FakeCollapsiblePane,
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
        "open_view": [],
        "open_group": [],
    }
    registry = ViewRegistry()
    registry.register_view("trajectory-3d", lambda: None)
    registry.register_view("speed-altitude", lambda: None)
    owner = FakeOwner()
    window = control_window.ControlWindow(
        owner,
        calls["open_view"].append,
        calls["open_group"].append,
        registry,
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


def test_native_controls_dispatch_playback_navigation_and_view_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _owner, calls = make_window(monkeypatch)

    window.play_pause_button.trigger(control_window.wx.EVT_BUTTON)
    window.direction_button.trigger(control_window.wx.EVT_BUTTON)
    window.speed_preset_buttons[10.0].trigger(control_window.wx.EVT_BUTTON)
    for button in window.navigation_buttons:
        button.trigger(control_window.wx.EVT_BUTTON)
    window.group_buttons["overview"].trigger(control_window.wx.EVT_BUTTON)
    window.view_buttons["speed-altitude"].trigger(control_window.wx.EVT_BUTTON)

    assert calls["toggle"] == [True]
    assert calls["reverse"] == [True]
    assert calls["speed"] == [10.0]
    assert calls["start"] == [True]
    assert calls["step_samples"] == [-1, 1]
    assert calls["step_seconds"] == [-60.0, 60.0]
    assert calls["end"] == [True]
    assert calls["open_group"] == ["overview"]
    assert calls["open_view"] == ["speed-altitude"]
    assert not window.group_buttons["state"].enabled
    assert not window.group_buttons["motion"].enabled
    assert window.group_buttons["overview"].enabled


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
