"""Feature rail and OEM metadata page for the playback workspace."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Protocol

import wx

from .constants import CONTROLS_PANE_NAME
from ..tooltips import set_tooltip

if TYPE_CHECKING:
    from .time_range_slider import TimeRangeSlider


class _FeatureNavigationState(Protocol):
    """Workspace-owned widgets used across the feature and timeline mixins."""

    _FEATURES: tuple[tuple[str, str], ...]
    _file_info_labels: list[wx.StaticText]
    _file_info_section_labels: list[wx.StaticText]
    _selected_feature: int
    _timeline_enabled: bool
    controls_pane: wx.Panel
    controls_title_label: wx.StaticText
    feature_book: wx.Simplebook
    feature_pages: list[wx.Panel]
    feature_rail_buttons: list[wx.BitmapToggleButton]
    file_info_page: wx.Panel
    file_info_scroll: wx.ScrolledWindow
    settings_page: wx.Panel
    state_page: wx.Panel
    timeline_slider: TimeRangeSlider

    def select_feature(self, index: int) -> None: ...

    def _on_feature_key_down(self, event: wx.KeyEvent) -> None: ...

    def _on_file_info_scroll_key_down(self, event: wx.KeyEvent) -> None: ...

    def _on_file_info_scroll_size(self, event: wx.SizeEvent) -> None: ...

    def _on_left_pane_size(self, event: wx.SizeEvent) -> None: ...

    def _wrap_feature_title(self) -> None: ...


def _display_file_info_value(value: str | None) -> str:
    display_value = value or "Unavailable"
    if (
        len(display_value) > 10
        and display_value[4:5] == "-"
        and display_value[7:8] == "-"
        and display_value[10:11] == "T"
    ):
        return display_value.replace("T", "T\n")
    return display_value


class FeatureNavigationMixin:
    """Implement the controls rail and OEM information page."""

    _FEATURES = (
        ("Settings", wx.ART_HELP_SETTINGS),
        ("OEM file information", wx.ART_INFORMATION),
        ("Ground Stations", wx.ART_LIST_VIEW),
        ("State", wx.ART_LIST_VIEW),
    )

    def update_oem_information(
        self: _FeatureNavigationState,
        context: Mapping[str, str],
        details: Sequence[tuple[str, str]],
        timeline_enabled: bool,
    ) -> None:
        """Refresh OEM metadata and timeline availability after loading another file."""
        self._timeline_enabled = timeline_enabled
        for label, key, title in zip(
            self._file_info_labels[:5],
            ("object", "frame", "center", "time_span", "sample_count"),
            ("Object", "Frame", "Center", "Time span", "Samples"),
        ):
            label.SetLabel(f"{title}: {_display_file_info_value(context.get(key))}")
        for label, (name, value) in zip(self._file_info_labels[5:], details):
            label.SetLabel(f"{name}: {_display_file_info_value(value)}")
        self.timeline_slider.Enable(timeline_enabled)
        self.file_info_scroll.FitInside()
        self.file_info_scroll.Layout()

    def select_feature(self: _FeatureNavigationState, index: int) -> None:
        """Select a feature page and keep the rail's toggle state synchronized."""
        if not 0 <= index < len(self.feature_rail_buttons):
            return
        self._selected_feature = index
        self.feature_book.ChangeSelection(index)
        self.controls_title_label.SetLabel(
            f"{CONTROLS_PANE_NAME} / {self._FEATURES[index][0]}"
        )
        self._wrap_feature_title()
        for button_index, button in enumerate(self.feature_rail_buttons):
            button.SetValue(button_index == index)

    def _on_left_pane_size(self: _FeatureNavigationState, event: wx.SizeEvent) -> None:
        self._wrap_feature_title()
        self.controls_pane.Layout()
        event.Skip()

    def _wrap_feature_title(self: _FeatureNavigationState) -> None:
        content_width = self.controls_pane.GetClientSize().width - 16
        if content_width > 0:
            self.controls_title_label.Wrap(content_width)

    def _build_feature_navigation(
        self: _FeatureNavigationState,
        context: Mapping[str, str],
        details: Sequence[tuple[str, str]],
    ) -> None:
        feature_sizer = wx.BoxSizer(wx.VERTICAL)
        self.controls_title_label = wx.StaticText(
            self.controls_pane,
            wx.ID_ANY,
            f"{CONTROLS_PANE_NAME} / {self._FEATURES[0][0]}",
        )
        self.controls_title_label.SetName(CONTROLS_PANE_NAME)
        feature_sizer.Add(
            self.controls_title_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8
        )
        self.controls_pane.Bind(wx.EVT_SIZE, self._on_left_pane_size)
        feature_content_sizer = wx.BoxSizer(wx.HORIZONTAL)
        feature_button_rail = wx.BoxSizer(wx.VERTICAL)
        self.feature_book = wx.Simplebook(self.controls_pane, wx.ID_ANY)
        self.feature_pages: list[wx.Panel] = []
        self.feature_rail_buttons: list[wx.BitmapToggleButton] = []

        for index, (name, art_id) in enumerate(self._FEATURES):
            feature_page = wx.Panel(self.feature_book, wx.ID_ANY)
            feature_page.SetName(name)
            self.feature_book.AddPage(feature_page, name)
            self.feature_pages.append(feature_page)
            feature_icon = wx.ArtProvider.GetBitmap(
                art_id, wx.ART_BUTTON, wx.Size(24, 24)
            )
            feature_button = wx.BitmapToggleButton(
                self.controls_pane, wx.ID_ANY, feature_icon
            )
            feature_button.SetName(name)
            set_tooltip(feature_button, name)
            feature_button.SetMinSize((36, 36))
            feature_button.SetValue(index == 0)
            feature_button.Bind(
                wx.EVT_TOGGLEBUTTON,
                lambda _event, selected=index: self.select_feature(selected),
            )
            feature_button.Bind(wx.EVT_KEY_DOWN, self._on_feature_key_down)
            feature_button_rail.Add(feature_button, 0, wx.EXPAND | wx.ALL, 2)
            self.feature_rail_buttons.append(feature_button)

        self.settings_page = self.feature_pages[0]
        self.file_info_page = self.feature_pages[1]
        self.ground_stations_page = self.feature_pages[2]
        self.state_page = self.feature_pages[3]
        file_info_sizer = wx.BoxSizer(wx.VERTICAL)
        self.file_info_scroll = wx.ScrolledWindow(
            self.file_info_page,
            wx.ID_ANY,
            style=wx.VSCROLL | wx.TAB_TRAVERSAL,
        )
        self.file_info_scroll.SetName("OEM information details")
        self.file_info_scroll.SetCanFocus(True)
        self.file_info_scroll.SetScrollRate(0, 10)
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        self._file_info_section_labels: list[wx.StaticText] = []
        self._file_info_labels: list[wx.StaticText] = []
        primary_heading = wx.StaticText(
            self.file_info_scroll, wx.ID_ANY, "File context"
        )
        primary_heading.SetName("Primary OEM file context")
        self._file_info_section_labels.append(primary_heading)
        info_sizer.Add(primary_heading, 0, wx.EXPAND | wx.ALL, 8)
        for label, key in (
            ("Object", "object"),
            ("Frame", "frame"),
            ("Center", "center"),
            ("Time span", "time_span"),
            ("Samples", "sample_count"),
        ):
            info_label = wx.StaticText(
                self.file_info_scroll,
                wx.ID_ANY,
                f"{label}: {_display_file_info_value(context.get(key))}",
            )
            info_label.SetName(f"OEM {label}")
            self._file_info_labels.append(info_label)
            info_sizer.Add(
                info_label,
                0,
                wx.EXPAND | wx.ALL,
                8,
            )
        if details:
            metadata_heading = wx.StaticText(
                self.file_info_scroll, wx.ID_ANY, "OEM metadata"
            )
            metadata_heading.SetName("Additional OEM metadata")
            self._file_info_section_labels.append(metadata_heading)
            info_sizer.Add(
                metadata_heading,
                0,
                wx.EXPAND | wx.ALL,
                8,
            )
            for label, value in details:
                info_label = wx.StaticText(
                    self.file_info_scroll,
                    wx.ID_ANY,
                    f"{label}: {_display_file_info_value(value)}",
                )
                info_label.SetName(f"OEM {label}")
                self._file_info_labels.append(info_label)
                info_sizer.Add(
                    info_label,
                    0,
                    wx.EXPAND | wx.ALL,
                    8,
                )
        self.file_info_scroll.SetSizer(info_sizer)
        file_info_sizer.Add(self.file_info_scroll, 1, wx.EXPAND)
        self.file_info_page.SetSizer(file_info_sizer)
        self.file_info_scroll.Bind(wx.EVT_SIZE, self._on_file_info_scroll_size)
        self.file_info_scroll.Bind(wx.EVT_KEY_DOWN, self._on_file_info_scroll_key_down)
        self.file_info_scroll.FitInside()

        feature_content_sizer.Add(feature_button_rail, 0, wx.EXPAND | wx.ALL, 4)
        feature_content_sizer.Add(self.feature_book, 1, wx.EXPAND | wx.ALL, 4)
        feature_sizer.Add(feature_content_sizer, 1, wx.EXPAND)
        self.controls_pane.SetSizer(feature_sizer)

    def _on_file_info_scroll_size(self, event: wx.SizeEvent) -> None:
        self.file_info_scroll.FitInside()
        content_width = self.file_info_scroll.GetClientSize().width - 16
        if content_width > 0:
            for label in (*self._file_info_section_labels, *self._file_info_labels):
                label.Wrap(content_width)
            self.file_info_scroll.Layout()
            self.file_info_scroll.FitInside()
        event.Skip()

    def _on_file_info_scroll_key_down(self, event: wx.KeyEvent) -> None:
        key_code = event.GetKeyCode()
        current_y = self.file_info_scroll.GetViewStart()[1]
        scroll_limit = max(
            0,
            self.file_info_scroll.GetScrollRange(wx.VERTICAL)
            - self.file_info_scroll.GetScrollThumb(wx.VERTICAL),
        )
        page_step = max(1, self.file_info_scroll.GetScrollThumb(wx.VERTICAL) - 1)
        if key_code == wx.WXK_UP:
            next_y = max(0, current_y - 1)
        elif key_code == wx.WXK_DOWN:
            next_y = min(scroll_limit, current_y + 1)
        elif key_code == wx.WXK_PAGEUP:
            next_y = max(0, current_y - page_step)
        elif key_code == wx.WXK_PAGEDOWN:
            next_y = min(scroll_limit, current_y + page_step)
        elif key_code == wx.WXK_HOME:
            next_y = 0
        elif key_code == wx.WXK_END:
            next_y = scroll_limit
        else:
            event.Skip()
            return
        self.file_info_scroll.Scroll(0, next_y)

    def _on_feature_key_down(self: _FeatureNavigationState, event: wx.KeyEvent) -> None:
        key_code = event.GetKeyCode()
        if key_code in (wx.WXK_UP, wx.WXK_DOWN):
            direction = -1 if key_code == wx.WXK_UP else 1
            self.select_feature(
                (self._selected_feature + direction) % len(self.feature_rail_buttons)
            )
            self.feature_rail_buttons[self._selected_feature].SetFocus()
            return
        event.Skip()
