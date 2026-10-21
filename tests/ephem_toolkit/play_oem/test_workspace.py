"""Behavioral tests for the wx playback workspace shell."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

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
        self.style = _kwargs.get("style", 0)
        self.value = False
        self.enabled = True
        self.name = ""
        self.tooltip = ""
        self.bindings: dict[object, Callable[[FakeEvent], None]] = {}
        self.wrap_width = None
        self.__class__.instances.append(self)

    def Bind(self, event_type: object, callback: Callable[[FakeEvent], None]) -> None:
        self.bindings[event_type] = callback

    def SetLabel(self, label: str) -> None:
        self.label = label

    def SetValue(self, value) -> None:
        self.value = value

    def GetValue(self):
        return self.value

    def GetBestSize(self):
        return FakeSize(40, 24)

    def Enable(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def IsEnabled(self) -> bool:
        return self.enabled

    def SetName(self, name: str) -> None:
        self.name = name

    def SetToolTip(self, tooltip: str) -> None:
        self.tooltip = tooltip

    def SetHint(self, hint: str) -> None:
        self.hint = hint

    def SetForegroundColour(self, colour) -> None:
        self.foreground_colour = colour

    def ChangeValue(self, value: str) -> None:
        self.value = value

    def SetInsertionPointEnd(self) -> None:
        self.insertion_point = len(self.value)

    def HasFocus(self) -> bool:
        return getattr(self, "focused", False)

    def Wrap(self, width: int) -> None:
        self.wrap_width = width

    def SetMinSize(self, size) -> None:
        self.minimum_size = size

    def SetMaxSize(self, size) -> None:
        self.maximum_size = size

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

    def GetItem(self, window) -> FakeSizerItem:
        return FakeSizerItem(self, window)


class FakeSizerItem:
    def __init__(self, sizer: FakeSizer, window) -> None:
        self.sizer = sizer
        self.window = window

    def SetProportion(self, proportion: int) -> None:
        self.sizer.items = [
            (
                item,
                proportion if item is self.window else entry_proportion,
                flags,
                border,
            )
            for item, entry_proportion, flags, border in self.sizer.items
        ]


class FakeSize:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


class FakePanel:
    def __init__(self, parent, _id: int, size=None) -> None:
        self.parent = parent
        self.sizer = None
        self.minimum_size = FakeSize(320, 280)
        self.client_size = FakeSize(180, 400)
        self.current_size = FakeSize(320, 280)
        self.name = ""
        self.shown = True
        self.bindings = {}
        self.size = size

    def SetSizer(self, sizer) -> None:
        self.sizer = sizer

    def Bind(self, event_type, callback) -> None:
        self.bindings[event_type] = callback

    def GetClientSize(self) -> FakeSize:
        return self.client_size

    def Layout(self) -> None:
        pass

    def SetName(self, name: str) -> None:
        self.name = name

    def SetCanFocus(self, can_focus: bool) -> None:
        self.can_focus = can_focus

    def SetFocus(self) -> None:
        self.focused = True

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

    def GetSize(self) -> FakeSize:
        return self.current_size

    def IsShownOnScreen(self) -> bool:
        return True

    def SetBackgroundColour(self, colour) -> None:
        self.background_colour = colour

    def SetCursor(self, cursor) -> None:
        self.cursor = cursor

    def CaptureMouse(self) -> None:
        self.captured = True

    def ReleaseMouse(self) -> None:
        self.captured = False

    def HasCapture(self) -> bool:
        return getattr(self, "captured", False)


class FakePoint:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class FakeMouse:
    position = (0, 0)


class FakeSystemSettings:
    @staticmethod
    def GetColour(colour_id):
        return ("system-colour", colour_id)


class FakeGraphPanel(FakePanel):
    def __init__(self, parent, panel_id: str) -> None:
        super().__init__(parent, -1)
        self.panel_id = panel_id
        self.draw_count = 0

    def draw_if_needed(self) -> None:
        self.draw_count += 1

    def request_redraw(self) -> None:
        self.draw_count += 1


class FakeScrolledWindow(FakePanel):
    FIT_HEIGHT = 600

    def __init__(self, parent, widget_id: int, **kwargs) -> None:
        super().__init__(parent, widget_id)
        self.style = kwargs.get("style", 0)
        self.always_shown_scrollbars = None
        self.scroll_range = 0
        self.scroll_thumb = 1
        self.view_start = (0, 0)
        self.scroll_rate = None

    def SetScrollRate(self, x_step: int, y_step: int) -> None:
        self.scroll_rate = (x_step, y_step)

    def AlwaysShowScrollbars(self, horizontal: bool, vertical: bool) -> None:
        self.always_shown_scrollbars = (horizontal, vertical)

    def GetScrollRange(self, _orientation: int) -> int:
        return self.scroll_range

    def GetScrollThumb(self, _orientation: int) -> int:
        return self.scroll_thumb

    def GetViewStart(self) -> tuple[int, int]:
        return self.view_start

    def Scroll(self, x: int, y: int) -> None:
        self.view_start = (x, y)

    def Layout(self) -> None:
        pass

    def FitInside(self) -> None:
        self.virtual_size = FakeSize(320, self.FIT_HEIGHT)
        # Like wx, the view cannot stay beyond the range that FitInside just set.
        x, y = self.view_start
        max_start = max(0, self.FIT_HEIGHT - self.GetClientSize().height)
        self.view_start = (x, min(y, max_start))

    def GetVirtualSize(self) -> FakeSize:
        return getattr(self, "virtual_size", FakeSize(320, 280))

    def SetVirtualSize(self, size) -> None:
        self.virtual_size = FakeSize(*size)


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
        self.split_orientations = []
        self.unsplit_calls = []
        self.is_split = False
        self.minimum_size = FakeSize(0, 0)
        self.destroyed = False
        self.bindings = {}

    def Bind(self, event_type, callback) -> None:
        self.bindings[event_type] = callback

    def SetMinimumPaneSize(self, size: int) -> None:
        self.minimum_pane_size = size

    def GetMinimumPaneSize(self) -> int:
        return self.minimum_pane_size

    def SetSashGravity(self, gravity: float) -> None:
        self.sash_gravity = gravity

    def SplitVertically(self, first, second, sash_position: int) -> bool:
        self.split_calls.append((first, second, sash_position))
        self.split_orientations.append("vertical")
        self.window1 = first
        self.window2 = second
        self.sash_position = sash_position
        self.is_split = True
        return True

    def SplitHorizontally(self, first, second, sash_position: int) -> bool:
        self.split_calls.append((first, second, sash_position))
        self.split_orientations.append("horizontal")
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

    def ReplaceWindow(self, old_window, new_window) -> bool:
        if self.window1 is old_window:
            self.window1 = new_window
        elif self.window2 is old_window:
            self.window2 = new_window
        else:
            return False
        new_window.Reparent(self)
        return True

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

    def GetSize(self) -> FakeSize:
        return self.minimum_size

    def SetSashPosition(self, sash_position: int) -> None:
        self.sash_position = sash_position

    def Layout(self) -> None:
        pass

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
    # Fake controls cannot host native SuperToolTip windows; retain the message
    # for assertions without creating GUI resources in these layout tests.
    monkeypatch.setattr(
        workspace, "set_tooltip", lambda widget, message: widget.SetToolTip(message)
    )
    FakeWidget.instances = []
    FakeCallLater.calls = []
    for name, value in {
        "Panel": FakePanel,
        "ScrolledWindow": FakeScrolledWindow,
        "SplitterWindow": FakeSplitter,
        "SystemSettings": FakeSystemSettings,
        "Cursor": lambda cursor_id: ("cursor", cursor_id),
        "GetMousePosition": lambda: FakePoint(*FakeMouse.position),
        "Simplebook": FakeSimplebook,
        "BitmapToggleButton": FakeWidget,
        "ToggleButton": FakeWidget,
        "Slider": FakeSlider,
        "StaticText": FakeWidget,
        "TextCtrl": FakeWidget,
        "Button": FakeWidget,
        "Choice": FakeChoice,
        "BoxSizer": FakeSizer,
        "ArtProvider": FakeArtProvider,
        "CallLater": FakeCallLater,
        "Size": lambda width, height: (width, height),
        "Colour": lambda *channels: channels,
        "ID_ANY": -1,
        "VERTICAL": 1,
        "HORIZONTAL": 2,
        "SP_LIVE_UPDATE": 4,
        "SP_3DSASH": 1024,
        "VSCROLL": 5,
        "TAB_TRAVERSAL": 4096,
        "EXPAND": 8,
        "ALL": 16,
        "BU_EXACTFIT": 1,
        "ALIGN_CENTER_VERTICAL": 24,
        "ALIGN_CENTER": 25,
        "LEFT": 32,
        "RIGHT": 64,
        "TOP": 128,
        "BOTTOM": 256,
        "SL_HORIZONTAL": 512,
        "ART_BUTTON": 1,
        "ART_GO_FORWARD": "forward",
        "ART_INFORMATION": "information",
        "EVT_BUTTON": "button",
        "EVT_TOGGLEBUTTON": "toggle-button",
        "EVT_CHOICE": "choice",
        "EVT_TEXT_ENTER": "text-enter",
        "TE_PROCESS_ENTER": 1024,
        "EVT_SIZE": "size",
        "EVT_KEY_DOWN": "key-down",
        "EVT_SLIDER": "slider",
        "EVT_SCROLLWIN": "scroll-window",
        "EVT_SPLITTER_SASH_POS_CHANGING": "splitter-sash-changing",
        "WXK_UP": 315,
        "WXK_DOWN": 317,
        "WXK_PAGEUP": 366,
        "WXK_PAGEDOWN": 367,
        "WXK_HOME": 313,
        "WXK_END": 312,
    }.items():
        monkeypatch.setattr(wx, name, value)


def make_workspace(
    monkeypatch: pytest.MonkeyPatch,
    *,
    timeline_enabled: bool = True,
    on_add_graph=None,
    view_choices=(),
    on_toggle_play=None,
    on_play_reverse=None,
    on_play_forward=None,
    on_set_transport_rate=None,
    on_step_samples=None,
) -> tuple[Any, list[float], FakeFrame]:
    configure_fake_wx(monkeypatch)
    frame = FakeFrame()
    seeks: list[float] = []
    time_seeks: list[str] = []
    # Monkeypatching replaces the native widgets with unrelated fake classes.
    # Keep this construction boundary dynamic so assertions see the fake
    # attributes rather than Workspace's production wx type annotations.
    workspace_factory = cast(Callable[..., Any], workspace.Workspace)
    result = workspace_factory(
        frame,
        seeks.append,
        on_toggle_play=on_toggle_play,
        on_play_reverse=on_play_reverse,
        on_play_forward=on_play_forward,
        on_set_transport_rate=on_set_transport_rate,
        on_step_samples=on_step_samples,
        timeline_enabled=timeline_enabled,
        timeline_start_utc="2000-01-01T00:00:00.000",
        timeline_end_utc="2000-01-01T00:01:00.000",
        on_seek_to_time=time_seeks.append,
        context={
            "object": "TEST",
            "frame": "GCRF",
            "center": "Earth",
            "time_span": "2024-01-01T00:00:00 – 2024-01-02T00:00:00",
            "sample_count": "2",
        },
        details=(
            ("Object ID", "2024-001A"),
            ("Time system", "UTC"),
            ("Frame epoch", ""),
            ("Usable start", "2024-01-01T00:00:00"),
            ("Usable stop", "2024-01-02T00:00:00"),
            ("Interpolation", "Lagrange"),
            ("Interpolation degree", "5"),
        ),
        view_choices=view_choices,
        on_add_graph=on_add_graph,
    )
    result._test_time_seeks = time_seeks
    return result, seeks, frame


def test_workspace_builds_feature_pages_split_panes_and_global_timeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, frame = make_workspace(monkeypatch)

    assert [label for _page, label in result.feature_book.pages] == [
        "Playback",
        "OEM file information",
        "State",
    ]
    assert result.feature_book.selection == 0
    assert result.feature_buttons[0].name == "Playback"
    assert result.feature_buttons[0].tooltip == "Playback"
    assert result.feature_buttons[1].name == "OEM file information"
    assert result.feature_buttons[2].name == "State"
    assert result.feature_buttons[2].tooltip == "State"
    assert [page.name for page in result.feature_pages] == [
        "Playback",
        "OEM file information",
        "State",
    ]
    assert result.left_pane.name == workspace.CONTROLS_PANE_NAME
    assert result.middle_pane.name == workspace.MAIN_ANALYSIS_PANE_NAME
    assert result.right_pane.name == workspace.COMPARISON_PANE_NAME
    assert result.middle_pane.sizer.items[0][0].items[0][0].label == "Main Analysis"
    assert result.right_pane.sizer.items[0][0].items[0][0].label == "Comparison"
    assert result.middle_stack.always_shown_scrollbars == (False, False)
    assert result.right_stack.always_shown_scrollbars == (False, False)
    assert result.graph_splitter.is_split is False
    assert result.graph_splitter.unsplit_calls == [result.right_pane]
    assert result._comparison_toggle.name == "Toggle Comparison pane"
    assert not result._comparison_toggle.value
    assert result.content_splitter.is_split
    assert result.content_splitter.minimum_pane_size == 240
    assert result.content_splitter.sash_gravity == 0.0
    assert result.content_splitter.style & workspace.wx.SP_3DSASH
    assert result.graph_splitter.minimum_pane_size == 320
    assert result.graph_splitter.sash_gravity == 1.0
    assert result.graph_splitter.style & workspace.wx.SP_3DSASH
    assert result.timeline_slider.minimum == 0
    assert result.timeline_slider.maximum == 10_000
    assert list(result.transport_buttons) == [
        -1000.0,
        -100.0,
        -10.0,
        -1.0,
        1.0,
        10.0,
        100.0,
        1000.0,
    ]
    assert result.transport_buttons[-1.0].name == "Set reverse playback speed to 1x"
    assert result.transport_buttons[1.0].name == "Set forward playback speed to 1x"
    assert result.transport_buttons[-1.0].tooltip == "Set reverse speed to 1x."
    assert result.transport_buttons[10.0].tooltip == "Increase forward speed by 10x."
    assert (
        result.transport_reverse_play_button.tooltip == "Play reverse at current speed."
    )
    assert result.transport_reverse_play_button.name == "Play reverse at current speed"
    assert result.transport_forward_play_button.name == "Play forward at current speed"
    assert result.transport_reverse_play_button.label == "◀"
    assert result.transport_forward_play_button.label == "▶"
    assert (
        result.timeline_panel.sizer.items[2][0].items[4][0]
        is result.transport_reverse_play_button
    )
    assert (
        result.timeline_panel.sizer.items[2][0].items[5][0]
        is result.transport_forward_play_button
    )
    assert [button.label for button in result.transport_buttons.values()] == [
        "<<< 1000×",
        "<< 100×",
        "< 10×",
        "< 1×",
        "1× >",
        "10× >",
        "100× >>",
        "1000× >>>",
    ]
    assert all(
        button.style == workspace.wx.BU_EXACTFIT
        for button in result.transport_buttons.values()
    )
    assert all(
        button.minimum_size == (44, -1) for button in result.transport_buttons.values()
    )
    assert frame.sizer.items[0][0] is result.content_splitter
    assert frame.sizer.items[1][0] is result.timeline_panel
    assert result.timeline_start_label.label == ("Start UTC: 2000-01-01T00:00:00.000")
    assert result.timeline_current_prefix.label == "Current UTC:"
    assert result.timeline_time_entry.name == "Current UTC or elapsed time"
    assert (
        result.timeline_time_entry.hint == "UTC timestamp or elapsed time, e.g. 1h30m"
    )
    assert result.timeline_end_label.label == "End UTC: 2000-01-01T00:01:00.000"


def test_transport_controls_dispatch_signed_rates_and_track_play_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toggles: list[bool] = []
    reverse_plays: list[bool] = []
    forward_plays: list[bool] = []
    rates: list[float] = []
    sample_steps: list[int] = []
    result, _seeks, _frame = make_workspace(
        monkeypatch,
        on_toggle_play=lambda: toggles.append(True),
        on_play_reverse=lambda: reverse_plays.append(True),
        on_play_forward=lambda: forward_plays.append(True),
        on_set_transport_rate=rates.append,
        on_step_samples=sample_steps.append,
    )

    result.update_transport_state(False, 1.0)
    result.transport_buttons[1.0].SetValue(False)
    result.transport_buttons[-1000.0].trigger(workspace.wx.EVT_TOGGLEBUTTON)
    result.transport_buttons[100.0].trigger(workspace.wx.EVT_TOGGLEBUTTON)
    result.transport_buttons[-1.0].trigger(workspace.wx.EVT_TOGGLEBUTTON)
    result.transport_buttons[1.0].trigger(workspace.wx.EVT_TOGGLEBUTTON)
    result.transport_buttons[-1.0].trigger(workspace.wx.EVT_LEFT_DCLICK)
    result.transport_buttons[1.0].trigger(workspace.wx.EVT_LEFT_DCLICK)
    assert rates == [-1000.0, 100.0, -1.0, 1.0]
    assert sample_steps == [-1, 1]
    assert result.transport_buttons[1.0].value
    result.transport_reverse_play_button.trigger(workspace.wx.EVT_BUTTON)
    assert reverse_plays == [True]
    result.update_transport_state(True, -100.0)
    assert result.transport_buttons[-100.0].value
    assert not result.transport_buttons[100.0].value
    assert result.transport_reverse_play_button.label == "Ⅱ"
    assert result.transport_reverse_play_button.name == "Pause reverse playback"
    assert result.transport_reverse_play_button.tooltip == "Pause reverse playback."
    assert result.transport_forward_play_button.label == "▶"
    assert (
        result.transport_forward_play_button.tooltip == "Play forward at current speed."
    )
    result.transport_reverse_play_button.trigger(workspace.wx.EVT_BUTTON)
    assert toggles == [True]
    result.transport_forward_play_button.trigger(workspace.wx.EVT_BUTTON)
    assert forward_plays == [True]
    result.update_transport_state(True, 10.0)
    assert result.transport_forward_play_button.label == "Ⅱ"
    assert result.transport_reverse_play_button.label == "◀"
    result.transport_forward_play_button.trigger(workspace.wx.EVT_BUTTON)
    assert toggles == [True, True]
    result.update_transport_state(False, 10.0)
    assert result.transport_reverse_play_button.label == "◀"
    assert result.transport_reverse_play_button.name == "Play reverse at current speed"
    assert result.transport_forward_play_button.label == "▶"


def test_graph_stack_scrollbars_are_forced_visible_only_when_content_overflows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    stack = result.middle_stack

    stack.scroll_range = 32
    stack.scroll_thumb = 20
    result._update_stack_scrollbar_visibility("middle")
    assert stack.always_shown_scrollbars == (False, True)

    stack.scroll_range = 20
    stack.scroll_thumb = 20
    result._update_stack_scrollbar_visibility("middle")
    assert stack.always_shown_scrollbars == (False, False)

    info_labels = [label.label for label in result._file_info_labels]
    assert "Object: TEST" in info_labels
    assert "Samples: 2" in info_labels
    assert "Object ID: 2024-001A" in info_labels
    assert "Time system: UTC" in info_labels
    assert "Frame epoch: Unavailable" in info_labels
    assert "Usable start: 2024-01-01T\n00:00:00" in info_labels
    assert "Usable stop: 2024-01-02T\n00:00:00" in info_labels
    assert "Interpolation: Lagrange" in info_labels
    assert "Interpolation degree: 5" in info_labels
    time_span_label = next(
        label for label in result._file_info_labels if label.name == "OEM Time span"
    )
    assert "T\n" in time_span_label.label
    assert [label.label for label in result._file_info_section_labels] == [
        "File context",
        "OEM metadata",
    ]
    assert result.file_info_scroll.scroll_rate == (0, 10)
    assert result.file_info_scroll.can_focus
    assert result.file_info_scroll.style & workspace.wx.TAB_TRAVERSAL
    assert result.file_info_scroll.name == "OEM information details"
    assert all(label.name.startswith("OEM ") for label in result._file_info_labels)
    assert (
        result.file_info_scroll.sizer.items[0][0] is result._file_info_section_labels[0]
    )
    assert (
        result.file_info_scroll.sizer.items[6][0] is result._file_info_section_labels[1]
    )

    result._comparison_toggle.SetValue(True)
    result._comparison_toggle.trigger(workspace.wx.EVT_TOGGLEBUTTON)
    assert result.graph_splitter.is_split
    assert result._comparison_toggle.value
    result._pane_close_buttons["right"].trigger(workspace.wx.EVT_BUTTON)
    assert not result.graph_splitter.is_split
    assert not result._comparison_toggle.value
    result.show_right_pane(False)
    assert not result.graph_splitter.is_split
    assert result.graph_splitter.split_calls[-1][1] is result.right_pane
    assert not result._comparison_toggle.value


def test_file_info_labels_wrap_to_the_available_pane_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    result.file_info_scroll.client_size = FakeSize(180, 400)
    event = FakeEvent()

    result.file_info_scroll.bindings[workspace.wx.EVT_SIZE](event)

    assert all(label.wrap_width == 164 for label in result._file_info_labels)
    assert all(label.wrap_width == 164 for label in result._file_info_section_labels)
    assert event.skipped


def test_file_info_page_supports_keyboard_scrolling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    scroll = result.file_info_scroll
    scroll.scroll_range = 20
    scroll.scroll_thumb = 5

    for key_code, expected_y in (
        (workspace.wx.WXK_DOWN, 1),
        (workspace.wx.WXK_PAGEDOWN, 5),
        (workspace.wx.WXK_END, 15),
        (workspace.wx.WXK_UP, 14),
        (workspace.wx.WXK_PAGEUP, 10),
        (workspace.wx.WXK_HOME, 0),
    ):
        event = FakeEvent(key_code=key_code)
        scroll.bindings[workspace.wx.EVT_KEY_DOWN](event)
        assert scroll.GetViewStart() == (0, expected_y)
        assert not event.skipped

    unhandled_event = FakeEvent(key_code=0)
    scroll.bindings[workspace.wx.EVT_KEY_DOWN](unhandled_event)
    assert unhandled_event.skipped


def test_main_pane_sashes_resize_independently_and_restore_right_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    right_panels = [
        FakeGraphPanel(result.right_stack, f"right-{index}") for index in range(2)
    ]
    for panel in right_panels:
        result.add_graph_panel(panel, "right")
    right_stack_splitter = result._stack_splitters["right"][0]
    right_stack_splitter.SetSashPosition(330)

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
    assert result._graph_panels["right"] == right_panels
    assert result._stack_splitters["right"][0] is right_stack_splitter
    assert right_stack_splitter.GetSashPosition() == 330
    result.graph_splitter.client_width = 1100
    result.show_right_pane(True)

    restored_width = (
        result.graph_splitter.GetClientSize().width
        - result.graph_splitter.GetSashPosition()
        - result.graph_splitter.GetSashSize()
    )
    assert restored_width == 396
    assert result._comparison_toggle.value
    result.show_right_pane(False)
    result.show_right_pane(True)
    assert result._graph_panels["right"] == right_panels
    assert right_stack_splitter.GetSashPosition() == 330


def test_graph_hosts_replace_empty_state_and_restore_it_when_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    host = FakeGraphPanel(result.middle_stack, "first")
    empty_panel = result._empty_panels["middle"]

    result.add_graph_panel(host)

    assert result._graph_panels["middle"] == [host]
    assert empty_panel.shown is False
    # A hidden empty state must leave both the native scroller and its sizer.
    assert empty_panel.GetParent() is result.middle_stack.GetParent()
    assert all(
        item[0] is not empty_panel for item in result._stack_sizers["middle"].items
    )

    result.remove_graph_panel(host)

    assert result._graph_panels["middle"] == []
    assert empty_panel.shown is True
    # Restore exactly one empty-state item when the last graph is removed.
    assert empty_panel.GetParent() is result.middle_stack
    assert [item[0] for item in result._stack_sizers["middle"].items] == [empty_panel]
    # Removed panels must also be parked while awaiting destruction or reuse.
    assert host.GetParent() is result.middle_stack.GetParent()
    # Reusing a parked panel must restore its scrolling parent and hide the
    # empty state again without leaving a hidden native scroll child.
    result.add_graph_panel(host)
    assert host.GetParent() is result.middle_stack
    assert empty_panel.GetParent() is result.middle_stack.GetParent()
    with pytest.raises(ValueError, match="unknown graph stack"):
        result.add_graph_panel(host, "invalid")


def test_dragging_graph_sash_resizes_panel_above_and_keeps_panels_below(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    panels = [
        FakeGraphPanel(result.middle_stack, f"panel-{index}") for index in range(3)
    ]
    for panel in panels:
        result.add_graph_panel(panel, "middle")
    inner = result._stack_splitters["middle"][0]
    root = result._stack_roots["middle"]
    assert inner.GetWindow1() is panels[0]
    # wx clamps a sash to the minimum size of the pane below it, so the
    # panels advertise only the small drag floor.
    assert panels[1].GetMinSize().height == workspace.SASH_DRAG_MIN_PANE

    class SashEvent(FakeEvent):
        def __init__(self, position: int) -> None:
            super().__init__()
            self.position = position
            self.vetoed = False

        def GetSashPosition(self) -> int:
            return self.position

        def Veto(self) -> None:
            self.vetoed = True

    event = SashEvent(340)
    result._on_graph_sash_changing("middle", inner, event)

    assert event.vetoed
    assert result._graph_panel_heights[panels[0]] == 340
    assert result._graph_panel_heights[panels[1]] == 280
    assert result._graph_panel_heights[panels[2]] == 280
    assert inner.GetSashPosition() == 340
    assert root.GetMinSize().height == 340 + 4 + 280 + 4 + 280

    panels[0].current_size = FakeSize(320, 340)
    result._on_graph_sash_changing("middle", inner, SashEvent(310))

    assert result._graph_panel_heights[panels[0]] == 310
    assert result._graph_panel_heights[panels[1]] == 280
    assert root.GetMinSize().height == 310 + 4 + 280 + 4 + 280

    result._on_graph_sash_changing("middle", inner, SashEvent(100))

    assert result._graph_panel_heights[panels[0]] == workspace.MIN_GRAPH_PANEL_HEIGHT


def test_bottom_handle_grows_bottom_panel_and_scroll_extends_past_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    panels = [
        FakeGraphPanel(result.middle_stack, f"panel-{index}") for index in range(2)
    ]
    for panel in panels:
        result.add_graph_panel(panel, "middle")
    stack = result.middle_stack
    handle = result._stack_handles["middle"]
    root = result._stack_roots["middle"]

    assert handle.shown
    assert stack.sizer.items[-1][0] is handle
    assert result._bottom_graph_panel("middle") is panels[1]
    root_entry = next(entry for entry in stack.sizer.items if entry[0] is root)
    assert root_entry[1] == 0
    # Slack equals one client viewport beyond the fitted content.
    assert stack.GetVirtualSize().height == FakeScrolledWindow.FIT_HEIGHT + (
        stack.GetClientSize().height
    )

    class DragEvent(FakeEvent):
        def Dragging(self) -> bool:
            return True

    FakeMouse.position = (0, 500)
    handle.bindings[workspace.wx.EVT_LEFT_DOWN](DragEvent())
    assert handle.HasCapture()

    FakeMouse.position = (0, 540)
    handle.bindings[workspace.wx.EVT_MOTION](DragEvent())

    assert result._graph_panel_heights[panels[1]] == 280 + 40
    assert result._graph_panel_heights[panels[0]] == 280

    handle.bindings[workspace.wx.EVT_LEFT_UP](DragEvent())
    assert not handle.HasCapture()

    FakeMouse.position = (0, 900)
    handle.bindings[workspace.wx.EVT_MOTION](DragEvent())
    assert result._graph_panel_heights[panels[1]] == 280 + 40


def test_growing_bottom_panel_keeps_stack_scroll_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    panels = [
        FakeGraphPanel(result.middle_stack, f"panel-{index}") for index in range(2)
    ]
    for panel in panels:
        result.add_graph_panel(panel, "middle")
    stack = result.middle_stack
    handle = result._stack_handles["middle"]
    stack.view_start = (0, 500)

    class DragEvent(FakeEvent):
        def Dragging(self) -> bool:
            return True

    FakeMouse.position = (0, 500)
    handle.bindings[workspace.wx.EVT_LEFT_DOWN](DragEvent())
    FakeMouse.position = (0, 560)
    handle.bindings[workspace.wx.EVT_MOTION](DragEvent())

    assert stack.view_start == (0, 500)


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
    # Both the hidden pane and its retiring splitter must leave the scroller
    # before the collapsed stack triggers another native allocation.
    assert middle_panels[0].GetParent() is result.middle_stack.GetParent()
    assert middle_root.GetParent() is result.middle_stack.GetParent()
    result.remove_graph_panel(middle_panels[2], "middle")
    assert result._stack_roots["middle"] is None


def test_many_graph_panels_keep_horizontal_sashes_and_minimum_sizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    panels = [
        FakeGraphPanel(result.middle_stack, f"many-{index}") for index in range(5)
    ]
    for panel in panels:
        result.add_graph_panel(panel, "middle")

    assert result._stack_roots["middle"].GetMinSize().height == 5 * 280 + 4 * 4
    assert len(result._stack_splitters["middle"]) == 4
    assert all(
        splitter.GetMinimumPaneSize() == workspace.SASH_DRAG_MIN_PANE
        for splitter in result._stack_splitters["middle"]
    )
    assert all(
        splitter.split_orientations == ["horizontal"]
        for splitter in result._stack_splitters["middle"]
    )
    assert result._graph_panels["right"] == []


def test_moving_graph_panel_reorders_live_hosts_without_replacing_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    panels = [
        FakeGraphPanel(result.middle_stack, f"panel-{index}") for index in range(3)
    ]
    for panel in panels:
        result.add_graph_panel(panel)

    result.move_graph_panel(panels[0], "middle", 1)

    assert result._graph_panels["middle"] == [panels[1], panels[0], panels[2]]
    assert [panel.panel_id for panel in result._graph_panels["middle"]] == [
        "panel-1",
        "panel-0",
        "panel-2",
    ]
    assert result._stack_roots["middle"] is not None
    result.move_graph_panel(panels[0], "middle", -1)
    assert result._graph_panels["middle"] == panels


def test_replacing_graph_panel_preserves_order_splitter_and_scroll_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    panels = [
        FakeGraphPanel(result.middle_stack, f"panel-{index}") for index in range(3)
    ]
    for panel in panels:
        result.add_graph_panel(panel)
    result.middle_stack.view_start = (0, 7)
    parent_splitter = panels[1].GetParent()
    sash_position = parent_splitter.GetSashPosition()
    replacement = FakeGraphPanel(result.middle_stack, "replacement")

    result.replace_graph_panel(panels[1], replacement)

    assert result._graph_panels["middle"] == [
        panels[0],
        replacement,
        panels[2],
    ]
    assert replacement.GetParent() is parent_splitter
    assert replacement in (
        parent_splitter.GetWindow1(),
        parent_splitter.GetWindow2(),
    )
    assert parent_splitter.GetSashPosition() == sash_position
    assert result.middle_stack.view_start == (0, 7)


def test_replacing_only_graph_panel_updates_stack_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    original = FakeGraphPanel(result.middle_stack, "original")
    replacement = FakeGraphPanel(result.middle_stack, "replacement")
    result.add_graph_panel(original)
    result.middle_stack.view_start = (0, 3)

    result.replace_graph_panel(original, replacement)

    assert result._stack_roots["middle"] is replacement
    assert result._graph_panels["middle"] == [replacement]
    assert replacement.GetParent() is result.middle_stack
    assert result.middle_stack.view_start == (0, 3)


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

    assert result.feature_title.label == "Controls & Info / Playback"

    result.feature_buttons[1].trigger(workspace.wx.EVT_TOGGLEBUTTON)

    assert result.feature_book.selection == 1
    assert result.feature_title.label == "Controls & Info / OEM file information"
    assert result.feature_buttons[1].value
    assert not result.feature_buttons[0].value

    event = FakeEvent(key_code=workspace.wx.WXK_UP)
    result.feature_buttons[1].trigger("key-down", event)

    assert result.feature_book.selection == 0
    assert result.feature_buttons[0].value
    assert result.feature_buttons[0].focused
    assert not event.skipped

    down_event = FakeEvent(key_code=workspace.wx.WXK_DOWN)
    result.feature_buttons[0].trigger("key-down", down_event)
    assert result.feature_book.selection == 1
    assert result.feature_title.label == "Controls & Info / OEM file information"
    assert result.feature_buttons[1].focused


def test_global_timeline_syncs_without_recursive_seek_and_dispatches_user_seek(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, seeks, _frame = make_workspace(monkeypatch)
    result.timeline_slider.emit_event_on_set = True

    result.update_timeline(0.25, "2000-01-01T00:00:15.000")

    assert result.timeline_slider.value == 2500
    assert result.timeline_time_entry.value == "2000-01-01T00:00:15.000"
    assert seeks == []
    for value, expected in ((0, 0.0), (5000, 0.5), (10_000, 1.0)):
        result.timeline_slider.trigger("slider", FakeEvent(value))
        assert seeks[-1] == expected


def test_current_time_editor_seeks_and_preserves_text_while_focused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _seeks, _frame = make_workspace(monkeypatch)
    focus_callbacks = []
    monkeypatch.setattr(
        workspace.wx, "CallAfter", lambda callback: focus_callbacks.append(callback)
    )
    result.timeline_time_entry.value = "1h30m"
    result.timeline_time_entry.trigger(workspace.wx.EVT_TEXT_ENTER)

    assert result._test_time_seeks == ["1h30m"]
    assert result.timeline_time_entry.insertion_point == len("1h30m")
    assert not getattr(result._focus_sink, "focused", False)
    focus_callbacks.pop()()
    assert result._focus_sink.focused
    assert not getattr(result.transport_forward_play_button, "focused", False)
    result.timeline_time_entry.focused = True
    result.update_timeline(0.5, "new UTC")
    assert result.timeline_time_entry.value == "1h30m"
    result.update_timeline(0.6, "updated while playing", playing=True)
    assert result.timeline_time_entry.value == "updated while playing"


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

    result.update_timeline(-1.0, "before start")
    assert result.timeline_slider.value == 0
    result.update_timeline(2.0, "after end")
    assert result.timeline_slider.value == 10_000
