"""Native wxPython settings and state panels."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import wx

from ephem_toolkit.core.interpolator.interpolation_spec import (
    DEFAULT_HERMITE_DEGREE,
    InterpolationType,
)

from .cursor import CursorState, CursorStatus
from .tooltips import set_tooltip

LAYOUT_MARGIN: int = 12
"""Spacing around playback and state controls (pixels)."""

SECONDS_PER_MINUTE: float = 60.0
"""Number of seconds in one minute."""

RENDER_RATE_FPS_MIN: int = 1
"""Minimum selectable playback frame rate (frames per second)."""

RENDER_RATE_FPS_MAX: int = 30
"""Maximum selectable playback frame rate (frames per second)."""

DEFAULT_RENDER_RATE_FPS: int = 30
"""Initial frame rate when constructing playback controls without an override."""

INTERPOLATION_MODE_CHOICES = (
    "Follow OEM metadata",
    "Use settings below",
)
FOLLOW_OEM_METADATA_SELECTION = 0
USE_CONFIGURED_INTERPOLATION_SELECTION = 1
INTERPOLATION_METHODS = tuple(item.value for item in InterpolationType)


class ControlWindow:
    """Build interpolation/render-rate settings and current-state panels."""

    def __init__(
        self,
        parent: wx.Window,
        on_toggle_play: Callable[[], None],
        on_reverse: Callable[[], None],
        *,
        on_set_render_rate_fps: Callable[[int], None] | None = None,
        render_rate_fps: int = DEFAULT_RENDER_RATE_FPS,
        on_set_interpolation: Callable[[bool, str, int], None] | None = None,
        use_oem_interpolation: bool = False,
        interpolation_method: str = InterpolationType.HERMITE.value,
        interpolation_degree: int = DEFAULT_HERMITE_DEGREE,
        active_interpolation: str = "No OEM loaded",
        on_step_samples: Callable[[int], None],
        on_step_seconds: Callable[[float], None],
        on_jump_to_start: Callable[[], None],
        on_jump_to_end: Callable[[], None],
        accelerator_parent: wx.Frame,
        state_parent: wx.Window | None = None,
    ) -> None:
        """Create the Settings and State panels and bind playback accelerators.

        Parameters
        ----------
        parent : wx.Window
            Parent of the Settings page panel.
        on_toggle_play : Callable[[], None]
            Toggle playback.
        on_reverse : Callable[[], None]
            Reverse the playback direction.
        on_set_render_rate_fps : Callable[[int], None] | None
            Set the render rate in frames per second.
        render_rate_fps : int
            Initial render rate in frames per second.
        on_set_interpolation : Callable[[bool, str, int], None] | None
            Update OEM metadata preference and configured interpolation.
        use_oem_interpolation : bool
            Whether to follow the current OEM file's interpolation metadata.
        interpolation_method : str
            Configured interpolation method.
        interpolation_degree : int
            Configured interpolation degree.
        active_interpolation : str
            Human-readable description of the currently active interpolation.
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
        self._on_set_render_rate_fps = on_set_render_rate_fps
        self._on_set_interpolation = on_set_interpolation
        self._use_oem_interpolation = use_oem_interpolation
        self._interpolation_method = interpolation_method
        self._interpolation_degree = interpolation_degree

        self.settings_scroller = wx.ScrolledWindow(
            parent, wx.ID_ANY, style=wx.VSCROLL | wx.TAB_TRAVERSAL
        )
        self.settings_scroller.SetName("Settings render rate")
        self.settings_scroller.SetScrollRate(0, 10)
        settings_sizer = wx.BoxSizer(wx.VERTICAL)

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

        self.render_rate_label = wx.StaticText(
            self.settings_scroller,
            wx.ID_ANY,
            f"Render rate: {render_rate_fps} FPS",
        )
        settings_sizer.Add(
            self.render_rate_label,
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        self.render_rate_slider = wx.Slider(
            self.settings_scroller,
            wx.ID_ANY,
            render_rate_fps,
            RENDER_RATE_FPS_MIN,
            RENDER_RATE_FPS_MAX,
            style=wx.SL_HORIZONTAL,
        )
        self.render_rate_slider.SetName("Render rate (frames per second)")
        set_tooltip(
            self.render_rate_slider,
            f"Set the render rate from {RENDER_RATE_FPS_MIN} to "
            f"{RENDER_RATE_FPS_MAX} frames per second.",
        )
        self.render_rate_slider.Bind(wx.EVT_SLIDER, self._on_render_rate_slider)
        settings_sizer.Add(
            self.render_rate_slider,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            LAYOUT_MARGIN,
        )

        self.interpolation_section_label = wx.StaticText(
            self.settings_scroller, wx.ID_ANY, "Interpolation"
        )
        settings_sizer.Add(
            self.interpolation_section_label,
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        self.interpolation_mode_choice = wx.Choice(
            self.settings_scroller,
            wx.ID_ANY,
            choices=list(INTERPOLATION_MODE_CHOICES),
        )
        self.interpolation_mode_choice.SetName("Interpolation source")
        self.interpolation_mode_choice.SetSelection(
            FOLLOW_OEM_METADATA_SELECTION
            if use_oem_interpolation
            else USE_CONFIGURED_INTERPOLATION_SELECTION
        )
        set_tooltip(
            self.interpolation_mode_choice,
            "Follow interpolation metadata in the OEM file or use the configured "
            "method and degree below.",
        )
        self.interpolation_mode_choice.Bind(
            wx.EVT_CHOICE, self._on_interpolation_mode_choice
        )
        settings_sizer.Add(
            self.interpolation_mode_choice,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )

        self.interpolation_method_choice = wx.Choice(
            self.settings_scroller,
            wx.ID_ANY,
            choices=list(INTERPOLATION_METHODS),
        )
        self.interpolation_method_choice.SetName("Interpolation method")
        self.interpolation_method_choice.SetSelection(
            INTERPOLATION_METHODS.index(interpolation_method)
        )
        self.interpolation_method_choice.Bind(
            wx.EVT_CHOICE, self._on_interpolation_method_choice
        )
        settings_sizer.Add(
            self.interpolation_method_choice,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )

        self.interpolation_degree_label = wx.StaticText(
            self.settings_scroller, wx.ID_ANY, "Interpolation degree"
        )
        settings_sizer.Add(
            self.interpolation_degree_label,
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        self.interpolation_degree_text = wx.TextCtrl(
            self.settings_scroller,
            wx.ID_ANY,
            str(interpolation_degree),
            style=wx.TE_PROCESS_ENTER,
        )
        self.interpolation_degree_text.SetName("Interpolation degree")
        set_tooltip(
            self.interpolation_degree_text,
            "Enter a non-negative integer degree and press Enter.",
        )
        self.interpolation_degree_text.Bind(
            wx.EVT_TEXT_ENTER, self._on_interpolation_degree_enter
        )
        self.interpolation_degree_text.Bind(
            wx.EVT_KILL_FOCUS, self._on_interpolation_degree_focus_lost
        )
        settings_sizer.Add(
            self.interpolation_degree_text,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        self.interpolation_error_label = wx.StaticText(
            self.settings_scroller, wx.ID_ANY, ""
        )
        self.interpolation_error_label.SetName("Interpolation setting error")
        settings_sizer.Add(
            self.interpolation_error_label,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        self.active_interpolation_label = wx.StaticText(
            self.settings_scroller,
            wx.ID_ANY,
            f"Active interpolation:\n{active_interpolation}",
        )
        self.active_interpolation_label.SetName("Active interpolation")
        settings_sizer.Add(
            self.active_interpolation_label,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
            LAYOUT_MARGIN,
        )
        self._set_interpolation_controls_enabled(not use_oem_interpolation)

        self.settings_scroller.SetSizer(settings_sizer)
        self.settings_scroller.FitInside()
        self._bind_accelerators(
            self._accelerator_parent,
            on_toggle_play,
            on_reverse,
            on_step_samples,
            on_step_seconds,
            on_jump_to_start,
            on_jump_to_end,
        )

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

    def update_active_interpolation(self, summary: str) -> None:
        """Display the effective interpolation strategy and its source."""
        self.active_interpolation_label.SetLabel(f"Active interpolation:\n{summary}")
        self.settings_scroller.FitInside()

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

    def _on_render_rate_slider(self, event: wx.CommandEvent) -> None:
        """Forward the selected render rate."""
        render_rate_fps = event.GetInt()
        self.render_rate_label.SetLabel(f"Render rate: {render_rate_fps} FPS")
        if self._on_set_render_rate_fps is not None:
            self._on_set_render_rate_fps(render_rate_fps)

    def _on_interpolation_mode_choice(self, event: wx.CommandEvent) -> None:
        use_oem_metadata = (
            self.interpolation_mode_choice.GetSelection()
            == FOLLOW_OEM_METADATA_SELECTION
        )
        self._set_interpolation_controls_enabled(not use_oem_metadata)
        if self._on_interpolation_settings_changed(use_oem_metadata):
            self._use_oem_interpolation = use_oem_metadata
        else:
            self.interpolation_mode_choice.SetSelection(
                FOLLOW_OEM_METADATA_SELECTION
                if self._use_oem_interpolation
                else USE_CONFIGURED_INTERPOLATION_SELECTION
            )
            self._set_interpolation_controls_enabled(not self._use_oem_interpolation)
        event.Skip()

    def _on_interpolation_method_choice(self, event: wx.CommandEvent) -> None:
        previous_method = self._interpolation_method
        selected_method = INTERPOLATION_METHODS[
            self.interpolation_method_choice.GetSelection()
        ]
        self._interpolation_method = selected_method
        if not self._on_interpolation_settings_changed(
            self._interpolation_uses_oem_metadata()
        ):
            self._interpolation_method = previous_method
            self.interpolation_method_choice.SetSelection(
                INTERPOLATION_METHODS.index(previous_method)
            )
        event.Skip()

    def _on_interpolation_degree_enter(self, event: wx.CommandEvent) -> None:
        self._commit_interpolation_degree()
        event.Skip()

    def _on_interpolation_degree_focus_lost(self, event: wx.FocusEvent) -> None:
        self._commit_interpolation_degree()
        event.Skip()

    def _commit_interpolation_degree(self) -> None:
        value = self.interpolation_degree_text.GetValue().strip()
        try:
            degree = int(value)
        except ValueError:
            self._show_interpolation_error(
                "Interpolation degree must be a non-negative integer."
            )
            return
        if degree < 0:
            self._show_interpolation_error(
                "Interpolation degree must be a non-negative integer."
            )
            return

        previous_degree = self._interpolation_degree
        self._interpolation_degree = degree
        self._show_interpolation_error("")
        if not self._on_interpolation_settings_changed(
            self._interpolation_uses_oem_metadata()
        ):
            self._interpolation_degree = previous_degree
            self.interpolation_degree_text.SetValue(str(previous_degree))

    def _on_interpolation_settings_changed(self, use_oem_metadata: bool) -> bool:
        try:
            if self._on_set_interpolation is not None:
                self._on_set_interpolation(
                    use_oem_metadata,
                    self._interpolation_method,
                    self._interpolation_degree,
                )
        except ValueError as error:
            self._show_interpolation_error(str(error))
            return False
        return True

    def _interpolation_uses_oem_metadata(self) -> bool:
        return (
            self.interpolation_mode_choice.GetSelection()
            == FOLLOW_OEM_METADATA_SELECTION
        )

    def _set_interpolation_controls_enabled(self, enabled: bool) -> None:
        self.interpolation_method_choice.Enable(enabled)
        self.interpolation_degree_text.Enable(enabled)

    def _show_interpolation_error(self, message: str) -> None:
        self.interpolation_error_label.SetLabel(message)

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
