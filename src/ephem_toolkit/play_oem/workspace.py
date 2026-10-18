"""Main wx workspace layout for playback and graph panels."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import wx

TIMELINE_SLIDER_MAX: int = 10_000
"""Maximum integer position of the timeline slider."""


class Workspace:
    """Own the feature rail, page host, graph splitters, and shared timeline."""

    _FEATURES = (
        ("Playback", wx.ART_GO_FORWARD),
        ("OEM file information", wx.ART_INFORMATION),
    )

    def __init__(
        self,
        frame: wx.Frame,
        on_seek: Callable[[float], None],
        *,
        timeline_enabled: bool,
        context: Mapping[str, str] | None = None,
        details: Sequence[tuple[str, str]] = (),
    ) -> None:
        self._on_seek = on_seek
        self._timeline_enabled = timeline_enabled
        self._syncing_timeline = False
        self._selected_feature = 0

        root = wx.BoxSizer(wx.VERTICAL)
        self.content_splitter = wx.SplitterWindow(
            frame, wx.ID_ANY, style=wx.SP_LIVE_UPDATE
        )
        self.left_pane = wx.Panel(self.content_splitter, wx.ID_ANY)
        self.graph_splitter = wx.SplitterWindow(
            self.content_splitter, wx.ID_ANY, style=wx.SP_LIVE_UPDATE
        )
        self.middle_stack = self._make_graph_placeholder(
            self.graph_splitter, "Graph panels"
        )
        self.right_stack = self._make_graph_placeholder(
            self.graph_splitter, "Optional graph panels"
        )
        self.graph_splitter.SetMinimumPaneSize(320)
        self.graph_splitter.SetSashGravity(1.0)
        self.graph_splitter.SplitVertically(self.middle_stack, self.right_stack, 320)
        self.graph_splitter.Unsplit(self.right_stack)
        self._right_pane_visible = False

        self._build_feature_navigation(context or {}, details)
        self.content_splitter.SetMinimumPaneSize(240)
        self.content_splitter.SplitVertically(self.left_pane, self.graph_splitter, 240)

        self.timeline_panel = wx.Panel(frame, wx.ID_ANY)
        timeline_layout = wx.BoxSizer(wx.VERTICAL)
        timeline_layout.Add(
            wx.StaticText(self.timeline_panel, wx.ID_ANY, "Timeline"),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            12,
        )
        self.timeline_slider = wx.Slider(
            self.timeline_panel,
            wx.ID_ANY,
            0,
            0,
            TIMELINE_SLIDER_MAX,
            style=wx.SL_HORIZONTAL,
        )
        self.timeline_slider.SetName("Playback timeline")
        self.timeline_slider.Enable(timeline_enabled)
        self.timeline_slider.Bind(wx.EVT_SLIDER, self._on_timeline_slider)
        timeline_layout.Add(
            self.timeline_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12
        )
        self.timeline_panel.SetSizer(timeline_layout)

        root.Add(self.content_splitter, 1, wx.EXPAND)
        root.Add(self.timeline_panel, 0, wx.EXPAND)
        frame.SetSizer(root)

    def set_playback_content(self, panel: wx.Window) -> None:
        """Place the playback controls in the Playback feature page."""
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(panel, 1, wx.EXPAND)
        self.playback_page.SetSizer(layout)

    def update_timeline(self, progress: float) -> None:
        """Synchronize the global timeline without emitting a seek."""
        value = round(min(max(progress, 0.0), 1.0) * TIMELINE_SLIDER_MAX)
        self._syncing_timeline = True
        try:
            self.timeline_slider.SetValue(value)
        finally:
            self._syncing_timeline = False

    def show_right_pane(self, visible: bool) -> None:
        """Show or hide the optional graph stack while retaining its contents."""
        if visible == self._right_pane_visible:
            return
        if visible:
            self.graph_splitter.SplitVertically(
                self.middle_stack, self.right_stack, 320
            )
        else:
            self.graph_splitter.Unsplit(self.right_stack)
        self._right_pane_visible = visible

    def select_feature(self, index: int) -> None:
        """Select a feature page and keep the rail's toggle state synchronized."""
        if not 0 <= index < len(self.feature_buttons):
            return
        self._selected_feature = index
        self.feature_book.ChangeSelection(index)
        for button_index, button in enumerate(self.feature_buttons):
            button.SetValue(button_index == index)

    def _build_feature_navigation(
        self, context: Mapping[str, str], details: Sequence[tuple[str, str]]
    ) -> None:
        left_layout = wx.BoxSizer(wx.HORIZONTAL)
        rail = wx.BoxSizer(wx.VERTICAL)
        self.feature_book = wx.Simplebook(self.left_pane, wx.ID_ANY)
        self.feature_pages: list[wx.Panel] = []
        self.feature_buttons: list[wx.BitmapToggleButton] = []

        for index, (name, art_id) in enumerate(self._FEATURES):
            page = wx.Panel(self.feature_book, wx.ID_ANY)
            self.feature_book.AddPage(page, name)
            self.feature_pages.append(page)
            bitmap = wx.ArtProvider.GetBitmap(art_id, wx.ART_BUTTON, wx.Size(24, 24))
            button = wx.BitmapToggleButton(self.left_pane, wx.ID_ANY, bitmap)
            button.SetName(name)
            button.SetToolTip(name)
            button.SetMinSize((36, 36))
            button.SetValue(index == 0)
            button.Bind(
                wx.EVT_BUTTON,
                lambda _event, selected=index: self.select_feature(selected),
            )
            button.Bind(wx.EVT_KEY_DOWN, self._on_feature_key_down)
            rail.Add(button, 0, wx.EXPAND | wx.ALL, 2)
            self.feature_buttons.append(button)

        self.playback_page = self.feature_pages[0]
        self.file_info_page = self.feature_pages[1]
        info_layout = wx.BoxSizer(wx.VERTICAL)
        for label, key in (
            ("Object", "object"),
            ("Frame", "frame"),
            ("Center", "center"),
            ("Time span", "time_span"),
            ("Samples", "sample_count"),
        ):
            info_layout.Add(
                wx.StaticText(
                    self.file_info_page,
                    wx.ID_ANY,
                    f"{label}: {context.get(key) or 'Unavailable'}",
                ),
                0,
                wx.EXPAND | wx.ALL,
                8,
            )
        for label, value in details:
            info_layout.Add(
                wx.StaticText(
                    self.file_info_page,
                    wx.ID_ANY,
                    f"{label}: {value or 'Unavailable'}",
                ),
                0,
                wx.EXPAND | wx.ALL,
                8,
            )
        self.file_info_page.SetSizer(info_layout)

        left_layout.Add(rail, 0, wx.EXPAND | wx.ALL, 4)
        left_layout.Add(self.feature_book, 1, wx.EXPAND | wx.ALL, 4)
        self.left_pane.SetSizer(left_layout)

    def _on_feature_key_down(self, event: wx.KeyEvent) -> None:
        key_code = event.GetKeyCode()
        if key_code in (wx.WXK_UP, wx.WXK_DOWN):
            direction = -1 if key_code == wx.WXK_UP else 1
            self.select_feature(
                (self._selected_feature + direction) % len(self.feature_buttons)
            )
            self.feature_buttons[self._selected_feature].SetFocus()
            return
        event.Skip()

    @staticmethod
    def _make_graph_placeholder(parent: wx.Window, label: str) -> wx.Panel:
        panel = wx.Panel(parent, wx.ID_ANY)
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(
            wx.StaticText(panel, wx.ID_ANY, label),
            0,
            wx.ALL,
            12,
        )
        panel.SetSizer(layout)
        return panel

    def _on_timeline_slider(self, event: wx.CommandEvent) -> None:
        if self._syncing_timeline or not self._timeline_enabled:
            return
        self._on_seek(event.GetInt() / TIMELINE_SLIDER_MAX)
