"""Matplotlib 3D trajectory playback view."""

from __future__ import annotations

from typing import Any

import numpy as np
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Path3DCollection

from ... import cursor, series, time_unit
from ...time_range import ResolvedTimeRange
from ..plotting import MAX_MATPLOTLIB_3D_DISPLAY_POINTS, decimate_indices

CARTESIAN_COMPONENT_COUNT: int = 3
"""Number of Cartesian coordinates in a position vector."""
CURSOR_EDGE_COLOR: str = "black"
"""Edge color used for the playback cursor marker."""
CURSOR_MARKER_COLOR: str = "#ffcc00"
"""Face color used for the playback cursor marker."""
CURSOR_MARKER_SIZE: float = 55.0
"""Area of the playback cursor marker in points squared."""
DEGENERATE_SPAN_FRACTION: float = 0.1
"""Fraction of coordinate magnitude used for degenerate trajectories."""
END_MARKER_COLOR: str = "red"
"""Color used to identify the final orbit sample."""
END_MARKER_SIZE: float = 65.0
"""Area of the final-sample marker in points squared."""
EQUAL_AXIS_PADDING_FACTOR: float = 0.55
"""Half-span multiplier used to provide padding around the orbit."""
FIGURE_SIZE_INCHES: tuple[float, float] = (8.0, 6.0)
"""Default 3D trajectory figure size in inches."""
MINIMUM_AXIS_SPAN_KM: float = 1.0
"""Minimum axis span for a degenerate trajectory (km)."""
ORBIT_LINE_WIDTH: float = 1.8
"""Width of the orbit path line."""
START_MARKER_COLOR: str = "green"
"""Color used to identify the first orbit sample."""
START_MARKER_SIZE: float = 55.0
"""Area of the first-sample marker in points squared."""


class Trajectory3DView:
    """Plot the orbit path and move a marker from direction-independent cursor state."""

    name: str = "trajectory3d"

    def __init__(
        self,
        oem_cursor: cursor.OemCursor,
        object_name: str,
        frame_context: str,
    ) -> None:
        """Create a 3D trajectory view for one OEM cursor and object.

        Parameters
        ----------
        oem_cursor : cursor.OemCursor
            State lookup used to position the satellite marker.
        object_name : str
            Object name displayed in the figure title.
        frame_context : str
            Reference-frame and origin description displayed in the title.
        """
        self._cursor: cursor.OemCursor = oem_cursor
        self._object_name: str = object_name
        self._frame_context: str = frame_context
        self._figure: Figure | None = None
        # Matplotlib's 3D axes API is missing from the installed type stubs.
        self._axes: Any | None = None
        self._cursor_artist: Path3DCollection | None = None
        self._cursor_position_km: tuple[float, float, float] | None = None
        self._positions_km: np.ndarray | None = None
        self._sample_times_s: np.ndarray | None = None
        self._segment_ids: np.ndarray | None = None
        # The installed Matplotlib stubs type 3D plot lines as 2D Line2D.
        self._orbit_artists: list[tuple[int, Any]] = []
        self._start_artist = None
        self._end_artist = None
        self._range_bounds: ResolvedTimeRange | None = None
        self._range_applied = False
        self._current_time_s = oem_cursor.t_start

    def build(
        self,
        orbit_series: series.OrbitSeries,
        _time_unit: time_unit.TimeUnit,
    ) -> Figure:
        """Build a 3D orbit plot with start, end, and playback markers.

        Parameters
        ----------
        orbit_series : series.OrbitSeries
            Derived orbit position history in kilometers.
        _time_unit : time_unit.TimeUnit
            Display unit required by the shared view protocol; unused in 3D.

        Returns
        -------
        Figure
            Matplotlib figure containing the 3D orbit.

        Raises
        ------
        RuntimeError
            If this view has already been built.
        ValueError
            If the position history is empty or is not an N-by-3 array.
        """
        if self._figure is not None:
            raise RuntimeError("3D trajectory view has already been built")
        if (
            orbit_series.position_km.ndim != 2
            or orbit_series.position_km.shape[1] != CARTESIAN_COMPONENT_COUNT
        ):
            raise ValueError("position_km must have shape (N, 3)")
        if len(orbit_series.position_km) == 0:
            raise ValueError("cannot plot an empty trajectory")

        figure = Figure(figsize=FIGURE_SIZE_INCHES, constrained_layout=True)
        trajectory_axes = figure.add_subplot(1, 1, 1, projection="3d")
        positions_km = orbit_series.position_km
        self._positions_km = np.asarray(positions_km, dtype=float).copy()
        self._segment_ids = np.asarray(orbit_series.segment_ids, dtype=int).copy()
        self._sample_times_s = (
            self._cursor.t_start
            + orbit_series.elapsed_time * _time_unit.get_divisor_s()
        )
        for segment_id in np.unique(orbit_series.segment_ids):
            if segment_id < 0:
                continue
            mask = orbit_series.segment_ids == segment_id
            segment_positions = positions_km[mask]
            segment_positions = segment_positions[
                decimate_indices(segment_positions, MAX_MATPLOTLIB_3D_DISPLAY_POINTS)
            ]
            (artist,) = trajectory_axes.plot(
                segment_positions[:, 0],
                segment_positions[:, 1],
                segment_positions[:, 2],
                linewidth=ORBIT_LINE_WIDTH,
                label="Orbit",
            )
            self._orbit_artists.append((int(segment_id), artist))
        self._start_artist = trajectory_axes.scatter(
            [positions_km[0, 0]],
            [positions_km[0, 1]],
            [positions_km[0, 2]],
            c=START_MARKER_COLOR,
            s=START_MARKER_SIZE,
            marker="o",
            label="Start",
        )
        self._end_artist = trajectory_axes.scatter(
            [positions_km[-1, 0]],
            [positions_km[-1, 1]],
            [positions_km[-1, 2]],
            c=END_MARKER_COLOR,
            s=END_MARKER_SIZE,
            marker="x",
            label="End",
        )
        initial_state = self._cursor.lookup(self._cursor.t_start)
        self._cursor_artist = trajectory_axes.scatter(
            [],
            [],
            [],
            c=CURSOR_MARKER_COLOR,
            edgecolors=CURSOR_EDGE_COLOR,
            s=CURSOR_MARKER_SIZE,
            marker="o",
            depthshade=False,
            label="Playback cursor",
        )
        trajectory_axes.set_xlabel("X (km)")
        trajectory_axes.set_ylabel("Y (km)")
        trajectory_axes.set_zlabel("Z (km)")
        trajectory_axes.set_title("3D Orbit Trajectory")
        trajectory_axes.legend(loc="upper left")
        self._set_equal_limits(trajectory_axes, positions_km)
        figure.suptitle(
            " | ".join(
                part for part in (self._object_name, self._frame_context) if part
            )
        )
        self._figure = figure
        self._axes = trajectory_axes
        self.update_cursor(initial_state)
        return figure

    def update_data(
        self, orbit_series: series.OrbitSeries, time_unit: time_unit.TimeUnit
    ) -> bool:
        positions_km = np.asarray(orbit_series.position_km, dtype=float)
        segment_ids = np.asarray(orbit_series.segment_ids, dtype=int)
        if (
            self._axes is None
            or positions_km.ndim != 2
            or positions_km.shape[1] != CARTESIAN_COMPONENT_COUNT
            or positions_km.shape[0] == 0
            or not np.all(np.isfinite(positions_km))
            or segment_ids.shape != positions_km.shape[:1]
            or orbit_series.elapsed_time.shape != positions_km.shape[:1]
        ):
            return False
        segment_ids_present = [
            int(segment_id)
            for segment_id in np.unique(segment_ids)
            if segment_id >= 0
        ]
        if segment_ids_present != [segment_id for segment_id, _ in self._orbit_artists]:
            return False

        self._positions_km = positions_km.copy()
        self._segment_ids = segment_ids.copy()
        self._sample_times_s = (
            self._cursor.t_start
            + orbit_series.elapsed_time * time_unit.get_divisor_s()
        )
        for segment_id, artist in self._orbit_artists:
            segment_positions = positions_km[segment_ids == segment_id]
            segment_positions = segment_positions[
                decimate_indices(
                    segment_positions, MAX_MATPLOTLIB_3D_DISPLAY_POINTS
                )
            ]
            artist.set_data_3d(
                segment_positions[:, 0],
                segment_positions[:, 1],
                segment_positions[:, 2],
            )
        for marker, position in (
            (self._start_artist, positions_km[0]),
            (self._end_artist, positions_km[-1]),
        ):
            if marker is not None:
                marker.set_offsets([[position[0], position[1]]])
                marker.set_3d_properties([position[2]], zdir="z")
        self._set_endpoint_visibility()
        return True

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, _coverage: tuple[float, float], /
    ) -> None:
        """Filter the orbit path and visible endpoint/current-state markers."""
        self._range_bounds = bounds
        self._range_applied = True
        if (
            self._axes is None
            or self._positions_km is None
            or self._sample_times_s is None
            or self._segment_ids is None
        ):
            return
        if bounds is None:
            first = last = 0
        else:
            first = int(
                np.searchsorted(self._sample_times_s, bounds.start_s, side="left")
            )
            last = int(
                np.searchsorted(self._sample_times_s, bounds.end_s, side="right")
            )
        for segment_id, artist in self._orbit_artists:
            segment_indices = np.flatnonzero(self._segment_ids == segment_id)
            if not len(segment_indices):
                artist.set_data_3d([], [], [])
                continue
            segment_start, segment_stop = (
                int(segment_indices[0]),
                int(segment_indices[-1]) + 1,
            )
            start = max(segment_start, first)
            stop = min(segment_stop, last)
            if start >= stop:
                selected = np.empty((0, 3), dtype=float)
            else:
                selected = self._positions_km[start:stop]
                if len(selected) > MAX_MATPLOTLIB_3D_DISPLAY_POINTS:
                    selected = selected[
                        decimate_indices(selected, MAX_MATPLOTLIB_3D_DISPLAY_POINTS)
                    ]
            artist.set_data_3d(selected[:, 0], selected[:, 1], selected[:, 2])
            artist.set_marker("." if len(selected) == 1 else "None")
        self._set_endpoint_visibility()
        self.update(self._current_time_s)

    def update(self, time_s: float) -> None:
        """Resolve and display the cursor state at an absolute OEM time.

        Parameters
        ----------
        time_s : float
            Absolute OEM time in TT seconds since J2000.
        """
        self._current_time_s = time_s
        self.update_cursor(self._cursor.lookup(time_s))

    def update_cursor(self, state: cursor.CursorState) -> None:
        """Move or hide the satellite marker from a resolved cursor state.

        Parameters
        ----------
        state : cursor.CursorState
            Resolved OEM state to display.

        Raises
        ------
        RuntimeError
            If this view has not been built.
        """
        if self._cursor_artist is None:
            raise RuntimeError("3D trajectory view has not been built")
        in_range = not self._range_applied or (
            self._range_bounds is not None
            and self._range_bounds.start_s <= state.t <= self._range_bounds.end_s
        )
        if state.r_km is None or not in_range:
            self._cursor_artist.set_visible(False)
            self._cursor_position_km = None
            return

        position = (
            float(state.r_km[0]),
            float(state.r_km[1]),
            float(state.r_km[2]),
        )
        self._cursor_artist.set_offsets([[position[0], position[1]]])
        self._cursor_artist.set_3d_properties([position[2]], zdir="z")
        self._cursor_artist.set_visible(True)
        self._cursor_position_km = position

    def _set_endpoint_visibility(self) -> None:
        if self._sample_times_s is None:
            return
        visible_start = self._contains_time(float(self._sample_times_s[0]))
        visible_end = self._contains_time(float(self._sample_times_s[-1]))
        if self._start_artist is not None:
            self._start_artist.set_visible(visible_start)
        if self._end_artist is not None:
            self._end_artist.set_visible(visible_end)

    def _contains_time(self, time_s: float) -> bool:
        return not self._range_applied or (
            self._range_bounds is not None
            and self._range_bounds.start_s <= time_s <= self._range_bounds.end_s
        )

    def close(self) -> None:
        """Release the figure, axes, and cursor marker."""
        if self._figure is not None:
            self._figure.clear()
        self._figure = None
        self._axes = None
        self._cursor_artist = None
        self._cursor_position_km = None
        self._positions_km = None
        self._sample_times_s = None
        self._segment_ids = None
        self._orbit_artists.clear()
        self._start_artist = None
        self._end_artist = None

    @staticmethod
    def _set_equal_limits(axes: Any, positions_km: np.ndarray) -> None:
        lower_position_km = np.min(positions_km, axis=0)
        upper_position_km = np.max(positions_km, axis=0)
        center_position_km = (lower_position_km + upper_position_km) / 2.0
        span_km = float(np.max(upper_position_km - lower_position_km))
        if span_km == 0.0:
            span_km = max(
                float(np.max(np.abs(center_position_km))) * DEGENERATE_SPAN_FRACTION,
                MINIMUM_AXIS_SPAN_KM,
            )
        half_span_km = span_km * EQUAL_AXIS_PADDING_FACTOR
        axes.set_xlim(
            center_position_km[0] - half_span_km,
            center_position_km[0] + half_span_km,
        )
        axes.set_ylim(
            center_position_km[1] - half_span_km,
            center_position_km[1] + half_span_km,
        )
        axes.set_zlim(
            center_position_km[2] - half_span_km,
            center_position_km[2] + half_span_km,
        )
        axes.set_box_aspect((1.0, 1.0, 1.0))
