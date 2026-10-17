"""Native wxPython playback controls."""

from __future__ import annotations

from collections.abc import Callable
import math

import wx

from .views import registry

BUTTON_SPACING: int = 4
"""Spacing between adjacent playback buttons (pixels)."""
CONTROL_SPACING: int = 8
"""Spacing between controls within a dashboard row (pixels)."""
LAYOUT_MARGIN: int = 12
"""Outer spacing around dashboard controls (pixels)."""
SECONDS_PER_MINUTE: float = 60.0
"""Number of seconds in one minute."""
SPEED_MAX: float = 1000.0
"""Maximum playback speed multiplier."""
SPEED_MIN: float = 1.0
"""Minimum playback speed multiplier."""
SPEED_PRESETS: tuple[float, ...] = (1.0, 10.0, 100.0, SPEED_MAX)
"""Playback speed multipliers available as preset buttons."""
SPEED_SLIDER_MAX: int = 300
"""Maximum integer position of the logarithmic speed slider."""
SPEED_SLIDER_STEPS_PER_DECADE: int = 100
"""Number of slider positions representing one order of magnitude."""
TIMELINE_SLIDER_MAX: int = 10_000
"""Maximum integer position of the timeline slider."""
TIME_ERROR_COLOR_RGB: tuple[int, int, int] = (160, 0, 0)
"""RGB color used to display time-entry errors."""


class ControlWindow:
    """Build and update the wx-native playback dashboard."""

    def __init__(
        self,
        parent: wx.Frame,
        on_open_view: Callable[[str], None],
        on_open_group: Callable[[str], None],
        view_registry: registry.ViewRegistry,
        on_toggle_play: Callable[[], None],
        on_seek: Callable[[float], None],
        on_set_speed: Callable[[float], None],
        on_reverse: Callable[[], None],
        *,
        on_seek_to_time: Callable[[str], None],
        on_step_samples: Callable[[int], None],
        on_step_seconds: Callable[[float], None],
        on_jump_to_start: Callable[[], None],
        on_jump_to_end: Callable[[], None],
        timeline_enabled: bool,
    ) -> None:
        """Create the wx dashboard and connect its controls to playback actions.

        Parameters
        ----------
        parent : wx.Frame
            Frame that owns the dashboard and keyboard accelerators.
        on_open_view : Callable[[str], None]
            Open one registered plot view.
        on_open_group : Callable[[str], None]
            Open a registered group of plot views.
        view_registry : registry.ViewRegistry
            Registry used to label and enable available view actions.
        on_toggle_play : Callable[[], None]
            Toggle playback.
        on_seek : Callable[[float], None]
            Seek to a normalized timeline position.
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
        timeline_enabled : bool
            Whether the timeline contains a seekable interval.
        """
        self._parent = parent
        self._on_seek = on_seek
        self._on_set_speed = on_set_speed
        self._on_seek_to_time = on_seek_to_time
        self._timeline_enabled = timeline_enabled
        self._syncing_sliders = False

        self.panel = wx.Panel(parent, wx.ID_ANY)
        layout = wx.BoxSizer(wx.VERTICAL)

        self.elapsed_label = wx.StaticText(self.panel, wx.ID_ANY, "")
        self.utc_label = wx.StaticText(self.panel, wx.ID_ANY, "")
        for label in (self.elapsed_label, self.utc_label):
            layout.Add(
                label,
                0,
                wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
                LAYOUT_MARGIN,
            )

        playback_row = wx.BoxSizer(wx.HORIZONTAL)
        self.play_pause_button = wx.Button(self.panel, wx.ID_ANY, "Play")
        self.play_pause_button.Bind(wx.EVT_BUTTON, lambda _event: on_toggle_play())
        playback_row.Add(self.play_pause_button, 0, wx.RIGHT, CONTROL_SPACING)

        self.direction_button = wx.ToggleButton(self.panel, wx.ID_ANY, "Reverse")
        self.direction_button.Bind(wx.EVT_BUTTON, lambda _event: on_reverse())
        playback_row.Add(self.direction_button, 0, wx.RIGHT, CONTROL_SPACING)
        self.speed_label = wx.StaticText(self.panel, wx.ID_ANY, "Speed: +1x")
        playback_row.Add(
            self.speed_label,
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            CONTROL_SPACING,
        )

        self.speed_preset_buttons: dict[float, wx.ToggleButton] = {}
        for preset_speed in SPEED_PRESETS:
            button = wx.ToggleButton(self.panel, wx.ID_ANY, f"{preset_speed:g}x")
            button.Bind(
                wx.EVT_BUTTON,
                lambda _event, selected_speed=preset_speed: on_set_speed(
                    selected_speed
                ),
            )
            playback_row.Add(button, 0, wx.RIGHT, BUTTON_SPACING)
            self.speed_preset_buttons[preset_speed] = button
        layout.Add(playback_row, 0, wx.EXPAND | wx.ALL, LAYOUT_MARGIN)

        entry_row = wx.BoxSizer(wx.HORIZONTAL)
        entry_row.Add(
            wx.StaticText(
                self.panel,
                wx.ID_ANY,
                "Seek to elapsed time or UTC:",
            ),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            CONTROL_SPACING,
        )
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
        entry_row.Add(self.time_entry, 1, wx.EXPAND | wx.RIGHT, CONTROL_SPACING)
        self.seek_button = wx.Button(self.panel, wx.ID_ANY, "Seek")
        self.seek_button.Bind(wx.EVT_BUTTON, self._submit_time_entry)
        entry_row.Add(self.seek_button, 0)
        layout.Add(
            entry_row,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            LAYOUT_MARGIN,
        )

        self.time_error_label = wx.StaticText(self.panel, wx.ID_ANY, "")
        self.time_error_label.SetForegroundColour(wx.Colour(*TIME_ERROR_COLOR_RGB))
        layout.Add(
            self.time_error_label,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            LAYOUT_MARGIN,
        )

        navigation_row = wx.BoxSizer(wx.HORIZONTAL)
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
            navigation_row.Add(button, 0, wx.RIGHT, BUTTON_SPACING)
            self.navigation_buttons.append(button)
        layout.Add(navigation_row, 0, wx.EXPAND | wx.ALL, LAYOUT_MARGIN)

        layout.Add(
            wx.StaticText(
                self.panel,
                wx.ID_ANY,
                "Timeline",
            ),
            0,
            wx.LEFT | wx.RIGHT,
            LAYOUT_MARGIN,
        )
        self.timeline_slider = wx.Slider(
            self.panel,
            wx.ID_ANY,
            0,
            0,
            TIMELINE_SLIDER_MAX,
            style=wx.SL_HORIZONTAL,
        )
        self.timeline_slider.SetName("Playback timeline")
        self.timeline_slider.Enable(timeline_enabled)
        self.timeline_slider.Bind(wx.EVT_SLIDER, self._on_timeline_slider)
        layout.Add(
            self.timeline_slider,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            LAYOUT_MARGIN,
        )

        layout.Add(
            wx.StaticText(
                self.panel,
                wx.ID_ANY,
                f"Playback speed (log scale, {SPEED_MIN:g}x to {SPEED_MAX:g}x)",
            ),
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
        self.speed_slider.Bind(wx.EVT_SLIDER, self._on_speed_slider)
        layout.Add(
            self.speed_slider,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            LAYOUT_MARGIN,
        )

        group_row = wx.BoxSizer(wx.HORIZONTAL)
        self.group_buttons: dict[str, wx.Button] = {}
        for name, label in registry.GROUP_LABELS:
            button = wx.Button(self.panel, wx.ID_ANY, label)
            button.Enable(view_registry.can_open(name))
            button.Bind(
                wx.EVT_BUTTON,
                lambda _event, group=name: on_open_group(group),
            )
            group_row.Add(button, 0, wx.RIGHT, BUTTON_SPACING)
            self.group_buttons[name] = button
        layout.Add(group_row, 0, wx.EXPAND | wx.ALL, LAYOUT_MARGIN)

        view_row = wx.BoxSizer(wx.HORIZONTAL)
        self.view_buttons: dict[str, wx.Button] = {}
        for name in view_registry.registered_views:
            button = wx.Button(self.panel, wx.ID_ANY, view_registry.label_for(name))
            button.Bind(
                wx.EVT_BUTTON,
                lambda _event, view=name: on_open_view(view),
            )
            view_row.Add(button, 0, wx.RIGHT, BUTTON_SPACING)
            self.view_buttons[name] = button
        layout.Add(
            view_row,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            LAYOUT_MARGIN,
        )

        self.panel.SetSizer(layout)
        self._bind_accelerators(
            parent,
            on_toggle_play,
            on_reverse,
            on_step_samples,
            on_step_seconds,
            on_jump_to_start,
            on_jump_to_end,
        )

    def update_playback_state(
        self, text: str, progress: float, playing: bool, rate: float
    ) -> None:
        """Update dashboard controls from the current playback state.

        Parameters
        ----------
        text : str
            Formatted elapsed-time and UTC readout.
        progress : float
            Timeline position normalized to the range from zero to one.
        playing : bool
            Whether playback is active.
        rate : float
            Signed playback speed multiplier.
        """
        self.update_time(text)
        self.play_pause_button.SetLabel("Pause" if playing else "Play")
        self.speed_label.SetLabel(f"Speed: {rate:+g}x")
        self.direction_button.SetLabel("Reverse" if rate > 0.0 else "Forward")
        self.direction_button.SetValue(rate < 0.0)

        for preset_speed, button in self.speed_preset_buttons.items():
            button.SetValue(bool(math.isclose(abs(rate), preset_speed)))

        timeline_value = round(min(max(progress, 0.0), 1.0) * TIMELINE_SLIDER_MAX)
        playback_speed = min(max(abs(rate), SPEED_MIN), SPEED_MAX)
        speed_value = round(math.log10(playback_speed) * SPEED_SLIDER_STEPS_PER_DECADE)
        self._syncing_sliders = True
        try:
            self.timeline_slider.SetValue(timeline_value)
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
        self.utc_label.SetLabel(utc_text if separator else "")

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

    def _on_timeline_slider(self, event: wx.CommandEvent) -> None:
        if self._syncing_sliders or not self._timeline_enabled:
            return
        self._on_seek(event.GetInt() / TIMELINE_SLIDER_MAX)

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
        self._parent.SetAcceleratorTable(self._empty_accelerator_table)
        event.Skip()

    def _enable_accelerators(self, event: wx.FocusEvent) -> None:
        self._parent.SetAcceleratorTable(self._accelerator_table)
        event.Skip()
