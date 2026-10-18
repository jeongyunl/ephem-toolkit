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

    def Hide(self) -> None:
        self.shown = False

    def Show(self) -> None:
        self.shown = True

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


class FakeChoice(FakeWidget):
    def __init__(self, parent, widget_id, choices=(), **kwargs) -> None:
        super().__init__(parent, widget_id, **kwargs)
        self.choices = list(choices)
        self.selection = -1

    def SetSelection(self, selection: int) -> None:
        self.selection = selection

    def GetSelection(self) -> int:
        return self.selection


class FakeSizer:
    def __init__(self, _orientation: int) -> None:
        self.items = []

    def Add(self, item, proportion: int, flags: int = 0, border: int = 0) -> None:
        self.items.append((item, proportion, flags, border))

    def Detach(self, item) -> bool:
        self.items = [entry for entry in self.items if entry[0] is not item]
        return True


class FakeSize:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


class FakePanel:
    def __init__(self, parent, _id: int) -> None:
        self.parent = parent
        self.sizer = None
        self.minimum_size = FakeSize(320, 280)
        self.name = ""
        self.shown = True

    def SetSizer(self, sizer) -> None:
        self.sizer = sizer

    def SetName(self, name: str) -> None:
        self.name = name

    def Hide(self) -> None:
        self.shown = False

    def Show(self) -> None:
        self.shown = True

    def Reparent(self, parent) -> bool:
        self.parent = parent
        return True

    def GetParent(self):
        return self.parent

    def SetMinSize(self, size) -> None:
        self.minimum_size = FakeSize(*size)

    def GetMinSize(self) -> FakeSize:
        return self.minimum_size

    def IsShownOnScreen(self) -> bool:
        return True


class FakeGraphPanel(FakePanel):
    def __init__(self, parent, panel_id: str) -> None:
        super().__init__(parent, -1)
        self.panel_id = panel_id
        self.draw_count = 0

    def draw_if_needed(self) -> None:
        self.draw_count += 1


class FakeScrolledWindow(FakePanel):
    def __init__(self, parent, widget_id: int, **_kwargs) -> None:
        super().__init__(parent, widget_id)

    def SetScrollRate(self, _x_step: int, _y_step: int) -> None:
        pass

    def Bind(self, _event_type, _callback) -> None:
        pass

    def Layout(self) -> None:
        pass

    def FitInside(self) -> None:
        pass


class FakeSplitter:
    def __init__(self, parent, _id: int, **kwargs) -> None:
        self.parent = parent
        self.style = kwargs["style"]
        self.minimum_pane_size = 0
        self.sash_gravity = 0.0
        self.sash_position = 0
        self.window1 = None
        self.window2 = None
        self.client_width = 1000
        self.sash_size = 4
        self.split_calls = []
        self.unsplit_calls = []
        self.is_split = False
        self.minimum_size = FakeSize(0, 0)
        self.destroyed = False

    def SetMinimumPaneSize(self, size: int) -> None:
        self.minimum_pane_size = size

    def GetMinimumPaneSize(self) -> int:
        return self.minimum_pane_size

    def SetSashGravity(self, gravity: float) -> None:
        self.sash_gravity = gravity

    def SplitVertically(self, first, second, sash_position: int) -> bool:
        self.split_calls.append((first, second, sash_position))
        self.window1 = first
        self.window2 = second
        self.sash_position = sash_position
        self.is_split = True
        return True

    def SplitHorizontally(self, first, second, sash_position: int) -> bool:
        self.split_calls.append((first, second, sash_position))
        self.window1 = first
        self.window2 = second
        self.sash_position = sash_position
        self.is_split = True
        return True

    def Unsplit(self, window=None) -> bool:
        self.unsplit_calls.append(window)
        self.is_split = False
        self.window1 = None
        self.window2 = None
        return True

    def GetWindow1(self):
        return self.window1

    def GetWindow2(self):
        return self.window2

    def GetParent(self):
        return self.parent

    def Reparent(self, parent) -> bool:
        self.parent = parent
        return True

    def SetMinSize(self, size) -> None:
        self.minimum_size = FakeSize(*size)

    def GetMinSize(self) -> FakeSize:
        return self.minimum_size

    def Destroy(self) -> bool:
        self.destroyed = True
        return True

    def GetSashPosition(self) -> int:
        return self.sash_position

    def SetSashPosition(self, sash_position: int) -> None:
        self.sash_position = sash_position

    def GetSashSize(self) -> int:
        return self.sash_size

    def GetClientSize(self) -> FakeSize:
        return FakeSize(self.client_width, 700)


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


class FakeCallLater:
    calls = []

    def __init__(self, delay_ms: int, callback) -> None:
        self.delay_ms = delay_ms
        self.callback = callback
        self.running = True
        self.__class__.calls.append(self)

    def IsRunning(self) -> bool:
        return self.running

    def Stop(self) -> None:
        self.running = False

    def fire(self) -> None:
        self.running = False
        self.callback()


def configure_fake_wx(monkeypatch: pytest.MonkeyPatch) -> None:
    wx = workspace.wx
    FakeWidget.instances = []
    FakeCallLater.calls = []
    for name, value in {
        "Panel": FakePanel,
        "ScrolledWindow": FakeScrolledWindow,
        "SplitterWindow": FakeSplitter,
        "Simplebook": FakeSimplebook,
        "BitmapToggleButton": FakeWidget,
        "Slider": FakeSlider,
        "StaticText": FakeWidget,
        "Button": FakeWidget,
        "Choice": FakeChoice,
        "BoxSizer": FakeSizer,
        "ArtProvider": FakeArtProvider,
        "CallLater": FakeCallLater,
        "Size": lambda width, height: (width, height),
        "ID_ANY": -1,
        "VERTICAL": 1,
        "HORIZONTAL": 2,
        "SP_LIVE_UPDATE": 4,
        "SP_3DSASH": 1024,
        "VSCROLL": 5,
        "EXPAND": 8,
        "ALL": 16,
        "ALIGN_CENTER_VERTICAL": 24,
        "LEFT": 32,
        "RIGHT": 64,
        "TOP": 128,
        "BOTTOM": 256,
        "SL_HORIZONTAL": 512,
        "ART_BUTTON": 1,
        "ART_GO_FORWARD": "forward",
        "ART_INFORMATION": "information",
        "EVT_BUTTON": "button",
        "EVT_CHOICE": "choice",
        "EVT_KEY_DOWN": "key-down",
        "EVT_SLIDER": "slider",
        "EVT_SCROLLWIN": "scroll-window",
        "WXK_UP": 315,
        "WXK_DOWN": 317,
    }.items():
        monkeypatch.setattr(wx, name, value)


def make_workspace(
    monkeypatch: pytest.MonkeyPatch,
    *,
    timeline_enabled: bool = True,
    on_add_graph=None,
    view_choices=(),
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
        view_choices=view_choices,
        on_add_graph=on_add_graph,
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
    assert result.left_pane.name == workspace.CONTROLS_PANE_NAME
    assert result.middle_pane.name == workspace.MAIN_ANALYSIS_PANE_NAME
    assert result.right_pane.name == workspace.COMPARISON_PANE_NAME
    assert result.middle_pane.sizer.items[0][0].items[0][0].label == "Main Analysis"
    assert result.right_pane.sizer.items[0][0].items[0][0].label == "Comparison"
    assert result.graph_splitter.is_split is False
    assert result.graph_splitter.unsplit_calls == [result.right_pane]
    assert result.content_splitter.is_split
    assert result.content_splitter.minimum_pane_size == 240
    assert result.content_splitter.sash_gravity == 0.0
    assert result.content_splitter.style & workspace.wx.SP_3DSASH
    assert result.graph_splitter.minimum_pane_size == 320
    assert result.graph_splitter.sash_gravity == 1.0
    assert result.graph_splitter.style & workspace.wx.SP_3DSASH
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
    assert result.graph_splitter.split_calls[-1][1] is result.right_pane


def test_main_pane_sashes_resize_independently_and_restore_right_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)

    result.content_splitter.SetSashPosition(300)
    assert result.content_splitter.GetSashPosition() == 300

    result.show_right_pane(True)
    assert (
        result.graph_splitter.GetClientSize().width
        - result.graph_splitter.GetSashPosition()
        - result.graph_splitter.GetSashSize()
        == workspace.DEFAULT_RIGHT_PANE_WIDTH
    )

    result.graph_splitter.SetSashPosition(600)
    result.show_right_pane(False)
    result.graph_splitter.client_width = 1100
    result.show_right_pane(True)

    restored_width = (
        result.graph_splitter.GetClientSize().width
        - result.graph_splitter.GetSashPosition()
        - result.graph_splitter.GetSashSize()
    )
    assert restored_width == 396


def test_graph_hosts_replace_empty_state_and_restore_it_when_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    host = FakeGraphPanel(result.middle_stack, "first")
    empty_panel = result._empty_panels["middle"]

    result.add_graph_panel(host)

    assert result._graph_panels["middle"] == [host]
    assert empty_panel.shown is False

    result.remove_graph_panel(host)

    assert result._graph_panels["middle"] == []
    assert empty_panel.shown is True
    with pytest.raises(ValueError, match="unknown graph stack"):
        result.add_graph_panel(host, "invalid")


def test_add_graph_actions_route_to_the_correct_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    added_to: list[str] = []
    result, _seeks, _frame = make_workspace(monkeypatch, on_add_graph=added_to.append)

    result._add_buttons["middle"].trigger(workspace.wx.EVT_BUTTON)
    result._add_buttons["right"].trigger(workspace.wx.EVT_BUTTON)
    result._empty_panels["middle"].sizer.items[1][0].trigger(workspace.wx.EVT_BUTTON)

    assert added_to == ["middle", "right", "middle"]


def test_graph_stacks_use_styled_horizontal_splitters_and_collapse_on_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    middle_panels = [
        FakeGraphPanel(result.middle_stack, f"middle-{index}") for index in range(3)
    ]
    right_panels = [
        FakeGraphPanel(result.right_stack, f"right-{index}") for index in range(2)
    ]

    for panel in middle_panels:
        result.add_graph_panel(panel, "middle")
    for panel in right_panels:
        result.add_graph_panel(panel, "right")

    middle_root = result._stack_roots["middle"]
    right_root = result._stack_roots["right"]
    assert isinstance(middle_root, FakeSplitter)
    assert isinstance(right_root, FakeSplitter)
    assert middle_root.style & workspace.wx.SP_3DSASH
    assert right_root.style & workspace.wx.SP_3DSASH
    assert middle_root.sash_gravity == 0.5
    assert right_root.sash_gravity == 0.5
    assert middle_root.GetMinSize().height == 3 * 280 + 2 * 4
    assert right_root.GetMinSize().height == 2 * 280 + 4

    result.remove_graph_panel(middle_panels[1], "middle")
    assert result._graph_panels["middle"] == [middle_panels[0], middle_panels[2]]
    assert result._stack_roots["middle"].GetMinSize().height == 2 * 280 + 4
    assert result._graph_panels["right"] == right_panels

    result.remove_graph_panel(middle_panels[0], "middle")
    assert result._stack_roots["middle"] is middle_panels[2]
    result.remove_graph_panel(middle_panels[2], "middle")
    assert result._stack_roots["middle"] is None


def test_workspace_serializes_and_coalesces_visible_graph_redraws(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)

    first = FakeGraphPanel(result.middle_stack, "first")
    second = FakeGraphPanel(result.middle_stack, "second")
    result.add_graph_panel(first)
    result.add_graph_panel(second)
    monkeypatch.setattr(result, "is_graph_panel_visible", lambda _panel: True)

    result.queue_graph_redraw(first)
    first_timer = result._graph_redraw_timer
    result.queue_graph_redraw(first)
    result.queue_graph_redraw(second)

    assert first_timer is not None and first_timer.delay_ms == 1
    first_timer.fire()
    second_timer = result._graph_redraw_timer
    assert first.draw_count == 1
    assert second.draw_count == 0
    assert second_timer is not None and second_timer.delay_ms == 33

    second_timer.fire()
    assert second.draw_count == 1
    assert result._graph_redraw_timer is None


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
