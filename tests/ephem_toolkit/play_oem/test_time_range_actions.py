"""Tests for application actions that link ranges until plot customization."""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from ephem_toolkit.play_oem.clock import PlaybackClock
from ephem_toolkit.play_oem.app.playback_actions import PlaybackActionsMixin
from ephem_toolkit.play_oem.time_range import (
    PlotTimeRange,
    ResolvedTimeRange,
    TimeRangeEndpoint,
    resolve_plot_range,
)
from ephem_toolkit.play_oem.app.time_range_actions import (
    TimeRangeActionsMixin,
    playback_range_plot_rule,
)


class _ActionHost(TimeRangeActionsMixin, PlaybackActionsMixin):
    def __init__(self) -> None:
        self.clock = PlaybackClock(0.0, 100.0, t_now=50.0, playing=True)
        self.plot_time_range = playback_range_plot_rule()
        self._last_frame_monotonic_s = 12.0
        self.dispatches: list[ResolvedTimeRange | None] = []
        self.display_updates = 0
        self.workspace = SimpleNamespace(
            show_time_error=lambda message: setattr(self, "time_error", message),
            clear_time_error=lambda: setattr(self, "time_error", ""),
            set_current_time_entry=lambda value: setattr(self, "current_entry", value),
        )
        self.status_bar = SimpleNamespace(
            set_message=lambda message: setattr(self, "status_message", message)
        )
        self.clock.subscribe(self._on_clock_time_changed)

    def _update_time_display(self) -> None:
        self.display_updates += 1

    def _dispatch_time_range(
        self, resolved: ResolvedTimeRange | None, _time_s: float | None = None
    ) -> None:
        self.dispatches.append(resolved)

    def _on_clock_time_changed(self, time_s: float) -> None:
        self._dispatch_time_range(
            resolve_plot_range(
                self.plot_time_range,
                (self.clock.t_start, self.clock.t_end),
                (self.clock.playback_start, self.clock.playback_end),
                time_s,
            ),
            time_s,
        )


def test_playback_edit_clamps_clock_and_preserves_plot_rule() -> None:
    host = _ActionHost()
    fixed_plot = PlotTimeRange(
        True, TimeRangeEndpoint("fixed", 10.0), TimeRangeEndpoint("fixed", 20.0)
    )
    host._apply_plot_time_range(fixed_plot)
    host.dispatches.clear()
    host.clock.play()
    host._last_frame_monotonic_s = 12.0

    host._apply_playback_bounds(60.0, 80.0)

    assert (host.clock.playback_start, host.clock.playback_end) == (60.0, 80.0)
    assert host.clock.t_now == 60.0
    assert not host.clock.playing
    assert host.plot_time_range == fixed_plot
    assert host.dispatches == [ResolvedTimeRange(10.0, 20.0)]
    assert host._last_frame_monotonic_s is None


def test_default_plot_range_follows_playback_bounds() -> None:
    host = _ActionHost()

    host._apply_playback_bounds(60.0, 80.0)

    assert host.plot_time_range == playback_range_plot_rule()
    assert host.dispatches == [ResolvedTimeRange(60.0, 80.0)]


def test_playback_edit_updates_only_endpoint_in_follow_mode() -> None:
    host = _ActionHost()
    host.plot_time_range = PlotTimeRange(
        True, TimeRangeEndpoint("follow", 0.0), TimeRangeEndpoint("fixed", 90.0)
    )

    host._apply_playback_bounds(60.0, 80.0)

    assert host.plot_time_range.end == TimeRangeEndpoint("fixed", 90.0)
    assert host.dispatches == [ResolvedTimeRange(60.0, 90.0)]


def test_plot_edit_does_not_seek_or_change_playback_bounds() -> None:
    host = _ActionHost()
    before = (host.clock.t_now, host.clock.playback_start, host.clock.playback_end)
    rule = PlotTimeRange(
        True, TimeRangeEndpoint("offset", 10.0), TimeRangeEndpoint("offset", 20.0)
    )

    host._apply_plot_time_range(rule)

    assert (
        host.clock.t_now,
        host.clock.playback_start,
        host.clock.playback_end,
    ) == before
    assert not host.clock.playing
    assert host.plot_time_range == rule
    assert host.dispatches == [ResolvedTimeRange(60.0, 70.0)]


def test_invalid_plot_edit_is_atomic() -> None:
    host = _ActionHost()
    prior = host.plot_time_range
    reversed_rule = PlotTimeRange(
        True, TimeRangeEndpoint("fixed", 90.0), TimeRangeEndpoint("fixed", 20.0)
    )

    with pytest.raises(ValueError):
        host._apply_plot_time_range(reversed_rule)

    assert host.plot_time_range == prior
    assert host.clock.t_now == 50.0
    assert host.clock.playing
    assert host.dispatches == []


def test_plot_handle_drag_preserves_endpoint_mode_and_never_seeks() -> None:
    host = _ActionHost()
    rule = PlotTimeRange(
        True, TimeRangeEndpoint("fixed", 10.0), TimeRangeEndpoint("offset", 15.0)
    )
    host.plot_time_range = rule
    before = (host.clock.t_now, host.clock.playback_start, host.clock.playback_end)

    host._drag_plot_endpoint("end", 75.0)

    assert host.plot_time_range.start == rule.start
    assert host.plot_time_range.end == TimeRangeEndpoint("offset", 25.0)
    assert (
        host.clock.t_now,
        host.clock.playback_start,
        host.clock.playback_end,
    ) == before
    assert host.dispatches == [ResolvedTimeRange(10.0, 75.0)]


def test_dragging_following_handle_detaches_it_as_fixed_timepoint() -> None:
    host = _ActionHost()
    host.plot_time_range = playback_range_plot_rule()

    host._drag_plot_endpoint("start", 25.0)

    assert host.plot_time_range.start == TimeRangeEndpoint("fixed", 25.0)
    assert host.plot_time_range.end == TimeRangeEndpoint("follow", 0.0)
    assert host.dispatches == [ResolvedTimeRange(25.0, 100.0)]


def test_changing_endpoint_mode_preserves_position_or_follows_playback() -> None:
    host = _ActionHost()

    host._set_plot_endpoint_mode("start", "fixed")
    assert host.plot_time_range.start == TimeRangeEndpoint("fixed", 0.0)

    host.clock.seek(60.0)
    host._set_plot_endpoint_mode("start", "offset")
    assert host.plot_time_range.start == TimeRangeEndpoint("offset", -60.0)

    host._set_plot_endpoint_mode("start", "follow")
    assert host.plot_time_range.start == TimeRangeEndpoint("follow", 0.0)
    assert host.dispatches[-1] == ResolvedTimeRange(0.0, 100.0)


def test_navigation_actions_always_use_playback_bounds() -> None:
    host = _ActionHost()
    host.clock.set_playback_bounds(20.0, 80.0)

    host._seek_to_fraction(1.0)  # The slider still maps the full OEM coverage.
    assert host.clock.t_now == 80.0
    host._jump_to_start()
    assert host.clock.t_now == 20.0
    host._jump_to_end()
    assert host.clock.t_now == 80.0
    host._step_seconds(10.0)
    assert host.clock.t_now == 80.0
    host._step_seconds(-100.0)
    assert host.clock.t_now == 20.0


def test_typed_time_inside_oem_but_outside_playback_is_clamped_with_status() -> None:
    import ephem_toolkit.core.time_utils as time_utils

    host = _ActionHost()
    host.clock.set_playback_bounds(20.0, 80.0)
    requested = time_utils.datetime_to_iso8601(time_utils.tt_s_to_datetime(90.0))

    host._seek_to_time(requested)

    assert host.clock.t_now == 80.0
    assert host.status_message == "Time was clamped to playback limits."
    assert host.current_entry == time_utils.datetime_to_iso8601(
        time_utils.tt_s_to_datetime(80.0)
    )
