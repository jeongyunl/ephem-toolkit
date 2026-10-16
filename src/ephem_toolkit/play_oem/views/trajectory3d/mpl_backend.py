"""Matplotlib 3D trajectory view and its legacy-Tk raster representation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import proj3d
from mpl_toolkits.mplot3d.axes3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Path3DCollection

from ...cursor import CursorState, OemCursor
from ...series import OrbitSeries
from ...time_unit import TimeUnit


@dataclass(frozen=True)
class TrajectoryRaster:
    """PPM pixels for displaying a static trajectory on legacy Tk."""

    width: int
    height: int
    ppm_data: bytes


class Trajectory3DView:
    """Plot the orbit path and move a marker from direction-independent cursor state."""

    name = "trajectory3d"

    def __init__(
        self,
        cursor: OemCursor,
        object_name: str,
        frame_context: str,
    ) -> None:
        self._cursor = cursor
        self._object_name = object_name
        self._frame_context = frame_context
        self._figure: Figure | None = None
        self._axes: Axes3D | None = None
        self._cursor_artist: Path3DCollection | None = None
        self._cursor_position_km: tuple[float, float, float] | None = None
        self._raster_size: tuple[int, int] | None = None

    def build(self, series: OrbitSeries, _time_unit: TimeUnit) -> Figure:
        if self._figure is not None:
            raise RuntimeError("3D trajectory view has already been built")
        if series.position_km.ndim != 2 or series.position_km.shape[1] != 3:
            raise ValueError("position_km must have shape (N, 3)")
        if len(series.position_km) == 0:
            raise ValueError("cannot plot an empty trajectory")

        figure = Figure(figsize=(8, 6), constrained_layout=True)
        axes = figure.add_subplot(1, 1, 1, projection="3d")
        positions = series.position_km
        axes.plot(
            positions[:, 0],
            positions[:, 1],
            positions[:, 2],
            linewidth=1.8,
            label="Orbit",
        )
        axes.scatter(
            [positions[0, 0]],
            [positions[0, 1]],
            [positions[0, 2]],
            c="green",
            s=55,
            marker="o",
            label="Start",
        )
        axes.scatter(
            [positions[-1, 0]],
            [positions[-1, 1]],
            [positions[-1, 2]],
            c="red",
            s=65,
            marker="x",
            label="End",
        )
        initial_state = self._cursor.lookup(self._cursor.t_start)
        self._cursor_artist = axes.scatter(
            [],
            [],
            [],
            c="#ffcc00",
            edgecolors="black",
            s=55,
            marker="o",
            depthshade=False,
            label="Playback cursor",
        )
        axes.set_xlabel("X (km)")
        axes.set_ylabel("Y (km)")
        axes.set_zlabel("Z (km)")
        axes.set_title("3D Orbit Trajectory")
        axes.legend(loc="upper left")
        self._set_equal_limits(axes, positions)
        figure.suptitle(
            " | ".join(
                part for part in (self._object_name, self._frame_context) if part
            )
        )
        self._figure = figure
        self._axes = axes
        self.update_cursor(initial_state)
        return figure

    def update(self, t_s: float) -> None:
        """Resolve and display the cursor state at an absolute OEM time."""
        self.update_cursor(self._cursor.lookup(t_s))

    def update_cursor(self, state: CursorState) -> None:
        """Move or hide the satellite marker from a resolved cursor state."""
        if self._cursor_artist is None:
            raise RuntimeError("3D trajectory view has not been built")
        if state.r_km is None:
            self._cursor_artist.set_visible(False)
            self._cursor_position_km = None
            return

        position = tuple(float(value) for value in state.r_km)
        self._cursor_artist.set_offsets([[position[0], position[1]]])
        self._cursor_artist.set_3d_properties([position[2]], zdir="z")
        self._cursor_artist.set_visible(True)
        self._cursor_position_km = position

    def render_raster(self) -> TrajectoryRaster:
        """Render a marker-free PPM base image for the legacy Tk path."""
        if self._figure is None or self._cursor_artist is None:
            raise RuntimeError("3D trajectory view has not been built")
        marker_visible = self._cursor_artist.get_visible()
        self._cursor_artist.set_visible(False)
        try:
            canvas = FigureCanvasAgg(self._figure)
            canvas.draw()
            width, height = canvas.get_width_height()
            rgb_pixels = np.asarray(canvas.buffer_rgba(), dtype=np.uint8)[:, :, :3]
            self._raster_size = (width, height)
            ppm_header = f"P6\n{width} {height}\n255\n".encode("ascii")
            return TrajectoryRaster(
                width,
                height,
                ppm_header + np.ascontiguousarray(rgb_pixels).tobytes(),
            )
        finally:
            self._cursor_artist.set_visible(marker_visible)

    def cursor_pixel(self, state: CursorState) -> tuple[int, int] | None:
        """Project a cursor position into the raster image's top-left pixel space."""
        if self._axes is None or self._raster_size is None:
            raise RuntimeError("trajectory raster has not been rendered")
        if state.r_km is None:
            return None

        projected_x, projected_y, _ = proj3d.proj_transform(
            float(state.r_km[0]),
            float(state.r_km[1]),
            float(state.r_km[2]),
            self._axes.get_proj(),
        )
        display_x, display_y = self._axes.transData.transform(
            (projected_x, projected_y)
        )
        width, height = self._raster_size
        x = min(max(round(display_x), 7), width - 8)
        y = min(max(height - 1 - round(display_y), 7), height - 8)
        return x, y

    def close(self) -> None:
        if self._figure is not None:
            self._figure.clear()
        self._figure = None
        self._axes = None
        self._cursor_artist = None
        self._cursor_position_km = None
        self._raster_size = None

    @staticmethod
    def _set_equal_limits(axes: Axes3D, positions_km: np.ndarray) -> None:
        lower = np.min(positions_km, axis=0)
        upper = np.max(positions_km, axis=0)
        center = (lower + upper) / 2.0
        span = float(np.max(upper - lower))
        if span == 0.0:
            span = max(float(np.max(np.abs(center))) * 0.1, 1.0)
        half_span = span * 0.55
        axes.set_xlim(center[0] - half_span, center[0] + half_span)
        axes.set_ylim(center[1] - half_span, center[1] + half_span)
        axes.set_zlim(center[2] - half_span, center[2] + half_span)
        axes.set_box_aspect((1.0, 1.0, 1.0))
