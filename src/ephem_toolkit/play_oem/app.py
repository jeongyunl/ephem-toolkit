"""Tk application shell and playback timer."""

from __future__ import annotations

import signal
import time
import tkinter as tk

import ephem_toolkit.core.time_utils as time_utils

from .clock import PlaybackClock
from .control_window import ControlWindow

DEFAULT_TICK_INTERVAL_MS = 33


class PlayerApp:
    """Own the Tk root, control window, playback clock and timer lifecycle."""

    def __init__(
        self,
        clock: PlaybackClock,
        *,
        tick_interval_ms: int = DEFAULT_TICK_INTERVAL_MS,
        root: tk.Tk | None = None,
    ) -> None:
        if tick_interval_ms < 1:
            raise ValueError("tick_interval_ms must be positive")
        self.clock = clock
        self.root = tk.Tk() if root is None else root
        self.control_window = ControlWindow(self.root, self.close)
        self._tick_interval_ms = tick_interval_ms
        self._last_tick: float | None = None
        self._timer_id: str | None = None
        self._started = False
        self._closed = False

    def run(self) -> None:
        """Start the Tk event loop and restore the process signal handler on exit."""
        previous_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._handle_sigint)
        try:
            self.start()
            self.root.mainloop()
        finally:
            self.close()
            signal.signal(signal.SIGINT, previous_sigint_handler)

    def start(self) -> None:
        """Initialize the time baseline and schedule playback timer callbacks."""
        if self._closed:
            raise RuntimeError("cannot start a closed PlayerApp")
        if self._started:
            return
        self._started = True
        self._last_tick = time.monotonic()
        self._update_time_display()
        self._schedule_tick()

    def close(self) -> None:
        """Stop pending timer callbacks and destroy the application window."""
        if self._closed:
            return
        self._closed = True
        if self._timer_id is not None:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None
        self.root.quit()
        self.root.destroy()

    def _schedule_tick(self) -> None:
        if not self._closed:
            self._timer_id = self.root.after(self._tick_interval_ms, self._on_timer)

    def _on_timer(self) -> None:
        self._timer_id = None
        if self._closed:
            return

        now = time.monotonic()
        if self._last_tick is None:
            self._last_tick = now
        else:
            self.clock.tick(now - self._last_tick)
            self._last_tick = now
        self._update_time_display()
        self._schedule_tick()

    def _update_time_display(self) -> None:
        elapsed_s = self.clock.t_now - self.clock.t_start
        utc_time = time_utils.datetime_to_iso8601(
            time_utils.tt_s_to_datetime(self.clock.t_now)
        )
        self.control_window.update_time(f"Elapsed: {elapsed_s:.3f} s\nUTC: {utc_time}")

    def _handle_sigint(self, _signum: int, _frame: object) -> None:
        self.close()
