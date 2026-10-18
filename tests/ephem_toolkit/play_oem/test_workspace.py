"""Behavioral tests for the wx playback workspace shell."""

from __future__ import annotations

import pytest

from ephem_toolkit.play_oem import workspace


class FakeEvent:
    def __init__(self, value: int = 0, key_code: int = 0) -> None:
        self.value = value
        self.key_code = key_code
        self.skipped = False

    def GetInt(self) -> int:
        return self.value

    def GetKeyCode(self) -> int:
        return self.key_code

    def Skip(self) -> None:
        self.skipped = True


class FakeWidget:
    instances: list[FakeWidget] = []

    def __init__(self, _parent, _id: int, label: str = "", **_kwargs) -> None:
        self.label = label
        self.value = False
        self.enabled = True
        self.name = ""
        self.tooltip = ""
        self.bindings: dict[object, object] = {}
        self.__class__.instances.append(self)

    def Bind(self, event_type, callback) -> None:
        self.bindings[event_type] = callback

    def SetLabel(self, label: str) -> None:
        self.label = label

    def SetValue(self, value) -> None:
        self.value = value

    def Enable(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def SetName(self, name: str) -> None:
        self.name = name

    def SetToolTip(self, tooltip: str) -> None:
        self.tooltip = tooltip

    def SetMinSize(self, size) -> None:
        self.minimum_size = size

    def SetFocus(self) -> None:
        self.focused = True

    def trigger(self, event_type, event=None) -> None:
        self.bindings[event_type](FakeEvent() if event is None else event)


class FakeSlider(FakeWidget):
    def __init__(
        self,
        parent,
        widget_id: int,
        value: int,
        minimum: int,
        maximum: int,
        **kwargs,
    ) -> None:
        super().__init__(parent, widget_id, **kwargs)
        self.value = value
        self.minimum = minimum
        self.maximum = maximum
        self.emit_event_on_set = False

    def SetValue(self, value: int) -> None:
        self.value = value
        if self.emit_event_on_set and "slider" in self.bindings:
            self.bindings["slider"](FakeEvent(value))


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


class FakeSplitter:
    def __init__(self, parent, _id: int, **kwargs) -> None:
        self.parent = parent
        self.minimum_pane_size = 0
        self.sash_gravity = 0.0
        self.split_calls = []
        self.unsplit_calls = []
        self.is_split = False

    def SetMinimumPaneSize(self, size: int) -> None:
        self.minimum_pane_size = size

    def SetSashGravity(self, gravity: float) -> None:
        self.sash_gravity = gravity

    def SplitVertically(self, first, second, sash_position: int) -> bool:
        self.split_calls.append((first, second, sash_position))
        self.is_split = True
        return True

    def Unsplit(self, window) -> bool:
        self.unsplit_calls.append(window)
        self.is_split = False
        return True


class FakeSimplebook:
    def __init__(self, _parent, _id: int) -> None:
        self.pages = []
        self.selection = 0

    def AddPage(self, page, label: str) -> None:
        self.pages.append((page, label))

    def ChangeSelection(self, index: int) -> int:
        previous = self.selection
        self.selection = index
        return previous


class FakeFrame:
    def SetSizer(self, sizer) -> None:
        self.sizer = sizer


class FakeArtProvider:
    @staticmethod
    def GetBitmap(art_id, _client, size):
        return (art_id, size)


def configure_fake_wx(monkeypatch: pytest.MonkeyPatch) -> None:
    wx = workspace.wx
    FakeWidget.instances = []
    for name, value in {
        "Panel": FakePanel,
        "SplitterWindow": FakeSplitter,
        "Simplebook": FakeSimplebook,
        "BitmapToggleButton": FakeWidget,
        "Slider": FakeSlider,
        "StaticText": FakeWidget,
        "BoxSizer": FakeSizer,
        "ArtProvider": FakeArtProvider,
        "Size": lambda width, height: (width, height),
        "ID_ANY": -1,
        "VERTICAL": 1,
        "HORIZONTAL": 2,
        "SP_LIVE_UPDATE": 4,
        "EXPAND": 8,
        "ALL": 16,
        "LEFT": 32,
        "RIGHT": 64,
        "TOP": 128,
        "BOTTOM": 256,
        "SL_HORIZONTAL": 512,
        "ART_BUTTON": 1,
        "ART_GO_FORWARD": "forward",
        "ART_INFORMATION": "information",
        "EVT_BUTTON": "button",
        "EVT_KEY_DOWN": "key-down",
        "EVT_SLIDER": "slider",
        "WXK_UP": 315,
        "WXK_DOWN": 317,
    }.items():
        monkeypatch.setattr(wx, name, value)


def make_workspace(
    monkeypatch: pytest.MonkeyPatch, *, timeline_enabled: bool = True
) -> tuple[workspace.Workspace, list[float], FakeFrame]:
    configure_fake_wx(monkeypatch)
    frame = FakeFrame()
    seeks: list[float] = []
    result = workspace.Workspace(
        frame,
        seeks.append,
        timeline_enabled=timeline_enabled,
        context={
            "object": "TEST",
            "frame": "GCRF",
            "center": "Earth",
            "time_span": "start – stop",
            "sample_count": "2",
        },
        details=(("Object ID", "2024-001A"),),
    )
    return result, seeks, frame


def test_workspace_builds_feature_pages_split_panes_and_global_timeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, frame = make_workspace(monkeypatch)

    assert [label for _page, label in result.feature_book.pages] == [
        "Playback",
        "OEM file information",
    ]
    assert result.feature_book.selection == 0
    assert result.feature_buttons[0].name == "Playback"
    assert result.feature_buttons[0].tooltip == "Playback"
    assert result.feature_buttons[1].name == "OEM file information"
    assert result.graph_splitter.is_split is False
    assert result.graph_splitter.unsplit_calls == [result.right_stack]
    assert result.content_splitter.is_split
    assert result.timeline_slider.minimum == 0
    assert result.timeline_slider.maximum == 10_000
    assert frame.sizer.items[0][0] is result.content_splitter
    assert frame.sizer.items[1][0] is result.timeline_panel

    info_labels = [item[0].label for item in result.file_info_page.sizer.items]
    assert "Object: TEST" in info_labels
    assert "Samples: 2" in info_labels
    assert "Object ID: 2024-001A" in info_labels

    result.show_right_pane(True)
    assert result.graph_splitter.is_split
    result.show_right_pane(False)
    assert not result.graph_splitter.is_split
    assert result.graph_splitter.split_calls[-1][1] is result.right_stack


def test_feature_rail_supports_click_and_vertical_keyboard_navigation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)

    result.feature_buttons[1].trigger("button")

    assert result.feature_book.selection == 1
    assert result.feature_buttons[1].value
    assert not result.feature_buttons[0].value

    event = FakeEvent(key_code=workspace.wx.WXK_UP)
    result.feature_buttons[1].trigger("key-down", event)

    assert result.feature_book.selection == 0
    assert result.feature_buttons[0].value
    assert result.feature_buttons[0].focused
    assert not event.skipped


def test_global_timeline_syncs_without_recursive_seek_and_dispatches_user_seek(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, seeks, _frame = make_workspace(monkeypatch)
    result.timeline_slider.emit_event_on_set = True

    result.update_timeline(0.25)

    assert result.timeline_slider.value == 2500
    assert seeks == []
    for value, expected in ((0, 0.0), (5000, 0.5), (10_000, 1.0)):
        result.timeline_slider.trigger("slider", FakeEvent(value))
        assert seeks[-1] == expected


def test_zero_duration_timeline_disables_user_seeking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, seeks, _frame = make_workspace(monkeypatch, timeline_enabled=False)

    assert not result.timeline_slider.enabled
    result.timeline_slider.trigger("slider", FakeEvent(5000))

    assert seeks == []


def test_timeline_update_clamps_progress_to_slider_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)

    result.update_timeline(-1.0)
    assert result.timeline_slider.value == 0
    result.update_timeline(2.0)
    assert result.timeline_slider.value == 10_000
