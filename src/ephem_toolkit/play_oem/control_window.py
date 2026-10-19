"""Native wxPython playback controls."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import math

import wx

from .cursor import CursorState, CursorStatus

BUTTON_SPACING: int = 4
"""Spacing between adjacent playback buttons (pixels)."""
CONTROL_SPACING: int = 8
"""Spacing between controls within a dashboard row (pixels)."""
LAYOUT_MARGIN: int = 12
"""Outer spacing around dashboard controls (pixels)."""
SECONDS_PER_MINUTE: float = 60.0
"""Number of seconds in one minute."""
SPEED_MAX: float = 9000.0
"""Maximum playback speed multiplier."""
SPEED_MIN: float = 1.0
"""Minimum playback speed multiplier."""
SPEED_SLIDER_MAX: int = 396
"""Maximum integer position of the logarithmic speed slider."""
SPEED_SLIDER_STEPS_PER_DECADE: int = 100
"""Number of slider positions representing one order of magnitude."""
TIME_ERROR_COLOR_RGB: tuple[int, int, int] = (160, 0, 0)
"""RGB color used to display time-entry errors."""


class ControlWindow:
    """Build and update the wx-native playback dashboard."""

    def __init__(
        self,
        parent: wx.Window,
        on_toggle_play: Callable[[], None],
        on_set_speed: Callable[[float], None],
        on_reverse: Callable[[], None],
        *,
        on_seek_to_time: Callable[[str], None],
        on_step_samples: Callable[[int], None],
        on_step_seconds: Callable[[float], None],
        on_jump_to_start: Callable[[], None],
        on_jump_to_end: Callable[[], None],
        accelerator_parent: wx.Frame,
        state_parent: wx.Window | None = None,
    ) -> None:
        """Create the wx dashboard and connect its controls to playback actions.

        Parameters
        ----------
        parent : wx.Window
            Parent of the playback controls panel.
        on_toggle_play : Callable[[], None]
            Toggle playback.
        on_set_speed : Callable[[float], None]
            Set the playback speed multiplier.
        on_reverse : Callable[[], None]
            Reverse the playback direction.
        on_seek_to_time : Callable[[str], None]
            Seek to a duration or UTC timestamp entered by the user.
        on_step_samples : Callable[[int], None]
            Step by a number of OEM samples.
        on_step_seconds : Callable[[float], None]
            Step by a duration in seconds.
        on_jump_to_start : Callable[[], None]
            Seek to the beginning of the timeline.
        on_jump_to_end : Callable[[], None]
            Seek to the end of the timeline.
        accelerator_parent : wx.Frame, optional
            Frame that owns the playback keyboard accelerators.
        """
        self._accelerator_parent = accelerator_parent
        self._on_set_speed = on_set_speed
        self._on_seek_to_time = on_seek_to_time
        self._syncing_sliders = False

        self.panel = wx.ScrolledWindow(
            parent, wx.ID_ANY, style=wx.VSCROLL | wx.TAB_TRAVERSAL
        )
        self.panel.SetScrollRate(0, 10)
        layout = wx.BoxSizer(wx.VERTICAL)

        self.state_panel = wx.ScrolledWindow(
            state_parent if state_parent is not None else parent,
            wx.ID_ANY,
            style=wx.VSCROLL | wx.TAB_TRAVERSAL,
        )
        self.state_panel.SetName("Current state readout")
        self.state_panel.SetScrollRate(0, 10)
        state_layout = wx.BoxSizer(wx.VERTICAL)
        self.position_label = wx.StaticText(
            self.state_panel,
            wx.ID_ANY,
            "Position (km)\nX: unavailable\nY: unavailable\nZ: unavailable",
        )
        self.position_label.SetName("Position components (kilometers)")
        self.velocity_label = wx.StaticText(
            self.state_panel,
            wx.ID_ANY,
            "Velocity (km/s)\nVx: unavailable\nVy: unavailable\nVz: unavailable",
        )
        self.velocity_label.SetName("Velocity components (kilometers per second)")
        self.speed_altitude_label = wx.StaticText(
            self.state_panel,
            wx.ID_ANY,
            "Derived values\nSpeed: unavailable km/s\nAltitude: unavailable km",
        )
        self.speed_altitude_label.SetName("Derived speed and altitude")
        self.cursor_status_label = wx.StaticText(
            self.state_panel, wx.ID_ANY, "Cursor status: unavailable"
        )
        self.cursor_status_label.SetName("Cursor data status")
        self._state_readout_labels = (
            self.position_label,
            self.velocity_label,
            self.speed_altitude_label,
            self.cursor_status_label,
        )
        for label in self._state_readout_labels:
            state_layout.Add(
                label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, LAYOUT_MARGIN
            )
        self.state_panel.SetSizer(state_layout)
        self.state_panel.Bind(wx.EVT_SIZE, self._on_state_panel_size)
        self._fit_state_content()

        self.elapsed_label = wx.StaticText(self.panel, wx.ID_ANY, "")
        self.utc_label = wx.StaticText(self.panel, wx.ID_ANY, "")
        for label in (self.elapsed_label, self.utc_label):
            layout.Add(
                label,
                0,
                wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
                LAYOUT_MARGIN,
            )

        playback_group = wx.BoxSizer(wx.VERTICAL)
        self.playback_label = wx.StaticText(self.panel, wx.ID_ANY, "Playback")
        playback_group.Add(
            self.playback_label,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        self.play_pause_button = wx.Button(self.panel, wx.ID_ANY, "Play")
        self.play_pause_button.Bind(wx.EVT_BUTTON, lambda _event: on_toggle_play())
        playback_group.Add(
            self.play_pause_button, 0, wx.EXPAND | wx.BOTTOM, CONTROL_SPACING
        )

        self.direction_button = wx.ToggleButton(self.panel, wx.ID_ANY, "Reverse")
        self.direction_button.Bind(wx.EVT_TOGGLEBUTTON, lambda _event: on_reverse())
        playback_group.Add(
            self.direction_button, 0, wx.EXPAND | wx.BOTTOM, CONTROL_SPACING
        )
        self.speed_label = wx.StaticText(self.panel, wx.ID_ANY, "Speed: +1x")
        playback_group.Add(
            self.speed_label,
            0,
            wx.EXPAND | wx.BOTTOM,
            BUTTON_SPACING,
        )

        self._speed_scale_label_text = (
            f"Speed slider: +{SPEED_MIN:g}x "
            f"(log scale, {SPEED_MIN:g}x to {SPEED_MAX:g}x)"
        )
        self.speed_scale_label = wx.StaticText(
            self.panel, wx.ID_ANY, self._speed_scale_label_text
        )
        playback_group.Add(
            self.speed_scale_label,
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        self.speed_slider = wx.Slider(
            self.panel,
            wx.ID_ANY,
            0,
            0,
            SPEED_SLIDER_MAX,
            style=wx.SL_HORIZONTAL,
        )
        self.speed_slider.SetName("Playback speed")
        self.speed_slider.SetToolTip(
            "Log scale: 100 slider steps per decade; buttons add 10x, 100x, or 1000x."
        )
        self.speed_slider.Bind(wx.EVT_SLIDER, self._on_speed_slider)
        playback_group.Add(
            self.speed_slider,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            LAYOUT_MARGIN,
        )
        layout.Add(playback_group, 0, wx.EXPAND | wx.ALL, LAYOUT_MARGIN)

        seek_group = wx.BoxSizer(wx.VERTICAL)
        self.seek_label = wx.StaticText(
            self.panel, wx.ID_ANY, "Seek to elapsed time or UTC:"
        )
        seek_group.Add(
            self.seek_label,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        entry_row = wx.BoxSizer(wx.VERTICAL)
        self.time_entry = wx.TextCtrl(
            self.panel,
            wx.ID_ANY,
            "",
            style=wx.TE_PROCESS_ENTER,
        )
        self.time_entry.SetName("Seek time")
        self.time_entry.SetHint("e.g. 1h30m or YYYY-MM-DDThh:mm:ssZ (UTC)")
        self.time_entry.Bind(wx.EVT_TEXT_ENTER, self._submit_time_entry)
        self.time_entry.Bind(wx.EVT_SET_FOCUS, self._disable_accelerators)
        self.time_entry.Bind(wx.EVT_KILL_FOCUS, self._enable_accelerators)
        entry_row.Add(self.time_entry, 0, wx.EXPAND | wx.BOTTOM, BUTTON_SPACING)
        self.seek_button = wx.Button(self.panel, wx.ID_ANY, "Seek")
        self.seek_button.Bind(wx.EVT_BUTTON, self._submit_time_entry)
        entry_row.Add(self.seek_button, 0, wx.EXPAND)
        seek_group.Add(
            entry_row,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            LAYOUT_MARGIN,
        )
        self.time_error_label = wx.StaticText(self.panel, wx.ID_ANY, "")
        self.time_error_label.SetForegroundColour(wx.Colour(*TIME_ERROR_COLOR_RGB))
        seek_group.Add(
            self.time_error_label,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            LAYOUT_MARGIN,
        )
        layout.Add(seek_group, 0, wx.EXPAND | wx.ALL, LAYOUT_MARGIN)

        navigation_group = wx.BoxSizer(wx.VERTICAL)
        navigation_row = wx.BoxSizer(wx.VERTICAL)
        navigation_actions: tuple[tuple[str, Callable[[], None]], ...] = (
            ("Start", on_jump_to_start),
            ("Previous sample", lambda: on_step_samples(-1)),
            ("-1 min", lambda: on_step_seconds(-SECONDS_PER_MINUTE)),
            ("+1 min", lambda: on_step_seconds(SECONDS_PER_MINUTE)),
            ("Next sample", lambda: on_step_samples(1)),
            ("End", on_jump_to_end),
        )
        self.navigation_buttons: list[wx.Button] = []
        for label, callback in navigation_actions:
            button = wx.Button(self.panel, wx.ID_ANY, label)
            button.Bind(wx.EVT_BUTTON, lambda _event, action=callback: action())
            navigation_row.Add(button, 0, wx.EXPAND | wx.BOTTOM, BUTTON_SPACING)
            self.navigation_buttons.append(button)
        self.navigation_label = wx.StaticText(self.panel, wx.ID_ANY, "Time navigation")
        navigation_group.Add(
            self.navigation_label,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        navigation_group.Add(navigation_row, 0, wx.EXPAND | wx.ALL, LAYOUT_MARGIN)
        layout.Add(navigation_group, 0, wx.EXPAND | wx.ALL, LAYOUT_MARGIN)

        focusable_controls = (
            self.play_pause_button,
            self.direction_button,
            self.seek_button,
            *self.navigation_buttons,
            self.speed_slider,
        )
        for control in focusable_controls:
            control.Bind(
                wx.EVT_SET_FOCUS,
                lambda event, focused=control: self._scroll_control_into_view(
                    focused, event
                ),
            )

        self.panel.SetSizer(layout)
        self.panel.FitInside()
        self.panel.Bind(wx.EVT_SIZE, self._on_panel_size)
        self._bind_accelerators(
            self._accelerator_parent,
            on_toggle_play,
            on_reverse,
            on_step_samples,
            on_step_seconds,
            on_jump_to_start,
            on_jump_to_end,
        )

    def _on_panel_size(self, event: wx.SizeEvent) -> None:
        """Recalculate wrapped controls and the scrollable content after resizing."""
        self._fit_playback_content()
        event.Skip()

    def _fit_playback_content(self) -> None:
        for _ in range(2):
            self.panel.FitInside()
            self._wrap_text_labels()
            self.panel.Layout()
        self.panel.FitInside()

    def _wrap_text_labels(self) -> None:
        content_width = self.panel.GetClientSize().width - 2 * LAYOUT_MARGIN
        if content_width <= 0:
            return
        for label in (
            self.elapsed_label,
            self.utc_label,
            self.playback_label,
            self.seek_label,
            self.speed_scale_label,
            self.navigation_label,
        ):
            label.Wrap(content_width)

    def _scroll_control_into_view(
        self, control: wx.Window, event: wx.FocusEvent
    ) -> None:
        _, view_start_y = self.panel.GetViewStart()
        _, scroll_unit_y = self.panel.GetScrollPixelsPerUnit()
        if scroll_unit_y > 0:
            viewport_height = self.panel.GetClientSize().height
            control_top = control.GetPosition().y
            control_bottom = control_top + control.GetSize().height
            if control_top < 0:
                scroll_top = view_start_y * scroll_unit_y + control_top
                self.panel.Scroll(0, max(0, scroll_top // scroll_unit_y))
            elif control_bottom > viewport_height:
                scroll_top = control_bottom - viewport_height
                self.panel.Scroll(
                    0, view_start_y + (scroll_top + scroll_unit_y - 1) // scroll_unit_y
                )
        event.Skip()

    def update_playback_state(self, text: str, playing: bool, rate: float) -> None:
        """Update dashboard controls from the current playback state.

        Parameters
        ----------
        text : str
            Formatted elapsed-time and UTC readout.
        playing : bool
            Whether playback is active.
        rate : float
            Signed playback speed multiplier.
        """
        self.update_time(text)
        self.play_pause_button.SetLabel("Pause" if playing else "Play")
        self.speed_label.SetLabel(f"Speed: {rate:+g}x")
        speed_scale_text = (
            f"Speed slider: {rate:+g}x "
            f"(log scale, {SPEED_MIN:g}x to {SPEED_MAX:g}x)"
        )
        if speed_scale_text != self._speed_scale_label_text:
            self._speed_scale_label_text = speed_scale_text
            self.speed_scale_label.SetLabel(speed_scale_text)
            self._fit_playback_content()
        self.direction_button.SetLabel("Reverse" if rate > 0.0 else "Forward")
        self.direction_button.SetValue(rate < 0.0)

        playback_speed = min(max(abs(rate), SPEED_MIN), SPEED_MAX)
        speed_value = round(math.log10(playback_speed) * SPEED_SLIDER_STEPS_PER_DECADE)
        self._syncing_sliders = True
        try:
            self.speed_slider.SetValue(speed_value)
        finally:
            self._syncing_sliders = False

    def update_time(self, text: str) -> None:
        """Update the elapsed-time and UTC readouts.

        Parameters
        ----------
        text : str
            Readout text, with elapsed time and UTC separated by a newline.
        """
        elapsed_text, separator, utc_text = text.partition("\n")
        self.elapsed_label.SetLabel(elapsed_text)
        timestamp_separator = utc_text.rfind("T")
        if timestamp_separator > utc_text.find(":"):
            utc_text = (
                f"{utc_text[:timestamp_separator + 1]}\n"
                f"{utc_text[timestamp_separator + 1:]}"
            )
        self.utc_label.SetLabel(utc_text if separator else "")
        self._wrap_text_labels()

    def update_current_state(self, state: CursorState) -> None:
        """Display the state at the current playback time, including unavailable data."""
        self.position_label.SetLabel(
            self._format_components("Position (km)", ("X", "Y", "Z"), state.r_km, 3)
        )
        self.velocity_label.SetLabel(
            self._format_components(
                "Velocity (km/s)", ("Vx", "Vy", "Vz"), state.v_kms, 6
            )
        )
        speed = "unavailable" if state.speed is None else f"{state.speed:.6f} km/s"
        altitude = (
            "unavailable" if state.altitude is None else f"{state.altitude:.3f} km"
        )
        self.speed_altitude_label.SetLabel(
            f"Derived values\nSpeed:\n{speed}\nAltitude:\n{altitude}"
        )
        status = {
            CursorStatus.EXACT_SAMPLE: "sampled",
            CursorStatus.INTERPOLATED: "interpolated",
            CursorStatus.OUT_OF_RANGE: "out of range",
            CursorStatus.UNAVAILABLE: "unavailable",
            CursorStatus.GAP: "data gap; no state available",
        }[state.status]
        self.cursor_status_label.SetLabel(f"Cursor status: {status}")
        self._fit_state_content()

    @staticmethod
    def _format_components(
        title: str,
        component_names: tuple[str, str, str],
        values: Iterable[float] | None,
        precision: int,
    ) -> str:
        if values is None:
            component_values = ("unavailable",) * len(component_names)
        else:
            component_values = tuple(f"{value:.{precision}f}" for value in values)
        rows = "\n".join(
            f"{component}: {value}"
            for component, value in zip(component_names, component_values)
        )
        return f"{title}\n{rows}"

    def _on_state_panel_size(self, event: wx.SizeEvent) -> None:
        self._fit_state_content()
        event.Skip()

    def _fit_state_content(self) -> None:
        for _ in range(2):
            self.state_panel.FitInside()
            content_width = self.state_panel.GetClientSize().width - 2 * LAYOUT_MARGIN
            if content_width <= 0:
                return
            for label in self._state_readout_labels:
                label.Wrap(content_width)
            self.state_panel.Layout()
        self.state_panel.FitInside()

    def show_time_error(self, message: str) -> None:
        """Display a time-entry validation error.

        Parameters
        ----------
        message : str
            Error text to show below the time-entry control.
        """
        self.time_error_label.SetLabel(message)

    def clear_time_error(self) -> None:
        """Clear a previously displayed time-entry error."""
        self.time_error_label.SetLabel("")

    def _on_speed_slider(self, event: wx.CommandEvent) -> None:
        if self._syncing_sliders:
            return
        self._on_set_speed(10.0 ** (event.GetInt() / SPEED_SLIDER_STEPS_PER_DECADE))

    def _submit_time_entry(self, _event: wx.CommandEvent | None = None) -> None:
        self._on_seek_to_time(self.time_entry.GetValue())

    def _bind_accelerators(
        self,
        parent: wx.Frame,
        on_toggle_play: Callable[[], None],
        on_reverse: Callable[[], None],
        on_step_samples: Callable[[int], None],
        on_step_seconds: Callable[[float], None],
        on_jump_to_start: Callable[[], None],
        on_jump_to_end: Callable[[], None],
    ) -> None:
        actions: tuple[tuple[int, int, Callable[[], None]], ...] = (
            (wx.ACCEL_NORMAL, wx.WXK_SPACE, on_toggle_play),
            (wx.ACCEL_NORMAL, ord("R"), on_reverse),
            (wx.ACCEL_NORMAL, wx.WXK_LEFT, lambda: on_step_samples(-1)),
            (wx.ACCEL_NORMAL, wx.WXK_RIGHT, lambda: on_step_samples(1)),
            (
                wx.ACCEL_SHIFT,
                wx.WXK_LEFT,
                lambda: on_step_seconds(-SECONDS_PER_MINUTE),
            ),
            (
                wx.ACCEL_SHIFT,
                wx.WXK_RIGHT,
                lambda: on_step_seconds(SECONDS_PER_MINUTE),
            ),
            (wx.ACCEL_NORMAL, wx.WXK_HOME, on_jump_to_start),
            (wx.ACCEL_NORMAL, wx.WXK_END, on_jump_to_end),
        )
        entries: list[wx.AcceleratorEntry] = []
        for flags, key_code, action in actions:
            command_id = int(wx.NewIdRef())
            entries.append(wx.AcceleratorEntry(flags, key_code, command_id))
            parent.Bind(
                wx.EVT_MENU,
                lambda _event, callback=action: callback(),
                id=command_id,
            )
        self._accelerator_table = wx.AcceleratorTable(entries)
        self._empty_accelerator_table = wx.AcceleratorTable()
        parent.SetAcceleratorTable(self._accelerator_table)

    def _disable_accelerators(self, event: wx.FocusEvent) -> None:
        self._scroll_control_into_view(self.time_entry, event)
        self._accelerator_parent.SetAcceleratorTable(self._empty_accelerator_table)

    def _enable_accelerators(self, event: wx.FocusEvent) -> None:
        self._accelerator_parent.SetAcceleratorTable(self._accelerator_table)
        event.Skip()
