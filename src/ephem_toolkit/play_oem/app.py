"""Tk application shell and playback timer."""

from __future__ import annotations

from datetime import timedelta
import math
import signal
import tempfile
import time
import tkinter as tk
from collections.abc import Callable, Sequence

from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import ephem_toolkit.core.time_utils as time_utils

from .clock import PlaybackClock
from .control_window import ControlWindow
from .cursor import CursorState, OemCursor
from .series import OrbitSeries
from .time_unit import TimeUnit
from .views.raster import RasterImage
from .views.speed_altitude import SpeedAltitudeView
from .views.state_components import StateComponentsView
from .views.trajectory3d import Trajectory3DView, TrajectoryRaster
from .views.registry import ViewRegistry

DEFAULT_TICK_INTERVAL_MS = 33


class PlayerApp:
    """Own the Tk root, control window, playback clock and timer lifecycle."""

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
        root: tk.Tk | None = None,
    ) -> None:
        if tick_interval_ms < 1:
            raise ValueError("tick_interval_ms must be positive")
        self.clock = clock
        self.series = series
        self.time_unit = time_unit
        self.cursor = cursor
        self.object_name = object_name
        self.frame_context = frame_context
        self.root = tk.Tk() if root is None else root
        self._view_registry = ViewRegistry()
        self._view_registry.register_view(
            "trajectory-3d", lambda: self.open_trajectory_view()
        )
        self._view_registry.register_view(
            "speed-altitude", lambda: self.open_speed_altitude_view()
        )
        self._view_registry.register_view(
            "state-components", lambda: self.open_state_components_view()
        )
        self._plots = self._view_registry.expand(plots)
        self.control_window = ControlWindow(
            self.root,
            self.close,
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
        self.root.bind_all("<space>", self._on_space)
        self.root.bind_all("<KeyRelease-space>", self._on_space_release)
        self.root.bind_all("<KeyPress-r>", self._on_reverse_key)
        self.root.bind_all("<KeyPress-R>", self._on_reverse_key)
        self.root.bind_all("<KeyRelease-r>", self._on_reverse_key_release)
        self.root.bind_all("<KeyRelease-R>", self._on_reverse_key_release)
        self.root.bind_all("<Left>", self._on_previous_sample)
        self.root.bind_all("<Right>", self._on_next_sample)
        self.root.bind_all("<Shift-Left>", self._on_previous_minute)
        self.root.bind_all("<Shift-Right>", self._on_next_minute)
        self.root.bind_all("<Home>", self._on_jump_to_start)
        self.root.bind_all("<End>", self._on_jump_to_end)
        self._tick_interval_ms = tick_interval_ms
        self._last_tick: float | None = None
        self._timer_id: str | None = None
        self._started = False
        self._closed = False
        self._space_pressed = False
        self._reverse_key_pressed = False
        self._speed_altitude_view: SpeedAltitudeView | None = None
        self._speed_altitude_window: tk.Toplevel | None = None
        self._speed_altitude_canvas: FigureCanvasTkAgg | None = None
        self._speed_altitude_click_connection_id: int | None = None
        self._speed_altitude_raster: RasterImage | None = None
        self._speed_altitude_base_image: tk.PhotoImage | None = None
        self._speed_altitude_image: tk.PhotoImage | None = None
        self._speed_altitude_cursor_columns: tuple[int, ...] | None = None
        self._unsubscribe_speed_altitude: Callable[[], None] | None = None
        self._state_components_view: StateComponentsView | None = None
        self._state_components_window: tk.Toplevel | None = None
        self._state_components_canvas: FigureCanvasTkAgg | None = None
        self._state_components_click_connection_id: int | None = None
        self._state_components_raster: RasterImage | None = None
        self._state_components_base_image: tk.PhotoImage | None = None
        self._state_components_image: tk.PhotoImage | None = None
        self._state_components_cursor_columns: tuple[int, ...] | None = None
        self._unsubscribe_state_components: Callable[[], None] | None = None
        self._trajectory_view: Trajectory3DView | None = None
        self._trajectory_window: tk.Toplevel | None = None
        self._trajectory_canvas: FigureCanvasTkAgg | None = None
        self._trajectory_raster: TrajectoryRaster | None = None
        self._trajectory_base_image: tk.PhotoImage | None = None
        self._trajectory_image: tk.PhotoImage | None = None
        self._trajectory_cursor_pixel: tuple[int, int] | None = None
        self._unsubscribe_trajectory: Callable[[], None] | None = None

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
        self.root.update_idletasks()
        self.open_plots(self._plots)
        self._schedule_tick()

    def close(self) -> None:
        """Stop pending timer callbacks and destroy the application window."""
        if self._closed:
            return
        self._closed = True
        self.close_state_components_view()
        self.close_trajectory_view()
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

        patchlevel, tk_version = self._get_tk_version()
        view = SpeedAltitudeView(self.clock.t_start)
        figure = view.build(self.series, self.time_unit)
        view.update(self.clock.t_now)
        window = tk.Toplevel(self.root)
        window.title(
            "Speed / Altitude"
            if tk_version >= (8, 6)
            else f"Speed / Altitude (Tk {patchlevel} raster view)"
        )
        canvas: FigureCanvasTkAgg | None = None
        raster: RasterImage | None = None
        base_image: tk.PhotoImage | None = None
        image: tk.PhotoImage | None = None
        if tk_version >= (8, 6):
            canvas = FigureCanvasTkAgg(figure, master=window)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            self._speed_altitude_click_connection_id = canvas.mpl_connect(
                "button_press_event",
                self._on_speed_altitude_plot_click,
            )
        else:
            speed_raster = view.render_raster()
            raster = speed_raster
            base_image = self._load_legacy_ppm_image(window, speed_raster.ppm_data)
            image = tk.PhotoImage(
                master=window,
                width=speed_raster.width,
                height=speed_raster.height,
            )
            image.tk.call(str(image), "copy", str(base_image))
            plot_button = tk.Button(
                window,
                image=image,
                relief="flat",
                borderwidth=0,
                highlightthickness=0,
                padx=0,
                pady=0,
                takefocus=False,
            )
            plot_button.pack(anchor="w", padx=12)
            plot_button.bind(
                "<Button-1>",
                lambda event: self._on_legacy_plot_click(event, speed_raster),
            )
        window.update_idletasks()
        if canvas is not None:
            canvas.draw()
        window.protocol("WM_DELETE_WINDOW", self.close_speed_altitude_view)
        self._speed_altitude_view = view
        self._speed_altitude_window = window
        self._speed_altitude_canvas = canvas
        self._speed_altitude_raster = raster
        self._speed_altitude_base_image = base_image
        self._speed_altitude_image = image
        self._speed_altitude_cursor_columns = None
        self._unsubscribe_speed_altitude = self.clock.subscribe(
            self._update_speed_altitude_view
        )
        if raster is not None:
            self._update_legacy_raster_cursor(self.clock.t_now)

    def open_state_components_view(self) -> None:
        """Open or raise the synchronized Cartesian state-components view."""
        if self._state_components_window is not None:
            self._state_components_window.lift()
            return

        patchlevel, tk_version = self._get_tk_version()
        view = StateComponentsView(self.clock.t_start, self.frame_context)
        figure = view.build(self.series, self.time_unit)
        view.update(self.clock.t_now)
        window = tk.Toplevel(self.root)
        window.title(
            "State Components"
            if tk_version >= (8, 6)
            else f"State Components (Tk {patchlevel} raster view)"
        )
        canvas: FigureCanvasTkAgg | None = None
        raster: RasterImage | None = None
        base_image: tk.PhotoImage | None = None
        image: tk.PhotoImage | None = None
        if tk_version >= (8, 6):
            canvas = FigureCanvasTkAgg(figure, master=window)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            self._state_components_click_connection_id = canvas.mpl_connect(
                "button_press_event",
                self._on_state_components_plot_click,
            )
        else:
            state_raster = view.render_raster()
            raster = state_raster
            base_image = self._load_legacy_ppm_image(window, state_raster.ppm_data)
            image = tk.PhotoImage(
                master=window,
                width=state_raster.width,
                height=state_raster.height,
            )
            image.tk.call(str(image), "copy", str(base_image))
            plot_button = tk.Button(
                window,
                image=image,
                relief="flat",
                borderwidth=0,
                highlightthickness=0,
                padx=0,
                pady=0,
                takefocus=False,
            )
            plot_button.pack(anchor="w", padx=12)
            plot_button.bind(
                "<Button-1>",
                lambda event: self._on_legacy_state_components_click(
                    event, state_raster
                ),
            )
        window.update_idletasks()
        if canvas is not None:
            canvas.draw()
        window.protocol("WM_DELETE_WINDOW", self.close_state_components_view)
        self._state_components_view = view
        self._state_components_window = window
        self._state_components_canvas = canvas
        self._state_components_raster = raster
        self._state_components_base_image = base_image
        self._state_components_image = image
        self._state_components_cursor_columns = None
        self._unsubscribe_state_components = self.clock.subscribe(
            self._update_state_components_view
        )
        if raster is not None:
            self._update_legacy_state_components_cursor(self.clock.t_now)

    def open_trajectory_view(self) -> None:
        """Open or raise the 3D orbit view."""
        if self._trajectory_window is not None:
            self._trajectory_window.lift()
            return

        patchlevel, tk_version = self._get_tk_version()
        view = Trajectory3DView(
            self.cursor,
            self.object_name,
            self.frame_context,
        )
        figure = view.build(self.series, self.time_unit)
        initial_state = self.cursor.lookup(self.clock.t_now)
        view.update_cursor(initial_state)
        window = tk.Toplevel(self.root)
        window.title(
            "3D Orbit"
            if tk_version >= (8, 6)
            else f"3D Orbit (Tk {patchlevel} raster view)"
        )
        canvas: FigureCanvasTkAgg | None = None
        raster: TrajectoryRaster | None = None
        base_image: tk.PhotoImage | None = None
        image: tk.PhotoImage | None = None
        if tk_version >= (8, 6):
            canvas = FigureCanvasTkAgg(figure, master=window)
            canvas.get_tk_widget().pack(fill="both", expand=True)
        else:
            raster = view.render_raster()
            base_image = self._load_legacy_ppm_image(window, raster.ppm_data)
            image = tk.PhotoImage(
                master=window,
                width=raster.width,
                height=raster.height,
            )
            image.tk.call(str(image), "copy", str(base_image))
            plot_button = tk.Button(
                window,
                image=image,
                relief="flat",
                borderwidth=0,
                highlightthickness=0,
                padx=0,
                pady=0,
                takefocus=False,
            )
            plot_button.pack(anchor="w", padx=12)
        window.update_idletasks()
        if canvas is not None:
            canvas.draw()
        window.protocol("WM_DELETE_WINDOW", self.close_trajectory_view)
        self._trajectory_view = view
        self._trajectory_window = window
        self._trajectory_canvas = canvas
        self._trajectory_raster = raster
        self._trajectory_base_image = base_image
        self._trajectory_image = image
        self._trajectory_cursor_pixel = None
        self._unsubscribe_trajectory = self.clock.subscribe(
            self._update_trajectory_view
        )
        if raster is not None:
            self._update_legacy_trajectory_cursor(initial_state)

    def open_overview(self) -> None:
        """Open or raise the synchronized trajectory and speed/altitude views."""
        self.open_group("overview")

    def open_view(self, name: str) -> None:
        """Open or raise an individual registered plot."""
        self._view_registry.open_view(name)

    def open_group(self, name: str) -> None:
        """Open or raise every plot in a registered group."""
        self._view_registry.open_group(name)

    def open_plots(self, selection: Sequence[str]) -> None:
        """Open or raise a CLI selection of plots and groups."""
        self._view_registry.open(selection)

    def close_trajectory_view(self) -> None:
        """Close the 3D trajectory view and unsubscribe it from clock updates."""
        if self._trajectory_view is None:
            return
        view = self._trajectory_view
        window = self._trajectory_window
        unsubscribe = self._unsubscribe_trajectory
        self._trajectory_view = None
        self._trajectory_window = None
        self._trajectory_canvas = None
        self._trajectory_raster = None
        self._trajectory_base_image = None
        self._trajectory_image = None
        self._trajectory_cursor_pixel = None
        self._unsubscribe_trajectory = None
        if unsubscribe is not None:
            unsubscribe()
        view.close()
        if window is not None:
            window.destroy()

    def close_state_components_view(self) -> None:
        """Close the state-components view and unsubscribe it from clock updates."""
        if self._state_components_view is None:
            return
        view = self._state_components_view
        window = self._state_components_window
        unsubscribe = self._unsubscribe_state_components
        canvas = self._state_components_canvas
        click_connection_id = self._state_components_click_connection_id
        self._state_components_view = None
        self._state_components_window = None
        self._state_components_canvas = None
        self._state_components_click_connection_id = None
        self._state_components_raster = None
        self._state_components_base_image = None
        self._state_components_image = None
        self._state_components_cursor_columns = None
        self._unsubscribe_state_components = None
        if unsubscribe is not None:
            unsubscribe()
        if canvas is not None and click_connection_id is not None:
            canvas.mpl_disconnect(click_connection_id)
        view.close()
        if window is not None:
            window.destroy()

    def _get_tk_version(self) -> tuple[str, tuple[int, int]]:
        patchlevel = str(self.root.tk.call("info", "patchlevel"))
        try:
            tk_version = tuple(int(part) for part in patchlevel.split(".")[:2])
        except ValueError as exception:
            raise RuntimeError(
                f"could not determine Tcl/Tk version from {patchlevel!r}"
            ) from exception
        if len(tk_version) != 2:
            raise RuntimeError(
                f"could not determine Tcl/Tk version from {patchlevel!r}"
            )
        return patchlevel, tk_version

    def close_speed_altitude_view(self) -> None:
        """Close the speed and altitude plot, leaving the control window open."""
        if self._speed_altitude_view is None:
            return
        view = self._speed_altitude_view
        window = self._speed_altitude_window
        unsubscribe = self._unsubscribe_speed_altitude
        canvas = self._speed_altitude_canvas
        click_connection_id = self._speed_altitude_click_connection_id
        self._speed_altitude_view = None
        self._speed_altitude_window = None
        self._speed_altitude_canvas = None
        self._speed_altitude_click_connection_id = None
        self._speed_altitude_raster = None
        self._speed_altitude_base_image = None
        self._speed_altitude_image = None
        self._speed_altitude_cursor_columns = None
        self._unsubscribe_speed_altitude = None
        if unsubscribe is not None:
            unsubscribe()
        if canvas is not None and click_connection_id is not None:
            canvas.mpl_disconnect(click_connection_id)
        view.close()
        if window is not None:
            window.destroy()

    @staticmethod
    def _load_legacy_ppm_image(window: tk.Toplevel, ppm_data: bytes) -> tk.PhotoImage:
        with tempfile.NamedTemporaryFile(suffix=".ppm") as image_file:
            image_file.write(ppm_data)
            image_file.flush()
            return tk.PhotoImage(master=window, file=image_file.name)

    def _update_speed_altitude_view(self, t_s: float) -> None:
        view = self._speed_altitude_view
        if view is None:
            return
        view.update(t_s)
        if self._speed_altitude_canvas is not None:
            self._speed_altitude_canvas.draw_idle()
        elif self._speed_altitude_raster is not None:
            self._update_legacy_raster_cursor(t_s)

    def _update_state_components_view(self, t_s: float) -> None:
        view = self._state_components_view
        if view is None:
            return
        view.update(t_s)
        if self._state_components_canvas is not None:
            self._state_components_canvas.draw_idle()
        elif self._state_components_raster is not None:
            self._update_legacy_state_components_cursor(t_s)

    def _update_trajectory_view(self, t_s: float) -> None:
        view = self._trajectory_view
        if view is None:
            return
        cursor_state = self.cursor.lookup(t_s)
        view.update_cursor(cursor_state)
        if self._trajectory_canvas is not None:
            self._trajectory_canvas.draw_idle()
        elif self._trajectory_raster is not None:
            self._update_legacy_trajectory_cursor(cursor_state)

    def _update_legacy_raster_cursor(self, t_s: float) -> None:
        raster = self._speed_altitude_raster
        image = self._speed_altitude_image
        base_image = self._speed_altitude_base_image
        if raster is None or image is None or base_image is None:
            raise RuntimeError("legacy raster plot images are not initialized")

        elapsed_time = (t_s - self.clock.t_start) / self.time_unit.get_divisor_s()
        columns = tuple(panel.cursor_column(elapsed_time) for panel in raster.panels)
        previous_columns = self._speed_altitude_cursor_columns
        if columns == previous_columns:
            return

        if previous_columns is not None:
            for old_x, panel in zip(previous_columns, raster.panels):
                image.tk.call(
                    str(image),
                    "copy",
                    str(base_image),
                    "-from",
                    old_x,
                    panel.plot_top,
                    old_x + 1,
                    panel.plot_bottom + 1,
                    "-to",
                    old_x,
                    panel.plot_top,
                )

        for cursor_x, panel in zip(columns, raster.panels):
            image.put(
                "#d62728",
                to=(
                    cursor_x,
                    panel.plot_top,
                    cursor_x + 1,
                    panel.plot_bottom + 1,
                ),
            )
        self._speed_altitude_cursor_columns = columns

    def _update_legacy_state_components_cursor(self, t_s: float) -> None:
        raster = self._state_components_raster
        image = self._state_components_image
        base_image = self._state_components_base_image
        if raster is None or image is None or base_image is None:
            raise RuntimeError("legacy state-components image is not initialized")

        elapsed_time = (t_s - self.clock.t_start) / self.time_unit.get_divisor_s()
        columns = tuple(panel.cursor_column(elapsed_time) for panel in raster.panels)
        previous_columns = self._state_components_cursor_columns
        if columns == previous_columns:
            return

        if previous_columns is not None:
            for panel, old_x in zip(raster.panels, previous_columns):
                image.tk.call(
                    str(image),
                    "copy",
                    str(base_image),
                    "-from",
                    old_x,
                    panel.plot_top,
                    old_x + 1,
                    panel.plot_bottom + 1,
                    "-to",
                    old_x,
                    panel.plot_top,
                )

        for panel, cursor_x in zip(raster.panels, columns):
            image.put(
                "#d62728",
                to=(
                    cursor_x,
                    panel.plot_top,
                    cursor_x + 1,
                    panel.plot_bottom + 1,
                ),
            )
        self._state_components_cursor_columns = columns

    def _update_legacy_trajectory_cursor(self, state: CursorState) -> None:
        view = self._trajectory_view
        image = self._trajectory_image
        base_image = self._trajectory_base_image
        if view is None or image is None or base_image is None:
            raise RuntimeError("legacy trajectory image is not initialized")

        if self._trajectory_cursor_pixel is not None:
            old_x, old_y = self._trajectory_cursor_pixel
            image.tk.call(
                str(image),
                "copy",
                str(base_image),
                "-from",
                old_x - 7,
                old_y - 7,
                old_x + 8,
                old_y + 8,
                "-to",
                old_x - 7,
                old_y - 7,
            )

        cursor_pixel = view.cursor_pixel(state)
        self._trajectory_cursor_pixel = cursor_pixel
        if cursor_pixel is None:
            return
        cursor_x, cursor_y = cursor_pixel
        image.put(
            "#303030", to=(cursor_x - 6, cursor_y - 6, cursor_x + 7, cursor_y + 7)
        )
        image.put(
            "#ffcc00", to=(cursor_x - 4, cursor_y - 4, cursor_x + 5, cursor_y + 5)
        )

    def _schedule_tick(self) -> None:
        if not self._closed:
            self._timer_id = self.root.after(self._tick_interval_ms, self._on_timer)

    def _toggle_playback(self) -> None:
        self.clock.toggle()
        self._update_time_display()

    def _on_space(self, event: tk.Event) -> str | None:
        if self._is_time_entry_event(event):
            return None
        if not self._space_pressed:
            self._space_pressed = True
            self._toggle_playback()
        return "break"

    def _on_space_release(self, event: tk.Event) -> str | None:
        self._space_pressed = False
        return None if self._is_time_entry_event(event) else "break"

    def _on_reverse_key(self, event: tk.Event) -> str | None:
        if self._is_time_entry_event(event):
            return None
        if not self._reverse_key_pressed:
            self._reverse_key_pressed = True
            self._reverse_playback()
        return "break"

    def _on_reverse_key_release(self, event: tk.Event) -> str | None:
        self._reverse_key_pressed = False
        return None if self._is_time_entry_event(event) else "break"

    def _is_time_entry_event(self, event: tk.Event | None) -> bool:
        return event is not None and event.widget is self.control_window.time_entry

    def _on_previous_sample(self, event: tk.Event) -> str | None:
        return self._handle_navigation_key(event, lambda: self._step_samples(-1))

    def _on_next_sample(self, event: tk.Event) -> str | None:
        return self._handle_navigation_key(event, lambda: self._step_samples(1))

    def _on_previous_minute(self, event: tk.Event) -> str | None:
        return self._handle_navigation_key(event, lambda: self._step_seconds(-60.0))

    def _on_next_minute(self, event: tk.Event) -> str | None:
        return self._handle_navigation_key(event, lambda: self._step_seconds(60.0))

    def _on_jump_to_start(self, event: tk.Event) -> str | None:
        return self._handle_navigation_key(event, self._jump_to_start)

    def _on_jump_to_end(self, event: tk.Event) -> str | None:
        return self._handle_navigation_key(event, self._jump_to_end)

    def _handle_navigation_key(
        self, event: tk.Event, action: Callable[[], None]
    ) -> str | None:
        if self._is_time_entry_event(event):
            return None
        action()
        return "break"

    def _step_samples(self, count: int) -> None:
        self.clock.step_samples(count)
        self._update_time_display()

    def _step_seconds(self, amount: float) -> None:
        self.clock.step(amount)
        self._update_time_display()

    def _jump_to_start(self) -> None:
        self.clock.seek(self.clock.t_start)
        self._update_time_display()

    def _jump_to_end(self) -> None:
        self.clock.seek(self.clock.t_end)
        self._update_time_display()

    def _seek_to_time(self, value: str) -> None:
        try:
            parsed_time = time_utils.parse_time_or_duration(value)
            if isinstance(parsed_time, timedelta):
                target_time = self.clock.t_start + parsed_time.total_seconds()
            else:
                target_time = time_utils.datetime_to_tt_s(parsed_time)
            if not self.clock.t_start <= target_time <= self.clock.t_end:
                raise ValueError("time is outside the OEM timeline")
        except (OverflowError, ValueError) as error:
            self.control_window.show_time_error(str(error))
            return

        self.clock.seek(target_time)
        self.control_window.clear_time_error()
        self._update_time_display()

    def _on_speed_altitude_plot_click(self, event: MouseEvent) -> None:
        if event.button != 1:
            return
        if event.inaxes is None:
            return
        xdata = event.xdata
        if xdata is None or not math.isfinite(xdata):
            return
        canvas = self._speed_altitude_canvas
        if canvas is None or self._navigation_mode_active(canvas):
            return
        self._seek_to_elapsed_time(float(xdata))

    def _on_state_components_plot_click(self, event: MouseEvent) -> None:
        if event.button != 1 or event.inaxes is None:
            return
        xdata = event.xdata
        if xdata is None or not math.isfinite(xdata):
            return
        canvas = self._state_components_canvas
        if canvas is None or self._navigation_mode_active(canvas):
            return
        self._seek_to_elapsed_time(float(xdata))

    def _on_legacy_plot_click(self, event: tk.Event, raster: RasterImage) -> None:
        for panel in raster.panels:
            if panel.contains_plot_point(event.x, event.y):
                self._seek_to_elapsed_time(panel.elapsed_at(event.x))
                return

    def _on_legacy_state_components_click(
        self, event: tk.Event, raster: RasterImage
    ) -> None:
        for panel in raster.panels:
            if panel.contains_plot_point(event.x, event.y):
                self._seek_to_elapsed_time(panel.elapsed_at(event.x))
                return

    def _seek_to_elapsed_time(self, elapsed_time: float) -> None:
        target_time = self.clock.t_start + elapsed_time * self.time_unit.get_divisor_s()
        self.clock.seek(target_time)
        self._update_time_display()

    @staticmethod
    def _navigation_mode_active(canvas: FigureCanvasTkAgg) -> bool:
        toolbar = getattr(canvas, "toolbar", None)
        if toolbar is None:
            manager = getattr(canvas, "manager", None)
            toolbar = getattr(manager, "toolbar", None)
        return bool(getattr(toolbar, "mode", None))

    def _seek_to_fraction(self, progress: float) -> None:
        span = self.clock.t_end - self.clock.t_start
        self.clock.seek(self.clock.t_start + progress * span)
        self._update_time_display()

    def _set_playback_speed(self, speed: float) -> None:
        self.clock.set_speed(speed)
        self._update_time_display()

    def _reverse_playback(self) -> None:
        self.clock.reverse()
        self._update_time_display()

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
        span = self.clock.t_end - self.clock.t_start
        progress = (
            0.0 if span == 0.0 else (self.clock.t_now - self.clock.t_start) / span
        )
        self.control_window.update_playback_state(
            f"Elapsed: {elapsed_s:.3f} s\nUTC: {utc_time}",
            progress,
            self.clock.playing,
            self.clock.rate,
        )

    def _handle_sigint(self, _signum: int, _frame: object) -> None:
        self.close()
