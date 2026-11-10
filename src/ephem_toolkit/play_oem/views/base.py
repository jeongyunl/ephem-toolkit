"""Toolkit-neutral interface for playback plot views."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from math import ceil
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast

from matplotlib.axes import Axes
from matplotlib.artist import Artist
from matplotlib.lines import Line2D

from matplotlib.figure import Figure
from matplotlib.path import Path
from matplotlib.patches import PathPatch
from matplotlib.transforms import Affine2D
import numpy as np

from ..oem_data_store import (
    ColumnGroupView,
    EarthFixedPositions,
    GroundTrackGroups,
    LoadStatus,
    OemDataStore,
    SeriesGroupName,
    SeriesGroups,
    SERIES_GROUPS,
    StationAccessView,
    StoreQuery,
    StoreSnapshot,
    TierName,
    TimeCoverage,
)
from ..cursor import CursorState
from ..ground_footprints import GroundFootprints
from ..ground_stations import GroundStation, StationMetrics
from ..station_access import LookAngleProfile, StationAccess
from ..series import OrbitSeries
from ..time_range import ResolvedTimeRange, validate_coverage
from ..time_unit import TimeUnit
from .plotting import (
    MAX_DISPLAY_POINTS_PER_SEGMENT,
    SegmentedPlotHistory,
    set_shared_x_limits,
    time_bounds_to_axis,
)

if TYPE_CHECKING:
    import wx

_ViewQueryValue = TypeVar("_ViewQueryValue")


class View(Protocol):
    """Lifecycle shared by all playback views."""

    name: str

    def build(self, series: OrbitSeries, time_unit: TimeUnit, /) -> Figure | wx.Window:
        """Build the view content and its initial cursor state."""
        ...

    def update(self, t_s: float, /) -> None:
        """Move the view's cursor to an absolute OEM time."""
        ...

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        """Select displayed samples; None clears data for an empty effective range."""
        ...

    def close(self) -> None:
        """Release the view's plot resources."""
        ...


@dataclass(frozen=True)
class StoreViewContext:
    """Snapshot-bound data reader plus view-owned range and display settings."""

    store: OemDataStore
    snapshot: StoreSnapshot
    time_unit: TimeUnit
    plot_range: ResolvedTimeRange | None
    coverage: tuple[float, float]

    @classmethod
    def capture(
        cls,
        store: OemDataStore,
        *,
        time_unit: TimeUnit,
        plot_range: ResolvedTimeRange | None,
        coverage: tuple[float, float],
    ) -> StoreViewContext:
        """Capture one stable snapshot for a set of related view queries."""
        return cls(store, store.snapshot(), time_unit, plot_range, coverage)

    def __post_init__(self) -> None:
        if not isinstance(self.store, OemDataStore):
            raise TypeError("store must be an OemDataStore")
        if not isinstance(self.snapshot, StoreSnapshot):
            raise TypeError("snapshot must be a StoreSnapshot")
        if not isinstance(self.time_unit, TimeUnit):
            raise TypeError("time_unit must be a TimeUnit")
        object.__setattr__(self, "coverage", validate_coverage(self.coverage))

    @property
    def bounds_s(self) -> tuple[float, float] | None:
        if self.plot_range is None:
            return None
        return self.plot_range.start_s, self.plot_range.end_s

    def refresh(self) -> StoreViewContext:
        """Capture the latest committed prefix with the same view settings."""
        return replace(self, snapshot=self.store.snapshot())

    def with_range(
        self,
        plot_range: ResolvedTimeRange | None,
        coverage: tuple[float, float],
    ) -> StoreViewContext:
        """Return a context with updated range state and the same snapshot."""
        return replace(self, plot_range=plot_range, coverage=coverage)

    def _empty_query(
        self, value: _ViewQueryValue
    ) -> StoreQuery[_ViewQueryValue]:
        return StoreQuery(
            self.snapshot.epoch,
            self.snapshot.revision,
            self.snapshot.policy_revision,
            value,
            TimeCoverage(None, (), True),
        )

    def series_groups(
        self,
        groups: Sequence[SeriesGroupName],
        *,
        max_samples: int | None = None,
        wait: bool = False,
    ) -> StoreQuery[SeriesGroups]:
        """Query named groups over the bound range without exposing the snapshot."""
        selected_groups = tuple(dict.fromkeys(groups))
        unknown_groups = set(selected_groups).difference(SERIES_GROUPS)
        if unknown_groups:
            raise ValueError(f"unsupported series groups: {sorted(unknown_groups)}")
        bounds = self.bounds_s
        if bounds is None:
            return self._empty_query(
                MappingProxyType({group: () for group in selected_groups})
            )
        return self.store.series(
            self.snapshot,
            bounds,
            groups=selected_groups,
            max_samples=max_samples,
            wait=wait,
        )

    def series(
        self,
        group: SeriesGroupName,
        *,
        max_samples: int | None = None,
        wait: bool = False,
    ) -> StoreQuery[tuple[ColumnGroupView, ...]]:
        """Query one series group as segments instead of a name-keyed mapping."""
        query = self.series_groups((group,), max_samples=max_samples, wait=wait)
        return replace(query, value=query.value[group])

    def query_series(
        self,
        groups: Sequence[SeriesGroupName],
        *,
        max_samples: int | None = None,
        wait: bool = False,
    ) -> StoreQuery[SeriesGroups]:
        """Compatibility spelling for a multi-group series query."""
        return self.series_groups(groups, max_samples=max_samples, wait=wait)

    def state_at(self, t_s: float) -> CursorState:
        """Resolve a point state against this context's stable snapshot."""
        return self.store.state_at(self.snapshot, t_s)

    def earth_fixed_positions(
        self, *, margin_s: float = 0.0, wait: bool = False
    ) -> StoreQuery[EarthFixedPositions]:
        bounds = self.bounds_s
        if bounds is None:
            return self._empty_query(())
        return self.store.earth_fixed_positions(
            self.snapshot, bounds, margin_s=margin_s, wait=wait
        )

    def ground_track(
        self,
        *,
        margin_s: float = 0.0,
        center_longitude_deg: float = 0.0,
        wait: bool = False,
    ) -> StoreQuery[GroundTrackGroups]:
        bounds = self.bounds_s
        if bounds is None:
            return self._empty_query(())
        return self.store.ground_track(
            self.snapshot,
            bounds,
            margin_s=margin_s,
            center_longitude_deg=center_longitude_deg,
            wait=wait,
        )

    def station_access(
        self,
        station: GroundStation,
        *,
        minimum_elevation_deg: int | None = None,
        wait: bool = False,
    ) -> StoreQuery[StationAccessView]:
        bounds = self.bounds_s
        if bounds is None:
            return self._empty_query(StationAccessView(station, (), (), None))
        return self.store.station_access(
            self.snapshot,
            station,
            bounds,
            minimum_elevation_deg=minimum_elevation_deg,
            wait=wait,
        )

    def station_metrics_at(
        self, station: GroundStation, t_s: float
    ) -> StationMetrics | None:
        return self.store.station_metrics_at(self.snapshot, station, t_s)

    def footprints(
        self, t_s: float, minimum_elevation_deg: float
    ) -> GroundFootprints | None:
        return self.store.footprints(self.snapshot, t_s, minimum_elevation_deg)

    def subscribe_tier(self, tier: TierName) -> Callable[[], None]:
        """Register this open view's interest in a derived store tier."""
        return self.store.subscribe_tier(tier)


class StoreViewBinding:
    """Own tier subscriptions for a view as its bound store context changes."""

    def __init__(self, tiers: Sequence[TierName] = ()) -> None:
        self._tiers = tuple(dict.fromkeys(tiers))
        self._store: OemDataStore | None = None
        self._unsubscribers: list[Callable[[], None]] = []
        self._context: StoreViewContext | None = None

    def bind(self, context: StoreViewContext) -> None:
        if self._store is not context.store:
            self._unsubscribe()
            self._store = context.store
            self._unsubscribers = [
                context.subscribe_tier(tier) for tier in self._tiers
            ]
        self._context = context

    @property
    def context(self) -> StoreViewContext | None:
        return self._context

    def with_range(
        self,
        plot_range: ResolvedTimeRange | None,
        coverage: tuple[float, float],
    ) -> StoreViewContext:
        if self._context is None:
            raise RuntimeError("store view binding has not been bound")
        self._context = self._context.with_range(plot_range, coverage)
        return self._context

    def close(self) -> None:
        self._unsubscribe()
        self._store = None
        self._context = None

    def _unsubscribe(self) -> None:
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()


def station_access_from_store(value: StationAccessView) -> StationAccess:
    """Adapt leased store columns to the station view model without copying."""
    profiles: list[LookAngleProfile] = []
    for profile in value.profiles:
        group = profile.group
        times = group.values[:, group.columns.index("t")]
        azimuths = group.values[:, group.columns.index("azimuth_deg")]
        elevations = group.values[:, group.columns.index("elevation_deg")]
        ranges = group.values[:, group.columns.index("range_km")]
        profiles.append(LookAngleProfile(times, azimuths, elevations, ranges))
    return StationAccess(
        value.station,
        value.intervals,
        value.limitation,
        look_angle_profiles=tuple(profiles),
    )


def store_load_status_message(context: StoreViewContext | None) -> str | None:
    """Describe terminal load states while allowing committed-prefix data to render."""
    if context is None:
        return None
    snapshot = context.snapshot
    if snapshot.status is LoadStatus.FAILED:
        if snapshot.failure:
            return f"OEM load failed: {snapshot.failure}"
        return "OEM load failed."
    if snapshot.status is LoadStatus.CANCELLED:
        return "OEM loading was cancelled; showing available data."
    return None


class StoreView(Protocol):
    """Store-query view lifecycle used by the unified player."""

    name: str

    def build_from_store(self, context: StoreViewContext, /) -> Figure | wx.Window:
        """Build from a stable store snapshot and its range-limited queries."""
        ...

    def update_from_store(self, context: StoreViewContext, /) -> None:
        """Refresh from a newer snapshot or changed plot range."""
        ...


def add_store_series_paths(
    axes: Axes,
    groups: Sequence[ColumnGroupView],
    value_column: str,
    time_origin_s: float,
    time_divisor_s: float,
    *,
    scale_y: float = 1.0,
    color: str = "C0",
    label: str | None = None,
    linewidth: float = 1.5,
    mask_zero: bool = False,
    minimum_samples: int = 1,
) -> tuple[Artist, ...]:
    """Plot strided store views without copying their coordinate values."""
    artists: list[Artist] = []
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
            transform = Affine2D.from_values(
                1.0 / time_divisor_s,
                0.0,
                0.0,
                scale_y,
                -time_origin_s / time_divisor_s,
                0.0,
            ) + axes.transData
            if mask_zero and len(points) == 1 and points[0, 1] == 0.0:
                continue
            codes = np.full(len(points), Path.LINETO, dtype=Path.code_type)
            codes[0] = Path.MOVETO
            if mask_zero:
                invalid = points[:, 1] == 0.0
                codes[invalid] = Path.MOVETO
                codes[1:][invalid[:-1]] = Path.MOVETO
            artist = PathPatch(
                Path(points, codes, readonly=True),
                facecolor="none",
                edgecolor=color,
                linewidth=linewidth,
                label=current_label or "_nolegend_",
                transform=transform,
            )
            axes.add_patch(artist)
            artists.append(artist)
            current_label = None
    return tuple(artists)


def add_raw_state_paths(
    axes: Axes,
    snapshot: StoreSnapshot,
    value_column: int,
    time_origin_s: float,
    time_divisor_s: float,
    *,
    bounds: ResolvedTimeRange | None,
    maximum_samples_per_segment: int,
    scale_y: float,
    color: str = "C0",
    linewidth: float = 1.5,
) -> tuple[Artist, ...]:
    """Plot strided raw-state columns while keeping path vertices store-backed."""
    if not 1 <= value_column < snapshot.raw.shape[1]:
        raise ValueError("state column must be between 1 and 6")
    if maximum_samples_per_segment < 1:
        raise ValueError("maximum_samples_per_segment must be positive")
    if bounds is None or snapshot.sample_count == 0:
        return ()

    times = snapshot.raw[:, 0]
    range_start = int(np.searchsorted(times, bounds.start_s, side="left"))
    range_stop = int(np.searchsorted(times, bounds.end_s, side="right"))
    artists: list[Artist] = []
    for segment_start, segment_stop in snapshot.segment_bounds:
        first = max(int(segment_start), range_start)
        stop = min(int(segment_stop), range_stop)
        sample_count = stop - first
        if sample_count <= 0:
            continue
        stride = max(1, ceil(sample_count / maximum_samples_per_segment))
        column_stride = value_column
        points = snapshot.raw[
            first:stop:stride, 0 : value_column + 1 : column_stride
        ]
        codes = np.full(len(points), Path.LINETO, dtype=Path.code_type)
        codes[0] = Path.MOVETO
        transform = Affine2D.from_values(
            1.0 / time_divisor_s,
            0.0,
            0.0,
            scale_y,
            -time_origin_s / time_divisor_s,
            0.0,
        ) + axes.transData
        artist = PathPatch(
            Path(points, codes, readonly=True),
            facecolor="none",
            edgecolor=color,
            linewidth=linewidth,
            transform=transform,
        )
        axes.add_patch(artist)
        artists.append(artist)
    return tuple(artists)


def clear_store_series_artists(axes: Axes, artists: Sequence[Artist]) -> None:
    for artist in artists:
        artist.remove()
    legend = axes.get_legend()
    if legend is not None:
        legend.remove()


def store_empty_label(
    context: StoreViewContext, *, not_enough_samples: bool = False
) -> str:
    if context.plot_range is None:
        return "Plot range does not overlap OEM coverage"
    if not_enough_samples:
        return "Not enough samples"
    return "No samples in plot range"


def set_store_series_y_limits(
    axes: Axes,
    groups: Sequence[ColumnGroupView],
    value_columns: Sequence[str],
    *,
    scale_y: float = 1.0,
) -> None:
    lower = float("inf")
    upper = float("-inf")
    for group in groups:
        for column in value_columns:
            values = group.values[:, group.columns.index(column)]
            column_lower = float(np.fmin.reduce(values, initial=np.inf))
            column_upper = float(np.fmax.reduce(values, initial=-np.inf))
            if not np.isfinite(column_lower) or not np.isfinite(column_upper):
                continue
            lower = min(lower, column_lower * scale_y)
            upper = max(upper, column_upper * scale_y)
    if lower == float("inf"):
        return
    padding = max((upper - lower) * 0.05, abs(upper) * 0.005, 0.001)
    axes.set_ylim(lower - padding, upper + padding)


def set_raw_state_y_limits(
    axes: Axes,
    snapshot: StoreSnapshot,
    value_column: int,
    *,
    scale_y: float,
) -> None:
    if snapshot.sample_count == 0:
        return
    values = snapshot.raw[:, value_column]
    lower = float(np.min(values)) * scale_y
    upper = float(np.max(values)) * scale_y
    padding = max((upper - lower) * 0.05, abs(upper) * 0.005, 0.001)
    axes.set_ylim(lower - padding, upper + padding)


class TimeRangeSupport:
    """Shared time-axis, range filtering, and cursor-visibility behavior."""

    # Views whose per-tick update changes only animated cursor artists.
    animated_cursor_updates: bool = False

    def _configure_time_range(
        self,
        axes: tuple[Axes, ...],
        histories: tuple[SegmentedPlotHistory, ...],
        cursor_artists: tuple[Line2D, ...],
        start_time_s: float,
        divisor_s: float,
    ) -> None:
        self._range_axes = axes
        self._range_histories = histories
        self._range_cursors = cursor_artists
        self._range_start_time_s = start_time_s
        self._range_divisor_s = divisor_s
        self._range_bounds: ResolvedTimeRange | None = None
        self._range_coverage = (start_time_s, start_time_s)
        self._last_cursor_time_s = start_time_s
        self._range_applied = False
        self._range_active = False
        self._range_changed = True
        self._setting_shared_xlim = False
        self._range_xlim_callbacks = [
            (
                axis,
                cast(Any, axis).callbacks.connect(
                    "xlim_changed", self._on_range_xlim_changed
                ),
            )
            for axis in axes
        ]
        self._full_y_limits = tuple(axis.get_ylim() for axis in axes)

    def _on_range_xlim_changed(self, _axis: Axes) -> None:
        if self._setting_shared_xlim or not self._range_active:
            return
        if not self._range_axes:
            return
        expected = time_bounds_to_axis(
            self._range_bounds,
            self._range_coverage,
            self._range_start_time_s,
            self._range_divisor_s,
        )
        self._setting_shared_xlim = True
        try:
            set_shared_x_limits(self._range_axes, expected)
        finally:
            self._setting_shared_xlim = False

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        if not hasattr(self, "_range_axes"):
            return
        if bounds != self._range_bounds or coverage != self._range_coverage:
            self._range_changed = True
        self._range_bounds = bounds
        self._range_coverage = coverage
        self._range_applied = True
        self._range_active = bounds is None or (
            bounds.start_s > coverage[0] or bounds.end_s < coverage[1]
        )
        limits = time_bounds_to_axis(
            bounds, coverage, self._range_start_time_s, self._range_divisor_s
        )
        has_samples = False
        for history in self._range_histories:
            has_samples = (
                history.update(
                    None if bounds is None else limits,
                    empty_range=bounds is None,
                )
                or has_samples
            )
        self._setting_shared_xlim = True
        try:
            set_shared_x_limits(self._range_axes, limits)
        finally:
            self._setting_shared_xlim = False
        if bounds is None:
            for cursor in self._range_cursors:
                cursor.set_visible(False)
        else:
            self._set_cursor_visibility(self._last_cursor_time_s)
        # Keep the current vertical zoom. Home on the navigation toolbar returns
        # to its captured full-data limits; this explicit hook serves other UIs.

    def consume_cursor_only_update(self) -> bool:
        """Return whether the time range is unchanged since the previous call.

        Callers pair this with a cursor ``update``; a True result means the only
        change was to animated cursors, so a cached background can be reused.
        """
        if not hasattr(self, "_range_changed"):
            return False
        range_changed = self._range_changed
        self._range_changed = False
        return self.animated_cursor_updates and not range_changed

    def restore_full_y_limits(self) -> None:
        """Restore build-time full-history Y bounds without changing shared X."""
        for axis, limits in zip(self._range_axes, self._full_y_limits):
            axis.set_ylim(*limits)

    def _update_history_data(
        self,
        datasets: Sequence[tuple[np.ndarray, np.ndarray, np.ndarray]],
        start_time_s: float,
        divisor_s: float,
    ) -> bool:
        """Replace time-series samples without rebuilding the figure."""
        if (
            not hasattr(self, "_range_histories")
            or start_time_s != self._range_start_time_s
            or divisor_s != self._range_divisor_s
            or len(datasets) != len(self._range_histories)
        ):
            return False
        if not all(
            history.can_replace_data(x, y, segment_ids)
            for history, (x, y, segment_ids) in zip(
                self._range_histories, datasets
            )
        ):
            return False

        y_limits = tuple(axis.get_ylim() for axis in self._range_axes)
        y_autoscale = tuple(axis.get_autoscaley_on() for axis in self._range_axes)
        for history, (x, y, segment_ids) in zip(self._range_histories, datasets):
            history.replace_data(x, y, segment_ids)
            if len(history.x):
                history.update((float(history.x[0]), float(history.x[-1])))
            else:
                history.update(None, empty_range=True)
        for axis, limits, autoscale in zip(
            self._range_axes, y_limits, y_autoscale
        ):
            axis.relim()
            if autoscale:
                axis.autoscale_view(scalex=False, scaley=True)
            else:
                axis.set_ylim(*limits)
        if any(y_autoscale):
            self._full_y_limits = tuple(axis.get_ylim() for axis in self._range_axes)
        current_limits = time_bounds_to_axis(
            self._range_bounds,
            self._range_coverage,
            self._range_start_time_s,
            self._range_divisor_s,
        )
        for history in self._range_histories:
            history.update(
                None if self._range_bounds is None else current_limits,
                empty_range=self._range_bounds is None,
            )
        self._range_changed = True
        return True

    def _close_time_range(self) -> None:
        for axis, callback_id in getattr(self, "_range_xlim_callbacks", ()):
            cast(Any, axis).callbacks.disconnect(callback_id)
        self._range_xlim_callbacks = []

    def _set_cursor_visibility(self, time_s: float) -> None:
        self._last_cursor_time_s = time_s
        if not self._range_applied:
            return
        visible = (
            self._range_bounds is not None
            and self._range_bounds.start_s <= time_s <= self._range_bounds.end_s
        )
        for cursor in self._range_cursors:
            cursor.set_visible(visible)
