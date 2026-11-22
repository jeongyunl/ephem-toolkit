"""Tests for TimeScrubber viewport and wheel behavior."""

from types import SimpleNamespace

import pytest
import wx

from ephem_toolkit.play_oem.workspace.time_scrubber import (
    MINIMUM_VIEWPORT_SECONDS,
    _clamp_viewport,
    _consume_vertical_wheel_notches,
)


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

    from ephem_toolkit.play_oem.workspace.time_scrubber import TimeScrubber

    TimeScrubber.pan(slider, 0.10)

    assert applied == [(22.0, 42.0)]


def test_horizontal_wheel_scroll_calls_pan_once() -> None:
    pan_calls = []
    slider = SimpleNamespace(
        pan=pan_calls.append,
        GetClientSize=lambda: SimpleNamespace(width=100),
    )
    event = SimpleNamespace(
        GetWheelRotation=lambda: 120,
        GetWheelDelta=lambda: 120,
        GetWheelAxis=lambda: wx.MOUSE_WHEEL_HORIZONTAL,
    )

    from ephem_toolkit.play_oem.workspace.time_scrubber import TimeScrubber

    TimeScrubber._mouse_wheel(slider, event)

    assert pan_calls == [0.05]
