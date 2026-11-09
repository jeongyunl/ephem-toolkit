"""Headless tests for Ground Track coordinate and seam handling."""

from __future__ import annotations

import numpy as np
import pytest

from ephem_toolkit.play_oem import ground_track


def _coordinates(
    points: list[tuple[float, float]], segment_ids: list[int] | None = None
) -> ground_track.GroundTrackCoordinates:
    count = len(points)
    return ground_track.GroundTrackCoordinates(
        np.arange(count, dtype=float) * 10.0,
        np.deg2rad([latitude for latitude, _ in points]),
        np.deg2rad([longitude for _, longitude in points]),
        np.asarray(segment_ids if segment_ids is not None else [0] * count),
        "ITRF",
    )


def test_state_position_to_itrf_normalizes_earth_fixed_alias() -> None:
    state = np.array([6_878_137.0, 1.0, 2.0, 0.0, 7_500.0, 0.0])

    position = ground_track.state_position_to_itrf_m(state, "itrf93", 5.0)

    np.testing.assert_array_equal(position, state[:3])
    assert not np.shares_memory(position, state)


def test_state_position_to_itrf_converts_inertial_state_at_epoch(monkeypatch) -> None:
    calls: list[tuple[str, float]] = []
    state = np.array([6_878_137.0, 0.0, 0.0, 0.0, 7_500.0, 0.0])

    def convert(frame: str, epoch: float, value: np.ndarray) -> np.ndarray:
        calls.append((frame, epoch))
        return value

    monkeypatch.setattr(ground_track, "_convert_inertial_state_to_itrf", convert)

    np.testing.assert_array_equal(
        ground_track.state_position_to_itrf_m(state, "GCRF", 42.0), state[:3]
    )
    assert calls == [("GCRF", 42.0)]


@pytest.mark.parametrize(
    ("state", "frame", "message"),
    [
        (np.zeros(5), "ITRF", "invalid"),
        (np.full(6, np.nan), "ITRF", "invalid"),
        (np.ones(6), "TOD", "not supported"),
    ],
)
def test_state_position_to_itrf_rejects_invalid_input(
    state: np.ndarray, frame: str, message: str
) -> None:
    with pytest.raises(ground_track.GroundTrackPreparationError, match=message):
        ground_track.state_position_to_itrf_m(state, frame, 0.0)


def test_split_track_runs_at_segments_and_eastward_date_line() -> None:
    runs = ground_track.split_ground_track_runs(
        _coordinates(
            [(0.0, 170.0), (10.0, -170.0), (20.0, -160.0), (30.0, 170.0)],
            [0, 0, 0, 1],
        ),
        0.0,
    )

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
    coordinates = _coordinates([(-5.0, -170.0), (5.0, 170.0)])

    across_zero = ground_track.split_ground_track_runs(coordinates, 0.0)
    around_180 = ground_track.split_ground_track_runs(coordinates, 180.0)

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
    with pytest.raises(ValueError, match="finite"):
        ground_track.split_ground_track_runs(_coordinates([(0.0, 0.0)]), float("nan"))
