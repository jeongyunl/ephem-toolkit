"""Tests for TimeScrubber viewport and wheel behavior."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
import wx

from ephem_toolkit.play_oem.widgets.time_scrubber import (
    MINIMUM_VIEWPORT_SECONDS,
    DEFAULT_CHEVRON_HEIGHT,
    TimeScrubber,
    ChevronButton,
    TimeTickRail,
    _clamp_viewport,
    _consume_vertical_wheel_notches,
)
from ephem_toolkit.play_oem import time_range


@pytest.mark.parametrize(
    ("accumulator", "rotation", "wheel_delta", "expected"),
    [
        (0, 120, 120, (120, 0)),
        (120, 120, 120, (0, 1)),
        (0, 480, 120, (0, 2)),
        (0, -480, 120, (0, -2)),
    ],
)
def test_vertical_wheel_notch_accumulation(
    accumulator: int,
    rotation: int,
    wheel_delta: int,
    expected: tuple[int, int],
) -> None:
    assert _consume_vertical_wheel_notches(
        accumulator,
        rotation,
        wheel_delta,
    ) == expected


def test_viewport_clamps_to_coverage_and_minimum_width() -> None:
    assert _clamp_viewport(-10.0, 5.0, (0.0, 100.0)) == (0.0, 15.0)
    assert _clamp_viewport(95.0, 110.0, (0.0, 100.0)) == (85.0, 100.0)
    assert _clamp_viewport(40.0, 60.0, (0.0, 100.0)) == (40.0, 60.0)
    assert MINIMUM_VIEWPORT_SECONDS == 10.0


def test_pan_preserves_width_and_clamps_to_coverage() -> None:
    slider = SimpleNamespace(
        _viewport=(20.0, 40.0),
        _coverage=(0.0, 100.0),
    )
    applied = []
    slider._apply_viewport = applied.append

    from ephem_toolkit.play_oem.widgets.time_scrubber import TimeScrubber

    cast(Any, TimeScrubber.pan)(slider, 0.10)

    assert applied == [(22.0, 42.0)]


def test_full_coverage_fit_expands_with_incremental_oem_loading() -> None:
    app = wx.App(False)
    frame = wx.Frame(None)
    try:
        parent = wx.Panel(frame)
        plot_rule = time_range.PlotTimeRange(
            True,
            time_range.TimeRangeEndpoint("fixed", 0.0),
            time_range.TimeRangeEndpoint("fixed", 0.0),
        )
        scrubber = TimeScrubber(
            parent,
            coverage=(0.0, 0.0),
            playback=(0.0, 0.0),
            plot_rule=plot_rule,
            now_s=0.0,
            viewport=(0.0, 0.0),
            on_playback=lambda _start, _end: None,
            on_plot_endpoint=lambda _name, _value: None,
        )

        expanded_plot = time_range.PlotTimeRange(
            True,
            time_range.TimeRangeEndpoint("fixed", 0.0),
            time_range.TimeRangeEndpoint("fixed", 100.0),
        )
        scrubber.set_ranges(
            (0.0, 100.0),
            (10.0, 90.0),
            expanded_plot,
            50.0,
        )

        assert scrubber.viewport == (0.0, 100.0)
    finally:
        frame.Destroy()
        app.Destroy()


def test_horizontal_wheel_scroll_calls_pan_once() -> None:
    pan_calls = []
    slider = SimpleNamespace(
        pan=pan_calls.append,
        GetClientSize=lambda: SimpleNamespace(width=100),
        _wheel_gesture_axis=None,
        _wheel_gesture_last_at=0.0,
        _vertical_wheel_accumulator=0,
    )
    event = SimpleNamespace(
        GetWheelRotation=lambda: 120,
        GetWheelDelta=lambda: 120,
        GetWheelAxis=lambda: wx.MOUSE_WHEEL_HORIZONTAL,
    )

    from ephem_toolkit.play_oem.widgets.time_scrubber import TimeScrubber

    cast(Any, TimeScrubber._mouse_wheel)(slider, event)

    assert pan_calls == [0.05]


def test_tick_rail_forwards_wheel_to_timescrubber() -> None:
    calls = []
    rail = SimpleNamespace(
        _on_wheel=calls.append,
    )
    event = SimpleNamespace(Skip=lambda _skip: None)

    cast(Any, TimeTickRail._mouse_wheel)(rail, event)

    assert calls == [event]


def test_tick_rail_drag_calls_pan_fraction() -> None:
    pan_calls = []
    rail = SimpleNamespace(
        _drag_start_x=50,
        _on_pan=pan_calls.append,
        GetClientSize=lambda: SimpleNamespace(width=200),
    )
    event = SimpleNamespace(
        GetX=lambda: 70,
        Dragging=lambda: True,
        LeftIsDown=lambda: True,
        Skip=lambda _skip: None,
    )

    cast(Any, TimeTickRail._motion)(rail, event)

    assert pan_calls == pytest.approx([-20 / 180])
    assert rail._drag_start_x == 70


def test_tick_rail_is_compact() -> None:
    app = wx.App(False)
    frame = wx.Frame(None)
    try:
        rail = TimeTickRail(frame)
        assert rail.GetMinSize().height == 18
        assert rail.GetFont().GetPointSize() > frame.GetFont().GetPointSize()
    finally:
        frame.Destroy()
        app.Destroy()


def test_chevron_height_matches_combined_track() -> None:
    app = wx.App(False)
    frame = wx.Frame(None)
    try:
        calls = []
        chevron = ChevronButton(
            frame,
            "‹",
            "Pan earlier",
            lambda: calls.append("pan"),
        )
        assert chevron.GetSize().height == DEFAULT_CHEVRON_HEIGHT
        assert chevron.GetValue()
        assert chevron.IsEnabled()
        chevron.set_scrollable(False)
        assert not chevron.GetValue()
        assert not chevron.IsEnabled()
        chevron.set_scrollable(True)
        assert chevron.GetValue()
        assert chevron.IsEnabled()
    finally:
        frame.Destroy()
        app.Destroy()


def test_chevron_hover_refresh_does_not_consume_tooltip_events() -> None:
    calls = []
    chevron = SimpleNamespace(Refresh=lambda: calls.append("refresh"))
    event = SimpleNamespace(Skip=lambda: calls.append("skip"))

    cast(Any, ChevronButton._on_pointer_boundary)(chevron, event)

    assert calls == ["refresh", "skip"]


def test_chevron_toggle_keeps_scrollable_state_and_pans_only_when_enabled() -> None:
    calls = []
    selected_values = []
    chevron = SimpleNamespace(
        _scrollable=True,
        _callback=lambda: calls.append("pan"),
        SetValue=selected_values.append,
    )
    event = SimpleNamespace(Skip=lambda _skip: None)

    cast(Any, ChevronButton._click)(chevron, event)
    chevron._scrollable = False
    cast(Any, ChevronButton._click)(chevron, event)

    assert calls == ["pan"]
    assert selected_values == [True, False]


def test_scrubber_is_compact_with_tick_rail_attachment() -> None:
    app = wx.App(False)
    frame = wx.Frame(None)
    try:
        plot_rule = time_range.PlotTimeRange(
            True,
            time_range.TimeRangeEndpoint("fixed", 0.0),
            time_range.TimeRangeEndpoint("fixed", 100.0),
        )
        scrubber = TimeScrubber(
            frame,
            coverage=(0.0, 100.0),
            playback=(10.0, 90.0),
            plot_rule=plot_rule,
            now_s=50.0,
            on_playback=lambda _start, _end: None,
            on_plot_endpoint=lambda _name, _value: None,
        )
        assert scrubber.GetMinSize().height == 56
    finally:
        frame.Destroy()
        app.Destroy()


def test_wheel_gesture_latches_axis_and_ignores_opposite_axis(monkeypatch) -> None:
    pan_calls = []
    zoom_calls = []
    slider = SimpleNamespace(
        pan=pan_calls.append,
        zoom_in=zoom_calls.append,
        zoom_out=lambda _fraction: None,
        GetClientSize=lambda: SimpleNamespace(width=100),
        _wheel_gesture_axis=None,
        _wheel_gesture_last_at=0.0,
        _vertical_wheel_accumulator=0,
    )

    import ephem_toolkit.play_oem.widgets.time_scrubber as time_scrubber_module

    monkeypatch.setattr(time_scrubber_module.time, "monotonic", lambda: 1.0)

    horizontal = SimpleNamespace(
        GetWheelRotation=lambda: 120,
        GetWheelDelta=lambda: 120,
        GetWheelAxis=lambda: wx.MOUSE_WHEEL_HORIZONTAL,
    )
    vertical = SimpleNamespace(
        GetWheelRotation=lambda: 120,
        GetWheelDelta=lambda: 120,
        GetWheelAxis=lambda: wx.MOUSE_WHEEL_VERTICAL,
        GetX=lambda: 50,
    )

    cast(Any, time_scrubber_module.TimeScrubber._mouse_wheel)(slider, horizontal)
    cast(Any, time_scrubber_module.TimeScrubber._mouse_wheel)(slider, vertical)

    assert pan_calls == [0.05]
    assert zoom_calls == []
