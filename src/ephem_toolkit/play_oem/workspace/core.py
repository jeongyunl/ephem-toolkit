"""Main wx workspace layout for playback and graph panels."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping, Sequence

import wx


from ..graph_panel import GraphPanelHost
from ..timestamp_markup import set_timestamp_label
from ..tooltips import set_tooltip
from .constants import (
    COMPARISON_PANE_NAME,
    CONTROLS_PANE_NAME,
    DEFAULT_RIGHT_PANE_WIDTH,
    MAIN_ANALYSIS_PANE_NAME,
    MIN_GRAPH_PANE_WIDTH,
    TIMELINE_SLIDER_MAX,
)
from .features import FeatureNavigationMixin
from .ground_stations import GroundStationsManager
from .graph_stack import GraphStackMixin
from .timeline import TimelineMixin
from .time_range_slider import TimeRangeSlider
from .. import time_range as range_model
from ..ground_stations import GroundStation
from ..display_time import UTC_DISPLAY, format_tt


class Workspace(FeatureNavigationMixin, GraphStackMixin, TimelineMixin):
    """Own the feature rail, page host, graph splitters, and shared timeline."""

    def __init__(
        self,
        frame: wx.Frame,
        on_seek: Callable[[float], None],
        *,
        on_toggle_play: Callable[[], None] | None = None,
        on_play_reverse: Callable[[], None] | None = None,
        on_play_forward: Callable[[], None] | None = None,
        on_set_playback_rate: Callable[[float], None] | None = None,
        on_step_samples: Callable[[int], None] | None = None,
        timeline_enabled: bool,
        on_seek_to_time: Callable[[str], None] | None = None,
        timeline_tooltip_at: Callable[[float], str] | None = None,
        context: Mapping[str, str] | None = None,
        details: Sequence[tuple[str, str]] = (),
        view_choices: tuple[tuple[str, str], ...] = (),
        on_add_graph: Callable[[str], None] | None = None,
        status_bar: wx.Window | None = None,
        playback_bounds: tuple[float, float] | None = None,
        oem_coverage: tuple[float, float] | None = None,
        slider_bounds: tuple[float, float] | None = None,
        playback_handle_bounds: tuple[float, float] | None = None,
        plot_time_range: range_model.PlotTimeRange | None = None,
        now_s: Callable[[], float] | None = None,
        on_playback_bounds: Callable[[float, float], None] | None = None,
        on_plot_endpoint: Callable[[str, float], None] | None = None,
        on_plot_endpoint_mode: (
            Callable[[str, range_model.EndpointMode], None] | None
        ) = None,
        on_begin_time_range_edit: Callable[[], None] | None = None,
        ground_stations: Sequence[GroundStation] = (),
        on_ground_stations_changed: Callable[[list[GroundStation]], None] | None = None,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        self._display_time_zone = display_time_zone
        self._on_seek = on_seek
        self._on_seek_to_time = on_seek_to_time
        self._timeline_enabled = timeline_enabled
        self._syncing_timeline = False
        self._selected_feature = 0
        self._graph_panels: dict[str, list[GraphPanelHost]] = {
            "middle": [],
            "right": [],
        }
        self._visible_graph_panels: set[GraphPanelHost] = set()
        self._graph_scroll_timers: dict[str, wx.CallLater | None] = {
            "middle": None,
            "right": None,
        }
        self._pending_graph_redraws: deque[GraphPanelHost] = deque()
        self._queued_graph_redraws: set[GraphPanelHost] = set()
        self._graph_redraw_timer: wx.CallLater | None = None
        self._stack_windows: dict[str, wx.ScrolledWindow] = {}
        self._stack_sizers: dict[str, wx.BoxSizer] = {}
        # Tracks whether each stack's final sizer item is the viewport-height tail.
        self._stack_bottom_padding_active: dict[str, bool] = {
            "middle": False,
            "right": False,
        }
        self._stack_handles: dict[str, wx.Panel] = {}
        self._bottom_drag_start: dict[str, tuple[int, int]] = {}
        self._stacks_fitting: set[str] = set()
        self._stack_overflowing: dict[str, bool] = {}
        self._empty_panels: dict[str, wx.Panel] = {}
        self._add_buttons: dict[str, wx.Button] = {}
        self._pane_close_buttons: dict[str, wx.Button] = {}
        self._stack_roots: dict[str, wx.Window | None] = {
            "middle": None,
            "right": None,
        }
        self._graph_panel_heights: dict[GraphPanelHost, int] = {}
        self._right_pane_width = DEFAULT_RIGHT_PANE_WIDTH
        self._comparison_toggle: wx.ToggleButton | None = None
        self._view_choices = view_choices
        self._on_add_graph = on_add_graph
        self._on_ground_stations_changed = on_ground_stations_changed

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.main_splitter = wx.SplitterWindow(
            frame, wx.ID_ANY, style=wx.SP_LIVE_UPDATE | wx.SP_3DSASH
        )
        self.controls_pane = wx.Panel(self.main_splitter, wx.ID_ANY)
        self.controls_pane.SetName(CONTROLS_PANE_NAME)
        self.graph_panes_splitter = wx.SplitterWindow(
            self.main_splitter,
            wx.ID_ANY,
            style=wx.SP_LIVE_UPDATE | wx.SP_3DSASH,
        )
        self.main_analysis_pane, self.main_analysis_stack = self._make_graph_pane(
            self.graph_panes_splitter, "middle", MAIN_ANALYSIS_PANE_NAME
        )
        self.comparison_pane, self.comparison_stack = self._make_graph_pane(
            self.graph_panes_splitter, "right", COMPARISON_PANE_NAME
        )
        self.graph_panes_splitter.SetMinimumPaneSize(MIN_GRAPH_PANE_WIDTH)
        self.graph_panes_splitter.SetSashGravity(1.0)
        self.graph_panes_splitter.SplitVertically(
            self.main_analysis_pane, self.comparison_pane, MIN_GRAPH_PANE_WIDTH
        )
        self.graph_panes_splitter.Unsplit(self.comparison_pane)
        self.main_splitter.SetMinimumPaneSize(240)
        self.main_splitter.SetSashGravity(0.0)
        self._right_pane_visible = False

        self._build_feature_navigation(context or {}, details)
        self.ground_station_manager = GroundStationsManager(
            self.ground_stations_page,
            ground_stations,
            on_ground_stations_changed,
        )
        self.main_splitter.SplitVertically(
            self.controls_pane, self.graph_panes_splitter, 240
        )

        self.timeline_panel = wx.ScrolledWindow(
            frame, wx.ID_ANY, style=wx.HSCROLL | wx.TAB_TRAVERSAL
        )
        self.timeline_panel.SetScrollRate(10, 0)
        timeline_sizer = wx.BoxSizer(wx.VERTICAL)
        # Give the timeline a clear boundary from the resizable analysis panes.
        timeline_sizer.Add(
            wx.StaticLine(self.timeline_panel, wx.ID_ANY),
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            8,
        )
        timeline_sizer.Add((0, 6), 0)
        self.timeline_track_row = wx.Panel(self.timeline_panel, wx.ID_ANY)
        self.timeline_track_row.SetName("Playback timeline row")
        self.timeline_track_row.SetBackgroundColour(
            self.timeline_panel.GetBackgroundColour()
        )
        timeline_track_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.timeline_track_row.SetSizer(timeline_track_sizer)
        self.playback_controls_row = wx.Panel(self.timeline_panel, wx.ID_ANY)
        self.playback_controls_row.SetName("Playback controls row")
        self.playback_controls_row.SetBackgroundColour(
            self.timeline_panel.GetBackgroundColour()
        )
        playback_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.playback_controls_row.SetSizer(playback_sizer)
        self.time_readout_row = wx.Panel(self.timeline_panel, wx.ID_ANY)
        self.time_readout_row.SetName("Playback time readout row")
        self.time_readout_row.SetBackgroundColour(
            self.timeline_panel.GetBackgroundColour()
        )
        time_label_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.time_readout_row.SetSizer(time_label_sizer)

        coverage = oem_coverage or playback_bounds or (0.0, 1.0)
        display_bounds = slider_bounds or coverage
        initial_playback = playback_bounds or coverage
        initial_playback_handles = playback_handle_bounds or initial_playback
        initial_plot_rule = plot_time_range or range_model.PlotTimeRange(
            False,
            range_model.TimeRangeEndpoint("fixed", coverage[0]),
            range_model.TimeRangeEndpoint("fixed", coverage[1]),
        )
        current_time = now_s or (lambda: coverage[0])
        self.timeline_slider = TimeRangeSlider(
            self.timeline_track_row,
            on_playback=on_playback_bounds or (lambda _start, _end: None),
            on_plot_endpoint=on_plot_endpoint or (lambda _name, _value: None),
            on_plot_endpoint_mode=on_plot_endpoint_mode or (lambda _name, _mode: None),
            on_begin_edit=on_begin_time_range_edit or (lambda: None),
        )
        self.timeline_slider.set_display_time_zone(display_time_zone)
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
        timeline_track_sizer.Add(
            self.timeline_slider,
            1,
            wx.EXPAND | wx.TOP | wx.BOTTOM,
            2,
        )
        self.timeline_slider.set_ranges(
            coverage,
            initial_playback,
            initial_plot_rule,
            current_time(),
            display_bounds,
            initial_playback_handles,
        )
        # Show playback bounds, not OEM coverage; shrink only displayed fractions.
        self.playback_start_label = wx.StaticText(self.time_readout_row, wx.ID_ANY, "")
        set_timestamp_label(
            self.playback_start_label,
            f"Start: {format_tt(initial_playback[0], self._display_time_zone)}",
        )
        self.playback_start_label.SetName("Playback range start time")
        current_time_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.timeline_current_prefix = wx.StaticText(
            self.time_readout_row, wx.ID_ANY, "Current time:"
        )
        # Put time entry beside its prefix, replacing the Playback seek form.
        self.timeline_time_entry = wx.TextCtrl(
            self.time_readout_row,
            wx.ID_ANY,
            "",
            style=wx.TE_PROCESS_ENTER,
        )
        self.timeline_time_entry.SetName("Current time or elapsed time")
        self.timeline_time_entry.SetHint("Timestamp or elapsed time, e.g. 1h30m")
        self.timeline_time_entry.SetMinSize(wx.Size(220, -1))
        if on_seek_to_time is not None:
            self.timeline_time_entry.Bind(
                wx.EVT_TEXT_ENTER,
                self._submit_timeline_time,
            )
        # Select the timestamp only when focus enters; later clicks can place
        # the caret normally while the editor remains focused.
        self.timeline_time_entry.Bind(
            wx.EVT_SET_FOCUS,
            self._on_timeline_time_focus,
        )
        self.time_error_label = wx.StaticText(self.time_readout_row, wx.ID_ANY, "")
        self.time_error_label.SetForegroundColour(wx.Colour(190, 35, 35))
        current_time_sizer.Add(
            self.timeline_current_prefix,
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            4,
        )
        current_time_sizer.Add(
            self.timeline_time_entry, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4
        )
        current_time_sizer.Add(self.time_error_label, 1, wx.ALIGN_CENTER_VERTICAL)
        self.playback_end_label = wx.StaticText(self.time_readout_row, wx.ID_ANY, "")
        set_timestamp_label(
            self.playback_end_label,
            f"End: {format_tt(initial_playback[1], self._display_time_zone)}",
        )
        self.playback_end_label.SetName("Playback range end time")
        time_label_sizer.Add(
            self.playback_start_label,
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        time_label_sizer.Add((0, 0), 1, wx.EXPAND)
        time_label_sizer.Add(current_time_sizer, 0, wx.ALIGN_CENTER_VERTICAL)
        time_label_sizer.Add((0, 0), 1, wx.EXPAND)
        time_label_sizer.Add(
            self.playback_end_label,
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        timeline_sizer.Add(
            self.time_readout_row,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            8,
        )
        timeline_sizer.Add((0, 8), 0)
        timeline_sizer.Add(
            self.timeline_track_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8
        )
        timeline_sizer.Add((0, 8), 0)
        self.playback_speed_buttons: dict[float, wx.ToggleButton] = {}
        self._playback_button_labels: dict[float, str] = {}
        for rate, glyph, direction in (
            (-1000.0, "<<< 1000×", "reverse"),
            (-100.0, "<< 100×", "reverse"),
            (-10.0, "< 10×", "reverse"),
            (-1.0, "< 1×", "reverse"),
        ):
            speed_button = self._make_playback_button(
                rate,
                glyph,
                direction,
                on_set_playback_rate,
                on_step_samples,
            )
            self.playback_speed_buttons[rate] = speed_button
            self._playback_button_labels[rate] = glyph
            playback_sizer.Add(speed_button, 0, wx.RIGHT, 4)

        self.playback_reverse_play_button = wx.Button(
            self.playback_controls_row, wx.ID_ANY, "◀"
        )
        self.playback_reverse_play_button.SetName("Play reverse at current speed")
        set_tooltip(
            self.playback_reverse_play_button,
            "Play reverse at current speed.",
        )
        if (
            on_toggle_play is not None
            and on_play_reverse is not None
            and on_play_forward is not None
        ):
            self.playback_reverse_play_button.Bind(
                wx.EVT_BUTTON,
                lambda _event: (
                    on_toggle_play()
                    if self._playback_playing and self._playback_rate < 0.0
                    else on_play_reverse()
                ),
            )
        playback_sizer.Add(self.playback_reverse_play_button, 0, wx.RIGHT, 2)
        self.playback_forward_play_button = wx.Button(
            self.playback_controls_row, wx.ID_ANY, "▶"
        )
        self.playback_forward_play_button.SetName("Play forward at current speed")
        set_tooltip(
            self.playback_forward_play_button,
            "Play forward at current speed.",
        )
        if (
            on_toggle_play is not None
            and on_play_reverse is not None
            and on_play_forward is not None
        ):
            self.playback_forward_play_button.Bind(
                wx.EVT_BUTTON,
                lambda _event: (
                    on_toggle_play()
                    if self._playback_playing and self._playback_rate > 0.0
                    else on_play_forward()
                ),
            )
        playback_sizer.Add(self.playback_forward_play_button, 0, wx.RIGHT, 2)
        # A non-text focus target: macOS buttons refuse keyboard focus unless
        # Full Keyboard Access is on, which leaves the text field's focus ring.
        self._focus_sink = wx.Panel(self.playback_controls_row, wx.ID_ANY, size=(1, 1))
        self._focus_sink.SetCanFocus(True)
        playback_sizer.Add(self._focus_sink, 0, wx.RIGHT, 2)
        # Blank space belongs to the panel, so move focus there instead of
        # leaving the UTC editor looking active after a background click.
        self.timeline_panel.Bind(
            wx.EVT_LEFT_DOWN, lambda _event: self._focus_sink.SetFocus()
        )

        for rate, glyph, direction in (
            (1.0, "1× >", "forward"),
            (10.0, "10× >", "forward"),
            (100.0, "100× >>", "forward"),
            (1000.0, "1000× >>>", "forward"),
        ):
            speed_button = self._make_playback_button(
                rate,
                glyph,
                direction,
                on_set_playback_rate,
                on_step_samples,
            )
            self.playback_speed_buttons[rate] = speed_button
            self._playback_button_labels[rate] = glyph
            playback_sizer.Add(speed_button, 0, wx.RIGHT, 4)
        timeline_sizer.Add(
            self.playback_controls_row,
            0,
            wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT,
            8,
        )
        for row in (
            self.timeline_track_row,
            self.playback_controls_row,
            self.time_readout_row,
        ):
            row.Bind(wx.EVT_LEFT_DOWN, lambda _event: self._focus_sink.SetFocus())
        self.timeline_panel.SetSizer(timeline_sizer)
        # Preserve the native controls' minimum widths when the frame narrows.
        # Reserve scrollbar height so the slider stays visible while scrolling.
        self.timeline_panel.SetMinSize(
            wx.Size(
                -1,
                timeline_sizer.CalcMin().height
                + wx.SystemSettings.GetMetric(wx.SYS_HSCROLL_Y),
            )
        )
        self.timeline_panel.FitInside()

        main_sizer.Add(self.main_splitter, 1, wx.EXPAND)
        main_sizer.Add(self.timeline_panel, 0, wx.EXPAND)
        if status_bar is not None:
            main_sizer.Add(status_bar, 0, wx.EXPAND)
        frame.SetSizer(main_sizer)
        self._playback_playing = False
        self._playback_rate = 1.0
        self._last_playback_state: tuple[bool, float] | None = None

    def set_settings_content(self, settings_panel: wx.Window) -> None:
        """Place settings controls in the Settings feature page."""
        page_sizer = wx.BoxSizer(wx.VERTICAL)
        page_sizer.Add(settings_panel, 1, wx.EXPAND)
        self.settings_page.SetSizer(page_sizer)

    def set_state_content(self, panel: wx.Window) -> None:
        """Place cursor state readouts in the State feature page."""
        page_sizer = wx.BoxSizer(wx.VERTICAL)
        page_sizer.Add(panel, 1, wx.EXPAND)
        self.state_page.SetSizer(page_sizer)

    def set_ground_stations(self, stations: Sequence[GroundStation]) -> None:
        """Update station definitions displayed in the management page."""
        self.ground_station_manager.set_stations(stations)

    def select_ground_stations(self) -> None:
        """Navigate to the Ground Stations management page."""
        index = next(
            index
            for index, (label, _icon) in enumerate(self._FEATURES)
            if label == "Ground Stations"
        )
        self.select_feature(index)

    def focus_neutral_target(self) -> None:
        """Move keyboard focus away from settings and text-entry controls."""
        self._focus_sink.SetFocus()

    def set_time_range_controls(
        self,
        coverage: tuple[float, float],
        playback: tuple[float, float],
        plot_rule: range_model.PlotTimeRange,
        now_s: float,
        slider_bounds: tuple[float, float] | None = None,
        playback_handle_bounds: tuple[float, float] | None = None,
    ) -> None:
        """Synchronize playback labels and range grips."""
        set_timestamp_label(
            self.playback_start_label,
            f"Start: {format_tt((playback_handle_bounds or playback)[0], self._display_time_zone)}",
        )
        set_timestamp_label(
            self.playback_end_label,
            f"End: {format_tt((playback_handle_bounds or playback)[1], self._display_time_zone)}",
        )
        self.timeline_slider.set_ranges(
            coverage,
            playback,
            plot_rule,
            now_s,
            slider_bounds,
            playback_handle_bounds,
        )

    def set_display_time_zone(self, display_time_zone: str) -> None:
        self._display_time_zone = display_time_zone
        self.timeline_slider.set_display_time_zone(display_time_zone)

    def close(self) -> None:
        """Stop pending graph redraw work during workspace shutdown."""
        if self._graph_redraw_timer is not None:
            if self._graph_redraw_timer.IsRunning():
                self._graph_redraw_timer.Stop()
            self._graph_redraw_timer = None
        for timer in self._graph_scroll_timers.values():
            if timer is not None and timer.IsRunning():
                timer.Stop()
        self._graph_scroll_timers = {"middle": None, "right": None}
        self._pending_graph_redraws.clear()
        self._queued_graph_redraws.clear()
