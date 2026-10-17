"""wxPython application shell for OEM playback."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
import signal
import time

import wx
from matplotlib.backend_bases import MouseButton, MouseEvent
from matplotlib.backends.backend_wxagg import (
    FigureCanvasWxAgg,
    NavigationToolbar2WxAgg,
)

import ephem_toolkit.core.time_utils as time_utils

from . import clock, control_window, cursor, series, time_unit
from .views import base, registry, speed_altitude, state_components, trajectory3d

DEFAULT_TICK_INTERVAL_MS: int = 33
"""Default interval between playback timer events (ms)."""
ELAPSED_TIME_DECIMAL_PLACES: int = 3
"""Number of decimal places shown in the elapsed-time readout."""
PLAYER_FRAME_MIN_SIZE: tuple[int, int] = (680, 360)
"""Minimum dashboard frame size (pixels)."""
PLAYER_FRAME_SIZE: tuple[int, int] = (800, 460)
"""Initial dashboard frame size (pixels)."""
PLOT_FRAME_SIZE: tuple[int, int] = (800, 600)
"""Default plot frame size (pixels)."""


@dataclass
class _OpenView:
    """Track the wx frame and clock subscription for an open plot."""

    frame: wx.Frame
    """Frame hosting the plot."""

    view: base.View
    """Plot view rendered in the frame."""

    unsubscribe: Callable[[], None]
    """Callback that removes this view from clock notifications."""

    canvas: FigureCanvasWxAgg
    """Wx canvas hosting the view's Matplotlib figure."""

    toolbar: NavigationToolbar2WxAgg
    """Wx navigation toolbar associated with the canvas."""

    click_callback_id: int
    """Matplotlib event identifier used to disconnect plot seeking."""


class PlayerApp:
    """Own the wx application, playback timer and playback windows."""

    def __init__(
        self,
        clock: clock.PlaybackClock,
        series: series.OrbitSeries,
        time_unit: time_unit.TimeUnit,
        cursor: cursor.OemCursor,
        object_name: str,
        frame_context: str,
        *,
        plots: Sequence[str] = ("overview",),
        tick_interval_ms: int = DEFAULT_TICK_INTERVAL_MS,
    ) -> None:
        """Create the wx playback application.

        Parameters
        ----------
        clock : clock.PlaybackClock
            Playback state and observer source.
        series : series.OrbitSeries
            Computed OEM data shared by plot views.
        time_unit : time_unit.TimeUnit
            Display unit for plotted values.
        cursor : cursor.OemCursor
            OEM state lookup used by the 3D orbit view.
        object_name : str
            Object name used in plot titles and labels.
        frame_context : str
            Reference-frame context used by plot views.
        plots : Sequence[str], optional
            Plot names and groups to open when the application starts.
        tick_interval_ms : int, default=DEFAULT_TICK_INTERVAL_MS
            Interval between playback timer events, in milliseconds.

        Raises
        ------
        ValueError
            If ``tick_interval_ms`` is less than one.
        """
        if tick_interval_ms < 1:
            raise ValueError("tick_interval_ms must be positive")

        self.clock = clock
        self.series = series
        self.time_unit = time_unit
        self.cursor = cursor
        self.object_name = object_name
        self.frame_context = frame_context
        self._tick_interval_ms = tick_interval_ms

        self._view_registry = registry.ViewRegistry()
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
        self.control_window = control_window.ControlWindow(
            self.frame,
            self.open_view,
            self.open_group,
            self._view_registry,
            self._toggle_playback,
            self._seek_to_fraction,
            self._set_playback_speed,
            self._reverse_playback,
            on_seek_to_time=self._seek_to_time,
            on_step_samples=self._step_samples,
            on_step_seconds=self._step_seconds,
            on_jump_to_start=self._jump_to_start,
            on_jump_to_end=self._jump_to_end,
            timeline_enabled=clock.t_start < clock.t_end,
        )
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(self.control_window.panel, 1, wx.EXPAND)
        self.frame.SetSizer(layout)
        self.frame.SetMinSize(PLAYER_FRAME_MIN_SIZE)
        self.frame.SetSize(PLAYER_FRAME_SIZE)
        self.frame.Bind(wx.EVT_CLOSE, self._on_frame_close)

        self._timer = wx.Timer(self.frame)
        self.frame.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self._last_tick_monotonic_s: float | None = None
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
        self._last_tick_monotonic_s = time.monotonic()
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
            lambda: speed_altitude.SpeedAltitudeView(self.clock.t_start),
        )

    def open_state_components_view(self) -> None:
        """Open or raise the Cartesian state-components plot."""
        self._open_view(
            "state-components",
            lambda: state_components.StateComponentsView(
                self.clock.t_start, self.frame_context
            ),
        )

    def open_trajectory_view(self) -> None:
        """Open or raise the 3D orbit plot."""
        self._open_view(
            "trajectory-3d",
            lambda: trajectory3d.Trajectory3DView(
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

    def _toggle_playback(self) -> None:
        self.clock.toggle()
        self._update_time_display()

    def _seek_to_fraction(self, progress: float) -> None:
        span_s = self.clock.t_end - self.clock.t_start
        self.clock.seek(self.clock.t_start + progress * span_s)
        self._update_time_display()

    def _set_playback_speed(self, speed: float) -> None:
        self.clock.set_speed(speed)
        self._update_time_display()

    def _reverse_playback(self) -> None:
        self.clock.reverse()
        self._update_time_display()

    def _step_samples(self, count: int) -> None:
        self.clock.step_samples(count)
        self._update_time_display()

    def _step_seconds(self, amount_s: float) -> None:
        self.clock.step(amount_s)
        self._update_time_display()

    def _jump_to_start(self) -> None:
        self.clock.seek(self.clock.t_start)
        self._update_time_display()

    def _jump_to_end(self) -> None:
        self.clock.seek(self.clock.t_end)
        self._update_time_display()

    def _seek_to_time(self, time_entry_text: str) -> None:
        try:
            parsed_time = time_utils.parse_time_or_duration(time_entry_text)
            if isinstance(parsed_time, timedelta):
                target_time_s = self.clock.t_start + parsed_time.total_seconds()
            else:
                target_time_s = time_utils.datetime_to_tt_s(parsed_time)
            if not self.clock.t_start <= target_time_s <= self.clock.t_end:
                raise ValueError("time is outside the OEM timeline")
        except (OverflowError, ValueError) as error:
            self.control_window.show_time_error(str(error))
            return

        self.clock.seek(target_time_s)
        self.control_window.clear_time_error()
        self._update_time_display()

    def close_view(self, name: str) -> None:
        """Close one plot frame and unsubscribe its view from the playback clock."""
        opened = self._open_views.get(name)
        if opened is not None:
            opened.frame.Close(force=True)

    def _open_view(self, name: str, create_view: Callable[[], base.View]) -> None:
        if self._closed:
            raise RuntimeError("cannot open a view in a closed PlayerApp")
        existing = self._open_views.get(name)
        if existing is not None:
            existing.frame.Raise()
            return

        view = create_view()
        frame: wx.Frame | None = None
        canvas: FigureCanvasWxAgg | None = None
        click_callback_id: int | None = None
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
            toolbar = NavigationToolbar2WxAgg(canvas)
            toolbar.Realize()
            layout = wx.BoxSizer(wx.VERTICAL)
            layout.Add(toolbar, 0, wx.EXPAND)
            layout.Add(canvas, 1, wx.EXPAND)
            frame.SetSizer(layout)
            frame.Bind(
                wx.EVT_CLOSE,
                lambda event: self._on_view_frame_close(name, event),
            )
            click_callback_id = canvas.mpl_connect(
                "button_press_event",
                lambda event: self._on_plot_click(event, toolbar),
            )

            def update_view(time_s: float) -> None:
                view.update(time_s)
                canvas.draw_idle()

            unsubscribe = self.clock.subscribe(update_view)
            self._open_views[name] = _OpenView(
                frame,
                view,
                unsubscribe,
                canvas,
                toolbar,
                click_callback_id,
            )
            frame.Layout()
            canvas.draw()
            if not frame.Show():
                raise RuntimeError(f"could not show the {name!r} plot frame")
        except Exception:
            self._open_views.pop(name, None)
            if canvas is not None and click_callback_id is not None:
                canvas.mpl_disconnect(click_callback_id)
            if unsubscribe is not None:
                unsubscribe()
            if frame is not None:
                frame.Destroy()
            view.close()
            raise

    def _on_plot_click(
        self, event: MouseEvent, toolbar: NavigationToolbar2WxAgg
    ) -> None:
        if (
            toolbar.mode
            or event.button != MouseButton.LEFT
            or event.inaxes is None
            or event.xdata is None
            or event.inaxes.name == "3d"
        ):
            return

        target_time_s = (
            self.clock.t_start + event.xdata * self.time_unit.get_divisor_s()
        )
        self.clock.seek(target_time_s)
        self._update_time_display()

    def _on_view_frame_close(self, name: str, event: wx.CloseEvent) -> None:
        opened = self._open_views.pop(name, None)
        if opened is not None:
            opened.canvas.mpl_disconnect(opened.click_callback_id)
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
        current_time_s = time.monotonic()
        if self._last_tick_monotonic_s is None:
            self._last_tick_monotonic_s = current_time_s
        else:
            elapsed_s = current_time_s - self._last_tick_monotonic_s
            self._last_tick_monotonic_s = current_time_s
            self.clock.tick(elapsed_s)
        self._update_time_display()

    def _update_time_display(self) -> None:
        elapsed_s = self.clock.t_now - self.clock.t_start
        utc_timestamp = time_utils.datetime_to_iso8601(
            time_utils.tt_s_to_datetime(self.clock.t_now)
        )
        span_s = self.clock.t_end - self.clock.t_start
        progress = (
            0.0 if span_s == 0.0 else (self.clock.t_now - self.clock.t_start) / span_s
        )
        self.control_window.update_playback_state(
            f"Elapsed: {elapsed_s:.{ELAPSED_TIME_DECIMAL_PLACES}f} s\n"
            f"UTC: {utc_timestamp}",
            progress,
            self.clock.playing,
            self.clock.rate,
        )

    def _handle_sigint(self, _signum: int, _frame: object) -> None:
        wx.CallAfter(self.close)
