"""Toolkit-neutral interface for playback plot data_views."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast, runtime_checkable

import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from ..cursor import CursorState
from ..ground_footprints import GroundFootprints
from ..ground_stations import GroundStation, StationMetrics
from ..oem_data_store import (
    SERIES_GROUPS,
    ColumnGroupView,
    EarthFixedPositions,
    GroundTrackGroups,
    LoadStatus,
    OemDataStore,
    RowSpan,
    SeriesGroupName,
    SeriesGroups,
    StationAccessView,
    StoreQuery,
    StoreSnapshot,
    TierName,
    TimeCoverage,
)
from ..station_access import LookAngleProfile, StationAccess
from ..station_analysis import StationAnalysisContext, StationAnalysisSelection
from ..time_range import ResolvedTimeRange, validate_coverage
from ..time_snapping import TimeSamplingPolicy
from ..time_unit import TimeUnit
from .plotting import (
    MAX_DISPLAY_POINTS_PER_SEGMENT,
    set_shared_x_limits,
    time_bounds_to_axis,
)

if TYPE_CHECKING:
    import wx

_ViewQueryValue = TypeVar("_ViewQueryValue")


def _snap_series_groups(
    groups: SeriesGroups,
    bounds: tuple[float, float],
    *,
    max_samples: int = MAX_DISPLAY_POINTS_PER_SEGMENT,
    time_sampling: TimeSamplingPolicy | None = None,
) -> SeriesGroups:
    """Resample plot series on a bounded, anchored half-second-multiple grid."""
    sampler = time_sampling or TimeSamplingPolicy()
    sampled_groups: dict[SeriesGroupName, tuple[ColumnGroupView, ...]] = {}
    for name, column_groups in groups.items():
        sampled: list[ColumnGroupView] = []
        for group in column_groups:
            try:
                time_column = group.columns.index("t")
            except ValueError:
                sampled.append(group)
                continue
            pieces: list[np.ndarray] = []
            for segment in group.segment_bounds:
                source = group.values[segment.first : segment.stop]
                if not len(source):
                    continue
                source_times = source[:, time_column]
                start = max(bounds[0], float(source_times[0]))
                stop = min(bounds[1], float(source_times[-1]))
                if start > stop:
                    continue
                remaining_columns = tuple(
                    column for column in range(source.shape[1]) if column != time_column
                )
                times, sampled_values = sampler.sample(
                    source_times,
                    source[:, remaining_columns],
                    bounds_s=(start, stop),
                    max_samples=max_samples,
                )
                if not times.size:
                    continue
                values = np.empty((times.size, source.shape[1]), dtype=float)
                values[:, time_column] = times
                values[:, remaining_columns] = sampled_values
                pieces.append(values)
            if pieces:
                values = np.concatenate(pieces)
                spans: list[RowSpan] = []
                offset = 0
                for piece in pieces:
                    spans.append(RowSpan(offset, offset + len(piece)))
                    offset += len(piece)
                sampled.append(
                    ColumnGroupView(
                        values,
                        group.columns,
                        tuple(spans),
                    )
                )
            else:
                sampled.append(group)
        sampled_groups[name] = tuple(sampled)
    return MappingProxyType(sampled_groups)


@dataclass(frozen=True)
class StoreViewContext:
    """Snapshot-bound data reader plus view-owned range and display settings."""

    store: OemDataStore
    snapshot: StoreSnapshot
    time_unit: TimeUnit
    plot_range: ResolvedTimeRange | None
    coverage: tuple[float, float]
    time_sampling: TimeSamplingPolicy = field(default_factory=TimeSamplingPolicy)

    @classmethod
    def capture(
        cls,
        store: OemDataStore,
        *,
        time_unit: TimeUnit,
        plot_range: ResolvedTimeRange | None,
        coverage: tuple[float, float],
        time_sampling: TimeSamplingPolicy | None = None,
    ) -> StoreViewContext:
        """Capture one stable snapshot for a set of related view queries."""
        return cls(
            store,
            store.snapshot(),
            time_unit,
            plot_range,
            coverage,
            TimeSamplingPolicy() if time_sampling is None else time_sampling,
        )

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

    def _empty_query(self, value: _ViewQueryValue) -> StoreQuery[_ViewQueryValue]:
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
        query = self.store.series(
            self.snapshot,
            bounds,
            groups=selected_groups,
            max_samples=max_samples,
            wait=wait,
        )
        display_limit = (
            MAX_DISPLAY_POINTS_PER_SEGMENT
            if max_samples is None
            else min(max_samples, MAX_DISPLAY_POINTS_PER_SEGMENT)
        )
        return replace(
            query,
            value=_snap_series_groups(
                query.value,
                bounds,
                max_samples=display_limit,
                time_sampling=self.time_sampling,
            ),
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
        return StoreQuery(
            query.epoch,
            query.revision,
            query.policy_revision,
            query.value[group],
            query.coverage,
        )

    def state_at(self, t_s: float) -> CursorState:
        """Resolve a point state against this context's stable snapshot."""
        return self.store.state_at(self.snapshot, t_s)

    def query_bounds(
        self,
        empty_value: _ViewQueryValue,
        query: Callable[[tuple[float, float]], StoreQuery[_ViewQueryValue]],
    ) -> StoreQuery[_ViewQueryValue]:
        """Run a snapshot-bound store query only when a finite range is selected."""
        bounds = self.bounds_s
        if bounds is None:
            return self._empty_query(empty_value)
        return query(bounds)

    def earth_fixed_positions(
        self, *, margin_s: float = 0.0, wait: bool = False
    ) -> StoreQuery[EarthFixedPositions]:
        return self.query_bounds(
            (),
            lambda bounds: self.store.earth_fixed_positions(
                self.snapshot, bounds, margin_s=margin_s, wait=wait
            ),
        )

    def ground_track(
        self,
        *,
        margin_s: float = 0.0,
        center_longitude_deg: float = 0.0,
        wait: bool = False,
    ) -> StoreQuery[GroundTrackGroups]:
        return self.query_bounds(
            (),
            lambda bounds: self.store.ground_track(
                self.snapshot,
                bounds,
                margin_s=margin_s,
                center_longitude_deg=center_longitude_deg,
                wait=wait,
            ),
        )

    def station_access(
        self,
        station: GroundStation,
        *,
        minimum_elevation_deg: int | None = None,
        wait: bool = False,
    ) -> StoreQuery[StationAccessView]:
        return self.query_bounds(
            StationAccessView(station, (), (), None),
            lambda bounds: self.store.station_access(
                self.snapshot,
                station,
                bounds,
                minimum_elevation_deg=minimum_elevation_deg,
                wait=wait,
            ),
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
            self._unsubscribers = [context.subscribe_tier(tier) for tier in self._tiers]
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


class StoreStationViewSupport:
    """Shared store binding lifecycle for ground-station data_views."""

    def _initialize_station_store(
        self,
        tiers: Sequence[TierName],
    ) -> None:
        self._station_store_context: StoreViewContext | None = None
        self._store_context: StoreViewContext | None = None
        self._store_binding = StoreViewBinding(tiers)
        self._station_access_binding = StationAccessBinding()
        self._station_access_preparation_key: tuple[object, ...] | None = None

    def _prepare_station_store_context(self, context: StoreViewContext) -> None:
        self._store_binding.bind(context)
        self._station_store_context = context
        self._store_context = context

    @property
    def _active_station_store_context(self) -> object | None:
        """Return the active station context through the unified store-state name."""
        context = getattr(self, "_store_context", None)
        if context is not None and callable(
            getattr(context, "station_metrics_at", None)
        ):
            return context
        context = getattr(self, "_station_store_context", None)
        if isinstance(context, StoreViewContext):
            return context
        return None

    def _begin_station_store_update(
        self,
        context: StoreViewContext,
        data_view_name: str,
    ) -> None:
        """Require an existing station view binding, then refresh it."""
        if self._active_station_store_context is None:
            raise RuntimeError(f"{data_view_name} view was not built from a store")
        self._prepare_station_store_context(context)

    def _station_store_context_for_range(
        self,
        bounds: ResolvedTimeRange | None,
        coverage: tuple[float, float],
    ) -> StoreViewContext:
        context = self._store_binding.with_range(bounds, coverage)
        self._station_store_context = context
        self._store_context = context
        return context

    def _close_station_store(self) -> None:
        self._store_binding.close()
        self._station_store_context = None
        self._store_context = None
        self._station_access_binding.clear()
        self._station_access_preparation_key = None

    def _station_time_sampling(self) -> TimeSamplingPolicy:
        """Return store sampling policy or the normal policy for result-only data_views."""
        context = self._active_station_store_context
        if isinstance(context, StoreViewContext):
            return context.time_sampling
        return TimeSamplingPolicy()


class GroundStationAnalysisMixin(StoreStationViewSupport):
    """Shared station selection and store-state support for Ground Station data_views."""

    def _initialize_ground_station_analysis(
        self,
        stations: Sequence[GroundStation],
        selection_context: StationAnalysisContext | None,
        *,
        oem_loaded: bool,
        tiers: Sequence[TierName] = ("station-access",),
    ) -> None:
        self._stations = tuple(stations)
        self._selection_context = selection_context
        self._oem_loaded = oem_loaded
        self._mask_filter_enabled = True

        context_station_id = (
            selection_context.selection.station_id
            if selection_context is not None
            else None
        )
        self._selected_station_id = self._resolve_ground_station_id(
            context_station_id
        )
        self._initialize_station_store(tiers)
        self._context_unsubscribe: Callable[[], None] = (
            selection_context.subscribe(self._on_ground_station_context_selection)
            if selection_context is not None
            else lambda: None
        )
        if (
            selection_context is not None
            and self._selected_station_id != context_station_id
        ):
            selection_context.select_station(self._selected_station_id)

    @property
    def selected_station_id(self) -> str | None:
        """Return the currently selected station identity."""
        return self._selected_station_id

    def _resolve_ground_station_id(self, station_id: str | None) -> str | None:
        if any(station.station_id == station_id for station in self._stations):
            return station_id
        return self._stations[0].station_id if self._stations else None

    def _selected_ground_station(self) -> GroundStation | None:
        station_id = self._selected_station_id
        return next(
            (
                station
                for station in self._stations
                if station.station_id == station_id
            ),
            None,
        )

    def _set_ground_station_stations(
        self,
        stations: Sequence[GroundStation],
    ) -> None:
        """Synchronize station definitions and retain a valid selection."""
        selected_id = self._selected_station_id
        self._stations = tuple(stations)
        self._selected_station_id = (
            selected_id
            if any(station.station_id == selected_id for station in stations)
            else (stations[0].station_id if stations else None)
        )
        station_choice = getattr(self, "_station_choice", None)
        if station_choice is not None:
            station_choice.Clear()
            selected_index = -1
            for index, station in enumerate(self._stations):
                station_choice.Append(station.name)
                if station.station_id == self._selected_station_id:
                    selected_index = index
            station_choice.SetSelection(selected_index)
        if self._selection_context is not None:
            self._selection_context.select_station(self._selected_station_id)

    def _on_ground_station_context_selection(
        self,
        selection: StationAnalysisSelection,
    ) -> None:
        """Apply shared station selection without reacting to interval-only changes."""
        station_id = self._resolve_ground_station_id(selection.station_id)
        if station_id != self._selected_station_id:
            self._selected_station_id = station_id
            station_choice = getattr(self, "_station_choice", None)
            if station_choice is not None:
                for index, station in enumerate(self._stations):
                    if station.station_id == station_id:
                        station_choice.SetSelection(index)
                        break
                else:
                    station_choice.SetSelection(-1)

    def _close_ground_station_analysis(self) -> None:
        """Release shared selection and store subscriptions."""
        self._context_unsubscribe()
        self._context_unsubscribe = lambda: None
        self._close_station_store()


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


class StationAccessBinding:
    """Deduplicate station-access preparation for store-bound Station views."""

    def __init__(self) -> None:
        self.context: StoreViewContext | None = None
        self.results: dict[str, StationAccess] = {}
        self.queries: dict[str, StoreQuery[StationAccessView]] = {}
        self._preparation_key: tuple[object, ...] | None = None

    @staticmethod
    def _station_key(stations: Sequence[GroundStation]) -> tuple[object, ...]:
        return tuple(
            (
                station.station_id,
                station.name,
                station.latitude_deg,
                station.longitude_deg,
                station.altitude_m,
                station.minimum_elevation_deg,
            )
            for station in stations
        )

    def prepare(
        self,
        context: object | None,
        *,
        stations: Sequence[GroundStation],
        oem_loaded: bool,
        extra_key: tuple[object, ...] = (),
        empty_range: bool = False,
    ) -> bool:
        """Prepare once per snapshot/range/station/policy identity."""
        if not oem_loaded or not isinstance(context, StoreViewContext):
            preparation_key = ("unavailable",)
            if preparation_key == self._preparation_key:
                return False
            self._preparation_key = preparation_key
            self.context = None
            self.results.clear()
            self.queries.clear()
            return True

        preparation_key = (
            context.snapshot.epoch,
            context.snapshot.revision,
            context.snapshot.policy_revision,
            context.plot_range,
            context.coverage,
            self._station_key(stations),
            extra_key,
        )
        if preparation_key == self._preparation_key:
            return False
        self._preparation_key = preparation_key
        self.context = context
        self.results.clear()
        self.queries.clear()
        if empty_range:
            for station in stations:
                self.results[station.station_id] = StationAccess(station, ())
            return True
        for station in stations:
            query = context.station_access(station)
            self.queries[station.station_id] = query
            self.results[station.station_id] = station_access_from_store(query.value)
        return True

    def clear(self) -> None:
        self.context = None
        self.results.clear()
        self.queries.clear()
        self._preparation_key = None


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


@runtime_checkable
class DataView(Protocol):
    """Canonical store-bound view lifecycle used by the unified player."""

    name: str

    def build_from_store(self, context: StoreViewContext, /) -> Figure | wx.Window:
        """Build from a stable store snapshot and its range-limited queries."""
        ...

    def update_from_store(self, context: StoreViewContext, /) -> None:
        """Apply one complete newer-snapshot/range context."""
        ...

    def update(self, t_s: float, /) -> None:
        """Move presentation state to an absolute OEM time."""
        ...

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        """Apply a range-only context update."""
        ...

    def consume_cursor_only_update(self) -> bool:
        """Return whether the latest update changes only playback cursor state."""
        ...

    def close(self) -> None:
        """Release store subscriptions and presentation resources."""
        ...


def validate_data_view_protocol(view: object) -> DataView:
    """Return a view only when it implements the canonical unified lifecycle."""
    missing: list[str] = []
    name = getattr(view, "name", None)
    if not isinstance(name, str) or not name.strip():
        missing.append("name")
    for method in (
        "build_from_store",
        "update_from_store",
        "update",
        "set_time_range",
        "close",
    ):
        if not callable(getattr(view, method, None)):
            missing.append(method)
    if missing:
        name = type(view).__name__
        raise TypeError(
            f"{name} does not implement the DataView protocol;"
            f" missing {', '.join(missing)}"
        )
    return cast(DataView, view)


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


class RangeLifecycleSupport:
    """Canonical range-change and cursor-only redraw state for every data view."""

    animated_cursor_updates: bool = False

    def _initialize_range_lifecycle(
        self,
        bounds: ResolvedTimeRange | None = None,
        coverage: tuple[float, float] | None = None,
    ) -> None:
        self._range_bounds = bounds
        self._range_coverage = coverage
        self._range_applied = bounds is not None
        self._range_changed = True

    def _apply_range_lifecycle(
        self,
        bounds: ResolvedTimeRange | None,
        coverage: tuple[float, float],
    ) -> bool:
        changed = (
            bounds != getattr(self, "_range_bounds", None)
            or coverage != getattr(self, "_range_coverage", None)
        )
        if changed:
            self._range_changed = True
        self._range_bounds = bounds
        self._range_coverage = coverage
        self._range_applied = True
        return changed

    def _mark_view_content_changed(self) -> None:
        self._range_changed = True

    def consume_cursor_only_update(self) -> bool:
        """Return whether only animated cursors changed since the prior update."""
        range_changed = getattr(self, "_range_changed", True)
        self._range_changed = False
        return self.animated_cursor_updates and not range_changed


class TimeRangeSupport(RangeLifecycleSupport):
    """Shared time-axis, range filtering, and cursor-visibility behavior."""

    # Views whose per-tick update changes only animated cursor artists.
    animated_cursor_updates: bool = False

    def _configure_time_range(
        self,
        axes: tuple[Axes, ...],
        histories: tuple[Any, ...],
        cursor_artists: tuple[Line2D, ...],
        start_time_s: float,
        divisor_s: float,
    ) -> None:
        self._initialize_range_lifecycle()
        self._range_axes = axes
        self._range_histories = histories
        self._range_cursors = cursor_artists
        self._range_start_time_s = start_time_s
        self._range_divisor_s = divisor_s
        self._range_coverage = (start_time_s, start_time_s)
        self._last_cursor_time_s = start_time_s
        self._range_active = False
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
        self._apply_range_lifecycle(bounds, coverage)
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

    def restore_full_y_limits(self) -> None:
        """Restore build-time full-history Y bounds without changing shared X."""
        for axis, limits in zip(self._range_axes, self._full_y_limits):
            axis.set_ylim(*limits)

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


class StoreSeriesPlotView(TimeRangeSupport):
    """Shared lifecycle for store-backed 2D series data_views."""

    preserve_canvas_aspect_ratio = False

    def _initialize_store_series(
        self,
        start_time_s: float,
        *,
        tiers: Sequence[TierName] = ("series",),
    ) -> None:
        self._start_time_s = start_time_s
        self._figure: Figure | None = None
        self._cursor_artists: tuple[Line2D, ...] | None = None
        self._time_unit_divisor_s = 1.0
        self._store_context: StoreViewContext | None = None
        self._store_binding = StoreViewBinding(tiers)
        self._store_start_time_s = start_time_s

    def _prepare_store_context(self, context: StoreViewContext) -> None:
        """Bind a snapshot and refresh the shared origin/time-unit state."""
        self._store_binding.bind(context)
        self._store_context = context
        self._store_start_time_s = context.coverage[0]
        self._time_unit_divisor_s = context.time_unit.get_divisor_s()
        self._range_start_time_s = self._store_start_time_s
        self._range_divisor_s = self._time_unit_divisor_s

    def _begin_store_context_update(
        self,
        context: StoreViewContext,
        *,
        axis_indexes: Sequence[int] | None = None,
    ) -> None:
        """Prepare one store snapshot/range update and clear existing artists."""
        if self._figure is None:
            raise RuntimeError("store view has not been built")
        self._prepare_store_context(context)
        axes = tuple(self._figure.axes)
        cursor_artists = tuple(getattr(self, "_cursor_artists", ()) or ())
        configured_axes = tuple(getattr(self, "_range_axes", ()) or ())
        configured_cursors = tuple(getattr(self, "_range_cursors", ()) or ())
        if configured_axes != axes or configured_cursors != cursor_artists:
            self._configure_time_range(
                axes,
                (),
                cursor_artists,
                context.coverage[0],
                context.time_unit.get_divisor_s(),
            )
        self._mark_view_content_changed()
        indexes = (
            tuple(range(len(self._figure.axes)))
            if axis_indexes is None
            else tuple(axis_indexes)
        )
        for index in indexes:
            self._figure.axes[index].set_xlabel(context.time_unit.get_axis_label())
        super().set_time_range(context.plot_range, context.coverage)

    def _request_store_view_redraw(self) -> None:
        """Request a canvas redraw after one store-backed rebuild completes."""
        canvas = getattr(self, "_time_series_canvas", None)
        if canvas is not None:
            canvas.draw_idle()

    def _store_context_for_range(
        self,
        bounds: ResolvedTimeRange | None,
        coverage: tuple[float, float],
    ) -> StoreViewContext:
        return self._store_binding.with_range(bounds, coverage)

    def _update_store_or_legacy_cursor(self, time_s: float) -> None:
        """Move every cursor using store context or the legacy OEM origin."""
        if self._cursor_artists is None:
            raise RuntimeError("view has not been built")
        if self._store_context is not None:
            self._last_cursor_time_s = time_s
            elapsed_time_axis = (
                time_s - self._store_start_time_s
            ) / self._time_unit_divisor_s
            bounds = self._store_context.plot_range
            visible = bounds is not None and bounds.start_s <= time_s <= bounds.end_s
            for cursor_artist in self._cursor_artists:
                cursor_artist.set_xdata([elapsed_time_axis, elapsed_time_axis])
                cursor_artist.set_visible(visible)
            return
        elapsed_time_axis = (time_s - self._start_time_s) / self._time_unit_divisor_s
        for cursor_artist in self._cursor_artists:
            cursor_artist.set_xdata([elapsed_time_axis, elapsed_time_axis])
        self._set_cursor_visibility(time_s)

    def _close_store_series_plot(self) -> None:
        """Release shared figure, range callbacks, and store subscriptions."""
        bindings = getattr(self, "_store_artist_bindings", ())
        for binding in bindings:
            binding.clear()
        if self._figure is not None:
            self._close_time_range()
            self._figure.clear()
        self._store_binding.close()
        self._store_context = None
        self._figure = None
        self._cursor_artists = None


class StoreTimeSeriesView(StoreSeriesPlotView):
    """Common base for 2D data_views whose x-axis represents absolute OEM time."""

    seek_on_click: bool = True

    def _initialize_store_time_series(
        self,
        start_time_s: float,
        *,
        tiers: Sequence[TierName] = ("series",),
    ) -> None:
        """Initialize store/range state and elapsed-time conversion."""
        self._initialize_store_series(start_time_s, tiers=tiers)
        self._time_series_origin_s = start_time_s
        self._time_series_divisor_s = 1.0

    def _configure_time_series_axes(
        self,
        axes: Sequence[Axes],
        *,
        start_time_s: float,
        time_unit: TimeUnit,
        seek_enabled: bool | None = None,
    ) -> None:
        """Apply shared labels and click-seek metadata to time-series axes."""
        divisor_s = time_unit.get_divisor_s()
        seek_allowed = self.seek_on_click if seek_enabled is None else seek_enabled
        self._time_series_origin_s = start_time_s
        self._time_series_divisor_s = divisor_s
        for axis in axes:
            axis.set_xlabel(time_unit.get_axis_label())
            setattr(axis, "_play_oem_seek_enabled", seek_allowed)
            setattr(axis, "_play_oem_time_origin_s", start_time_s)
            setattr(axis, "_play_oem_time_divisor_s", divisor_s)

    def _prepare_store_time_series_context(
        self,
        context: StoreViewContext,
    ) -> None:
        """Bind a store snapshot and configure all time-series axes."""
        self._prepare_store_context(context)
        if self._figure is not None:
            self._configure_time_series_axes(
                tuple(self._figure.axes),
                start_time_s=context.coverage[0],
                time_unit=context.time_unit,
            )

    def _begin_store_time_series_update(
        self,
        context: StoreViewContext,
        *,
        axis_indexes: Sequence[int] | None = None,
    ) -> None:
        """Prepare a store snapshot update and refresh time-axis metadata."""
        self._begin_store_context_update(context, axis_indexes=axis_indexes)
        if self._figure is not None:
            indexes = (
                tuple(range(len(self._figure.axes)))
                if axis_indexes is None
                else tuple(axis_indexes)
            )
            axes = tuple(self._figure.axes[index] for index in indexes)
            self._configure_time_series_axes(
                axes,
                start_time_s=context.coverage[0],
                time_unit=context.time_unit,
            )

    def _axis_time(self, time_s: float) -> float:
        """Convert an absolute OEM time to elapsed axis units."""
        return (
            time_s - self._time_series_origin_s
        ) / self._time_series_divisor_s

    def _axis_times(self, times_s: np.ndarray) -> np.ndarray:
        """Convert absolute OEM times to elapsed axis units."""
        return (
            np.asarray(times_s, dtype=float) - self._time_series_origin_s
        ) / self._time_series_divisor_s

    def _absolute_time_from_axis(self, axis_value: float) -> float:
        """Convert elapsed axis units back to an absolute OEM time."""
        return (
            self._time_series_origin_s
            + float(axis_value) * self._time_series_divisor_s
        )

    def _axis_bounds(
        self,
        bounds: ResolvedTimeRange | None,
        coverage: tuple[float, float],
    ) -> tuple[float, float]:
        """Convert a range and coverage pair to elapsed axis limits."""
        return time_bounds_to_axis(
            bounds,
            coverage,
            self._time_series_origin_s,
            self._time_series_divisor_s,
        )

    def _close_store_time_series(self) -> None:
        """Release shared store/range/figure resources."""
        self._close_store_series_plot()


def __getattr__(name: str) -> object:
    if name == "TimeSeriesWxPanelMixin":
        from .time_series_support import TimeSeriesWxPanelMixin

        return TimeSeriesWxPanelMixin
    raise AttributeError(name)


