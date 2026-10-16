"""Tk application shell and playback timer."""

from __future__ import annotations

import signal
import tempfile
import time
import tkinter as tk
from collections.abc import Callable

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import ephem_toolkit.core.time_utils as time_utils

from .clock import PlaybackClock
from .control_window import ControlWindow
from .cursor import CursorState, OemCursor
from .series import OrbitSeries
from .time_unit import TimeUnit
from .views.speed_altitude import RasterPlot, SpeedAltitudeView
from .views.trajectory3d import Trajectory3DView, TrajectoryRaster

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
        self.control_window = ControlWindow(
            self.root,
            self.close,
            self.open_overview,
            self._toggle_playback,
            self._seek_to_fraction,
            self._set_playback_speed,
            timeline_enabled=clock.t_start < clock.t_end,
        )
        self.root.bind_all("<space>", self._on_space)
        self.root.bind_all("<KeyRelease-space>", self._on_space_release)
        self._tick_interval_ms = tick_interval_ms
        self._last_tick: float | None = None
        self._timer_id: str | None = None
        self._started = False
        self._closed = False
        self._space_pressed = False
        self._speed_altitude_view: SpeedAltitudeView | None = None
        self._speed_altitude_window: tk.Toplevel | None = None
        self._speed_altitude_canvas: FigureCanvasTkAgg | None = None
        self._speed_altitude_rasters: tuple[RasterPlot, ...] = ()
        self._speed_altitude_base_images: tuple[tk.PhotoImage, ...] = ()
        self._speed_altitude_images: tuple[tk.PhotoImage, ...] = ()
        self._speed_altitude_cursor_x: int | None = None
        self._unsubscribe_speed_altitude: Callable[[], None] | None = None
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
        self.open_overview()
        self._schedule_tick()

    def close(self) -> None:
        """Stop pending timer callbacks and destroy the application window."""
        if self._closed:
            return
        self._closed = True
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
        rasters: tuple[RasterPlot, ...] = ()
        base_images: tuple[tk.PhotoImage, ...] = ()
        images: tuple[tk.PhotoImage, ...] = ()
        if tk_version >= (8, 6):
            canvas = FigureCanvasTkAgg(figure, master=window)
            canvas.get_tk_widget().pack(fill="both", expand=True)
        else:
            rasters = view.render_rasters()
            base_images_list: list[tk.PhotoImage] = []
            images_list: list[tk.PhotoImage] = []
            titles = ("Speed (km/s)", "Altitude (km)")
            for title, raster in zip(titles, rasters):
                self._pack_legacy_plot_caption(window, title)
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
                base_images_list.append(base_image)
                images_list.append(image)
            self._pack_legacy_plot_caption(window, self.time_unit.get_axis_label())
            base_images = tuple(base_images_list)
            images = tuple(images_list)
        window.update_idletasks()
        if canvas is not None:
            canvas.draw()
        window.protocol("WM_DELETE_WINDOW", self.close_speed_altitude_view)
        self._speed_altitude_view = view
        self._speed_altitude_window = window
        self._speed_altitude_canvas = canvas
        self._speed_altitude_rasters = rasters
        self._speed_altitude_base_images = base_images
        self._speed_altitude_images = images
        self._unsubscribe_speed_altitude = self.clock.subscribe(
            self._update_speed_altitude_view
        )
        if rasters:
            self._update_legacy_raster_cursor(self.clock.t_now)

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
        self.open_trajectory_view()
        self.open_speed_altitude_view()

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
        self._speed_altitude_view = None
        self._speed_altitude_window = None
        self._speed_altitude_canvas = None
        self._speed_altitude_rasters = ()
        self._speed_altitude_base_images = ()
        self._speed_altitude_images = ()
        self._speed_altitude_cursor_x = None
        self._unsubscribe_speed_altitude = None
        if unsubscribe is not None:
            unsubscribe()
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
        elif self._speed_altitude_rasters:
            self._update_legacy_raster_cursor(t_s)

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

    def _pack_legacy_plot_caption(self, window: tk.Toplevel, text: str) -> None:
        caption = tk.Button(
            window,
            text=text,
            anchor="w",
            height=1,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
            background="white",
            foreground="black",
        )
        caption.pack(fill="x", padx=12, pady=(4, 0))

    def _update_legacy_raster_cursor(self, t_s: float) -> None:
        if (
            not self._speed_altitude_rasters
            or len(self._speed_altitude_rasters) != len(self._speed_altitude_images)
            or len(self._speed_altitude_rasters)
            != len(self._speed_altitude_base_images)
        ):
            raise RuntimeError("legacy raster plot images are not initialized")

        raster = self._speed_altitude_rasters[0]
        elapsed_time = (t_s - self.clock.t_start) / self.time_unit.get_divisor_s()
        cursor_x = raster.cursor_column(elapsed_time)
        if cursor_x == self._speed_altitude_cursor_x:
            return

        if self._speed_altitude_cursor_x is not None:
            old_x = self._speed_altitude_cursor_x
            for image, base_image, panel in zip(
                self._speed_altitude_images,
                self._speed_altitude_base_images,
                self._speed_altitude_rasters,
            ):
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

        for image, panel in zip(
            self._speed_altitude_images, self._speed_altitude_rasters
        ):
            image.put(
                "#d62728",
                to=(
                    cursor_x,
                    panel.plot_top,
                    cursor_x + 1,
                    panel.plot_bottom + 1,
                ),
            )
        self._speed_altitude_cursor_x = cursor_x

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

    def _on_space(self, _event: tk.Event) -> str:
        if not self._space_pressed:
            self._space_pressed = True
            self._toggle_playback()
        return "break"

    def _on_space_release(self, _event: tk.Event) -> str:
        self._space_pressed = False
        return "break"

    def _seek_to_fraction(self, progress: float) -> None:
        span = self.clock.t_end - self.clock.t_start
        self.clock.seek(self.clock.t_start + progress * span)
        self._update_time_display()

    def _set_playback_speed(self, speed: float) -> None:
        self.clock.set_speed(speed)
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
