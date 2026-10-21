"""Playback actions that connect workspace controls to the playback clock."""

from __future__ import annotations

from datetime import timedelta

import ephem_toolkit.core.time_utils as time_utils
from .state import PlayerAppState


class PlaybackActionsMixin:
    """Handle playback, seeking, stepping and timeline display actions."""

    def _toggle_playback(self: PlayerAppState) -> None:
        self.clock.toggle()
        self._update_time_display()

    def _seek_to_fraction(self: PlayerAppState, progress: float) -> None:
        span_s = self.clock.t_end - self.clock.t_start
        self.clock.seek(self.clock.t_start + progress * span_s)
        self._update_time_display()

    def _timeline_tooltip_at(self: PlayerAppState, progress: float) -> str:
        """Format the UTC time at a timeline position for its hover tooltip."""
        epoch_s = self.clock.t_start + progress * (
            self.clock.t_end - self.clock.t_start
        )
        # Keep hover text compact; the persistent readouts retain fractions.
        return time_utils.datetime_to_iso8601(
            time_utils.tt_s_to_datetime(epoch_s), fractional_second_places=0
        )

    def _set_playback_speed(self: PlayerAppState, speed: float) -> None:
        self.clock.set_speed(speed)
        self._update_time_display()

    def _set_transport_rate(self: PlayerAppState, rate: float) -> None:
        """Step within the selected transport speed range or select its base."""
        direction = 1 if rate > 0.0 else -1
        increment = abs(rate)
        current_speed = abs(self.clock.rate)
        same_direction = (self.clock.rate > 0.0) == (rate > 0.0)
        # Unit-speed buttons select exactly 1×; larger presets add their speed step.
        if increment == 1.0:
            base_speed = 1.0
        elif (
            same_direction
            and increment <= current_speed
            and current_speed < min(increment * 10.0, self.clock.MAX_SPEED)
        ):
            base_speed = min(current_speed + increment, self.clock.MAX_SPEED)
        else:
            base_speed = increment
        self.clock.set_direction(direction)
        self.clock.set_speed(base_speed)
        if base_speed >= 1000.0:
            self.workspace.transport_speed_buttons[direction * 1000.0].SetFocus()
        elif base_speed >= 100.0:
            self.workspace.transport_speed_buttons[direction * 100.0].SetFocus()
        self._update_time_display()

    def _play_reverse_at_current_speed(self: PlayerAppState) -> None:
        self.clock.set_direction(-1)
        self.clock.play()
        self._update_time_display()

    def _play_forward_at_current_speed(self: PlayerAppState) -> None:
        self.clock.set_direction(1)
        self.clock.play()
        self._update_time_display()

    def _reverse_playback(self: PlayerAppState) -> None:
        self.clock.reverse()
        self._update_time_display()

    def _step_samples(self: PlayerAppState, count: int) -> None:
        self.clock.step_samples(count)
        self._update_time_display()

    def _step_seconds(self: PlayerAppState, amount_s: float) -> None:
        self.clock.step(amount_s)
        self._update_time_display()

    def _jump_to_start(self: PlayerAppState) -> None:
        self.clock.seek(self.clock.t_start)
        self._update_time_display()

    def _jump_to_end(self: PlayerAppState) -> None:
        self.clock.seek(self.clock.t_end)
        self._update_time_display()

    def _seek_to_time(self: PlayerAppState, time_entry_text: str) -> None:
        try:
            parsed_time = time_utils.parse_time_or_duration(time_entry_text)
            if isinstance(parsed_time, timedelta):
                target_time_s = self.clock.t_start + parsed_time.total_seconds()
            else:
                target_time_s = time_utils.datetime_to_tt_s(parsed_time)
            if not self.clock.t_start <= target_time_s <= self.clock.t_end:
                raise ValueError("time is outside the OEM timeline")
        except (OverflowError, ValueError) as error:
            self.workspace.show_time_error(str(error))
            return

        self.clock.seek(target_time_s)
        self.workspace.clear_time_error()
        self._update_time_display()
        self.workspace.set_current_time_entry(
            time_utils.datetime_to_iso8601(
                time_utils.tt_s_to_datetime(self.clock.t_now)
            )
        )
