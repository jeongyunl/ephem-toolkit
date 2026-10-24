"""Timeline, playback controls and time-entry behavior."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

import wx

from .constants import TIMELINE_SLIDER_MAX
from ..tooltips import SuperToolTip, position_tooltip_at_pointer, set_tooltip

if TYPE_CHECKING:
    from .time_range_slider import TimeRangeSlider


class _TimelineState(Protocol):
    """Workspace-owned controls and callbacks used by the timeline mixin."""

    _add_buttons: dict[str, wx.Button]
    _focus_sink: wx.Panel
    _last_playback_state: tuple[bool, float] | None
    _on_seek: Callable[[float], None]
    _on_seek_to_time: Callable[[str], None] | None
    _syncing_timeline: bool
    _timeline_enabled: bool
    _timeline_tooltip: SuperToolTip
    _timeline_tooltip_at: Callable[[float], str]
    _playback_button_labels: dict[float, str]
    _playback_playing: bool
    _playback_rate: float
    timeline_panel: wx.ScrolledWindow
    timeline_slider: TimeRangeSlider
    timeline_time_entry: wx.TextCtrl
    time_error_label: wx.StaticText
    playback_forward_play_button: wx.Button
    playback_reverse_play_button: wx.Button
    playback_speed_buttons: dict[float, wx.ToggleButton]

    def _on_timeline_slider(self, event: wx.CommandEvent) -> None: ...

    def _on_timeline_time_focus(self, event: wx.FocusEvent) -> None: ...

    def _on_timeline_motion(self, event: wx.MouseEvent) -> None: ...

    def _submit_timeline_time(self, _event: wx.CommandEvent) -> None: ...


class TimelineMixin:
    """Implement playback and shared time navigation controls."""

    def _make_playback_button(
        self: _TimelineState,
        rate: float,
        glyph: str,
        direction: str,
        on_set_playback_rate: Callable[[float], None] | None,
        on_step_samples: Callable[[int], None] | None,
    ) -> wx.ToggleButton:
        speed_button = wx.ToggleButton(
            self.timeline_panel,
            wx.ID_ANY,
            glyph,
            style=wx.BU_EXACTFIT,
        )
        speed_button.SetMinSize(wx.Size(speed_button.GetBestSize().width + 4, -1))
        magnitude = abs(rate)
        speed_button.SetName(f"Set {direction} playback speed to {magnitude:g}x")
        if magnitude == 1.0:
            message = f"Set {direction} speed to 1x."
        else:
            message = f"Increase {direction} speed by {magnitude:g}x."
        set_tooltip(speed_button, message)
        if on_set_playback_rate is not None:

            def set_playback_rate(
                _event, selected_rate: float = rate, speed_button=speed_button
            ) -> None:
                on_set_playback_rate(selected_rate)
                if abs(selected_rate) == 1.0:
                    # Re-selecting the current rate may skip the normal state refresh.
                    speed_button.SetValue(True)

            speed_button.Bind(
                wx.EVT_TOGGLEBUTTON,
                set_playback_rate,
            )
        if abs(rate) == 1.0 and on_step_samples is not None:
            speed_button.Bind(
                wx.EVT_LEFT_DCLICK,
                lambda _event, count=-1 if rate < 0.0 else 1: on_step_samples(count),
            )
        return speed_button

    def update_playback_state(
        self: _TimelineState, playing: bool, rate: float
    ) -> None:
        """Synchronize direction play/pause controls and speed presets with the clock."""
        state = (playing, rate)
        if self._last_playback_state == state:
            return
        # Rewriting unchanged native button labels on every tick prevents GTK's
        # pending slider tooltip from appearing.
        self._last_playback_state = state
        self._playback_playing = playing
        self._playback_rate = rate
        speed = abs(rate)
        for selected_rate, button in self.playback_speed_buttons.items():
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
                label = self._playback_button_labels[selected_rate]
            button.SetLabel(label)
        reverse_active = playing and rate < 0.0
        self.playback_reverse_play_button.SetLabel("Ⅱ" if reverse_active else "◀")
        self.playback_reverse_play_button.SetName(
            "Pause reverse playback"
            if reverse_active
            else "Play reverse at current speed"
        )
        set_tooltip(
            self.playback_reverse_play_button,
            (
                "Pause reverse playback."
                if reverse_active
                else "Play reverse at current speed."
            ),
        )
        forward_active = playing and rate > 0.0
        self.playback_forward_play_button.SetLabel("Ⅱ" if forward_active else "▶")
        self.playback_forward_play_button.SetName(
            "Pause forward playback"
            if forward_active
            else "Play forward at current speed"
        )
        set_tooltip(
            self.playback_forward_play_button,
            (
                "Pause forward playback."
                if forward_active
                else "Play forward at current speed."
            ),
        )

    def update_timeline(
        self: _TimelineState,
        progress: float,
        current_utc: str,
        *,
        playing: bool = False,
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

    def set_oem_loaded(self: _TimelineState, loaded: bool) -> None:
        """Enable file-dependent workspace actions only after an OEM is loaded."""
        self.timeline_time_entry.Enable(loaded)
        for button in (
            *self.playback_speed_buttons.values(),
            self.playback_reverse_play_button,
            self.playback_forward_play_button,
        ):
            button.Enable(loaded)
        self.timeline_slider.Enable(loaded and self._timeline_enabled)
        if not self.timeline_slider.IsEnabled() and hasattr(self, "_timeline_tooltip"):
            self._timeline_tooltip.DoHideNow()
        for button in self._add_buttons.values():
            button.Enable(loaded)

    def show_time_error(self: _TimelineState, message: str) -> None:
        self.time_error_label.SetLabel(message)

    def clear_time_error(self: _TimelineState) -> None:
        self.time_error_label.SetLabel("")

    def set_current_time_entry(self: _TimelineState, current_utc: str) -> None:
        """Replace submitted text with the normalized current UTC timestamp."""
        self.timeline_time_entry.ChangeValue(current_utc)

    def _on_timeline_slider(self: _TimelineState, event: wx.CommandEvent) -> None:
        if self._syncing_timeline or not self._timeline_enabled:
            return
        self._on_seek(event.GetInt() / TIMELINE_SLIDER_MAX)

    def _submit_timeline_time(self: _TimelineState, _event: wx.CommandEvent) -> None:
        if self._on_seek_to_time is not None:
            self._on_seek_to_time(self.timeline_time_entry.GetValue())
        # Keep an inactive selection from appearing highlighted after submit.
        self.timeline_time_entry.SetInsertionPointEnd()
        # Defer focus transfer until wx finishes processing Enter; otherwise
        # the native text control can reclaim focus after this handler returns.
        wx.CallAfter(self._focus_sink.SetFocus)

    def _on_timeline_time_focus(self: _TimelineState, event: wx.FocusEvent) -> None:
        """Select the current value once when the timeline editor gains focus."""
        event.Skip()
        wx.CallAfter(self.timeline_time_entry.SelectAll)

    def _on_timeline_motion(self: _TimelineState, event: wx.MouseEvent) -> None:
        if not self._timeline_enabled or not self.timeline_slider.IsEnabled():
            self._timeline_tooltip.DoHideNow()
            event.Skip()
            return
        if not self.timeline_slider.is_pointer_over_timeline_track(
            event.GetPosition()
        ):
            self._timeline_tooltip.DoHideNow()
            event.Skip()
            return
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
