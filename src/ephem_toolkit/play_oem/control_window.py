"""Native wxPython playback controls."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import math

import wx

from .cursor import CursorState, CursorStatus
from .timestamp_markup import set_small_fraction_label, set_timestamp_label
from .tooltips import set_tooltip

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

FPS_MIN: int = 1
"""Minimum selectable playback frame rate (frames per second)."""

FPS_MAX: int = 60
"""Maximum selectable playback frame rate (frames per second)."""

DEFAULT_FPS: int = 30
"""Initial frame rate when constructing playback controls without an override."""


class ControlWindow:
    """Build and update the wx-native playback dashboard."""

    def __init__(
        self,
        parent: wx.Window,
        on_toggle_play: Callable[[], None],
        on_set_speed: Callable[[float], None],
        on_reverse: Callable[[], None],
        *,
        on_set_fps: Callable[[int], None] | None = None,
        fps: int = DEFAULT_FPS,
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
        on_set_fps : Callable[[int], None] | None
            Set the render rate in frames per second.
        fps : int
            Initial render rate in frames per second.
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
        self._on_set_fps = on_set_fps
        self._syncing_sliders = False

        self.playback_scroller = wx.ScrolledWindow(
            parent, wx.ID_ANY, style=wx.VSCROLL | wx.TAB_TRAVERSAL
        )
        self.playback_scroller.SetScrollRate(0, 10)
        controls_sizer = wx.BoxSizer(wx.VERTICAL)

        self.state_scroller = wx.ScrolledWindow(
            state_parent if state_parent is not None else parent,
            wx.ID_ANY,
            style=wx.VSCROLL | wx.TAB_TRAVERSAL,
        )
        self.state_scroller.SetName("Current state readout")
        self.state_scroller.SetScrollRate(0, 10)
        state_sizer = wx.BoxSizer(wx.VERTICAL)
        self.state_position_label = wx.StaticText(
            self.state_scroller,
            wx.ID_ANY,
            "Position (km)\nX: unavailable\nY: unavailable\nZ: unavailable",
        )
        self.state_position_label.SetName("Position components (kilometers)")
        self.state_velocity_label = wx.StaticText(
            self.state_scroller,
            wx.ID_ANY,
            "Velocity (km/s)\nVx: unavailable\nVy: unavailable\nVz: unavailable",
        )
        self.state_velocity_label.SetName("Velocity components (kilometers per second)")
        self.state_derived_label = wx.StaticText(
            self.state_scroller,
            wx.ID_ANY,
            "Derived values\nSpeed: unavailable km/s\nAltitude: unavailable km",
        )
        self.state_derived_label.SetName("Derived speed and altitude")
        self.state_cursor_status_label = wx.StaticText(
            self.state_scroller, wx.ID_ANY, "Cursor status: unavailable"
        )
        self.state_cursor_status_label.SetName("Cursor data status")
        self._state_readout_labels = (
            self.state_position_label,
            self.state_velocity_label,
            self.state_derived_label,
            self.state_cursor_status_label,
        )
        for label in self._state_readout_labels:
            state_sizer.Add(
                label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, LAYOUT_MARGIN
            )
        self.state_scroller.SetSizer(state_sizer)
        self.state_scroller.Bind(wx.EVT_SIZE, self._on_state_panel_size)
        self._fit_state_content()

        self.elapsed_time_label = wx.StaticText(self.playback_scroller, wx.ID_ANY, "")
        self.utc_time_label = wx.StaticText(self.playback_scroller, wx.ID_ANY, "")
        for label in (self.elapsed_time_label, self.utc_time_label):
            controls_sizer.Add(
                label,
                0,
                wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
                LAYOUT_MARGIN,
            )

        playback_group = wx.BoxSizer(wx.VERTICAL)
        self.playback_heading_label = wx.StaticText(
            self.playback_scroller, wx.ID_ANY, "Playback"
        )
        playback_group.Add(
            self.playback_heading_label,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        self.play_pause_button = wx.Button(self.playback_scroller, wx.ID_ANY, "Play")
        self.play_pause_button.Bind(wx.EVT_BUTTON, lambda _event: on_toggle_play())
        playback_group.Add(
            self.play_pause_button, 0, wx.EXPAND | wx.BOTTOM, CONTROL_SPACING
        )

        self.reverse_toggle_button = wx.ToggleButton(
            self.playback_scroller, wx.ID_ANY, "Reverse"
        )
        self.reverse_toggle_button.Bind(
            wx.EVT_TOGGLEBUTTON, lambda _event: on_reverse()
        )
        playback_group.Add(
            self.reverse_toggle_button, 0, wx.EXPAND | wx.BOTTOM, CONTROL_SPACING
        )
        self.speed_readout_label = wx.StaticText(
            self.playback_scroller, wx.ID_ANY, "Speed: +1x"
        )
        playback_group.Add(
            self.speed_readout_label,
            0,
            wx.EXPAND | wx.BOTTOM,
            BUTTON_SPACING,
        )

        self._speed_scale_label_text = (
            f"Speed slider: +{SPEED_MIN:g}x "
            f"(log scale, {SPEED_MIN:g}x to {SPEED_MAX:g}x)"
        )
        self.speed_scale_label = wx.StaticText(
            self.playback_scroller, wx.ID_ANY, self._speed_scale_label_text
        )
        playback_group.Add(
            self.speed_scale_label,
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        self.speed_slider = wx.Slider(
            self.playback_scroller,
            wx.ID_ANY,
            0,
            0,
            SPEED_SLIDER_MAX,
            style=wx.SL_HORIZONTAL,
        )
        self.speed_slider.SetName("Playback speed")
        set_tooltip(
            self.speed_slider,
            "Log scale: 100 slider steps per decade; buttons add 10x, 100x, or 1000x.",
        )
        self.speed_slider.Bind(wx.EVT_SLIDER, self._on_speed_slider)
        playback_group.Add(
            self.speed_slider,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            LAYOUT_MARGIN,
        )
        # Show the requested frame rate beside its slider, independently of speed.
        self.fps_label = wx.StaticText(
            self.playback_scroller, wx.ID_ANY, f"Render rate: {fps} FPS"
        )
        playback_group.Add(
            self.fps_label,
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        self.fps_slider = wx.Slider(
            self.playback_scroller,
            wx.ID_ANY,
            fps,
            FPS_MIN,
            FPS_MAX,
            style=wx.SL_HORIZONTAL,
        )
        self.fps_slider.SetName("Playback frames per second")
        set_tooltip(self.fps_slider, "Set the playback update rate from 1 to 60 FPS.")
        self.fps_slider.Bind(wx.EVT_SLIDER, self._on_fps_slider)
        playback_group.Add(
            self.fps_slider,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            LAYOUT_MARGIN,
        )
        controls_sizer.Add(playback_group, 0, wx.EXPAND | wx.ALL, LAYOUT_MARGIN)

        navigation_group = wx.BoxSizer(wx.VERTICAL)
        navigation_sizer = wx.BoxSizer(wx.VERTICAL)
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
            navigation_button = wx.Button(self.playback_scroller, wx.ID_ANY, label)
            navigation_button.Bind(
                wx.EVT_BUTTON, lambda _event, action=callback: action()
            )
            navigation_sizer.Add(
                navigation_button, 0, wx.EXPAND | wx.BOTTOM, BUTTON_SPACING
            )
            self.navigation_buttons.append(navigation_button)
        self.navigation_heading_label = wx.StaticText(
            self.playback_scroller, wx.ID_ANY, "Time navigation"
        )
        navigation_group.Add(
            self.navigation_heading_label,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        navigation_group.Add(navigation_sizer, 0, wx.EXPAND | wx.ALL, LAYOUT_MARGIN)
        controls_sizer.Add(navigation_group, 0, wx.EXPAND | wx.ALL, LAYOUT_MARGIN)

        focusable_controls = (
            self.play_pause_button,
            self.reverse_toggle_button,
            *self.navigation_buttons,
            self.speed_slider,
            self.fps_slider,
        )
        for control in focusable_controls:
            control.Bind(
                wx.EVT_SET_FOCUS,
                lambda event, focused=control: self._scroll_control_into_view(
                    focused, event
                ),
            )

        self.playback_scroller.SetSizer(controls_sizer)
        self.playback_scroller.FitInside()
        self.playback_scroller.Bind(wx.EVT_SIZE, self._on_panel_size)
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
            self.playback_scroller.FitInside()
            self._wrap_text_labels()
            self.playback_scroller.Layout()
        self.playback_scroller.FitInside()

    def _wrap_text_labels(self) -> None:
        content_width = self.playback_scroller.GetClientSize().width - 2 * LAYOUT_MARGIN
        if content_width <= 0:
            return
        for label in (
            self.elapsed_time_label,
            self.utc_time_label,
            self.playback_heading_label,
            self.speed_scale_label,
            self.fps_label,
            self.navigation_heading_label,
        ):
            label.Wrap(content_width)

    def _scroll_control_into_view(
        self, control: wx.Window, event: wx.FocusEvent
    ) -> None:
        _, view_start_y = self.playback_scroller.GetViewStart()
        _, scroll_unit_y = self.playback_scroller.GetScrollPixelsPerUnit()
        if scroll_unit_y > 0:
            viewport_height = self.playback_scroller.GetClientSize().height
            control_top = control.GetPosition().y
            control_bottom = control_top + control.GetSize().height
            if control_top < 0:
                scroll_top = view_start_y * scroll_unit_y + control_top
                self.playback_scroller.Scroll(0, max(0, scroll_top // scroll_unit_y))
            elif control_bottom > viewport_height:
                scroll_top = control_bottom - viewport_height
                self.playback_scroller.Scroll(
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
        self.speed_readout_label.SetLabel(f"Speed: {rate:+g}x")
        speed_scale_text = (
            f"Speed slider: {rate:+g}x "
            f"(log scale, {SPEED_MIN:g}x to {SPEED_MAX:g}x)"
        )
        if speed_scale_text != self._speed_scale_label_text:
            self._speed_scale_label_text = speed_scale_text
            self.speed_scale_label.SetLabel(speed_scale_text)
            self._fit_playback_content()
        self.reverse_toggle_button.SetLabel("Reverse" if rate > 0.0 else "Forward")
        self.reverse_toggle_button.SetValue(rate < 0.0)

        playback_speed = min(max(abs(rate), SPEED_MIN), SPEED_MAX)
        speed_value = round(math.log10(playback_speed) * SPEED_SLIDER_STEPS_PER_DECADE)
        self._syncing_sliders = True
        try:
            self.speed_slider.SetValue(speed_value)
        finally:
            self._syncing_sliders = False

    def set_playback_enabled(self, enabled: bool) -> None:
        """Disable playback controls until a file provides a timeline."""
        for control in (
            self.play_pause_button,
            self.reverse_toggle_button,
            self.speed_slider,
            *self.navigation_buttons,
        ):
            control.Enable(enabled)

    def update_time(self, text: str) -> None:
        """Update the elapsed-time and UTC readouts.

        Parameters
        ----------
        text : str
            Readout text, with elapsed time and UTC separated by a newline.
        """
        elapsed_text, separator, utc_text = text.partition("\n")
        # These read-only labels can style fractions without changing their values.
        set_small_fraction_label(self.elapsed_time_label, elapsed_text)
        timestamp_separator = utc_text.rfind("T")
        if timestamp_separator > utc_text.find(":"):
            utc_text = (
                f"{utc_text[:timestamp_separator + 1]}\n"
                f"{utc_text[timestamp_separator + 1:]}"
            )
        set_timestamp_label(self.utc_time_label, utc_text if separator else "")
        self._wrap_text_labels()

    def update_current_state(self, state: CursorState) -> None:
        """Display the state at the current playback time, including unavailable data."""
        self.state_position_label.SetLabel(
            self._format_components("Position (km)", ("X", "Y", "Z"), state.r_km, 3)
        )
        self.state_velocity_label.SetLabel(
            self._format_components(
                "Velocity (km/s)", ("Vx", "Vy", "Vz"), state.v_kms, 6
            )
        )
        speed = "unavailable" if state.speed is None else f"{state.speed:.6f} km/s"
        altitude = (
            "unavailable" if state.altitude is None else f"{state.altitude:.3f} km"
        )
        self.state_derived_label.SetLabel(
            f"Derived values\nSpeed:\n{speed}\nAltitude:\n{altitude}"
        )
        status = {
            CursorStatus.EXACT_SAMPLE: "sampled",
            CursorStatus.INTERPOLATED: "interpolated",
            CursorStatus.OUT_OF_RANGE: "out of range",
            CursorStatus.UNAVAILABLE: "unavailable",
            CursorStatus.GAP: "data gap; no state available",
        }[state.status]
        self.state_cursor_status_label.SetLabel(f"Cursor status: {status}")
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
            self.state_scroller.FitInside()
            content_width = (
                self.state_scroller.GetClientSize().width - 2 * LAYOUT_MARGIN
            )
            if content_width <= 0:
                return
            for label in self._state_readout_labels:
                label.Wrap(content_width)
            self.state_scroller.Layout()
        self.state_scroller.FitInside()

    def _on_speed_slider(self, event: wx.CommandEvent) -> None:
        if self._syncing_sliders:
            return
        self._on_set_speed(10.0 ** (event.GetInt() / SPEED_SLIDER_STEPS_PER_DECADE))

    def _on_fps_slider(self, event: wx.CommandEvent) -> None:
        """Update the playback timer rate from the FPS slider."""
        fps = event.GetInt()
        self.fps_label.SetLabel(f"Render rate: {fps} FPS")
        # PlayerApp owns the timer; the dashboard only forwards the selected rate.
        if self._on_set_fps is not None:
            self._on_set_fps(fps)

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

    def bind_time_entry(self, time_entry: wx.TextCtrl) -> None:
        """Let the shared timeline editor temporarily receive playback keys."""
        time_entry.Bind(wx.EVT_SET_FOCUS, self._disable_accelerators)
        time_entry.Bind(wx.EVT_KILL_FOCUS, self._enable_accelerators)

    def _disable_accelerators(self, event: wx.FocusEvent) -> None:
        self._accelerator_parent.SetAcceleratorTable(self._empty_accelerator_table)
        event.Skip()

    def _enable_accelerators(self, event: wx.FocusEvent) -> None:
        self._accelerator_parent.SetAcceleratorTable(self._accelerator_table)
        event.Skip()
