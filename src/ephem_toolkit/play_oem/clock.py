"""GUI-independent playback clock for OEM timelines."""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Sequence

ClockObserver = Callable[[float], None]


class PlaybackClock:
    """Track playback time, speed, direction, looping and observer updates."""

    MIN_SPEED = 1.0
    MAX_SPEED = 9000.0

    def __init__(
        self,
        t_start: float,
        t_end: float,
        *,
        t_now: float | None = None,
        rate: float = 1.0,
        playing: bool = False,
        loop: bool = False,
        sample_times: Sequence[float] | None = None,
    ) -> None:
        self._validate_finite(t_start, "t_start")
        self._validate_finite(t_end, "t_end")
        if t_start > t_end:
            raise ValueError("t_start must be less than or equal to t_end")
        self._validate_finite(rate, "rate")
        if rate == 0.0:
            raise ValueError("rate must not be zero")

        self._t_start = float(t_start)
        self._t_end = float(t_end)
        self._t_now = self._clamp_time(
            self._t_start if t_now is None else self._validate_time(t_now)
        )
        self._rate = math.copysign(
            min(max(abs(float(rate)), self.MIN_SPEED), self.MAX_SPEED), rate
        )
        self._playing = bool(playing)
        self._loop = bool(loop)
        self._observers: list[ClockObserver] = []
        self._sample_times = self._validate_sample_times(sample_times)

    @property
    def t_start(self) -> float:
        return self._t_start

    @property
    def t_end(self) -> float:
        return self._t_end

    @property
    def t_now(self) -> float:
        return self._t_now

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def loop(self) -> bool:
        return self._loop

    def tick(self, wall_dt: float) -> None:
        """Advance by elapsed monotonic wall time, applying boundary behavior."""
        self._validate_finite(wall_dt, "wall_dt")
        if wall_dt < 0.0:
            raise ValueError("wall_dt must not be negative")
        if not self._playing or wall_dt == 0.0:
            return

        span = self._t_end - self._t_start
        if span == 0.0:
            self._playing = False
            self._notify_observers()
            return

        next_time = self._t_now + self._rate * wall_dt
        if self._rate > 0.0 and next_time >= self._t_end:
            if self._loop:
                self._t_now = self._t_start + (next_time - self._t_start) % span
            else:
                self._t_now = self._t_end
                self._playing = False
        elif self._rate < 0.0 and next_time <= self._t_start:
            if self._loop:
                self._t_now = self._t_end - (self._t_start - next_time) % span
            else:
                self._t_now = self._t_start
                self._playing = False
        else:
            self._t_now = next_time

        self._notify_observers()

    def seek(self, t: float) -> None:
        """Set the current timeline time, clamping it to the configured bounds."""
        self._t_now = self._clamp_time(self._validate_time(t))
        self._notify_observers()

    def play(self) -> None:
        self._playing = True

    def pause(self) -> None:
        self._playing = False

    def toggle(self) -> None:
        self._playing = not self._playing

    def set_speed(self, speed: float) -> None:
        """Set speed magnitude, preserving direction and clamping it to 1x–9000x."""
        self._validate_finite(speed, "speed")
        if speed == 0.0:
            raise ValueError("speed must not be zero")
        magnitude = min(max(abs(float(speed)), self.MIN_SPEED), self.MAX_SPEED)
        self._rate = math.copysign(magnitude, self._rate)

    def set_direction(self, direction: int) -> None:
        """Set playback direction to -1 or +1 without moving the clock."""
        if isinstance(direction, bool) or direction not in (-1, 1):
            raise ValueError("direction must be -1 or +1")
        self._rate = math.copysign(abs(self._rate), direction)

    def reverse(self) -> None:
        """Reverse playback direction without changing the current time."""
        self._rate = -self._rate

    def step(self, amount: float | int, *, unit: str = "seconds") -> None:
        """Seek by seconds or by a signed number of OEM sample intervals."""
        if unit == "seconds":
            self._validate_finite(amount, "amount")
            self.seek(self._t_now + amount)
            return
        if unit == "samples":
            if isinstance(amount, bool) or not isinstance(amount, int):
                raise ValueError("sample count must be an integer")
            self.step_samples(amount)
            return
        raise ValueError("unit must be 'seconds' or 'samples'")

    def step_samples(self, count: int) -> None:
        """Seek to a neighboring OEM sample by signed sample count."""
        if isinstance(count, bool) or not isinstance(count, int):
            raise ValueError("sample count must be an integer")
        if not self._sample_times:
            raise ValueError("sample_times are required for sample stepping")
        if count == 0:
            self.seek(self._t_now)
            return

        if count > 0:
            index = bisect_right(self._sample_times, self._t_now) + count - 1
        else:
            index = bisect_left(self._sample_times, self._t_now) + count
        index = min(max(index, 0), len(self._sample_times) - 1)
        self.seek(self._sample_times[index])

    def subscribe(self, observer: ClockObserver) -> Callable[[], None]:
        """Subscribe to time updates and return a function that unsubscribes it."""
        if not callable(observer):
            raise TypeError("observer must be callable")
        self._observers.append(observer)

        def unsubscribe() -> None:
            if observer in self._observers:
                self._observers.remove(observer)

        return unsubscribe

    def _notify_observers(self) -> None:
        for observer in tuple(self._observers):
            observer(self._t_now)

    def _clamp_time(self, t: float) -> float:
        return min(max(float(t), self._t_start), self._t_end)

    def _validate_time(self, t: float) -> float:
        self._validate_finite(t, "t")
        return float(t)

    def _validate_sample_times(
        self, sample_times: Sequence[float] | None
    ) -> tuple[float, ...]:
        if sample_times is None:
            return ()

        values = tuple(self._validate_time(t) for t in sample_times)
        if any(t < self._t_start or t > self._t_end for t in values):
            raise ValueError("sample_times must lie within the timeline bounds")
        if any(first >= second for first, second in zip(values, values[1:])):
            raise ValueError("sample_times must be strictly increasing")
        return values

    @staticmethod
    def _validate_finite(value: float, name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a finite number")
        if not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number")
