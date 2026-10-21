"""Main wx workspace layout for playback and graph panels."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping, Sequence

import wx

from .graph_panel import GRAPH_PANEL_MIN_SIZE, GraphPanelHost
from .timestamp_markup import set_timestamp_label
from .tooltips import position_tooltip_at_pointer, set_tooltip

TIMELINE_SLIDER_MAX: int = 10_000
"""Maximum integer position of the timeline slider."""
GRAPH_REDRAW_INTERVAL_MS: int = 33
"""Minimum spacing between scheduled visible graph-panel redraws (milliseconds)."""
MIN_GRAPH_PANE_WIDTH: int = 320
"""Minimum width for either side of the graph-stack splitter."""
MIN_GRAPH_PANEL_HEIGHT: int = GRAPH_PANEL_MIN_SIZE[1]
"""Minimum height for graph panels separated by horizontal stack splitters."""
DEFAULT_RIGHT_PANE_WIDTH: int = 320
"""Initial width of the optional right graph pane."""
CONTROLS_PANE_NAME: str = "Controls & Info"
"""Visible and programmatic name for the left feature pane."""
MAIN_ANALYSIS_PANE_NAME: str = "Main Analysis"
"""Visible and programmatic name for the middle graph pane."""
COMPARISON_PANE_NAME: str = "Comparison"
"""Visible and programmatic name for the optional right graph pane."""


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


class Workspace:
    """Own the feature rail, page host, graph splitters, and shared timeline."""

    _FEATURES = (
        ("Playback", wx.ART_GO_FORWARD),
        ("OEM file information", wx.ART_INFORMATION),
        ("State", wx.ART_LIST_VIEW),
    )

    def __init__(
        self,
        frame: wx.Frame,
        on_seek: Callable[[float], None],
        *,
        on_toggle_play: Callable[[], None] | None = None,
        on_play_reverse: Callable[[], None] | None = None,
        on_play_forward: Callable[[], None] | None = None,
        on_set_transport_rate: Callable[[float], None] | None = None,
        on_step_samples: Callable[[int], None] | None = None,
        timeline_enabled: bool,
        timeline_start_utc: str,
        timeline_end_utc: str,
        on_seek_to_time: Callable[[str], None] | None = None,
        timeline_tooltip_at: Callable[[float], str] | None = None,
        context: Mapping[str, str] | None = None,
        details: Sequence[tuple[str, str]] = (),
        view_choices: tuple[tuple[str, str], ...] = (),
        on_add_graph: Callable[[str], None] | None = None,
    ) -> None:
        self._on_seek = on_seek
        self._on_seek_to_time = on_seek_to_time
        self._timeline_enabled = timeline_enabled
        self._syncing_timeline = False
        self._selected_feature = 0
        self._graph_panels: dict[str, list[GraphPanelHost]] = {
            "middle": [],
            "right": [],
        }
        self._pending_graph_redraws: deque[GraphPanelHost] = deque()
        self._queued_graph_redraws: set[GraphPanelHost] = set()
        self._graph_redraw_timer: wx.CallLater | None = None
        self._stack_windows: dict[str, wx.ScrolledWindow] = {}
        self._stack_sizers: dict[str, wx.BoxSizer] = {}
        self._empty_states: dict[str, wx.StaticText] = {}
        self._empty_panels: dict[str, wx.Panel] = {}
        self._add_buttons: dict[str, wx.Button] = {}
        self._pane_close_buttons: dict[str, wx.Button] = {}
        self._stack_roots: dict[str, wx.Window | None] = {
            "middle": None,
            "right": None,
        }
        self._stack_splitters: dict[str, list[wx.SplitterWindow]] = {
            "middle": [],
            "right": [],
        }
        self._right_pane_width = DEFAULT_RIGHT_PANE_WIDTH
        self._comparison_toggle: wx.ToggleButton | None = None
        self._view_choices = view_choices
        self._on_add_graph = on_add_graph

        root = wx.BoxSizer(wx.VERTICAL)
        self.content_splitter = wx.SplitterWindow(
            frame, wx.ID_ANY, style=wx.SP_LIVE_UPDATE | wx.SP_3DSASH
        )
        self.left_pane = wx.Panel(self.content_splitter, wx.ID_ANY)
        self.left_pane.SetName(CONTROLS_PANE_NAME)
        self.graph_splitter = wx.SplitterWindow(
            self.content_splitter,
            wx.ID_ANY,
            style=wx.SP_LIVE_UPDATE | wx.SP_3DSASH,
        )
        self.middle_pane, self.middle_stack = self._make_graph_pane(
            self.graph_splitter, "middle", MAIN_ANALYSIS_PANE_NAME
        )
        self.right_pane, self.right_stack = self._make_graph_pane(
            self.graph_splitter, "right", COMPARISON_PANE_NAME
        )
        self.graph_splitter.SetMinimumPaneSize(MIN_GRAPH_PANE_WIDTH)
        self.graph_splitter.SetSashGravity(1.0)
        self.graph_splitter.SplitVertically(
            self.middle_pane, self.right_pane, MIN_GRAPH_PANE_WIDTH
        )
        self.graph_splitter.Unsplit(self.right_pane)
        self.content_splitter.SetMinimumPaneSize(240)
        self.content_splitter.SetSashGravity(0.0)
        self._right_pane_visible = False

        self._build_feature_navigation(context or {}, details)
        self.content_splitter.SplitVertically(self.left_pane, self.graph_splitter, 240)

        self.timeline_panel = wx.Panel(frame, wx.ID_ANY)
        timeline_layout = wx.BoxSizer(wx.VERTICAL)
        timeline_layout.Add(
            wx.StaticText(self.timeline_panel, wx.ID_ANY, "Timeline"),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            12,
        )
        time_labels = wx.BoxSizer(wx.HORIZONTAL)
        # Shrink only displayed fractions; retain the full ISO-8601 timestamp.
        self.timeline_start_label = wx.StaticText(self.timeline_panel, wx.ID_ANY, "")
        set_timestamp_label(
            self.timeline_start_label, f"Start UTC: {timeline_start_utc}"
        )
        self.timeline_start_label.SetName("Timeline start time (UTC)")
        current_time_row = wx.BoxSizer(wx.HORIZONTAL)
        self.timeline_current_prefix = wx.StaticText(
            self.timeline_panel, wx.ID_ANY, "Current UTC:"
        )
        # Put time entry beside the current UTC prefix to replace the Playback seek form.
        self.timeline_time_entry = wx.TextCtrl(
            self.timeline_panel,
            wx.ID_ANY,
            "",
            style=wx.TE_PROCESS_ENTER,
        )
        self.timeline_time_entry.SetName("Current UTC or elapsed time")
        self.timeline_time_entry.SetHint("UTC timestamp or elapsed time, e.g. 1h30m")
        self.timeline_time_entry.SetMinSize(wx.Size(220, -1))
        if on_seek_to_time is not None:
            self.timeline_time_entry.Bind(
                wx.EVT_TEXT_ENTER,
                self._submit_timeline_time,
            )
        self.time_error_label = wx.StaticText(self.timeline_panel, wx.ID_ANY, "")
        self.time_error_label.SetForegroundColour(wx.Colour(190, 35, 35))
        current_time_row.Add(
            self.timeline_current_prefix,
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            4,
        )
        current_time_row.Add(
            self.timeline_time_entry, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4
        )
        current_time_row.Add(self.time_error_label, 1, wx.ALIGN_CENTER_VERTICAL)
        self.timeline_end_label = wx.StaticText(self.timeline_panel, wx.ID_ANY, "")
        set_timestamp_label(self.timeline_end_label, f"End UTC: {timeline_end_utc}")
        self.timeline_end_label.SetName("Timeline end time (UTC)")
        time_labels.Add(
            self.timeline_start_label,
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        time_labels.Add((0, 0), 1, wx.EXPAND)
        time_labels.Add(current_time_row, 0, wx.ALIGN_CENTER_VERTICAL)
        time_labels.Add((0, 0), 1, wx.EXPAND)
        time_labels.Add(
            self.timeline_end_label,
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        timeline_layout.Add(time_labels, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)
        transport_row = wx.BoxSizer(wx.HORIZONTAL)
        self.transport_buttons: dict[float, wx.ToggleButton] = {}
        self._transport_button_labels: dict[float, str] = {}
        for rate, glyph, direction in (
            (-1000.0, "<<< 1000×", "reverse"),
            (-100.0, "<< 100×", "reverse"),
            (-10.0, "< 10×", "reverse"),
            (-1.0, "< 1×", "reverse"),
        ):
            button = self._make_transport_button(
                rate,
                glyph,
                direction,
                on_set_transport_rate,
                on_step_samples,
            )
            self.transport_buttons[rate] = button
            self._transport_button_labels[rate] = glyph
            transport_row.Add(button, 0, wx.RIGHT, 4)

        self.transport_reverse_play_button = wx.Button(
            self.timeline_panel, wx.ID_ANY, "◀"
        )
        self.transport_reverse_play_button.SetName("Play reverse at current speed")
        set_tooltip(
            self.transport_reverse_play_button,
            "Play reverse at current speed.",
        )
        if (
            on_toggle_play is not None
            and on_play_reverse is not None
            and on_play_forward is not None
        ):
            self.transport_reverse_play_button.Bind(
                wx.EVT_BUTTON,
                lambda _event: (
                    on_toggle_play()
                    if self._transport_playing and self._transport_rate < 0.0
                    else on_play_reverse()
                ),
            )
        transport_row.Add(self.transport_reverse_play_button, 0, wx.RIGHT, 2)
        self.transport_forward_play_button = wx.Button(
            self.timeline_panel, wx.ID_ANY, "▶"
        )
        self.transport_forward_play_button.SetName("Play forward at current speed")
        set_tooltip(
            self.transport_forward_play_button,
            "Play forward at current speed.",
        )
        if (
            on_toggle_play is not None
            and on_play_reverse is not None
            and on_play_forward is not None
        ):
            self.transport_forward_play_button.Bind(
                wx.EVT_BUTTON,
                lambda _event: (
                    on_toggle_play()
                    if self._transport_playing and self._transport_rate > 0.0
                    else on_play_forward()
                ),
            )
        transport_row.Add(self.transport_forward_play_button, 0, wx.RIGHT, 2)
        # A non-text focus target: macOS buttons refuse keyboard focus unless
        # Full Keyboard Access is on, which leaves the text field's focus ring.
        self._focus_sink = wx.Panel(self.timeline_panel, wx.ID_ANY, size=(1, 1))
        self._focus_sink.SetCanFocus(True)
        transport_row.Add(self._focus_sink, 0, wx.RIGHT, 2)

        for rate, glyph, direction in (
            (1.0, "1× >", "forward"),
            (10.0, "10× >", "forward"),
            (100.0, "100× >>", "forward"),
            (1000.0, "1000× >>>", "forward"),
        ):
            button = self._make_transport_button(
                rate,
                glyph,
                direction,
                on_set_transport_rate,
                on_step_samples,
            )
            self.transport_buttons[rate] = button
            self._transport_button_labels[rate] = glyph
            transport_row.Add(button, 0, wx.RIGHT, 4)
        timeline_layout.Add(transport_row, 0, wx.ALIGN_CENTER | wx.TOP, 4)
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
        if timeline_tooltip_at is not None:
            self._timeline_tooltip_at = timeline_tooltip_at
            self._timeline_tooltip = set_tooltip(
                self.timeline_slider,
                timeline_tooltip_at(0.0),
            )
            # Let the motion handler position the first popup before the
            # automatic hover timer can place it at the slider edge.
            self._timeline_tooltip.SetStartDelay(1)
            self.timeline_slider.Bind(wx.EVT_MOTION, self._on_timeline_motion)
        timeline_layout.Add(
            self.timeline_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12
        )
        self.timeline_panel.SetSizer(timeline_layout)

        root.Add(self.content_splitter, 1, wx.EXPAND)
        root.Add(self.timeline_panel, 0, wx.EXPAND)
        frame.SetSizer(root)
        self._transport_playing = False
        self._transport_rate = 1.0
        self._last_transport_state: tuple[bool, float] | None = None

    def _make_transport_button(
        self,
        rate: float,
        glyph: str,
        direction: str,
        on_set_transport_rate: Callable[[float], None] | None,
        on_step_samples: Callable[[int], None] | None,
    ) -> wx.ToggleButton:
        button = wx.ToggleButton(
            self.timeline_panel,
            wx.ID_ANY,
            glyph,
            style=wx.BU_EXACTFIT,
        )
        button.SetMinSize(wx.Size(button.GetBestSize().width + 4, -1))
        magnitude = abs(rate)
        button.SetName(f"Set {direction} playback speed to {magnitude:g}x")
        if magnitude == 1.0:
            message = f"Set {direction} speed to 1x."
        else:
            message = f"Increase {direction} speed by {magnitude:g}x."
        set_tooltip(button, message)
        if on_set_transport_rate is not None:

            def set_transport_rate(
                _event, selected_rate: float = rate, speed_button=button
            ) -> None:
                on_set_transport_rate(selected_rate)
                if abs(selected_rate) == 1.0:
                    # Re-selecting the current rate may skip the normal state refresh.
                    speed_button.SetValue(True)

            button.Bind(
                wx.EVT_TOGGLEBUTTON,
                set_transport_rate,
            )
        if abs(rate) == 1.0 and on_step_samples is not None:
            button.Bind(
                wx.EVT_LEFT_DCLICK,
                lambda _event, count=-1 if rate < 0.0 else 1: on_step_samples(count),
            )
        return button

    def update_transport_state(self, playing: bool, rate: float) -> None:
        """Synchronize direction play/pause controls and speed presets with the clock."""
        state = (playing, rate)
        if self._last_transport_state == state:
            return
        # Rewriting unchanged native button labels on every tick prevents GTK's
        # pending slider tooltip from appearing.
        self._last_transport_state = state
        self._transport_playing = playing
        self._transport_rate = rate
        speed = abs(rate)
        for selected_rate, button in self.transport_buttons.items():
            step = abs(selected_rate)
            if step == 1.0:
                # The 1× controls select one exact rate, not a speed range.
                in_speed_range = speed == 1.0
            else:
                in_speed_range = speed >= step and (
                    step == 1000.0 or speed < step * 10.0
                )
            active = in_speed_range and ((rate > 0.0) == (selected_rate > 0.0))
            button.SetValue(active)
            if active and step != 1.0:
                arrow_count = {10.0: 1, 100.0: 2, 1000.0: 3}[step]
                arrow = ">" * arrow_count if rate > 0.0 else "<" * arrow_count
                label = f"{speed:g}x {arrow}" if rate > 0.0 else f"{arrow} {speed:g}x"
            else:
                label = self._transport_button_labels[selected_rate]
            button.SetLabel(label)
        reverse_active = playing and rate < 0.0
        self.transport_reverse_play_button.SetLabel("Ⅱ" if reverse_active else "◀")
        self.transport_reverse_play_button.SetName(
            "Pause reverse playback"
            if reverse_active
            else "Play reverse at current speed"
        )
        set_tooltip(
            self.transport_reverse_play_button,
            (
                "Pause reverse playback."
                if reverse_active
                else "Play reverse at current speed."
            ),
        )
        forward_active = playing and rate > 0.0
        self.transport_forward_play_button.SetLabel("Ⅱ" if forward_active else "▶")
        self.transport_forward_play_button.SetName(
            "Pause forward playback"
            if forward_active
            else "Play forward at current speed"
        )
        set_tooltip(
            self.transport_forward_play_button,
            (
                "Pause forward playback."
                if forward_active
                else "Play forward at current speed."
            ),
        )

    def set_playback_content(self, panel: wx.Window) -> None:
        """Place the playback controls in the Playback feature page."""
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(panel, 1, wx.EXPAND)
        self.playback_page.SetSizer(layout)

    def set_state_content(self, panel: wx.Window) -> None:
        """Place cursor state readouts in the State feature page."""
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(panel, 1, wx.EXPAND)
        self.state_page.SetSizer(layout)

    def update_timeline(
        self, progress: float, current_utc: str, *, playing: bool = False
    ) -> None:
        """Synchronize the global timeline and UTC label without emitting a seek."""
        value = round(min(max(progress, 0.0), 1.0) * TIMELINE_SLIDER_MAX)
        self._syncing_timeline = True
        try:
            if self.timeline_slider.GetValue() != value:
                self.timeline_slider.SetValue(value)
        finally:
            self._syncing_timeline = False
        # Preserve text the user is editing while playback updates the readout.
        if playing or not self.timeline_time_entry.HasFocus():
            self.timeline_time_entry.ChangeValue(current_utc)

    def show_time_error(self, message: str) -> None:
        self.time_error_label.SetLabel(message)

    def clear_time_error(self) -> None:
        self.time_error_label.SetLabel("")

    def set_current_time_entry(self, current_utc: str) -> None:
        """Replace submitted text with the normalized current UTC timestamp."""
        self.timeline_time_entry.ChangeValue(current_utc)

    def show_right_pane(self, visible: bool) -> None:
        """Show or hide the optional graph stack while retaining its contents."""
        if visible == self._right_pane_visible:
            return
        if visible:
            client_width = self.graph_splitter.GetClientSize().width
            sash_size = self.graph_splitter.GetSashSize()
            if client_width > 0:
                max_right_width = max(
                    MIN_GRAPH_PANE_WIDTH,
                    client_width - MIN_GRAPH_PANE_WIDTH - sash_size,
                )
                right_width = min(self._right_pane_width, max_right_width)
                sash_position = client_width - right_width - sash_size
            else:
                sash_position = MIN_GRAPH_PANE_WIDTH
            self.graph_splitter.SplitVertically(
                self.middle_pane, self.right_pane, sash_position
            )
        else:
            client_width = self.graph_splitter.GetClientSize().width
            if client_width > 0:
                self._right_pane_width = max(
                    MIN_GRAPH_PANE_WIDTH,
                    client_width
                    - self.graph_splitter.GetSashPosition()
                    - self.graph_splitter.GetSashSize(),
                )
            self.graph_splitter.Unsplit(self.right_pane)
        self._right_pane_visible = visible
        if self._comparison_toggle is not None:
            self._comparison_toggle.SetValue(visible)
        self.graph_splitter.Layout()
        if visible:
            self._request_stack_redraws("right")

    def add_graph_panel(self, panel: GraphPanelHost, stack: str = "middle") -> None:
        """Add a graph host, separating adjacent panels with horizontal splitters."""
        if stack not in self._graph_panels:
            raise ValueError(f"unknown graph stack {stack!r}")
        if panel in self._graph_panels[stack]:
            raise ValueError("graph panel is already in this stack")

        window = self._stack_windows[stack]
        sizer = self._stack_sizers[stack]
        root = self._stack_roots[stack]
        if root is None:
            root = panel
            # A reused panel may be parked outside the scroller after removal.
            root.Reparent(window)
            sizer.Add(root, 1, wx.EXPAND)
        else:
            root_min_height = root.GetMinSize().height
            splitter = wx.SplitterWindow(
                window, wx.ID_ANY, style=wx.SP_LIVE_UPDATE | wx.SP_3DSASH
            )
            splitter.SetMinimumPaneSize(MIN_GRAPH_PANEL_HEIGHT)
            splitter.SetSashGravity(0.5)
            sizer.Detach(root)
            root.Reparent(splitter)
            panel.Reparent(splitter)
            if not splitter.SplitHorizontally(root, panel, root_min_height):
                root.Reparent(window)
                panel.Reparent(window)
                splitter.Destroy()
                sizer.Add(root, 1, wx.EXPAND)
                raise RuntimeError(f"could not split graph stack {stack!r}")
            self._stack_splitters[stack].append(splitter)
            root = splitter
            sizer.Add(root, 1, wx.EXPAND)

        self._graph_panels[stack].append(panel)
        self._stack_roots[stack] = root
        self._layout_graph_stack(stack)

    def remove_graph_panel(self, panel: GraphPanelHost, stack: str = "middle") -> None:
        """Remove a graph host and collapse its splitter without disturbing others."""
        if stack not in self._graph_panels:
            raise ValueError(f"unknown graph stack {stack!r}")
        if panel not in self._graph_panels[stack]:
            return
        self._remove_panel_from_stack_tree(stack, panel)
        self._graph_panels[stack].remove(panel)
        if panel in self._queued_graph_redraws:
            self._pending_graph_redraws = deque(
                queued for queued in self._pending_graph_redraws if queued is not panel
            )
            self._queued_graph_redraws.remove(panel)
        if not self._pending_graph_redraws and self._graph_redraw_timer is not None:
            if self._graph_redraw_timer.IsRunning():
                self._graph_redraw_timer.Stop()
            self._graph_redraw_timer = None
        self._layout_graph_stack(stack)

    def replace_graph_panel(
        self,
        old_panel: GraphPanelHost,
        new_panel: GraphPanelHost,
        stack: str = "middle",
    ) -> None:
        """Replace a graph host in place, preserving stack order and scroll position."""
        if stack not in self._graph_panels:
            raise ValueError(f"unknown graph stack {stack!r}")
        panels = self._graph_panels[stack]
        if old_panel not in panels:
            raise ValueError("graph panel is not in this stack")
        if new_panel in panels:
            raise ValueError("replacement graph panel is already in this stack")

        window = self._stack_windows[stack]
        sizer = self._stack_sizers[stack]
        root = self._stack_roots[stack]
        view_start = window.GetViewStart()
        if root is old_panel:
            sizer.Detach(old_panel)
            # The replaced panel may await deferred destruction while the
            # new layout scrolls; keep it outside GTK's scrolling children.
            old_panel.Reparent(window.GetParent())
            new_panel.Reparent(window)
            sizer.Add(new_panel, 1, wx.EXPAND)
            self._stack_roots[stack] = new_panel
        else:
            parent = old_panel.GetParent()
            if not isinstance(parent, wx.SplitterWindow):
                raise RuntimeError(
                    f"graph panel {old_panel.panel_id!r} has an invalid parent"
                )
            new_panel.Reparent(parent)
            if not parent.ReplaceWindow(old_panel, new_panel):
                new_panel.Reparent(window)
                raise RuntimeError(
                    f"could not replace graph panel {old_panel.panel_id!r}"
                )

        panels[panels.index(old_panel)] = new_panel
        self._layout_graph_stack(stack)
        window.Scroll(*view_start)

    def move_graph_panel(self, panel: GraphPanelHost, stack: str, offset: int) -> None:
        """Move a live panel within its stack without recreating its view."""
        if stack not in self._graph_panels:
            raise ValueError(f"unknown graph stack {stack!r}")
        panels = self._graph_panels[stack]
        current_index = panels.index(panel)
        target_index = min(max(current_index + offset, 0), len(panels) - 1)
        if target_index == current_index:
            return

        reordered = list(panels)
        reordered.insert(target_index, reordered.pop(current_index))
        stack_window = self._stack_windows[stack]
        for existing_panel in tuple(panels):
            self.remove_graph_panel(existing_panel, stack)
            existing_panel.Reparent(stack_window)
        for existing_panel in reordered:
            self.add_graph_panel(existing_panel, stack)

    def close(self) -> None:
        """Stop pending graph redraw work during workspace shutdown."""
        if self._graph_redraw_timer is not None:
            if self._graph_redraw_timer.IsRunning():
                self._graph_redraw_timer.Stop()
            self._graph_redraw_timer = None
        self._pending_graph_redraws.clear()
        self._queued_graph_redraws.clear()

    def request_visible_graph_redraws(self) -> None:
        """Redraw graph hosts that are visible after a stack scroll."""
        self._request_stack_redraws("middle")
        self._request_stack_redraws("right")

    def queue_graph_redraw(self, panel: GraphPanelHost) -> None:
        """Queue one visible panel for the shared redraw budget."""
        if not self.is_graph_panel_visible(panel):
            return
        if panel in self._queued_graph_redraws:
            return
        self._pending_graph_redraws.append(panel)
        self._queued_graph_redraws.add(panel)
        if self._graph_redraw_timer is None:
            self._graph_redraw_timer = wx.CallLater(1, self._draw_next_graph_panel)

    def draw_initial_graphs(self) -> None:
        """Draw currently visible plots before the playback timer starts."""
        if self._graph_redraw_timer is not None:
            if self._graph_redraw_timer.IsRunning():
                self._graph_redraw_timer.Stop()
            self._graph_redraw_timer = None
        pending = tuple(self._pending_graph_redraws)
        self._pending_graph_redraws.clear()
        self._queued_graph_redraws.clear()
        for panel in pending:
            if self.is_graph_panel_visible(panel):
                panel.draw_initial()

    def is_graph_panel_visible(self, panel: GraphPanelHost) -> bool:
        """Check whether a graph host intersects its scroll stack's viewport."""
        if not panel.IsShownOnScreen():
            return False
        stack_window = next(
            (
                self._stack_windows[stack]
                for stack, panels in self._graph_panels.items()
                if panel in panels
            ),
            None,
        )
        if stack_window is None:
            return False
        viewport = wx.Rect(
            stack_window.ClientToScreen((0, 0)), stack_window.GetClientSize()
        )
        return panel.GetScreenRect().Intersects(viewport)

    def _remove_panel_from_stack_tree(self, stack: str, panel: GraphPanelHost) -> None:
        root = self._stack_roots[stack]
        if root is panel:
            self._stack_sizers[stack].Detach(panel)
            # Removing it from the sizer alone still leaves a native scroll
            # child until the caller destroys or reuses the panel.
            panel.Reparent(self._stack_windows[stack].GetParent())
            self._stack_roots[stack] = None
            return
        if not isinstance(root, wx.SplitterWindow):
            raise RuntimeError(f"graph stack {stack!r} has an invalid splitter tree")
        if not self._remove_panel_from_splitter(stack, root, panel):
            raise RuntimeError(
                f"graph panel {panel.panel_id!r} is missing from its stack"
            )

    def _remove_panel_from_splitter(
        self, stack: str, splitter: wx.SplitterWindow, panel: GraphPanelHost
    ) -> bool:
        first = splitter.GetWindow1()
        second = splitter.GetWindow2()
        if first is panel or second is panel:
            sibling = second if first is panel else first
            stack_window = self._stack_windows[stack]
            splitter.Unsplit(panel)
            # Unsplit hides the removed pane. Park it outside the scroller
            # so GTK cannot allocate it during the following layout update.
            panel.Reparent(stack_window.GetParent())
            if splitter is self._stack_roots[stack]:
                self._stack_sizers[stack].Detach(splitter)
                sibling.Reparent(stack_window)
                # Destroy() is deferred: keep the retiring splitter out of
                # native scrolling while GTK finishes deleting it.
                splitter.Reparent(stack_window.GetParent())
                splitter.Destroy()
                self._stack_sizers[stack].Add(sibling, 1, wx.EXPAND)
                self._stack_roots[stack] = sibling
            else:
                parent = splitter.GetParent()
                if not isinstance(parent, wx.SplitterWindow):
                    raise RuntimeError(
                        f"graph stack {stack!r} has a broken splitter hierarchy"
                    )
                parent_first = parent.GetWindow1()
                parent_second = parent.GetWindow2()
                parent_sash_position = parent.GetSashPosition()
                parent.Unsplit(splitter)
                sibling.Reparent(parent)
                splitter.Destroy()
                if parent_first is splitter:
                    split_succeeded = parent.SplitHorizontally(
                        sibling, parent_second, parent_sash_position
                    )
                else:
                    split_succeeded = parent.SplitHorizontally(
                        parent_first, sibling, parent_sash_position
                    )
                if not split_succeeded:
                    raise RuntimeError(f"could not restore graph stack {stack!r}")
            self._stack_splitters[stack].remove(splitter)
            return True

        if isinstance(first, wx.SplitterWindow) and self._remove_panel_from_splitter(
            stack, first, panel
        ):
            return True
        if isinstance(second, wx.SplitterWindow) and self._remove_panel_from_splitter(
            stack, second, panel
        ):
            return True
        return False

    def _layout_graph_stack(self, stack: str) -> None:
        """Synchronize the empty state, minimum sizes, and scroll layout."""

        def minimum_height(window: wx.Window) -> int:
            if not isinstance(window, wx.SplitterWindow):
                return window.GetMinSize().height
            height = (
                minimum_height(window.GetWindow1())
                + minimum_height(window.GetWindow2())
                + window.GetSashSize()
            )
            window.SetMinimumPaneSize(MIN_GRAPH_PANEL_HEIGHT)
            window.SetMinSize((GRAPH_PANEL_MIN_SIZE[0], height))
            return height

        root = self._stack_roots[stack]
        if root is not None:
            minimum_height(root)

        window = self._stack_windows[stack]
        sizer = self._stack_sizers[stack]
        empty_panel = self._empty_panels[stack]
        if root is not None and empty_panel.GetParent() is window:
            # wxGTK allocates even hidden direct children when scrolling.
            # Detach and park the empty state until it is needed again.
            empty_panel.Hide()
            sizer.Detach(empty_panel)
            empty_panel.Reparent(window.GetParent())
        elif root is None and empty_panel.GetParent() is not window:
            # Only return the empty state to the scroller when it is visible.
            empty_panel.Reparent(window)
            sizer.Add(empty_panel, 0, wx.EXPAND)
            empty_panel.Show()

        window.Layout()
        window.FitInside()
        self._update_stack_scrollbar_visibility(stack)

    def _update_stack_scrollbar_visibility(self, stack: str) -> None:
        window = self._stack_windows[stack]
        has_overflow = window.GetScrollRange(wx.VERTICAL) > window.GetScrollThumb(
            wx.VERTICAL
        )
        window.AlwaysShowScrollbars(False, has_overflow)

    def _on_stack_size(self, stack: str, event: wx.SizeEvent) -> None:
        self._update_stack_scrollbar_visibility(stack)
        event.Skip()

    def select_feature(self, index: int) -> None:
        """Select a feature page and keep the rail's toggle state synchronized."""
        if not 0 <= index < len(self.feature_buttons):
            return
        self._selected_feature = index
        self.feature_book.ChangeSelection(index)
        self.feature_title.SetLabel(
            f"{CONTROLS_PANE_NAME} / {self._FEATURES[index][0]}"
        )
        self._wrap_feature_title()
        for button_index, button in enumerate(self.feature_buttons):
            button.SetValue(button_index == index)

    def _on_left_pane_size(self, event: wx.SizeEvent) -> None:
        self._wrap_feature_title()
        self.left_pane.Layout()
        event.Skip()

    def _wrap_feature_title(self) -> None:
        content_width = self.left_pane.GetClientSize().width - 16
        if content_width > 0:
            self.feature_title.Wrap(content_width)

    def _build_feature_navigation(
        self, context: Mapping[str, str], details: Sequence[tuple[str, str]]
    ) -> None:
        left_layout = wx.BoxSizer(wx.VERTICAL)
        self.feature_title = wx.StaticText(
            self.left_pane,
            wx.ID_ANY,
            f"{CONTROLS_PANE_NAME} / {self._FEATURES[0][0]}",
        )
        self.feature_title.SetName(CONTROLS_PANE_NAME)
        left_layout.Add(
            self.feature_title, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8
        )
        self.left_pane.Bind(wx.EVT_SIZE, self._on_left_pane_size)
        content_layout = wx.BoxSizer(wx.HORIZONTAL)
        rail = wx.BoxSizer(wx.VERTICAL)
        self.feature_book = wx.Simplebook(self.left_pane, wx.ID_ANY)
        self.feature_pages: list[wx.Panel] = []
        self.feature_buttons: list[wx.BitmapToggleButton] = []

        for index, (name, art_id) in enumerate(self._FEATURES):
            page = wx.Panel(self.feature_book, wx.ID_ANY)
            page.SetName(name)
            self.feature_book.AddPage(page, name)
            self.feature_pages.append(page)
            bitmap = wx.ArtProvider.GetBitmap(art_id, wx.ART_BUTTON, wx.Size(24, 24))
            button = wx.BitmapToggleButton(self.left_pane, wx.ID_ANY, bitmap)
            button.SetName(name)
            set_tooltip(button, name)
            button.SetMinSize((36, 36))
            button.SetValue(index == 0)
            button.Bind(
                wx.EVT_TOGGLEBUTTON,
                lambda _event, selected=index: self.select_feature(selected),
            )
            button.Bind(wx.EVT_KEY_DOWN, self._on_feature_key_down)
            rail.Add(button, 0, wx.EXPAND | wx.ALL, 2)
            self.feature_buttons.append(button)

        self.playback_page = self.feature_pages[0]
        self.file_info_page = self.feature_pages[1]
        self.state_page = self.feature_pages[2]
        file_info_page_layout = wx.BoxSizer(wx.VERTICAL)
        self.file_info_scroll = wx.ScrolledWindow(
            self.file_info_page,
            wx.ID_ANY,
            style=wx.VSCROLL | wx.TAB_TRAVERSAL,
        )
        self.file_info_scroll.SetName("OEM information details")
        self.file_info_scroll.SetCanFocus(True)
        self.file_info_scroll.SetScrollRate(0, 10)
        info_layout = wx.BoxSizer(wx.VERTICAL)
        self._file_info_section_labels: list[wx.StaticText] = []
        self._file_info_labels: list[wx.StaticText] = []
        primary_heading = wx.StaticText(
            self.file_info_scroll, wx.ID_ANY, "File context"
        )
        primary_heading.SetName("Primary OEM file context")
        self._file_info_section_labels.append(primary_heading)
        info_layout.Add(primary_heading, 0, wx.EXPAND | wx.ALL, 8)
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
            info_layout.Add(
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
            info_layout.Add(
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
                info_layout.Add(
                    info_label,
                    0,
                    wx.EXPAND | wx.ALL,
                    8,
                )
        self.file_info_scroll.SetSizer(info_layout)
        file_info_page_layout.Add(self.file_info_scroll, 1, wx.EXPAND)
        self.file_info_page.SetSizer(file_info_page_layout)
        self.file_info_scroll.Bind(wx.EVT_SIZE, self._on_file_info_scroll_size)
        self.file_info_scroll.Bind(wx.EVT_KEY_DOWN, self._on_file_info_scroll_key_down)
        self.file_info_scroll.FitInside()

        content_layout.Add(rail, 0, wx.EXPAND | wx.ALL, 4)
        content_layout.Add(self.feature_book, 1, wx.EXPAND | wx.ALL, 4)
        left_layout.Add(content_layout, 1, wx.EXPAND)
        self.left_pane.SetSizer(left_layout)

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

    def _make_graph_pane(
        self, parent: wx.Window, stack: str, title: str
    ) -> tuple[wx.Panel, wx.ScrolledWindow]:
        pane = wx.Panel(parent, wx.ID_ANY)
        pane.SetName(title)
        layout = wx.BoxSizer(wx.VERTICAL)
        header = wx.BoxSizer(wx.HORIZONTAL)
        title_label = wx.StaticText(pane, wx.ID_ANY, title)
        title_label.SetName(title)
        header.Add(title_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 8)
        add_button = wx.Button(pane, wx.ID_ANY, "Add graph")
        add_button.SetName(f"Add graph to {stack} stack")
        set_tooltip(add_button, f"Add a graph to {title}")
        self._add_buttons[stack] = add_button
        add_button.Bind(
            wx.EVT_BUTTON,
            lambda _event, stack=stack: self._request_add_graph(stack),
        )
        header.Add(add_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        if stack == "middle":
            comparison_toggle = wx.ToggleButton(pane, wx.ID_ANY, "Comparison")
            self._comparison_toggle = comparison_toggle
            comparison_toggle.SetName("Toggle Comparison pane")
            set_tooltip(comparison_toggle, "Show or hide the Comparison pane")
            comparison_toggle.SetValue(False)
            comparison_toggle.Bind(
                wx.EVT_TOGGLEBUTTON,
                lambda _event: self.show_right_pane(comparison_toggle.GetValue()),
            )
            header.Add(comparison_toggle, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        else:
            close_button = wx.Button(pane, wx.ID_ANY, "Close pane")
            close_button.SetName("Close Comparison pane")
            set_tooltip(close_button, "Hide the Comparison pane")
            close_button.Bind(wx.EVT_BUTTON, lambda _event: self.show_right_pane(False))
            self._pane_close_buttons[stack] = close_button
            header.Add(close_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        layout.Add(header, 0, wx.EXPAND)
        stack_window = self._make_graph_stack(pane, stack)
        stack_window.SetName(f"{title} graph stack")
        layout.Add(stack_window, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        pane.SetSizer(layout)
        return pane, stack_window

    def _make_graph_stack(self, parent: wx.Window, stack: str) -> wx.ScrolledWindow:
        window = wx.ScrolledWindow(parent, wx.ID_ANY, style=wx.VSCROLL)
        window.AlwaysShowScrollbars(False, False)
        window.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        empty_panel = wx.Panel(window, wx.ID_ANY)
        empty_layout = wx.BoxSizer(wx.VERTICAL)
        empty_state = wx.StaticText(empty_panel, wx.ID_ANY, "No graph panels")
        empty_state.SetName(f"{stack} stack empty state")
        empty_layout.Add(empty_state, 0, wx.ALL, 12)
        add_button = wx.Button(empty_panel, wx.ID_ANY, "Add graph")
        add_button.SetName(f"Add graph to empty {stack} stack")
        add_button.Bind(
            wx.EVT_BUTTON,
            lambda _event, stack=stack: self._request_add_graph(stack),
        )
        empty_layout.Add(add_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        empty_panel.SetSizer(empty_layout)
        sizer.Add(empty_panel, 0, wx.EXPAND)
        window.SetSizer(sizer)
        window.Bind(wx.EVT_SCROLLWIN, self._on_stack_scroll)
        window.Bind(
            wx.EVT_SIZE,
            lambda event, stack=stack: self._on_stack_size(stack, event),
        )
        self._stack_windows[stack] = window
        self._stack_sizers[stack] = sizer
        self._empty_states[stack] = empty_state
        self._empty_panels[stack] = empty_panel
        return window

    def _request_add_graph(self, stack: str) -> None:
        if self._on_add_graph is None:
            raise RuntimeError("graph-panel creation handler is not configured")
        self._on_add_graph(stack)

    def _request_stack_redraws(self, stack: str) -> None:
        for panel in self._graph_panels[stack]:
            panel.request_redraw()

    def _draw_next_graph_panel(self) -> None:
        self._graph_redraw_timer = None
        while self._pending_graph_redraws:
            panel = self._pending_graph_redraws.popleft()
            self._queued_graph_redraws.remove(panel)
            if self.is_graph_panel_visible(panel):
                panel.draw_if_needed()
                break
        if self._pending_graph_redraws:
            self._graph_redraw_timer = wx.CallLater(
                GRAPH_REDRAW_INTERVAL_MS, self._draw_next_graph_panel
            )

    def _on_stack_scroll(self, event: wx.ScrollWinEvent) -> None:
        self.request_visible_graph_redraws()
        event.Skip()

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

    def _on_timeline_slider(self, event: wx.CommandEvent) -> None:
        if self._syncing_timeline or not self._timeline_enabled:
            return
        self._on_seek(event.GetInt() / TIMELINE_SLIDER_MAX)

    def _submit_timeline_time(self, _event: wx.CommandEvent) -> None:
        if self._on_seek_to_time is not None:
            self._on_seek_to_time(self.timeline_time_entry.GetValue())
        # Keep an inactive selection from appearing highlighted after submit.
        self.timeline_time_entry.SetInsertionPointEnd()
        # Defer focus transfer until wx finishes processing Enter; otherwise
        # the native text control can reclaim focus after this handler returns.
        wx.CallAfter(self._focus_sink.SetFocus)

    def _on_timeline_motion(self, event: wx.MouseEvent) -> None:
        width = self.timeline_slider.GetClientSize().GetWidth()
        if width > 0:
            fraction = min(max(event.GetX() / width, 0.0), 1.0)
            self._timeline_tooltip.SetMessage(self._timeline_tooltip_at(fraction))
            position_tooltip_at_pointer(
                self._timeline_tooltip,
                self.timeline_slider,
                event.GetPosition(),
            )
        event.Skip()
