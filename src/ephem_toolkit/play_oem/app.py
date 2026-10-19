"""wxPython application shell for OEM playback."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
import gc
import signal
import sys
import time
from typing import cast
from uuid import uuid4

import wx
from matplotlib.backend_bases import MouseButton, MouseEvent
from matplotlib.backends.backend_wxagg import (
    FigureCanvasWxAgg,
    NavigationToolbar2WxAgg,
)
from matplotlib.figure import Figure

import ephem_toolkit.core.time_utils as time_utils

from . import clock, control_window, cursor, series, time_unit, workspace
from .graph_panel import GraphPanelHost
from .views import (
    angular_velocity,
    base,
    distance,
    direction_change,
    registry,
    rtn,
    speed_altitude,
    state_components,
    trajectory3d,
)
from .views.trajectory3d import selection as trajectory3d_selection

DEFAULT_TICK_INTERVAL_MS: int = 33
"""Default interval between playback timer events (ms)."""
ELAPSED_TIME_DECIMAL_PLACES: int = 3
"""Number of decimal places shown in the elapsed-time readout."""
PLAYER_FRAME_MIN_SIZE: tuple[int, int] = (920, 480)
"""Minimum dashboard frame size (pixels)."""
PLAYER_FRAME_SIZE: tuple[int, int] = (1100, 760)
"""Initial dashboard frame size (pixels)."""
EMPTY_GRAPH_VIEW: str = "empty"
"""Sentinel name for a graph panel with no selected view."""
EMPTY_GRAPH_LABEL: str = "Empty"
"""Selector label for an unconfigured graph panel."""


class _EmptyGraphView:
    """View placeholder shown before a graph type is selected."""

    name = EMPTY_GRAPH_VIEW

    def __init__(self, parent: wx.Window) -> None:
        self._parent = parent

    def build(
        self, _series: series.OrbitSeries, _time_unit: time_unit.TimeUnit
    ) -> wx.Window:
        prompt = wx.StaticText(self._parent, wx.ID_ANY, "Select a graph view above")
        prompt.SetName("Empty graph prompt")
        return prompt

    def update(self, _t_s: float) -> None:
        pass

    def close(self) -> None:
        pass


@dataclass
class _OpenView:
    """Track one graph-panel instance and its clock subscription."""

    panel_id: str
    """Stable identity independent of the registered view type."""

    view_name: str
    """Registered view type hosted by this panel instance."""

    stack: str
    """Graph stack containing this panel instance."""

    panel: GraphPanelHost
    """Embedded graph-panel host."""

    view: base.View
    """Plot view rendered in the frame."""

    unsubscribe: Callable[[], None]
    """Callback that removes this view from clock notifications."""

    canvas: FigureCanvasWxAgg | None
    """Wx canvas hosting a Matplotlib figure, if this view uses one."""

    toolbar: NavigationToolbar2WxAgg | None
    """Wx navigation toolbar associated with a Matplotlib canvas."""

    click_callback_id: int | None
    """Matplotlib event identifier used to disconnect plot seeking, if connected."""


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
        dashboard_context: dict[str, str] | None = None,
        metadata_details: Sequence[tuple[str, str]] = (),
        plots: Sequence[str] = ("overview",),
        three_d_backend: str = "auto",
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
        three_d_backend : str, default="auto"
            Backend used for the 3D trajectory view.
        tick_interval_ms : int, default=DEFAULT_TICK_INTERVAL_MS
            Interval between playback timer events, in milliseconds.

        Raises
        ------
        ValueError
            If ``tick_interval_ms`` is less than one or the 3D backend is invalid.
        """
        if tick_interval_ms < 1:
            raise ValueError("tick_interval_ms must be positive")
        if three_d_backend not in trajectory3d_selection.THREE_D_BACKEND_CHOICES:
            raise ValueError(
                "three_d_backend must be one of "
                f"{', '.join(trajectory3d_selection.THREE_D_BACKEND_CHOICES)}"
            )

        self.clock = clock
        self.series = series
        self.time_unit = time_unit
        self.cursor = cursor
        self.object_name = object_name
        self.frame_context = frame_context
        self._tick_interval_ms = tick_interval_ms
        self._requested_3d_backend = three_d_backend
        self._selected_3d_backend = (
            "matplotlib" if three_d_backend == "matplotlib" else None
        )

        self._view_registry = registry.ViewRegistry()
        self._view_registry.register_view("trajectory-3d", self.open_trajectory_view)
        self._view_registry.register_view(
            "speed-altitude", self.open_speed_altitude_view
        )
        self._view_registry.register_view(
            "state-components", self.open_state_components_view
        )
        self._view_registry.register_view("rtn", self.open_rtn_view)
        self._view_registry.register_view(
            "angular-velocity", self.open_angular_velocity_view
        )
        self._view_registry.register_view(
            "direction-change", self.open_direction_change_view
        )
        self._view_registry.register_view("distance", self.open_distance_view)
        self._plots = self._view_registry.expand(plots)
        self._panel_view_choices = ((EMPTY_GRAPH_VIEW, EMPTY_GRAPH_LABEL),) + tuple(
            (name, self._view_registry.label_for(name))
            for name in self._view_registry.registered_views
        )

        self.wx_app: wx.App = cast(wx.App, wx.GetApp())
        if self.wx_app is None:
            self.wx_app = wx.App(False)

        self.frame: wx.Frame = wx.Frame(
            None,
            title=f"play-oem (3D backend: {three_d_backend})",
        )
        self.workspace: workspace.Workspace = workspace.Workspace(
            self.frame,
            self._seek_to_fraction,
            on_toggle_play=self._toggle_playback,
            on_play_reverse=self._play_reverse_at_current_speed,
            on_play_forward=self._play_forward_at_current_speed,
            on_set_transport_rate=self._set_transport_rate,
            on_step_samples=self._step_samples,
            timeline_enabled=clock.t_start < clock.t_end,
            timeline_start_utc=time_utils.datetime_to_iso8601(
                time_utils.tt_s_to_datetime(clock.t_start)
            ),
            timeline_end_utc=time_utils.datetime_to_iso8601(
                time_utils.tt_s_to_datetime(clock.t_end)
            ),
            on_seek_to_time=self._seek_to_time,
            timeline_tooltip_at=self._timeline_tooltip_at,
            context=dashboard_context,
            details=metadata_details,
            view_choices=self._panel_view_choices,
            on_add_graph=self._add_graph_panel,
        )
        self.control_window: control_window.ControlWindow = (
            control_window.ControlWindow(
                self.workspace.playback_page,
                self._toggle_playback,
                self._set_playback_speed,
                self._reverse_playback,
                on_step_samples=self._step_samples,
                on_step_seconds=self._step_seconds,
                on_jump_to_start=self._jump_to_start,
                on_jump_to_end=self._jump_to_end,
                accelerator_parent=self.frame,
                state_parent=self.workspace.state_page,
            )
        )
        self.control_window.bind_time_entry(self.workspace.timeline_time_entry)
        self.workspace.set_playback_content(self.control_window.panel)
        self.workspace.set_state_content(self.control_window.state_panel)
        self.frame.SetMinSize(PLAYER_FRAME_MIN_SIZE)
        self.frame.SetSize(PLAYER_FRAME_SIZE)
        self.frame.Bind(wx.EVT_CLOSE, self._on_frame_close)

        self._timer: wx.Timer = wx.Timer(self.frame)
        self.frame.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self._last_tick_monotonic_s: float | None = None
        self._in_timer_tick = False
        self._started = False
        self._closed = False
        self._open_views: dict[str, _OpenView] = {}
        self._open_panels: dict[str, _OpenView] = {}

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
                try:
                    signal.signal(signal.SIGINT, previous_sigint_handler)
                finally:
                    self._release_wx_resources()
                    # Dispose wx/Matplotlib wrapper cycles before wx teardown at exit.
                    gc.collect()

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
        self.workspace.draw_initial_graphs()
        if not self._timer.Start(self._tick_interval_ms):
            raise RuntimeError("could not start the wx playback timer")

    def close(self) -> None:
        """Close all playback windows and stop the wx timer."""
        if self._closed:
            return
        if not self.frame.Close(force=True) and not self._closed:
            raise RuntimeError("could not close the play-oem frame")

    def _release_wx_resources(self) -> None:
        """Drop wx wrappers and callbacks after the event loop has stopped."""
        self._view_registry.clear()
        self.control_window = cast(control_window.ControlWindow, None)
        self.workspace = cast(workspace.Workspace, None)
        self._timer = cast(wx.Timer, None)
        self.frame = cast(wx.Frame, None)
        self.wx_app = cast(wx.App, None)

    def open_speed_altitude_view(
        self, panel_id: str | None = None, stack: str = "middle"
    ) -> None:
        """Open or raise the speed and altitude plot."""
        self._open_view(
            "speed-altitude",
            lambda _panel: speed_altitude.SpeedAltitudeView(self.clock.t_start),
            panel_id=panel_id,
            stack=stack,
        )

    def open_rtn_view(self, panel_id: str | None = None, stack: str = "middle") -> None:
        """Open or raise the RTN position-delta plot."""
        self._open_view(
            "rtn",
            lambda _panel: rtn.RtnDeltaView(self.clock.t_start, self.object_name),
            panel_id=panel_id,
            stack=stack,
        )

    def open_angular_velocity_view(
        self, panel_id: str | None = None, stack: str = "middle"
    ) -> None:
        """Open or raise the angular-velocity plot."""
        self._open_view(
            "angular-velocity",
            lambda _panel: angular_velocity.AngularVelocityView(
                self.clock.t_start, self.object_name
            ),
            panel_id=panel_id,
            stack=stack,
        )

    def open_direction_change_view(
        self, panel_id: str | None = None, stack: str = "middle"
    ) -> None:
        """Open or raise the direction-change plot."""
        self._open_view(
            "direction-change",
            lambda _panel: direction_change.DirectionChangeView(
                self.clock.t_start, self.object_name
            ),
            panel_id=panel_id,
            stack=stack,
        )

    def open_distance_view(
        self, panel_id: str | None = None, stack: str = "middle"
    ) -> None:
        """Open or raise the geocentric-distance plot."""
        self._open_view(
            "distance",
            lambda _panel: distance.GeocentricDistanceView(
                self.clock.t_start, self.object_name
            ),
            panel_id=panel_id,
            stack=stack,
        )

    def open_state_components_view(
        self, panel_id: str | None = None, stack: str = "middle"
    ) -> None:
        """Open or raise the Cartesian state-components plot."""
        self._open_view(
            "state-components",
            lambda _panel: state_components.StateComponentsView(
                self.clock.t_start, self.frame_context
            ),
            panel_id=panel_id,
            stack=stack,
        )

    def open_trajectory_view(
        self, panel_id: str | None = None, stack: str = "middle"
    ) -> None:
        """Open or raise the selected 3D orbit backend."""
        if self._selected_3d_backend == "matplotlib":
            self._open_matplotlib_trajectory_view(panel_id, stack)
            return

        try:
            self._open_view(
                "trajectory-3d",
                lambda panel: trajectory3d_selection.create_vtk_view(
                    panel,
                    self.cursor,
                    self.object_name,
                    self.frame_context,
                    lambda: self.clock.rate,
                ),
                panel_id=panel_id,
                stack=stack,
            )
        except trajectory3d_selection.VTKBackendUnavailableError as error:
            if self._requested_3d_backend == "vtk":
                raise RuntimeError(
                    "the requested VTK 3D backend is unavailable: "
                    f"{error}. Install it with "
                    '`pip install "ephem-toolkit[playback,vtk]"`.'
                ) from error
            print(
                "Warning: VTK 3D backend is unavailable "
                f"({error}); falling back to Matplotlib.",
                file=sys.stderr,
            )
            self._set_3d_backend("matplotlib")
            self._open_matplotlib_trajectory_view(panel_id, stack)
            return

        self._set_3d_backend("vtk")

    def _open_matplotlib_trajectory_view(
        self, panel_id: str | None = None, stack: str = "middle"
    ) -> None:
        self._open_view(
            "trajectory-3d",
            lambda _panel: trajectory3d.Trajectory3DView(
                self.cursor,
                self.object_name,
                self.frame_context,
            ),
            panel_id=panel_id,
            stack=stack,
        )
        self._set_3d_backend("matplotlib")

    def _set_3d_backend(self, backend_name: str) -> None:
        self._selected_3d_backend = backend_name
        self.frame.SetTitle(f"play-oem (3D backend: {backend_name})")

    def open_view(self, name: str) -> None:
        self._view_registry.open_view(name)

    def open_panel_view(self, name: str, panel_id: str, stack: str = "middle") -> None:
        """Open a view in the graph-panel instance identified by ``panel_id``."""
        if name == EMPTY_GRAPH_VIEW:
            self._open_view(
                name,
                _EmptyGraphView,
                panel_id=panel_id,
                stack=stack,
            )
            return
        if name not in self._view_registry.registered_views:
            raise ValueError(f"unknown view name: {name!r}")
        openers = {
            "trajectory-3d": self.open_trajectory_view,
            "speed-altitude": self.open_speed_altitude_view,
            "state-components": self.open_state_components_view,
            "rtn": self.open_rtn_view,
            "angular-velocity": self.open_angular_velocity_view,
            "direction-change": self.open_direction_change_view,
            "distance": self.open_distance_view,
        }
        openers[name](panel_id=panel_id, stack=stack)

    def _add_graph_panel(self, stack: str) -> None:
        try:
            self.open_panel_view(EMPTY_GRAPH_VIEW, uuid4().hex, stack)
        except Exception as error:
            wx.MessageBox(
                f"Could not add a graph panel: {error}",
                "Graph panel error",
                wx.OK | wx.ICON_ERROR,
                self.frame,
            )

    def _select_panel_view(self, name: str, panel_id: str, stack: str) -> None:
        try:
            self.open_panel_view(name, panel_id, stack)
        except Exception as error:
            wx.MessageBox(
                f"Could not create {self._panel_view_label(name)}: {error}",
                "Graph view error",
                wx.OK | wx.ICON_ERROR,
                self.frame,
            )

    def _move_panel(self, panel_id: str, offset: int) -> None:
        opened = self._open_panels.get(panel_id)
        if opened is not None:
            self.workspace.move_graph_panel(opened.panel, opened.stack, offset)

    def _duplicate_panel(self, panel_id: str) -> None:
        opened = self._open_panels.get(panel_id)
        if opened is None:
            return
        try:
            self.open_panel_view(opened.view_name, uuid4().hex, opened.stack)
        except Exception as error:
            wx.MessageBox(
                f"Could not duplicate graph panel: {error}",
                "Graph panel error",
                wx.OK | wx.ICON_ERROR,
                self.frame,
            )

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

    def _timeline_tooltip_at(self, progress: float) -> str:
        """Format the UTC time at a timeline position for its hover tooltip."""
        epoch_s = self.clock.t_start + progress * (
            self.clock.t_end - self.clock.t_start
        )
        # Keep hover text compact; the persistent readouts retain fractions.
        return time_utils.datetime_to_iso8601(
            time_utils.tt_s_to_datetime(epoch_s), fractional_second_places=0
        )

    def _set_playback_speed(self, speed: float) -> None:
        self.clock.set_speed(speed)
        self._update_time_display()

    def _set_transport_rate(self, rate: float) -> None:
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
            self.workspace.transport_buttons[direction * 1000.0].SetFocus()
        elif base_speed >= 100.0:
            self.workspace.transport_buttons[direction * 100.0].SetFocus()
        self._update_time_display()

    def _play_reverse_at_current_speed(self) -> None:
        self.clock.set_direction(-1)
        self.clock.play()
        self._update_time_display()

    def _play_forward_at_current_speed(self) -> None:
        self.clock.set_direction(1)
        self.clock.play()
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

    def close_view(self, name: str) -> None:
        """Close the default panel instance for a registered view."""
        opened = self._open_views.get(name)
        if opened is not None:
            self.close_panel(opened.panel_id)

    def close_panel(self, panel_id: str) -> None:
        """Close one graph-panel instance by its stable identifier."""
        self._dispose_open_view(panel_id)

    def _open_view(
        self,
        name: str,
        create_view: Callable[[wx.Window], base.View],
        *,
        panel_id: str | None = None,
        stack: str = "middle",
    ) -> None:
        if self._closed:
            raise RuntimeError("cannot open a view in a closed PlayerApp")
        if stack == "middle":
            stack_parent = self.workspace.middle_stack
        elif stack == "right":
            stack_parent = self.workspace.right_stack
        else:
            raise ValueError(f"unknown graph stack {stack!r}")

        is_default_instance = panel_id is None
        replacing: _OpenView | None = None
        if is_default_instance:
            existing = self._open_views.get(name)
            if existing is not None:
                existing.panel.SetFocus()
                return
            panel_id = uuid4().hex
        elif not panel_id:
            raise ValueError("panel_id cannot be empty")
        else:
            existing = self._open_panels.get(panel_id)
            if existing is not None:
                if existing.view_name == name:
                    existing.panel.SetFocus()
                    return
                replacing = existing

        if panel_id in self._open_panels and replacing is None:
            raise ValueError(f"panel instance already exists: {panel_id!r}")

        panel: GraphPanelHost | None = None
        panel_inserted = False
        view: base.View | None = None
        canvas: FigureCanvasWxAgg | None = None
        toolbar: NavigationToolbar2WxAgg | None = None
        click_callback_id: int | None = None
        unsubscribe: Callable[[], None] | None = None
        try:
            panel = GraphPanelHost(
                stack_parent,
                self._panel_view_label(name),
                lambda: self.close_panel(panel_id),
                is_visible=lambda: panel is not None
                and self.workspace.is_graph_panel_visible(panel),
                on_redraw_request=self.workspace.queue_graph_redraw,
                panel_id=panel_id,
                view_choices=self._panel_view_choices,
                selected_view=name,
                on_view_selected=lambda selected: self._select_panel_view(
                    selected, panel_id, stack
                ),
                on_move_up=lambda: self._move_panel(panel_id, -1),
                on_move_down=lambda: self._move_panel(panel_id, 1),
                on_duplicate=lambda: self._duplicate_panel(panel_id),
            )
            if replacing is None:
                self.workspace.add_graph_panel(panel, stack=stack)
            else:
                self.workspace.replace_graph_panel(replacing.panel, panel, stack=stack)
            panel_inserted = True
            view = create_view(panel)
            content = view.build(self.series, self.time_unit)
            view.update(self.clock.t_now)
            if isinstance(content, Figure):
                canvas = FigureCanvasWxAgg(panel, wx.ID_ANY, content)
                plot_toolbar = NavigationToolbar2WxAgg(canvas)
                plot_toolbar.Realize()
                toolbar = plot_toolbar
                panel.set_matplotlib_content(plot_toolbar, canvas)
                click_callback_id = canvas.mpl_connect(
                    "button_press_event",
                    lambda event: self._on_plot_click(event, plot_toolbar),
                )
            elif isinstance(content, wx.Window):
                panel.set_native_content(content)
            else:
                raise TypeError(
                    f"{name!r} view build returned unsupported content "
                    f"{type(content).__name__!r}"
                )

            def update_view(time_s: float) -> None:
                view.update(time_s)
                if panel is not None and canvas is not None:
                    panel.request_redraw()

            unsubscribe = (
                self.clock.subscribe(update_view)
                if name != EMPTY_GRAPH_VIEW
                else lambda: None
            )
            opened_state = _OpenView(
                panel_id,
                name,
                stack,
                panel,
                view,
                unsubscribe,
                canvas,
                toolbar,
                click_callback_id,
            )
            self.frame.Layout()
            panel.Layout()
            if isinstance(content, wx.Window) and name == "trajectory-3d":
                trajectory3d_selection.validate_vtk_render_context(view)
            if canvas is not None:
                panel.request_redraw()
        except Exception:
            if replacing is None:
                self._open_panels.pop(panel_id, None)
            if self._open_views.get(name) is not None:
                if self._open_views[name].panel_id == panel_id:
                    self._open_views.pop(name)
            if canvas is not None and click_callback_id is not None:
                canvas.mpl_disconnect(click_callback_id)
            if unsubscribe is not None:
                unsubscribe()
            if view is not None:
                view.close()
            if panel is not None:
                try:
                    if panel_inserted:
                        if replacing is None:
                            self.workspace.remove_graph_panel(panel, stack=stack)
                        else:
                            self.workspace.replace_graph_panel(
                                panel, replacing.panel, stack=stack
                            )
                finally:
                    panel.Destroy()
            raise
        self._open_panels[panel_id] = opened_state
        if is_default_instance:
            self._open_views[name] = opened_state
        if replacing is not None:
            try:
                self._release_open_view_resources(replacing)
            finally:
                replacing.panel.Destroy()

    def _on_plot_click(
        self, event: MouseEvent, toolbar: NavigationToolbar2WxAgg
    ) -> None:
        if (
            getattr(toolbar, "mode", "")
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

    def _panel_view_label(self, name: str) -> str:
        if name == EMPTY_GRAPH_VIEW:
            return EMPTY_GRAPH_LABEL
        return self._view_registry.label_for(name)

    def _dispose_open_view(self, panel_id: str) -> None:
        opened = self._open_panels.pop(panel_id, None)
        if opened is None:
            return
        try:
            self._release_open_view_resources(opened)
        finally:
            try:
                self.workspace.remove_graph_panel(opened.panel, stack=opened.stack)
            finally:
                opened.panel.Destroy()

    def _release_open_view_resources(self, opened: _OpenView) -> None:
        if self._open_views.get(opened.view_name) is opened:
            self._open_views.pop(opened.view_name)
        if opened.canvas is not None and opened.click_callback_id is not None:
            opened.canvas.mpl_disconnect(opened.click_callback_id)
        opened.unsubscribe()
        opened.view.close()

    def _on_frame_close(self, event: wx.CloseEvent) -> None:
        if not self._closed:
            self._closed = True
            self._timer.Stop()
            try:
                for panel_id in tuple(self._open_panels):
                    self.close_panel(panel_id)
            finally:
                self.workspace.close()
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
            self._in_timer_tick = True
            try:
                self.clock.tick(elapsed_s)
            finally:
                self._in_timer_tick = False
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
            self.clock.playing,
            self.clock.rate,
        )
        self.workspace.update_timeline(progress, utc_timestamp)
        self.workspace.update_transport_state(self.clock.playing, self.clock.rate)
        self.control_window.update_current_state(self.cursor.lookup(self.clock.t_now))

    def _handle_sigint(self, _signum: int, _frame: object) -> None:
        wx.CallAfter(self.close)
