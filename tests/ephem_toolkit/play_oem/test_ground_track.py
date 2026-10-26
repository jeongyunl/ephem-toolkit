"""Headless tests for Earth-fixed Ground Track data preparation."""

from __future__ import annotations

import numpy as np
import pytest
from pyproj import Transformer

from ephem_toolkit.play_oem import ground_track

_WGS84_GEODETIC_TO_ECEF = Transformer.from_crs("EPSG:4979", "EPSG:4978", always_xy=True)


def _source(
    geodetic_deg: list[tuple[float, float]],
    *,
    segment_ids: list[int] | None = None,
    center_name: str = "EARTH",
    frame_name: str = "ITRF",
) -> ground_track.GroundTrackSource:
    longitudes_deg = np.asarray([lon for lat, lon in geodetic_deg], dtype=float)
    latitudes_deg = np.asarray([lat for lat, lon in geodetic_deg], dtype=float)
    altitudes = np.zeros(len(geodetic_deg), dtype=float)
    if len(geodetic_deg) == 1:
        longitudes_m, latitudes_m, altitudes_m = _WGS84_GEODETIC_TO_ECEF.transform(
            float(longitudes_deg[0]), float(latitudes_deg[0]), 0.0
        )
        longitudes_m = [longitudes_m]
        latitudes_m = [latitudes_m]
        altitudes_m = [altitudes_m]
    else:
        longitudes_m, latitudes_m, altitudes_m = _WGS84_GEODETIC_TO_ECEF.transform(
            longitudes_deg, latitudes_deg, altitudes
        )
    positions = np.column_stack((longitudes_m, latitudes_m, altitudes_m))
    states = np.column_stack((positions, np.zeros_like(positions)))
    count = len(geodetic_deg)
    return ground_track.GroundTrackSource.from_samples(
        np.arange(count, dtype=float) * 10.0,
        states,
        segment_ids if segment_ids is not None else [0] * count,
        center_name,
        frame_name,
    )


def test_prepare_direct_earth_fixed_positions_returns_wgs84_radians() -> None:
    prepared = ground_track.prepare_ground_track(
        _source([(0.0, 0.0), (45.0, 90.0), (-90.0, -45.0)], frame_name="ITRF93")
    )

    np.testing.assert_allclose(prepared.latitude_rad, np.deg2rad([0.0, 45.0, -90.0]))
    np.testing.assert_allclose(prepared.longitude_rad[:2], np.deg2rad([0.0, 90.0]))
    assert prepared.source_frame == "ITRF1993"


def test_prepare_normalizes_earth_center_and_itrf_frame_alias() -> None:
    prepared = ground_track.prepare_ground_track(
        _source([(0.0, 180.0)], center_name=" 399 ", frame_name="itrf93")
    )

    assert prepared.source_frame == "ITRF1993"
    assert prepared.longitude_rad[0] == pytest.approx(np.pi)


def test_prepare_converts_inertial_states_at_each_tt_epoch(monkeypatch) -> None:
    direct = _source([(10.0, -75.0), (11.0, -74.0)])
    calls: list[tuple[str, float]] = []

    def convert(frame_name: str, epoch_tt_s: float, state_m: np.ndarray) -> np.ndarray:
        calls.append((frame_name, epoch_tt_s))
        return state_m

    monkeypatch.setattr(ground_track, "_convert_inertial_state_to_itrf", convert)
    inertial = ground_track.GroundTrackSource.from_samples(
        direct.timestamps_s,
        direct.states_m,
        direct.segment_ids,
        "earth",
        "GCRF",
    )

    prepared = ground_track.prepare_ground_track(inertial)

    assert calls == [("GCRF", 0.0), ("GCRF", 10.0)]
    np.testing.assert_allclose(prepared.latitude_rad, np.deg2rad([10.0, 11.0]))
    np.testing.assert_allclose(prepared.longitude_rad, np.deg2rad([-75.0, -74.0]))


@pytest.mark.parametrize("center", ["MARS", "EARTH BARYCENTER", ""])
def test_prepare_rejects_non_earth_centers(center: str) -> None:
    with pytest.raises(
        ground_track.GroundTrackPreparationError, match="Earth-centered"
    ):
        ground_track.prepare_ground_track(_source([(0.0, 0.0)], center_name=center))


@pytest.mark.parametrize("frame", ["ITRF2000", "ITRF1997", "TOD", "UNKNOWN"])
def test_prepare_rejects_unsupported_frames(frame: str) -> None:
    with pytest.raises(ground_track.GroundTrackPreparationError, match="not supported"):
        ground_track.prepare_ground_track(_source([(0.0, 0.0)], frame_name=frame))


def test_prepare_reports_frame_conversion_failure(monkeypatch) -> None:
    def fail(_frame_name: str, _epoch_tt_s: float, _state_m: np.ndarray) -> np.ndarray:
        raise RuntimeError("kernel range is unavailable")

    monkeypatch.setattr(ground_track, "_convert_inertial_state_to_itrf", fail)
    with pytest.raises(ground_track.GroundTrackPreparationError, match="kernel range"):
        ground_track.prepare_ground_track(_source([(0.0, 0.0)], frame_name="J2000"))


def test_prepare_rejects_positions_inside_the_wgs84_ellipsoid() -> None:
    source = ground_track.GroundTrackSource.from_samples(
        [0.0], [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]], [0], "EARTH", "ITRF"
    )

    with pytest.raises(ground_track.GroundTrackPreparationError, match="inside"):
        ground_track.prepare_ground_track(source)


def test_split_track_runs_at_segments_and_eastward_date_line() -> None:
    prepared = ground_track.prepare_ground_track(
        _source(
            [(0.0, 170.0), (10.0, -170.0), (20.0, -160.0), (30.0, 170.0)],
            segment_ids=[0, 0, 0, 1],
        )
    )

    runs = ground_track.split_ground_track_runs(prepared, 0.0)

    assert len(runs) == 3
    np.testing.assert_allclose(
        np.rad2deg(runs[0].longitude_relative_rad), [170.0, 180.0]
    )
    np.testing.assert_allclose(
        np.rad2deg(runs[1].longitude_relative_rad), [-180.0, -170.0, -160.0]
    )
    np.testing.assert_allclose(np.rad2deg(runs[2].longitude_relative_rad), [170.0])
    assert runs[0].timestamps_s[-1] == pytest.approx(5.0)
    assert runs[1].timestamps_s[0] == pytest.approx(5.0)


def test_split_track_handles_westward_date_line_and_adjustable_center() -> None:
    prepared = ground_track.prepare_ground_track(
        _source([(-5.0, -170.0), (5.0, 170.0)])
    )

    across_zero = ground_track.split_ground_track_runs(prepared, 0.0)
    around_180 = ground_track.split_ground_track_runs(prepared, 180.0)

    assert len(across_zero) == 2
    np.testing.assert_allclose(
        np.rad2deg(across_zero[0].longitude_relative_rad), [-170.0, -180.0]
    )
    np.testing.assert_allclose(
        np.rad2deg(across_zero[1].longitude_relative_rad), [180.0, 170.0]
    )
    assert len(around_180) == 1
    np.testing.assert_allclose(
        np.rad2deg(around_180[0].longitude_relative_rad), [10.0, -10.0]
    )


def test_split_track_rejects_nonfinite_center_longitude() -> None:
    prepared = ground_track.prepare_ground_track(_source([(0.0, 0.0)]))

    with pytest.raises(ValueError, match="finite"):
        ground_track.split_ground_track_runs(prepared, float("nan"))


def test_prepare_with_bounds_converts_only_samples_near_the_window(monkeypatch) -> None:
    source = _source([(0.0, float(index)) for index in range(100)])
    source = ground_track.GroundTrackSource.from_samples(
        np.arange(100, dtype=float) * 60.0,
        source.states_m,
        source.segment_ids,
        source.center_name,
        source.frame_name,
    )
    cache = ground_track.EarthFixedPositionCache()

    coordinates = ground_track.prepare_ground_track(
        source, position_cache=cache, bounds=(3_000.0, 3_300.0)
    )

    assert coordinates.timestamps_s[0] == 2_940.0
    assert coordinates.timestamps_s[-1] == 3_360.0
    assert int(cache._computed.sum()) == len(coordinates.timestamps_s)
