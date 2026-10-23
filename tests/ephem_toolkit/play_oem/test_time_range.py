"""Tests for toolkit-independent playback and plot range resolution."""

from __future__ import annotations

import random

import pytest

from ephem_toolkit.play_oem.time_range import (
    PlaybackTimeRange,
    PlotTimeRange,
    ResolvedTimeRange,
    TimeRangeEndpoint,
    resolve_plot_range,
    validate_playback_range,
    validate_plot_range,
)


COVERAGE = (0.0, 100.0)


def fixed(start: float, end: float, *, enabled: bool = True) -> PlotTimeRange:
    return PlotTimeRange(
        enabled,
        TimeRangeEndpoint("fixed", start),
        TimeRangeEndpoint("fixed", end),
    )


@pytest.mark.parametrize(
    ("start", "end", "time", "expected"),
    [
        (TimeRangeEndpoint("fixed", 20), TimeRangeEndpoint("fixed", 40), 50, (20, 40)),
        (TimeRangeEndpoint("offset", -20), TimeRangeEndpoint("offset", 10), 50, (30, 60)),
        (TimeRangeEndpoint("fixed", 20), TimeRangeEndpoint("offset", 10), 50, (20, 60)),
        (TimeRangeEndpoint("offset", -20), TimeRangeEndpoint("fixed", 40), 50, (30, 40)),
    ],
)
def test_resolves_all_endpoint_combinations_independent_of_playback_bounds(
    start: TimeRangeEndpoint,
    end: TimeRangeEndpoint,
    time: float,
    expected: tuple[float, float],
) -> None:
    # Playback is narrowed to [45, 55], but plot bounds may lie outside it.
    validate_playback_range(PlaybackTimeRange(45, 55), COVERAGE)
    assert resolve_plot_range(PlotTimeRange(True, start, end), COVERAGE, time) == (
        ResolvedTimeRange(*expected)
    )


def test_disabled_filter_selects_full_coverage_and_empty_is_distinct() -> None:
    assert resolve_plot_range(fixed(20, 80, enabled=False), COVERAGE, 50) == (
        ResolvedTimeRange(0, 100)
    )
    assert resolve_plot_range(fixed(120, 130), COVERAGE, 50) is None
    assert resolve_plot_range(fixed(50, 50), COVERAGE, 50) == ResolvedTimeRange(50, 50)


@pytest.mark.parametrize(
    ("start", "end", "time", "expected"),
    [
        (TimeRangeEndpoint("fixed", -10), TimeRangeEndpoint("fixed", 10), 50, (0, 10)),
        (TimeRangeEndpoint("fixed", 90), TimeRangeEndpoint("fixed", 110), 50, (90, 100)),
        (TimeRangeEndpoint("offset", 10), TimeRangeEndpoint("offset", 30), 50, (60, 80)),
        (TimeRangeEndpoint("offset", -30), TimeRangeEndpoint("offset", -10), 50, (20, 40)),
    ],
)
def test_clips_at_oem_edges(
    start: TimeRangeEndpoint,
    end: TimeRangeEndpoint,
    time: float,
    expected: tuple[float, float],
) -> None:
    assert resolve_plot_range(PlotTimeRange(True, start, end), COVERAGE, time) == (
        ResolvedTimeRange(*expected)
    )


def test_mixed_endpoints_may_cross_and_resolve_empty() -> None:
    rule = PlotTimeRange(
        True, TimeRangeEndpoint("fixed", 60), TimeRangeEndpoint("offset", 0)
    )
    assert resolve_plot_range(rule, COVERAGE, 50) is None
    assert resolve_plot_range(rule, COVERAGE, 70) == ResolvedTimeRange(60, 70)


def test_plot_outside_playback_range_and_disjoint_from_it_is_valid() -> None:
    playback = validate_playback_range((20, 40), COVERAGE)
    assert playback == PlaybackTimeRange(20, 40)
    assert resolve_plot_range(fixed(60, 80), COVERAGE, 30) == ResolvedTimeRange(60, 80)


def test_relative_resolution_is_deterministic_for_arbitrary_playback_times() -> None:
    rng = random.Random(4107)
    rule = PlotTimeRange(
        True, TimeRangeEndpoint("offset", -5), TimeRangeEndpoint("offset", 7)
    )
    for time in [0, 100, *[rng.uniform(0, 100) for _ in range(50)]]:
        result = resolve_plot_range(rule, COVERAGE, time)
        assert result == ResolvedTimeRange(max(0, time - 5), min(100, time + 7))


@pytest.mark.parametrize("bounds", [(-1, 10), (10, 101), (20, 10), (float("nan"), 10)])
def test_rejects_invalid_playback_bounds(bounds: tuple[float, float]) -> None:
    with pytest.raises(ValueError):
        validate_playback_range(bounds, COVERAGE)


@pytest.mark.parametrize(
    "rule",
    [
        fixed(20, 10),
        PlotTimeRange(True, TimeRangeEndpoint("offset", 5), TimeRangeEndpoint("offset", -5)),
        PlotTimeRange(True, TimeRangeEndpoint("bad", 0), TimeRangeEndpoint("fixed", 1)),  # type: ignore[arg-type]
    ],
)
def test_rejects_invalid_plot_rules(rule: PlotTimeRange) -> None:
    with pytest.raises(ValueError):
        validate_plot_range(rule)


@pytest.mark.parametrize("time", [-1, 101, float("inf")])
def test_rejects_playback_time_outside_or_invalid_for_resolver(time: float) -> None:
    with pytest.raises(ValueError):
        resolve_plot_range(fixed(0, 1), COVERAGE, time)


def test_import_does_not_load_gui_or_rendering_modules() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import ephem_toolkit.play_oem.time_range; "
            "assert not any(m == 'wx' or m.startswith('matplotlib') "
            "or m == 'vtk' or m.startswith('vtk.') for m in sys.modules)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
