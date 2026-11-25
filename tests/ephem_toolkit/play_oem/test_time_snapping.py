"""Tests for shared Play-OEM timestamp alignment and resampling."""

import numpy as np
import pytest

from ephem_toolkit.play_oem.time_snapping import (
    aligned_sample_times,
    sample_time_series,
    snap_tt_s_to_utc_half_second,
)


def test_aligned_sample_times_uses_one_anchor_and_bounded_half_second_gaps() -> None:
    start_s = 800_000_000.1
    stop_s = start_s + 10_000.0

    times = aligned_sample_times(start_s, stop_s, max_samples=101)

    assert 0 < len(times) <= 101
    assert times[0] >= start_s
    assert times[-1] <= stop_s
    assert snap_tt_s_to_utc_half_second(float(times[0])) == pytest.approx(times[0])
    half_second_gaps = np.diff(times) / 0.5
    np.testing.assert_allclose(half_second_gaps, np.rint(half_second_gaps))
    assert np.all(half_second_gaps >= 1)


def test_aligned_sample_times_keeps_a_single_sample_for_short_ranges() -> None:
    start_s = 800_000_000.0

    times = aligned_sample_times(start_s, start_s + 0.01, max_samples=100)

    assert times.shape == (1,)
    assert times[0] == start_s


def test_sample_time_series_clips_and_interpolates_values() -> None:
    source_times = np.asarray([0.0, 2.0, 5.0, 9.0, 12.0]) + 800_000_000.0
    source_values = np.column_stack(
        (2.0 * source_times + 3.0, -source_times + 7.0)
    )
    bounds = (source_times[1] + 0.1, source_times[-2] - 0.1)

    times, values = sample_time_series(
        source_times,
        source_values,
        bounds_s=bounds,
        max_samples=20,
    )

    assert times.size <= 20
    assert times[0] >= bounds[0]
    assert times[-1] <= bounds[1]
    np.testing.assert_allclose(values[:, 0], 2.0 * times + 3.0)
    np.testing.assert_allclose(values[:, 1], -times + 7.0)


@pytest.mark.parametrize(
    ("start_s", "stop_s", "max_samples"),
    [
        (2.0, 1.0, 2),
        (1.0, 2.0, 0),
        (1.0, 2.0, True),
    ],
)
def test_aligned_sample_times_rejects_invalid_arguments(
    start_s: float, stop_s: float, max_samples: int
) -> None:
    with pytest.raises(ValueError):
        aligned_sample_times(start_s, stop_s, max_samples)


def test_sample_time_series_rejects_mismatched_shapes() -> None:
    with pytest.raises(ValueError, match="one row per source time"):
        sample_time_series(
            [1.0, 2.0],
            [1.0],
            bounds_s=(1.0, 2.0),
            max_samples=2,
        )
