"""Toolkit-independent playback and plot time range models.

Times are absolute TT seconds since J2000 and offsets are durations in seconds.
The OEM coverage, allowed playback interval, and effective plot interval are
separate values: plot resolution clips only to OEM coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

EndpointMode = Literal["follow", "fixed", "offset"]
Coverage = tuple[float, float]


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def validate_coverage(coverage: Coverage) -> Coverage:
    """Return finite ordered OEM coverage, rejecting malformed bounds."""
    if not isinstance(coverage, tuple) or len(coverage) != 2:
        raise ValueError("coverage must be a pair of finite timestamps")
    start = _finite(coverage[0], "coverage start")
    end = _finite(coverage[1], "coverage end")
    if start > end:
        raise ValueError("coverage start must be less than or equal to coverage end")
    return start, end


@dataclass(frozen=True)
class PlaybackTimeRange:
    """Independent inclusive playback limits, contained in OEM coverage."""

    start_s: float
    end_s: float


@dataclass(frozen=True)
class TimeRangeEndpoint:
    """A playback-bound endpoint, fixed epoch, or offset from playback time."""

    mode: EndpointMode
    value_s: float


@dataclass(frozen=True)
class PlotTimeRange:
    """One requested plot interval whose endpoints may use different modes."""

    enabled: bool
    start: TimeRangeEndpoint
    end: TimeRangeEndpoint


@dataclass(frozen=True)
class ResolvedTimeRange:
    """Inclusive nonempty effective plot bounds in absolute TT seconds."""

    start_s: float
    end_s: float


def validate_playback_range(
    bounds: PlaybackTimeRange | tuple[float, float], coverage: Coverage
) -> PlaybackTimeRange:
    """Validate ordered playback bounds contained by the immutable OEM coverage."""
    d0, d1 = validate_coverage(coverage)
    if isinstance(bounds, PlaybackTimeRange):
        start_value, end_value = bounds.start_s, bounds.end_s
    elif isinstance(bounds, tuple) and len(bounds) == 2:
        start_value, end_value = bounds
    else:
        raise ValueError("playback bounds must be a PlaybackTimeRange or pair")
    start = _finite(start_value, "playback start")
    end = _finite(end_value, "playback end")
    if start > end:
        raise ValueError("playback start must be less than or equal to playback end")
    if start < d0 or end > d1:
        raise ValueError("playback bounds must lie within OEM coverage")
    return PlaybackTimeRange(start, end)


def validate_plot_range(rule: PlotTimeRange) -> PlotTimeRange:
    """Validate a plot rule, including endpoint modes and always-reversed pairs."""
    if not isinstance(rule, PlotTimeRange):
        raise ValueError("rule must be a PlotTimeRange")
    if not isinstance(rule.enabled, bool):
        raise ValueError("enabled must be a boolean")
    for label, endpoint in (("start", rule.start), ("end", rule.end)):
        if not isinstance(endpoint, TimeRangeEndpoint):
            raise ValueError(f"{label} must be a TimeRangeEndpoint")
        if endpoint.mode not in ("follow", "fixed", "offset"):
            raise ValueError(f"{label} mode must be 'follow', 'fixed', or 'offset'")
        _finite(endpoint.value_s, f"{label} value")
    if (
        rule.start.mode == rule.end.mode
        and rule.start.mode != "follow"
        and rule.start.value_s > rule.end.value_s
    ):
        raise ValueError("plot start must not be after plot end")
    return rule


def convert_endpoint_mode(
    endpoint: TimeRangeEndpoint,
    mode: EndpointMode,
    current_time_s: float,
    playback_bound_s: float,
) -> TimeRangeEndpoint:
    """Change endpoint mode while preserving its current absolute position."""
    if not isinstance(endpoint, TimeRangeEndpoint):
        raise ValueError("endpoint must be a TimeRangeEndpoint")
    if endpoint.mode not in ("follow", "fixed", "offset"):
        raise ValueError("endpoint mode must be 'follow', 'fixed', or 'offset'")
    endpoint_value = _finite(endpoint.value_s, "endpoint value")
    current = _finite(current_time_s, "playback time")
    playback_bound = _finite(playback_bound_s, "playback bound")
    if mode not in ("follow", "fixed", "offset"):
        raise ValueError("mode must be 'follow', 'fixed', or 'offset'")
    if endpoint.mode == "follow":
        absolute = playback_bound
    elif endpoint.mode == "offset":
        absolute = endpoint_value + current
    else:
        absolute = endpoint_value
    if mode == "follow":
        return TimeRangeEndpoint("follow", 0.0)
    if mode == "offset":
        return TimeRangeEndpoint("offset", absolute - current)
    return TimeRangeEndpoint("fixed", absolute)


def resolve_plot_range(
    rule: PlotTimeRange,
    coverage: Coverage,
    playback_bounds: PlaybackTimeRange | tuple[float, float],
    t_s: float,
) -> ResolvedTimeRange | None:
    """Resolve and clip a plot rule to OEM coverage, independent of playback bounds.

    ``None`` represents an empty effective interval. Disabled filtering always
    resolves to the complete OEM coverage.
    """
    d0, d1 = validate_coverage(coverage)
    playback = validate_playback_range(playback_bounds, (d0, d1))
    t = _finite(t_s, "playback time")
    if not d0 <= t <= d1:
        raise ValueError("playback time must lie within OEM coverage")
    checked = validate_plot_range(rule)
    if not checked.enabled:
        return ResolvedTimeRange(d0, d1)

    def resolve_endpoint(endpoint: TimeRangeEndpoint, name: str) -> float:
        if endpoint.mode == "follow":
            return playback.start_s if name == "start" else playback.end_s
        if endpoint.mode == "offset":
            return endpoint.value_s + t
        return endpoint.value_s

    start_requested = resolve_endpoint(checked.start, "start")
    end_requested = resolve_endpoint(checked.end, "end")
    if start_requested > end_requested:
        return None
    start = max(d0, start_requested)
    end = min(d1, end_requested)
    if start > end:
        return None
    return ResolvedTimeRange(start, end)
