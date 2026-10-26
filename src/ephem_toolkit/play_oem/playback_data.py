"""Prepare an OEM and its playback data for the interactive player."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from ephem_toolkit.core.interpolator.interpolation_spec import (
    DEFAULT_HERMITE_DEGREE,
    InterpolationType,
)
from ephem_toolkit.core.ccsds.oem import OemStateBatch
from ephem_toolkit.core import time_utils
import numpy as np

from . import clock as playback_clock, cursor, series, time_unit
from .data import read_oem_states
from .ground_track import GroundTrackSource
from .display_time import UTC_DISPLAY, format_tt


@dataclass
class AppendablePlaybackData:
    """Incremental source and derived data for a partially loaded OEM."""

    series: series.OrbitSeries
    time_unit: time_unit.TimeUnit
    cursor: cursor.OemCursor
    ground_track_source: GroundTrackSource
    center_name: str
    frame_name: str
    _series_accumulator: series.OrbitSeriesAccumulator = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._series_accumulator = series.OrbitSeriesAccumulator(self.series)

    @classmethod
    def from_batch(
        cls,
        batch: OemStateBatch,
        *,
        center_name: str,
        frame_name: str,
        interpolation_method: str = InterpolationType.HERMITE.value,
        interpolation_degree: int = DEFAULT_HERMITE_DEGREE,
    ) -> AppendablePlaybackData:
        """Build an incremental store from its first non-empty parser batch."""
        timestamps_s = [float(timestamp) for timestamp, _ in batch.states]
        states_m = [np.asarray(state, dtype=float).copy() for _, state in batch.states]
        segment_ids = [int(segment_id) for segment_id in batch.segment_ids]
        cls._validate_batch(timestamps_s, states_m, segment_ids)
        selected_time_unit = time_unit.TimeUnit.for_duration(
            timestamps_s[-1] - timestamps_s[0]
        )
        orbit_series = series.align_single_sample_series(
            series.compute_orbit_series(
                timestamps_s, states_m, selected_time_unit, segment_ids
            )
        )
        state_cursor = cursor.OemCursor(
            timestamps_s,
            states_m,
            interpolation=interpolation_method,
            interpolation_degree=interpolation_degree,
            segment_ids=segment_ids,
        )
        return cls(
            orbit_series,
            selected_time_unit,
            state_cursor,
            GroundTrackSource(
                state_cursor.timestamps_s,
                state_cursor.states_m,
                state_cursor.segment_ids,
                center_name,
                frame_name,
            ),
            center_name,
            frame_name,
        )

    @property
    def source_sample_count(self) -> int:
        """Number of states in the currently loaded prefix."""
        return len(self.timestamps_s)

    @property
    def timestamps_s(self) -> np.ndarray:
        """Loaded source epochs shared with the cursor storage."""
        return self.cursor.timestamps_s

    @property
    def states_m(self) -> np.ndarray:
        """Loaded SI states shared with the cursor storage."""
        return self.cursor.states_m

    @property
    def segment_ids(self) -> np.ndarray:
        """Loaded segment IDs shared with the cursor storage."""
        return self.cursor.segment_ids

    def append_batch(self, batch: OemStateBatch) -> None:
        """Append a parser batch and derive only new rows plus its boundary pair."""
        new_timestamps_s = [float(timestamp) for timestamp, _ in batch.states]
        new_states_m = [np.asarray(state, dtype=float).copy() for _, state in batch.states]
        new_segment_ids = [int(segment_id) for segment_id in batch.segment_ids]
        self._validate_batch(new_timestamps_s, new_states_m, new_segment_ids)
        old_timestamps_s = self.timestamps_s
        old_states_m = self.states_m
        old_segment_ids = self.segment_ids
        if new_timestamps_s[0] <= old_timestamps_s[-1]:
            raise ValueError("appended timestamps must follow loaded timestamps")
        if new_segment_ids[0] < old_segment_ids[-1]:
            raise ValueError("appended segment IDs must not move backwards")

        final_span_s = new_timestamps_s[-1] - old_timestamps_s[0]
        next_time_unit = time_unit.TimeUnit.for_duration(final_span_s)
        if next_time_unit != self.time_unit:
            self._rescale_time_axes(next_time_unit)

        next_series = self._series_accumulator.append(
            old_timestamps_s[-1],
            old_states_m[-1],
            int(old_segment_ids[-1]),
            new_timestamps_s,
            new_states_m,
            new_segment_ids,
            self.time_unit,
        )
        self.cursor.append(new_timestamps_s, new_states_m, new_segment_ids)
        self.series = next_series
        self.ground_track_source = GroundTrackSource(
            self.cursor.timestamps_s,
            self.cursor.states_m,
            self.cursor.segment_ids,
            self.center_name,
            self.frame_name,
        )

    def _rescale_time_axes(self, new_unit: time_unit.TimeUnit) -> None:
        """Switch elapsed-time units when observed coverage crosses one hour."""
        divisor = new_unit.get_divisor_s()
        origin = self.timestamps_s[0]
        self.series = replace(
            self.series,
            elapsed_time=(self.timestamps_s - origin) / divisor,
            rtn_elapsed_time=(self.timestamps_s[1:] - origin) / divisor,
        )
        self._series_accumulator = series.OrbitSeriesAccumulator(self.series)
        self.time_unit = new_unit

    @staticmethod
    def _validate_batch(
        timestamps_s: list[float],
        states_m: list[np.ndarray],
        segment_ids: list[int],
    ) -> None:
        """Validate ordering, finiteness, and alignment before mutating the store."""
        if not timestamps_s:
            raise ValueError("state batch must not be empty")
        if len(states_m) != len(timestamps_s) or len(segment_ids) != len(timestamps_s):
            raise ValueError("timestamps, states, and segment IDs must be aligned")
        timestamp_array = np.asarray(timestamps_s, dtype=float)
        if not np.all(np.isfinite(timestamp_array)) or np.any(
            np.diff(timestamp_array) <= 0.0
        ):
            raise ValueError("timestamps in each batch must be finite and increasing")
        if any(state.shape != (6,) or not np.all(np.isfinite(state)) for state in states_m):
            raise ValueError("each state must be a finite 6D vector")
        if np.any(np.diff(np.asarray(segment_ids, dtype=int)) < 0):
            raise ValueError("segment IDs must be non-decreasing")


@dataclass
class PlaybackData:
    """All file-dependent state required by a playback window."""

    clock: playback_clock.PlaybackClock
    series: series.OrbitSeries
    time_unit: time_unit.TimeUnit
    cursor: cursor.OemCursor
    object_name: str
    frame_context: str
    dashboard_context: dict[str, str]
    metadata_details: tuple[tuple[str, str], ...]
    source_sample_count: int
    ground_track_source: GroundTrackSource | None = None
    oem_interpolation: str | None = None
    oem_interpolation_degree: int | None = None
    incremental_store: AppendablePlaybackData | None = None
    slider_bounds: tuple[float, float] | None = None


@dataclass(frozen=True)
class PreparedPlaybackBatch:
    """Worker-prepared data handed to the GUI for a short install step."""

    initial_data: PlaybackData | None
    incremental_store: AppendablePlaybackData
    timestamps_s: tuple[float, ...]
    series: series.OrbitSeries
    time_unit: time_unit.TimeUnit
    cursor: cursor.OemCursor
    ground_track_source: GroundTrackSource
    source_sample_count: int
    slider_bounds: tuple[float, float]


class IncrementalPlaybackPreparer:
    """Derive an OEM stream on its loader thread and publish each prefix."""

    def __init__(
        self,
        source: str | Path,
        *,
        use_oem_interpolation: bool = False,
        interpolation_method: str = InterpolationType.HERMITE.value,
        interpolation_degree: int = DEFAULT_HERMITE_DEGREE,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        self.source = source
        self.use_oem_interpolation = use_oem_interpolation
        self.interpolation_method = interpolation_method
        self.interpolation_degree = interpolation_degree
        self.display_time_zone = display_time_zone
        self._store: AppendablePlaybackData | None = None
        self._initial_data: PlaybackData | None = None
        self._slider_bounds: tuple[float, float] | None = None

    def __call__(self, batch: OemStateBatch) -> PreparedPlaybackBatch:
        if self._store is None:
            self._initial_data = playback_data_from_batch(
                batch,
                self.source,
                use_oem_interpolation=self.use_oem_interpolation,
                interpolation_method=self.interpolation_method,
                interpolation_degree=self.interpolation_degree,
                display_time_zone=self.display_time_zone,
            )
            self._store = self._initial_data.incremental_store
        else:
            self._store.append_batch(batch)

        assert self._store is not None
        observed_bounds = (
            float(self._store.timestamps_s[0]),
            float(self._store.timestamps_s[-1]),
        )
        batch_meta = dict(batch.meta)
        batch_bounds = oem_slider_bounds(
            str(batch_meta.get("START_TIME", "")),
            str(batch_meta.get("STOP_TIME", "")),
            observed_bounds,
        )
        self._slider_bounds = _merge_time_bounds(self._slider_bounds, batch_bounds)
        initial_data = self._initial_data
        self._initial_data = None
        return PreparedPlaybackBatch(
            initial_data,
            self._store,
            tuple(float(timestamp) for timestamp, _ in batch.states),
            self._store.series,
            self._store.time_unit,
            self._store.cursor,
            self._store.ground_track_source,
            self._store.source_sample_count,
            self._slider_bounds or observed_bounds,
        )


def _merge_time_bounds(
    existing: tuple[float, float] | None,
    incoming: tuple[float, float],
) -> tuple[float, float]:
    if existing is None:
        return incoming
    return min(existing[0], incoming[0]), max(existing[1], incoming[1])


def oem_slider_bounds(
    start_time: str,
    stop_time: str,
    observed_bounds: tuple[float, float],
) -> tuple[float, float]:
    """Return an ordered slider domain using declared bounds plus observed data."""
    declared: list[float] = []
    for value in (start_time, stop_time):
        if not value.strip():
            continue
        try:
            declared.append(
                time_utils.datetime_to_tt_s(time_utils.iso8601_to_datetime(value))
            )
        except (TypeError, ValueError, OverflowError):
            continue
    candidates = [*observed_bounds, *declared]
    lower = min(candidates)
    upper = max(candidates)
    if len(declared) == 2 and declared[0] > declared[1]:
        return observed_bounds
    return lower, upper


def load_playback_data(
    source: str | Path,
    *,
    use_oem_interpolation: bool = False,
    interpolation_method: str = InterpolationType.HERMITE.value,
    interpolation_degree: int = DEFAULT_HERMITE_DEGREE,
    display_time_zone: str = UTC_DISPLAY,
) -> PlaybackData:
    """Read and prepare an entire OEM for playback."""
    oem_data, timestamps_s, states_m = read_oem_states(source)
    source_sample_count = len(states_m)
    # Choose the time-axis unit from the full span of this OEM.
    selected_time_unit = time_unit.TimeUnit.for_duration(
        timestamps_s[-1] - timestamps_s[0]
    )

    # Keep all samples and their segment IDs together across the full OEM span.
    segment_ids = oem_data.segment_ids[: len(timestamps_s)]
    orbit_series = series.compute_orbit_series(
        timestamps_s, states_m, selected_time_unit, segment_ids
    )
    # Clock defaults start paused at the first sample, at 1x speed without looping.
    clock = playback_clock.PlaybackClock(
        timestamps_s[0],
        timestamps_s[-1],
        sample_times=timestamps_s,
    )

    state_cursor = cursor.OemCursor(
        timestamps_s,
        states_m,
        interpolation=(
            oem_data.meta.interpolation
            if use_oem_interpolation
            else interpolation_method
        ),
        interpolation_degree=(
            oem_data.meta.interpolation_degree
            if use_oem_interpolation
            else interpolation_degree
        ),
        segment_ids=segment_ids,
    )
    frame_context = (
        " / ".join(
            value
            for value in (
                oem_data.meta.ref_frame.strip(),
                oem_data.meta.center_name.strip(),
            )
            if value
        )
        or "Frame metadata unavailable"
    )
    object_name = oem_data.meta.object_name.strip() or Path(source).name
    dashboard_context = {
        "object": object_name,
        "frame": oem_data.meta.ref_frame.strip(),
        "center": oem_data.meta.center_name.strip(),
        "time_span": (
            f"{format_tt(timestamps_s[0], display_time_zone)} – "
            f"{format_tt(timestamps_s[-1], display_time_zone)}"
        ),
        "sample_count": str(len(timestamps_s)),
    }
    metadata_details = (
        ("Object ID", oem_data.meta.object_id),
        ("Time system", oem_data.meta.time_system),
        ("Frame epoch", oem_data.meta.ref_frame_epoch),
        ("Usable start", oem_data.meta.useable_start_time),
        ("Usable stop", oem_data.meta.useable_stop_time),
        ("Interpolation", oem_data.meta.interpolation or ""),
        (
            "Interpolation degree",
            (
                ""
                if oem_data.meta.interpolation_degree is None
                else str(oem_data.meta.interpolation_degree)
            ),
        ),
    )
    return PlaybackData(
        clock,
        orbit_series,
        selected_time_unit,
        state_cursor,
        object_name,
        frame_context,
        dashboard_context,
        metadata_details,
        source_sample_count,
        GroundTrackSource.from_samples(
            timestamps_s,
            states_m,
            segment_ids,
            oem_data.meta.center_name,
            oem_data.meta.ref_frame,
        ),
        oem_data.meta.interpolation,
        oem_data.meta.interpolation_degree,
        slider_bounds=oem_slider_bounds(
            oem_data.meta.start_time,
            oem_data.meta.stop_time,
            (timestamps_s[0], timestamps_s[-1]),
        ),
    )


def playback_data_from_batch(
    batch: OemStateBatch,
    source: str | Path,
    *,
    use_oem_interpolation: bool = False,
    interpolation_method: str = InterpolationType.HERMITE.value,
    interpolation_degree: int = DEFAULT_HERMITE_DEGREE,
    display_time_zone: str = UTC_DISPLAY,
) -> PlaybackData:
    """Create the first visible playback model from a parser batch."""
    raw_meta = dict(batch.meta)
    oem_interpolation = str(raw_meta.get("INTERPOLATION", "")) or None
    oem_interpolation_degree_value = raw_meta.get("INTERPOLATION_DEGREE")
    oem_interpolation_degree = (
        None
        if oem_interpolation_degree_value is None
        else int(oem_interpolation_degree_value)
    )
    selected_interpolation = (
        oem_interpolation if use_oem_interpolation else interpolation_method
    )
    selected_degree = (
        oem_interpolation_degree if use_oem_interpolation else interpolation_degree
    )
    center_name = str(raw_meta.get("CENTER_NAME", ""))
    frame_name = str(raw_meta.get("REF_FRAME", ""))
    store = AppendablePlaybackData.from_batch(
        batch,
        center_name=center_name,
        frame_name=frame_name,
        interpolation_method=selected_interpolation or InterpolationType.HERMITE.value,
        interpolation_degree=selected_degree,
    )
    first_time_s = store.timestamps_s[0]
    last_time_s = store.timestamps_s[-1]
    clock = playback_clock.PlaybackClock(
        first_time_s,
        last_time_s,
        sample_times=store.timestamps_s,
    )
    frame_context = " / ".join(
        value for value in (frame_name.strip(), center_name.strip()) if value
    ) or "Frame metadata unavailable"
    source_name = Path(source).name
    object_name = str(raw_meta.get("OBJECT_NAME", "")).strip() or source_name
    dashboard_context = {
        "object": object_name,
        "frame": frame_name,
        "center": center_name,
        "time_span": (
            f"{format_tt(first_time_s, display_time_zone)} – "
            f"{format_tt(last_time_s, display_time_zone)}"
        ),
        "sample_count": str(store.source_sample_count),
    }
    metadata_details = (
        ("Object ID", str(raw_meta.get("OBJECT_ID", ""))),
        ("Time system", str(raw_meta.get("TIME_SYSTEM", ""))),
        ("Frame epoch", str(raw_meta.get("REF_FRAME_EPOCH", ""))),
        ("Usable start", str(raw_meta.get("USEABLE_START_TIME", ""))),
        ("Usable stop", str(raw_meta.get("USEABLE_STOP_TIME", ""))),
        ("Interpolation", oem_interpolation or ""),
        (
            "Interpolation degree",
            "" if oem_interpolation_degree is None else str(oem_interpolation_degree),
        ),
    )
    return PlaybackData(
        clock,
        store.series,
        store.time_unit,
        store.cursor,
        object_name,
        frame_context,
        dashboard_context,
        metadata_details,
        store.source_sample_count,
        store.ground_track_source,
        oem_interpolation,
        oem_interpolation_degree,
        store,
        oem_slider_bounds(
            str(raw_meta.get("START_TIME", "")),
            str(raw_meta.get("STOP_TIME", "")),
            (first_time_s, last_time_s),
        ),
    )

def empty_playback_data() -> PlaybackData:
    """Create inert backing state for the window before an OEM is selected."""
    # The existing controls expect non-empty clock and cursor objects. Keep one
    # private sample behind the empty UI; playback and graph controls stay disabled.
    # Use hours as a neutral placeholder until an OEM determines the axis unit.
    selected_time_unit = time_unit.TimeUnit.HOURS
    timestamp = 0.0
    state = np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0])
    orbit_series = series.compute_orbit_series([timestamp], [state], selected_time_unit)
    empty_clock = playback_clock.PlaybackClock(
        timestamp, timestamp, sample_times=[timestamp]
    )
    empty_cursor = cursor.OemCursor([timestamp], [state])
    return PlaybackData(
        empty_clock,
        orbit_series,
        selected_time_unit,
        empty_cursor,
        "No OEM loaded",
        "",
        {
            "object": "No OEM loaded",
            "frame": "",
            "center": "",
            "time_span": "",
            "sample_count": "0",
        },
        (
            ("Object ID", ""),
            ("Time system", ""),
            ("Frame epoch", ""),
            ("Usable start", ""),
            ("Usable stop", ""),
            ("Interpolation", ""),
            ("Interpolation degree", ""),
        ),
        0,
    )
