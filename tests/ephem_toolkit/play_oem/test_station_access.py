"""Tests for station-access interval boundary handling."""

from ephem_toolkit.play_oem.ground_stations import GroundStation, StationMetrics
from ephem_toolkit.play_oem.station_access import _intervals_for_segment


class _NoLookupCursor:
    def lookup(self, _epoch: float, /):
        raise AssertionError("these samples do not require crossing refinement")


def _metrics(
    azimuth_deg: float,
    elevation_deg: float,
    slant_range_km: float,
) -> StationMetrics:
    return StationMetrics(azimuth_deg, elevation_deg, slant_range_km, True)


def test_missing_metric_splits_access_intervals_and_resets_extrema() -> None:
    station = GroundStation("test", "Test", 0.0, 0.0, 0.0)
    intervals = _intervals_for_segment(
        station,
        _NoLookupCursor(),
        "ITRF",
        (0.0, 10.0, 20.0, 30.0, 40.0),
        (
            _metrics(0.0, 20.0, 500.0),
            _metrics(10.0, 30.0, 400.0),
            None,
            _metrics(30.0, 25.0, 300.0),
            _metrics(40.0, 35.0, 200.0),
        ),
        starts_at_coverage=False,
        ends_at_coverage=False,
        starts_after_gap=False,
        ends_before_gap=False,
    )

    assert len(intervals) == 2
    first, second = intervals
    assert (first.start_s, first.end_s) == (0.0, 10.0)
    assert (first.peak_time_s, first.peak_elevation_deg) == (10.0, 30.0)
    assert (first.minimum_range_time_s, first.minimum_range_km) == (10.0, 400.0)
    assert not first.clipped_at_start
    assert first.clipped_at_end
    assert (second.start_s, second.end_s) == (30.0, 40.0)
    assert (second.peak_time_s, second.peak_elevation_deg) == (40.0, 35.0)
    assert (second.minimum_range_time_s, second.minimum_range_km) == (40.0, 200.0)
    assert not second.clipped_at_start
    assert not second.clipped_at_end


def test_interval_records_coverage_and_gap_limited_endpoints() -> None:
    station = GroundStation("test", "Test", 0.0, 0.0, 0.0)
    intervals = _intervals_for_segment(
        station,
        _NoLookupCursor(),
        "ITRF",
        (10.0, 20.0),
        (_metrics(0.0, 20.0, 500.0), _metrics(10.0, 30.0, 400.0)),
        starts_at_coverage=True,
        ends_at_coverage=True,
        starts_after_gap=True,
        ends_before_gap=True,
    )

    assert len(intervals) == 1
    interval = intervals[0]
    assert interval.clipped_at_start
    assert interval.clipped_at_end
    assert interval.limited_by_gap_at_start
    assert interval.limited_by_gap_at_end
