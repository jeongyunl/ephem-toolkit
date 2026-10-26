"""Tests for sampled access intervals and OEM boundary handling."""

from __future__ import annotations

import numpy as np
import pytest
from pyproj import Transformer

from ephem_toolkit.play_oem.cursor import CursorStatus, OemCursor
from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem.ground_track import GroundTrackSource
from ephem_toolkit.play_oem import ground_track, station_access
from ephem_toolkit.play_oem.station_access import (
    MAX_ACCESS_SAMPLE_STEP_S,
    StationAccessCache,
    current_station_metrics,
    prepare_station_access,
)

_GEODETIC_TO_ECEF = Transformer.from_crs(
    "EPSG:4979", "EPSG:4978", always_xy=True
)


def _source(
    times: list[float],
    states: np.ndarray,
    segments: list[int] | None = None,
    *,
    frame: str = "ITRF",
) -> GroundTrackSource:
    ids = segments if segments is not None else [0] * len(times)
    return GroundTrackSource.from_samples(times, states, ids, "EARTH", frame)


def _cursor(source: GroundTrackSource) -> OemCursor:
    return OemCursor(
        source.timestamps_s,
        source.states_m,
        segment_ids=source.segment_ids,
    )


def _state_at_elevation(elevation_deg: float) -> np.ndarray:
    x, y, z = _GEODETIC_TO_ECEF.transform(0.0, 0.0, 0.0)
    elevation = np.deg2rad(elevation_deg)
    return np.array(
        [
            x + np.sin(elevation) * 1_000_000.0,
            y + np.cos(elevation) * 1_000_000.0,
            z,
            0.0,
            0.0,
            0.0,
        ]
    )


def test_current_metrics_are_unavailable_outside_or_in_segment_gap() -> None:
    source = _source(
        [0.0, 10.0, 20.0, 30.0],
        np.tile(_state_at_elevation(45.0), (4, 1)),
        [0, 0, 1, 1],
    )
    station = GroundStation("id", "Site", 0.0, 0.0, 0.0)

    assert current_station_metrics(station, _cursor(source), 15.0, source) is None
    assert current_station_metrics(station, _cursor(source), -1.0, source) is None
    assert current_station_metrics(station, _cursor(source), 5.0, source) is not None
    assert _cursor(source).lookup(15.0).status == CursorStatus.GAP


def test_pass_crossings_are_refined_and_clipped_to_coverage() -> None:
    source = _source(
        [0.0, 60.0, 120.0],
        np.vstack(
            [
                _state_at_elevation(0.0),
                _state_at_elevation(60.0),
                _state_at_elevation(0.0),
            ]
        ),
    )
    station = GroundStation("id", "Site", 0.0, 0.0, 0.0, 30)

    access = prepare_station_access(source, _cursor(source), station)

    assert len(access.intervals) == 1
    interval = access.intervals[0]
    assert interval.start_s == pytest.approx(30.0, abs=2.0)
    assert interval.end_s == pytest.approx(90.0, abs=2.0)
    assert interval.peak_elevation_deg > 50.0
    assert interval.start_azimuth_deg == pytest.approx(90.0, abs=1e-6)
    assert interval.end_azimuth_deg == pytest.approx(90.0, abs=1e-6)
    assert interval.start_elevation_deg == pytest.approx(30.0, abs=1.0)
    assert interval.end_elevation_deg == pytest.approx(30.0, abs=1.0)
    assert not interval.clipped_at_start
    assert not interval.clipped_at_end
    profile = access.look_angle_profiles[0]
    assert np.array_equal(profile.times_s, access.elevation_profiles[0].times_s)
    assert np.array_equal(profile.elevations_deg, access.elevation_profiles[0].elevations_deg)
    assert np.isfinite(profile.azimuths_deg).all()
    assert np.all((profile.azimuths_deg >= 0.0) & (profile.azimuths_deg < 360.0))
    assert MAX_ACCESS_SAMPLE_STEP_S == 30.0


def test_coverage_edge_access_is_marked_clipped() -> None:
    source = _source(
        [0.0, 60.0, 120.0],
        np.vstack(
            [
                _state_at_elevation(45.0),
                _state_at_elevation(60.0),
                _state_at_elevation(45.0),
            ]
        ),
    )
    station = GroundStation("id", "Site", 0.0, 0.0, 0.0, 30)

    interval = prepare_station_access(source, _cursor(source), station).intervals[0]

    assert interval.clipped_at_start
    assert interval.clipped_at_end
    assert interval.start_s == 0.0
    assert interval.end_s == 120.0


def test_large_source_sample_gap_marks_prediction_unavailable() -> None:
    source = _source(
        [0.0, 301.0],
        np.vstack([_state_at_elevation(0.0), _state_at_elevation(60.0)]),
    )
    station = GroundStation("id", "Site", 0.0, 0.0, 0.0, 10)

    result = prepare_station_access(source, _cursor(source), station)

    assert result.intervals == ()
    assert "exceeds five minutes" in result.limitation


def test_access_intervals_stop_at_segment_gaps() -> None:
    source = _source(
        [0.0, 60.0, 120.0, 180.0],
        np.tile(_state_at_elevation(45.0), (4, 1)),
        [0, 0, 1, 1],
    )
    station = GroundStation("id", "Site", 0.0, 0.0, 0.0, 30)

    result = prepare_station_access(source, _cursor(source), station)

    assert len(result.intervals) == 2
    assert result.intervals[0].end_s == 60.0
    assert result.intervals[0].limited_by_gap_at_end
    assert result.intervals[1].start_s == 120.0
    assert result.intervals[1].limited_by_gap_at_start
    assert "segment gap" in result.limitation


def test_current_metrics_reject_non_earth_center() -> None:
    source = GroundTrackSource.from_samples(
        [0.0, 10.0],
        np.tile(_state_at_elevation(45.0), (2, 1)),
        [0, 0],
        "MARS",
        "ITRF",
    )
    station = GroundStation("id", "Site", 0.0, 0.0, 0.0)

    with pytest.raises(ValueError, match="Earth-centered"):
        current_station_metrics(station, _cursor(source), 5.0, source)


def test_substep_local_maximum_finds_a_narrow_access_pass(monkeypatch) -> None:
    source = _source(
        [0.0, 120.0],
        np.vstack([_state_at_elevation(0.0), _state_at_elevation(0.0)]),
    )
    station = GroundStation("id", "Site", 0.0, 0.0, 0.0, 10)

    def synthetic_metrics(_station, _state, _frame, epoch):
        elevation = 20.0 * np.exp(-((epoch - 45.0) / 2.0) ** 2)
        return station_access.StationMetrics(0.0, elevation, 100.0, elevation >= 10.0)

    monkeypatch.setattr(station_access, "station_metrics", synthetic_metrics)

    result = prepare_station_access(source, _cursor(source), station)

    assert len(result.intervals) == 1
    interval = result.intervals[0]
    assert interval.start_s == pytest.approx(43.3, abs=0.5)
    assert interval.end_s == pytest.approx(46.7, abs=0.5)
    assert interval.peak_time_s == pytest.approx(45.0, abs=1.0)


def test_access_cache_reuses_same_inputs_and_recomputes_changed_station(
    monkeypatch,
) -> None:
    source = _source(
        [0.0, 10.0],
        np.tile(_state_at_elevation(45.0), (2, 1)),
    )
    station = GroundStation("id", "Site", 0.0, 0.0, 0.0)
    calls = []

    def prepare(source_arg, cursor_arg, station_arg, _position_cache):
        calls.append((source_arg, cursor_arg, station_arg))
        return station_access.StationAccess(station_arg, ())

    monkeypatch.setattr(station_access, "prepare_station_access", prepare)
    cache = StationAccessCache()
    cursor = _cursor(source)

    first = cache.prepare(source, cursor, station)
    second = cache.prepare(source, cursor, station)
    changed = GroundStation("id", "Site", 1.0, 0.0, 0.0)
    third = cache.prepare(source, cursor, changed)

    assert first is second
    assert third.station == changed
    assert len(calls) == 2


def test_ground_track_and_access_share_converted_sample_positions(monkeypatch) -> None:
    source = _source(
        [0.0, 120.0],
        np.tile([6_878_137.0, 0.0, 0.0, 0.0, 7_500.0, 0.0], (2, 1)),
    )
    station = GroundStation("id", "Site", 0.0, 0.0, 0.0, 0)
    position_cache = ground_track.EarthFixedPositionCache()
    original_converter = ground_track.state_position_to_itrf_m
    conversions = []

    def convert(state, frame_name, epoch):
        conversions.append(epoch)
        return original_converter(state, frame_name, epoch)

    monkeypatch.setattr(ground_track, "state_position_to_itrf_m", convert)

    ground_track.prepare_ground_track(source, position_cache=position_cache)
    StationAccessCache(position_cache).prepare(source, _cursor(source), station)

    assert conversions == [0.0, 120.0, 30.0, 60.0, 90.0]
