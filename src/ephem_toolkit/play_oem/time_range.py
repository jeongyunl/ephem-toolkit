"""Toolkit-independent playback and plot time range models.

Times are absolute TT seconds since J2000 and offsets are durations in seconds.
The OEM coverage, allowed playback interval, and effective plot interval are
separate values: plot resolution clips only to OEM coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

EndpointMode = Literal["fixed", "offset"]
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


@dataclass(frozen=True, slots=True)
class PlaybackTimeRange:
    """Independent inclusive playback limits, contained in OEM coverage."""

    start_s: float
    end_s: float


@dataclass(frozen=True, slots=True)
class TimeRangeEndpoint:
    """A fixed absolute epoch or signed offset from current playback time."""

    mode: EndpointMode
    value_s: float


@dataclass(frozen=True, slots=True)
class PlotTimeRange:
    """One requested plot interval whose endpoints may use different modes."""

    enabled: bool
    start: TimeRangeEndpoint
    end: TimeRangeEndpoint


@dataclass(frozen=True, slots=True)
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
        if endpoint.mode not in ("fixed", "offset"):
            raise ValueError(f"{label} mode must be 'fixed' or 'offset'")
        _finite(endpoint.value_s, f"{label} value")
    if rule.start.mode == rule.end.mode and rule.start.value_s > rule.end.value_s:
        raise ValueError("plot start must not be after plot end")
    return rule


def resolve_plot_range(
    rule: PlotTimeRange, coverage: Coverage, t_s: float
) -> ResolvedTimeRange | None:
    """Resolve and clip a plot rule to OEM coverage, independent of playback bounds.

    ``None`` represents an empty effective interval. Disabled filtering always
    resolves to the complete OEM coverage.
    """
    d0, d1 = validate_coverage(coverage)
    t = _finite(t_s, "playback time")
    if not d0 <= t <= d1:
        raise ValueError("playback time must lie within OEM coverage")
    checked = validate_plot_range(rule)
    if not checked.enabled:
        return ResolvedTimeRange(d0, d1)
    start_requested = checked.start.value_s + (
        t if checked.start.mode == "offset" else 0.0
    )
    end_requested = checked.end.value_s + (t if checked.end.mode == "offset" else 0.0)
    if start_requested > end_requested:
        return None
    start = max(d0, start_requested)
    end = min(d1, end_requested)
    if start > end:
        return None
    return ResolvedTimeRange(start, end)
