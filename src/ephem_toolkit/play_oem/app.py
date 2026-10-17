"""wxPython application shell for OEM playback."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import signal
import time

import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg

import ephem_toolkit.core.time_utils as time_utils

from .clock import PlaybackClock
from .cursor import OemCursor
from .series import OrbitSeries
from .time_unit import TimeUnit
from .views.base import View
from .views.registry import ViewRegistry
from .views.speed_altitude import SpeedAltitudeView
from .views.state_components import StateComponentsView
from .views.trajectory3d import Trajectory3DView

DEFAULT_TICK_INTERVAL_MS = 33
PLOT_FRAME_SIZE = (800, 600)


@dataclass
class _OpenView:
    frame: wx.Frame
    view: View
    unsubscribe: Callable[[], None]


class PlayerApp:
    """Own the wx application, playback timer and playback windows."""

    def __init__(
        self,
        clock: PlaybackClock,
        series: OrbitSeries,
        time_unit: TimeUnit,
        cursor: OemCursor,
        object_name: str,
        frame_context: str,
        *,
        plots: Sequence[str] = ("overview",),
        tick_interval_ms: int = DEFAULT_TICK_INTERVAL_MS,
    ) -> None:
        if tick_interval_ms < 1:
            raise ValueError("tick_interval_ms must be positive")

        self.clock = clock
        self.series = series
        self.time_unit = time_unit
        self.cursor = cursor
        self.object_name = object_name
        self.frame_context = frame_context
        self._tick_interval_ms = tick_interval_ms

        self._view_registry = ViewRegistry()
        self._view_registry.register_view("trajectory-3d", self.open_trajectory_view)
        self._view_registry.register_view(
            "speed-altitude", self.open_speed_altitude_view
        )
        self._view_registry.register_view(
            "state-components", self.open_state_components_view
        )
        self._plots = self._view_registry.expand(plots)

        self.wx_app = wx.GetApp()
        if self.wx_app is None:
            self.wx_app = wx.App(False)

        self.frame = wx.Frame(None, title="play-oem")
        self._time_display = wx.StaticText(self.frame, wx.ID_ANY, "")
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(self._time_display, 1, wx.EXPAND | wx.ALL, 16)
        self.frame.SetSizer(layout)
        self.frame.SetMinSize((360, 100))
        self.frame.SetSize((480, 120))
        self.frame.Bind(wx.EVT_CLOSE, self._on_frame_close)

        self._timer = wx.Timer(self.frame)
        self.frame.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self._last_tick: float | None = None
        self._started = False
        self._closed = False
        self._open_views: dict[str, _OpenView] = {}

    def run(self) -> None:
        """Run the wx event loop and restore the prior SIGINT handler on exit."""
        previous_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._handle_sigint)
        try:
            self.start()
            self.wx_app.MainLoop()
        finally:
            try:
                self.close()
            finally:
                signal.signal(signal.SIGINT, previous_sigint_handler)

    def start(self) -> None:
        """Show the application, open the selected plots and start playback ticks."""
        if self._closed:
            raise RuntimeError("cannot start a closed PlayerApp")
        if self._started:
            return

        self._started = True
        self._last_tick = time.monotonic()
        self._update_time_display()
        self.frame.Show()
        self.open_plots(self._plots)
        if not self._timer.Start(self._tick_interval_ms):
            raise RuntimeError("could not start the wx playback timer")

    def close(self) -> None:
        """Close all playback windows and stop the wx timer."""
        if self._closed:
            return
        if not self.frame.Close(force=True) and not self._closed:
            raise RuntimeError("could not close the play-oem frame")

    def open_speed_altitude_view(self) -> None:
        """Open or raise the speed and altitude plot."""
        self._open_view(
            "speed-altitude",
            lambda: SpeedAltitudeView(self.clock.t_start),
        )

    def open_state_components_view(self) -> None:
        """Open or raise the Cartesian state-components plot."""
        self._open_view(
            "state-components",
            lambda: StateComponentsView(self.clock.t_start, self.frame_context),
        )

    def open_trajectory_view(self) -> None:
        """Open or raise the 3D orbit plot."""
        self._open_view(
            "trajectory-3d",
            lambda: Trajectory3DView(
                self.cursor,
                self.object_name,
                self.frame_context,
            ),
        )

    def open_view(self, name: str) -> None:
        self._view_registry.open_view(name)

    def open_group(self, name: str) -> None:
        self._view_registry.open_group(name)

    def open_plots(self, selection: Sequence[str]) -> None:
        self._view_registry.open(selection)

    def close_view(self, name: str) -> None:
        """Close one plot frame and unsubscribe its view from the playback clock."""
        opened = self._open_views.get(name)
        if opened is not None:
            opened.frame.Close(force=True)

    def _open_view(self, name: str, create_view: Callable[[], View]) -> None:
        if self._closed:
            raise RuntimeError("cannot open a view in a closed PlayerApp")
        existing = self._open_views.get(name)
        if existing is not None:
            existing.frame.Raise()
            return

        view = create_view()
        frame: wx.Frame | None = None
        unsubscribe: Callable[[], None] | None = None
        try:
            figure = view.build(self.series, self.time_unit)
            view.update(self.clock.t_now)
            frame = wx.Frame(
                self.frame,
                title=self._view_registry.label_for(name),
                size=PLOT_FRAME_SIZE,
            )
            canvas = FigureCanvasWxAgg(frame, wx.ID_ANY, figure)
            layout = wx.BoxSizer(wx.VERTICAL)
            layout.Add(canvas, 1, wx.EXPAND)
            frame.SetSizer(layout)
            frame.Bind(
                wx.EVT_CLOSE,
                lambda event: self._on_view_frame_close(name, event),
            )

            def update_view(t_s: float) -> None:
                view.update(t_s)
                canvas.draw_idle()

            unsubscribe = self.clock.subscribe(update_view)
            self._open_views[name] = _OpenView(frame, view, unsubscribe)
            frame.Layout()
            canvas.draw()
            if not frame.Show():
                raise RuntimeError(f"could not show the {name!r} plot frame")
        except Exception:
            self._open_views.pop(name, None)
            if unsubscribe is not None:
                unsubscribe()
            if frame is not None:
                frame.Destroy()
            view.close()
            raise

    def _on_view_frame_close(self, name: str, event: wx.CloseEvent) -> None:
        opened = self._open_views.pop(name, None)
        if opened is not None:
            opened.unsubscribe()
            opened.view.close()
        event.Skip()

    def _on_frame_close(self, event: wx.CloseEvent) -> None:
        if not self._closed:
            self._closed = True
            self._timer.Stop()
            for name in tuple(self._open_views):
                self.close_view(name)
        event.Skip()

    def _on_timer(self, _event: wx.TimerEvent) -> None:
        if self._closed:
            return
        now = time.monotonic()
        if self._last_tick is None:
            self._last_tick = now
        else:
            elapsed = now - self._last_tick
            self._last_tick = now
            self.clock.tick(elapsed)
        self._update_time_display()

    def _update_time_display(self) -> None:
        elapsed_s = self.clock.t_now - self.clock.t_start
        utc_time = time_utils.datetime_to_iso8601(
            time_utils.tt_s_to_datetime(self.clock.t_now)
        )
        playback_state = "Playing" if self.clock.playing else "Paused"
        loop_state = "Loop" if self.clock.loop else "No loop"
        self._time_display.SetLabel(
            f"Elapsed: {elapsed_s:.3f} s\n"
            f"UTC: {utc_time}\n"
            f"{playback_state} | {self.clock.rate:+g}x | {loop_state}"
        )

    def _handle_sigint(self, _signum: int, _frame: object) -> None:
        wx.CallAfter(self.close)
