"""Tk application shell and playback timer."""

from __future__ import annotations

import signal
import time
import tkinter as tk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import ephem_toolkit.core.time_utils as time_utils

from .clock import PlaybackClock
from .control_window import ControlWindow
from .series import OrbitSeries
from .time_unit import TimeUnit
from .views.speed_altitude import SpeedAltitudeView

DEFAULT_TICK_INTERVAL_MS = 33


class PlayerApp:
    """Own the Tk root, control window, playback clock and timer lifecycle."""

    def __init__(
        self,
        clock: PlaybackClock,
        series: OrbitSeries,
        time_unit: TimeUnit,
        *,
        tick_interval_ms: int = DEFAULT_TICK_INTERVAL_MS,
        root: tk.Tk | None = None,
    ) -> None:
        if tick_interval_ms < 1:
            raise ValueError("tick_interval_ms must be positive")
        self.clock = clock
        self.series = series
        self.time_unit = time_unit
        self.root = tk.Tk() if root is None else root
        self.control_window = ControlWindow(
            self.root, self.close, self.open_speed_altitude_view
        )
        self._tick_interval_ms = tick_interval_ms
        self._last_tick: float | None = None
        self._timer_id: str | None = None
        self._started = False
        self._closed = False
        self._speed_altitude_view: SpeedAltitudeView | None = None
        self._speed_altitude_window: tk.Toplevel | None = None

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
        self.close_speed_altitude_view()
        if self._timer_id is not None:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None
        self.root.quit()
        self.root.destroy()

    def open_speed_altitude_view(self) -> None:
        """Open or raise the speed and altitude plot window."""
        if self._speed_altitude_window is not None:
            self._speed_altitude_window.lift()
            return

        view = SpeedAltitudeView(self.clock.t_start)
        figure = view.build(self.series, self.time_unit)
        window = tk.Toplevel(self.root)
        window.title("Speed / Altitude")
        canvas = FigureCanvasTkAgg(figure, master=window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        window.protocol("WM_DELETE_WINDOW", self.close_speed_altitude_view)
        self._speed_altitude_view = view
        self._speed_altitude_window = window

    def close_speed_altitude_view(self) -> None:
        """Close the speed and altitude plot, leaving the control window open."""
        if self._speed_altitude_view is None:
            return
        view = self._speed_altitude_view
        window = self._speed_altitude_window
        self._speed_altitude_view = None
        self._speed_altitude_window = None
        view.close()
        if window is not None:
            window.destroy()

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
