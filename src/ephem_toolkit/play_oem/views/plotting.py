"""Plot helpers that preserve OEM segment boundaries."""

from __future__ import annotations

from collections.abc import Sequence
from math import ceil

import numpy as np
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from matplotlib.transforms import Affine2D

from ..oem_data_store import ColumnGroupView, StoreSnapshot
from ..time_range import ResolvedTimeRange
from ..time_snapping import TimeSamplingPolicy

MAX_DISPLAY_POINTS_PER_SEGMENT = 2000
MAX_MATPLOTLIB_3D_DISPLAY_POINTS = 500


class StoreLineSegmentBinding:
    """Reuse Line2D artists for store-derived or projected segment pairs."""

    def __init__(self) -> None:
        self.artists: tuple[Line2D, ...] = ()

    def clear(self) -> None:
        for artist in self.artists:
            artist.remove()
        self.artists = ()

    def sync(
        self,
        axes: Axes,
        segments: Sequence[tuple[np.ndarray, np.ndarray]],
        *,
        color: str = "C0",
        linewidth: float = 1.5,
        markers: Sequence[str | None] | None = None,
        zorder: float | None = None,
        label: str | None = None,
    ) -> tuple[Line2D, ...]:
        existing = iter(self.artists)
        artists: list[Line2D] = []
        for index, (x_values, y_values) in enumerate(segments):
            marker = (
                "None"
                if markers is None or markers[index] is None
                else markers[index]
            )
            artist = next(existing, None)
            if artist is None:
                artist = Line2D(
                    x_values,
                    y_values,
                    color=color,
                    linewidth=linewidth,
                    marker=marker,
                    markersize=4,
                    linestyle="solid" if marker in (None, "None") else "None",
                    zorder=zorder,
                    label=label or "_nolegend_",
                )
                axes.add_line(artist)
            else:
                artist.set_data(x_values, y_values)
                artist.set_color(color)
                artist.set_linewidth(linewidth)
                artist.set_marker(marker)
                artist.set_markersize(4)
                artist.set_linestyle(
                    "solid" if marker in (None, "None") else "None"
                )
                if zorder is not None:
                    artist.set_zorder(zorder)
                artist.set_label(label or "_nolegend_")
                artist.set_visible(True)
            artists.append(artist)
        for artist in existing:
            artist.remove()
        self.artists = tuple(artists)
        return self.artists


class StoreArtistBinding:
    """Reuse Matplotlib artists while synchronizing store-backed plot segments."""

    def __init__(self) -> None:
        self.artists: tuple[Artist, ...] = ()

    def clear(self) -> None:
        for artist in self.artists:
            artist.remove()
        self.artists = ()

    def _sync_segments(
        self,
        axes: Axes,
        segments: Sequence[tuple[np.ndarray, np.ndarray | None]],
        *,
        transform: Affine2D,
        facecolor: str = "none",
        edgecolor: str = "C0",
        linewidth: float = 1.5,
        labels: Sequence[str | None] | None = None,
        one_point_as_line: bool = False,
    ) -> tuple[Artist, ...]:
        existing = iter(self.artists)
        artists: list[Artist] = []
        for index, (points, codes) in enumerate(segments):
            label = (
                "_nolegend_"
                if labels is None or labels[index] is None
                else labels[index]
            )
            candidate = next(existing, None)
            if len(points) == 1 and one_point_as_line:
                if isinstance(candidate, Line2D):
                    artist = candidate
                    artist.set_data(points[:, 0], points[:, 1])
                    artist.set_marker(".")
                    artist.set_linestyle("None")
                    artist.set_color(edgecolor)
                    artist.set_label(label)
                else:
                    if isinstance(candidate, Artist):
                        candidate.remove()
                    artist = Line2D(
                        points[:, 0],
                        points[:, 1],
                        marker=".",
                        linestyle="None",
                        color=edgecolor,
                        label=label,
                    )
                    axes.add_line(artist)
            else:
                if codes is None:
                    segment_codes = np.full(
                        len(points),
                        Path.LINETO,
                        dtype=Path.code_type,
                    )
                    segment_codes[0] = Path.MOVETO
                else:
                    segment_codes = codes
                if isinstance(candidate, PathPatch):
                    artist = candidate
                    artist.set_path(Path(points, segment_codes, readonly=True))
                else:
                    if isinstance(candidate, Artist):
                        candidate.remove()
                    artist = PathPatch(
                        Path(points, segment_codes, readonly=True),
                        facecolor=facecolor,
                        edgecolor=edgecolor,
                        linewidth=linewidth,
                        label=label,
                    )
                    axes.add_patch(artist)
                artist.set_facecolor(facecolor)
                artist.set_edgecolor(edgecolor)
                artist.set_linewidth(linewidth)
                artist.set_label(label)
            artist.set_transform(transform)
            artist.set_visible(True)
            artists.append(artist)
        for artist in existing:
            artist.remove()
        self.artists = tuple(artists)
        return self.artists

    def sync_pairs(
        self,
        axes: Axes,
        pairs: Sequence[np.ndarray],
        *,
        time_origin_s: float,
        time_divisor_s: float,
        scale_y: float = 1.0,
        edgecolor: str = "C0",
        linewidth: float = 1.5,
        label: str | None = None,
    ) -> tuple[Artist, ...]:
        """Synchronize 2-column point arrays as reusable line or path artists."""
        transform = (
            Affine2D.from_values(
                1.0 / time_divisor_s,
                0.0,
                0.0,
                scale_y,
                -time_origin_s / time_divisor_s,
                0.0,
            )
            + axes.transData
        )
        segments = [(points, None) for points in pairs if len(points) > 0]
        labels = [label] if label is not None else None
        if labels is not None:
            labels = [label] + [None] * max(0, len(segments) - 1)
        return self._sync_segments(
            axes,
            segments,
            transform=transform,
            edgecolor=edgecolor,
            linewidth=linewidth,
            labels=labels,
            one_point_as_line=True,
        )

    def sync_store_series(
        self,
        axes: Axes,
        groups: Sequence[ColumnGroupView],
        value_column: str,
        *,
        time_origin_s: float,
        time_divisor_s: float,
        scale_y: float = 1.0,
        edgecolor: str = "C0",
        linewidth: float = 1.5,
        label: str | None = None,
        mask_zero: bool = False,
        minimum_samples: int = 1,
    ) -> tuple[Artist, ...]:
        """Synchronize store-derived series segments without rebuilding them."""
        segments: list[tuple[np.ndarray, np.ndarray]] = []
        labels: list[str | None] = []
        current_label = label
        for group in groups:
            for span in group.segment_bounds:
                sample_count = span.stop - span.first
                if sample_count < minimum_samples:
                    continue
                stride = max(1, ceil(sample_count / MAX_DISPLAY_POINTS_PER_SEGMENT))
                points = group.pair(
                    "t",
                    value_column,
                    slice(span.first, span.stop, stride),
                )
                if mask_zero and len(points) == 1 and points[0, 1] == 0.0:
                    continue
                codes = np.full(len(points), Path.LINETO, dtype=Path.code_type)
                codes[0] = Path.MOVETO
                if mask_zero:
                    invalid = points[:, 1] == 0.0
                    codes[invalid] = Path.MOVETO
                    if len(codes) > 1:
                        codes[1:][invalid[:-1]] = Path.MOVETO
                segments.append((points, codes))
                labels.append(current_label)
                current_label = None
        transform = (
            Affine2D.from_values(
                1.0 / time_divisor_s,
                0.0,
                0.0,
                scale_y,
                -time_origin_s / time_divisor_s,
                0.0,
            )
            + axes.transData
        )
        return self._sync_segments(
            axes,
            segments,
            transform=transform,
            edgecolor=edgecolor,
            linewidth=linewidth,
            labels=labels,
        )

    def sync_raw_state(
        self,
        axes: Axes,
        snapshot: StoreSnapshot,
        value_column: int,
        *,
        bounds: ResolvedTimeRange | None,
        maximum_samples_per_segment: int,
        time_sampling: TimeSamplingPolicy | None,
        time_origin_s: float,
        time_divisor_s: float,
        scale_y: float = 1.0,
        edgecolor: str = "C0",
        linewidth: float = 1.5,
    ) -> tuple[Artist, ...]:
        """Synchronize sampled raw-state segments for one component axis."""
        if not 1 <= value_column < snapshot.raw.shape[1]:
            raise ValueError("state column must be between 1 and 6")
        if maximum_samples_per_segment < 1:
            raise ValueError("maximum_samples_per_segment must be positive")
        segments: list[tuple[np.ndarray, np.ndarray]] = []
        if bounds is not None and snapshot.sample_count:
            times = snapshot.raw[:, 0]
            range_start = int(np.searchsorted(times, bounds.start_s, side="left"))
            range_stop = int(np.searchsorted(times, bounds.end_s, side="right"))
            sampler = time_sampling or TimeSamplingPolicy()
            for segment_start, segment_stop in snapshot.segment_bounds:
                first = max(int(segment_start), range_start)
                stop = min(int(segment_stop), range_stop)
                if stop <= first:
                    continue
                source = snapshot.raw[first:stop]
                sample_times, sample_values = sampler.sample(
                    source[:, 0],
                    source[:, value_column],
                    bounds_s=(float(source[0, 0]), float(source[-1, 0])),
                    max_samples=maximum_samples_per_segment,
                )
                points = np.column_stack((sample_times, sample_values))
                codes = np.full(len(points), Path.LINETO, dtype=Path.code_type)
                codes[0] = Path.MOVETO
                segments.append((points, codes))
        transform = (
            Affine2D.from_values(
                1.0 / time_divisor_s,
                0.0,
                0.0,
                scale_y,
                -time_origin_s / time_divisor_s,
                0.0,
            )
            + axes.transData
        )
        return self._sync_segments(
            axes,
            segments,
            transform=transform,
            edgecolor=edgecolor,
            linewidth=linewidth,
        )




def time_bounds_to_axis(
    bounds: ResolvedTimeRange | None,
    coverage: tuple[float, float],
    start_time_s: float,
    divisor_s: float,
) -> tuple[float, float]:
    """Convert absolute bounds to elapsed display units, using coverage if empty."""
    source = (
        (coverage[0], coverage[1]) if bounds is None else (bounds.start_s, bounds.end_s)
    )
    return (
        (source[0] - start_time_s) / divisor_s,
        (source[1] - start_time_s) / divisor_s,
    )


def set_shared_x_limits(axes: Sequence[Axes], limits: tuple[float, float]) -> None:
    """Set common x limits, widening singleton ranges only for visible rendering."""
    left, right = limits
    if left == right:
        left -= 0.5
        right += 0.5
    for axis in axes:
        axis.set_xlim(left, right, auto=False)


def decimate_indices(
    values: np.ndarray, maximum: int = MAX_DISPLAY_POINTS_PER_SEGMENT
) -> np.ndarray:
    """Select ordered bucket extrema from an N-by-M display-only value array."""
    if values.ndim != 2:
        raise ValueError("values must be a two-dimensional array")
    if maximum < 4:
        raise ValueError("maximum must be at least four")
    if len(values) <= maximum:
        return np.arange(len(values))
    bucket_count = max(1, (maximum - 2) // (2 * values.shape[1]))
    edges = np.linspace(0, len(values), bucket_count + 1, dtype=int)
    # Every bucket is non-empty because bucket_count is below len(values) here.
    starts = edges[:-1]
    bucket_of_row = np.repeat(np.arange(bucket_count), np.diff(edges))
    row_indices = np.arange(len(values))
    extrema: list[np.ndarray] = []
    for column in range(values.shape[1]):
        local = np.ascontiguousarray(values[:, column])
        for ufunc in (np.minimum, np.maximum):
            bucket_extreme = ufunc.reduceat(local, starts)
            # NaN never compares equal, so match NaN rows explicitly to pick the
            # first NaN as np.argmin and np.argmax do.
            at_extreme = (local == bucket_extreme[bucket_of_row]) | (
                np.isnan(local) & np.isnan(bucket_extreme)[bucket_of_row]
            )
            first_index = np.where(at_extreme, row_indices, len(values))
            extrema.append(np.minimum.reduceat(first_index, starts))
    selected = np.concatenate([[0], *extrema, [len(values) - 1]])
    return np.unique(selected)


def bounded_sample_indices(
    sample_count: int,
    maximum: int = MAX_DISPLAY_POINTS_PER_SEGMENT,
) -> np.ndarray:
    """Choose evenly spaced rows with an allocation bounded by ``maximum``."""
    if sample_count < 0:
        raise ValueError("sample_count must be non-negative")
    if maximum < 1:
        raise ValueError("maximum must be positive")
    display_count = min(sample_count, maximum)
    if display_count == sample_count:
        return np.arange(display_count)
    return np.linspace(
        0, sample_count - 1, num=display_count, dtype=np.intp
    )


def plot_segments(
    axes: Axes,
    x: np.ndarray,
    y: np.ndarray,
    segment_ids: Sequence[int] | np.ndarray,
    *,
    max_display_points: int = MAX_DISPLAY_POINTS_PER_SEGMENT,
    **kwargs: object,
) -> list[Line2D]:
    """Plot contiguous segment runs separately, omitting invalid boundary samples."""
    if max_display_points < 4:
        raise ValueError("max_display_points must be at least four")
    ids = np.asarray(segment_ids, dtype=int)
    if x.shape[0] != y.shape[0] or ids.shape != x.shape:
        raise ValueError("x, y, and segment_ids must have matching first dimensions")
    artists: list[Line2D] = []
    start = 0
    while start < len(ids):
        if ids[start] < 0:
            start += 1
            continue
        stop = start + 1
        while stop < len(ids) and ids[stop] == ids[start]:
            stop += 1
        run_x = x[start:stop]
        run_y = y[start:stop]
        if len(run_x) > max_display_points:
            bucket_count = max(1, (max_display_points - 2) // 2)
            edges = np.linspace(0, len(run_x), bucket_count + 1, dtype=int)
            selected: list[int] = [0]
            for left, right in zip(edges[:-1], edges[1:]):
                if right <= left:
                    continue
                local = run_y[left:right]
                selected.extend(
                    (left + int(np.argmin(local)), left + int(np.argmax(local)))
                )
            selected.append(len(run_x) - 1)
            indices = np.unique(selected)
            run_x = run_x[indices]
            run_y = run_y[indices]
        artists.extend(axes.plot(run_x, run_y, **kwargs))
        start = stop
    return artists
