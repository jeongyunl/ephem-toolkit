"""Tests for the GUI-independent play-oem playback clock."""

from __future__ import annotations

import pytest

from ephem_toolkit.play_oem.clock import PlaybackClock


def test_tick_advances_by_signed_rate_and_pauses_at_forward_end() -> None:
    clock = PlaybackClock(0.0, 20.0, t_now=5.0, rate=2.0, playing=True)

    clock.tick(3.0)
    assert clock.t_now == 11.0
    assert clock.playing

    clock.tick(10.0)
    assert clock.t_now == 20.0
    assert not clock.playing


def test_reverse_playback_pauses_at_start() -> None:
    clock = PlaybackClock(0.0, 20.0, t_now=5.0, rate=-2.0, playing=True)

    clock.tick(3.0)
    assert clock.t_now == 0.0
    assert not clock.playing


@pytest.mark.parametrize(
    ("t_now", "rate", "wall_dt", "expected"),
    [
        (8.0, 1.0, 5.0, 3.0),
        (2.0, -1.0, 5.0, 7.0),
        (2.0, 1.0, 20.0, 2.0),
        (8.0, -1.0, 20.0, 8.0),
    ],
)
def test_loop_wraps_at_both_ends_and_preserves_overshoot(
    t_now: float, rate: float, wall_dt: float, expected: float
) -> None:
    clock = PlaybackClock(0.0, 10.0, t_now=t_now, rate=rate, playing=True, loop=True)

    clock.tick(wall_dt)

    assert clock.t_now == expected
    assert clock.playing


def test_loop_wraps_when_tick_lands_exactly_on_boundary() -> None:
    clock = PlaybackClock(0.0, 10.0, t_now=8.0, playing=True, loop=True)

    clock.tick(2.0)

    assert clock.t_now == 0.0


def test_paused_tick_does_not_advance() -> None:
    clock = PlaybackClock(0.0, 10.0, t_now=4.0)

    clock.tick(2.0)

    assert clock.t_now == 4.0


def test_seek_clamps_and_preserves_playback_controls() -> None:
    clock = PlaybackClock(0.0, 10.0, t_now=4.0, rate=-4.0, playing=True)

    clock.seek(12.0)

    assert clock.t_now == 10.0
    assert clock.rate == -4.0
    assert clock.playing


def test_speed_clamps_magnitude_and_preserves_direction() -> None:
    clock = PlaybackClock(0.0, 10.0, rate=-4.0)

    clock.set_speed(0.5)
    assert clock.rate == -1.0
    clock.set_speed(2500.0)
    assert clock.rate == -2500.0
    clock.set_speed(clock.MAX_SPEED * 2)
    assert clock.rate == -clock.MAX_SPEED
    clock.set_direction(1)
    assert clock.rate == clock.MAX_SPEED


def test_reverse_and_playback_controls_do_not_change_time() -> None:
    clock = PlaybackClock(0.0, 10.0, t_now=4.0)

    clock.play()
    clock.reverse()
    clock.toggle()

    assert clock.t_now == 4.0
    assert clock.rate == -1.0
    assert not clock.playing
    clock.toggle()
    assert clock.playing
    clock.pause()
    assert not clock.playing


def test_time_and_sample_stepping_clamp_to_timeline() -> None:
    clock = PlaybackClock(
        0.0,
        10.0,
        t_now=4.0,
        sample_times=(0.0, 2.0, 5.0, 9.0),
    )

    clock.step(2.0)
    assert clock.t_now == 6.0
    clock.step(-1, unit="samples")
    assert clock.t_now == 5.0
    clock.step(-2, unit="samples")
    assert clock.t_now == 0.0
    clock.step(-1.0)
    assert clock.t_now == 0.0


def test_sample_stepping_from_between_samples() -> None:
    clock = PlaybackClock(
        0.0,
        10.0,
        t_now=3.0,
        sample_times=(0.0, 2.0, 5.0, 9.0),
    )

    clock.step(1, unit="samples")
    assert clock.t_now == 5.0
    clock.step(-1, unit="samples")
    assert clock.t_now == 2.0


def test_observers_receive_tick_and_seek_updates_and_can_unsubscribe() -> None:
    clock = PlaybackClock(0.0, 10.0, t_now=2.0, playing=True)
    observed: list[float] = []
    unsubscribe = clock.subscribe(observed.append)

    clock.tick(1.0)
    clock.seek(8.0)
    unsubscribe()
    clock.seek(3.0)

    assert observed == [3.0, 8.0]


@pytest.mark.parametrize(
    ("args", "kwargs"),
    [
        ((2.0, 1.0), {}),
        ((0.0, 1.0), {"rate": 0.0}),
        ((0.0, 1.0), {"t_now": float("nan")}),
        ((0.0, 1.0), {"sample_times": (0.0, 0.0)}),
    ],
)
def test_constructor_rejects_invalid_timeline_values(args, kwargs) -> None:
    with pytest.raises(ValueError):
        PlaybackClock(*args, **kwargs)


def test_invalid_tick_and_sample_step_raise_value_error() -> None:
    clock = PlaybackClock(0.0, 10.0)

    with pytest.raises(ValueError, match="wall_dt"):
        clock.tick(-1.0)
    with pytest.raises(ValueError, match="sample_times"):
        clock.step(1, unit="samples")
    with pytest.raises(ValueError, match="unit"):
        clock.step(1.0, unit="minutes")


def test_playback_bounds_are_independent_and_clamp_once() -> None:
    clock = PlaybackClock(0.0, 100.0, t_now=10.0, rate=-4.0, playing=True)
    observed: list[float] = []
    clock.subscribe(observed.append)

    assert (clock.t_start, clock.t_end) == (0.0, 100.0)
    assert (clock.playback_start, clock.playback_end) == (0.0, 100.0)
    clock.set_playback_bounds(20.0, 80.0)

    assert (clock.playback_start, clock.playback_end) == (20.0, 80.0)
    assert (clock.t_start, clock.t_end) == (0.0, 100.0)
    assert clock.t_now == 20.0
    assert clock.playing
    assert clock.rate == -4.0
    assert observed == [20.0]


@pytest.mark.parametrize("bounds", [(-1.0, 10.0), (10.0, 101.0), (30.0, 20.0)])
def test_invalid_playback_bounds_are_atomic(bounds: tuple[float, float]) -> None:
    clock = PlaybackClock(0.0, 100.0, t_now=50.0)
    observed: list[float] = []
    clock.subscribe(observed.append)

    with pytest.raises(ValueError):
        clock.set_playback_bounds(*bounds)

    assert (clock.playback_start, clock.playback_end, clock.t_now) == (0.0, 100.0, 50.0)
    assert observed == []


def test_tick_seek_and_step_obey_narrowed_playback_bounds() -> None:
    clock = PlaybackClock(
        0.0,
        100.0,
        t_now=50.0,
        sample_times=(0.0, 20.0, 40.0, 60.0, 80.0, 100.0),
    )
    clock.set_playback_bounds(30.0, 70.0)
    clock.seek(-1.0)
    assert clock.t_now == 30.0
    clock.seek(101.0)
    assert clock.t_now == 70.0
    clock.step(-100.0)
    assert clock.t_now == 30.0
    clock.seek(50.0)
    clock.step_samples(5)
    assert clock.t_now == 70.0
    clock.set_direction(1)
    clock.seek(65.0)
    clock.play()
    clock.tick(10.0)
    assert clock.t_now == 70.0
    assert not clock.playing


@pytest.mark.parametrize(
    ("time", "rate", "expected"), [(27.0, 1.0, 2.0), (3.0, -1.0, 28.0)]
)
def test_loop_wraps_inside_playback_bounds(time: float, rate: float, expected: float) -> None:
    clock = PlaybackClock(
        0.0, 30.0, t_now=time, rate=rate, playing=True, loop=True
    )
    clock.set_playback_bounds(2.0, 28.0)
    clock.tick(1.0)
    assert clock.t_now == expected
    assert clock.playing


def test_singleton_playback_bounds_cannot_play_or_advance() -> None:
    clock = PlaybackClock(0.0, 10.0, t_now=5.0)
    clock.set_playback_bounds(5.0, 5.0)
    clock.play()
    assert not clock.playing
    clock.tick(5.0)
    assert clock.t_now == 5.0
