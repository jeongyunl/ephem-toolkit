"""Tests for parsing compact endpoint input at the wx editor boundary."""

import pytest
from types import SimpleNamespace

from ephem_toolkit.core import time_utils
from ephem_toolkit.play_oem.workspace.time_range import TimeRangeEditor, _parse_endpoint
from ephem_toolkit.play_oem.time_range import PlotTimeRange, TimeRangeEndpoint


@pytest.mark.parametrize(
    ("text", "expected"),
    (("-1h", -3600.0), ("+3h", 10800.0), ("0s", 0.0), ("-90m", -5400.0)),
)
def test_signed_duration_becomes_playback_offset(text: str, expected: float) -> None:
    assert _parse_endpoint(text, fixed=False) == TimeRangeEndpoint("offset", expected)


def test_fixed_endpoint_requires_timestamp() -> None:
    with pytest.raises(ValueError, match="Fixed time requires"):
        _parse_endpoint("+3h", fixed=True)


def test_offset_endpoint_requires_duration() -> None:
    with pytest.raises(ValueError, match="Playback offset requires"):
        _parse_endpoint("2026-10-23T12:00:00Z", fixed=False)


def test_fixed_utc_timestamp_retains_fractional_precision() -> None:
    endpoint = _parse_endpoint("2026-10-23T12:00:00.125Z", fixed=True)
    assert endpoint.mode == "fixed"
    assert time_utils.datetime_to_iso8601(
        time_utils.tt_s_to_datetime(endpoint.value_s), fractional_second_places=3
    ) == "2026-10-23T12:00:00.125"


def test_enabling_plot_range_defaults_to_playback_bounds() -> None:
    applied = []
    prior_rule = PlotTimeRange(
        False, TimeRangeEndpoint("fixed", 5.0), TimeRangeEndpoint("fixed", 15.0)
    )
    editor = SimpleNamespace(
        _syncing=False,
        playback=(20.0, 80.0),
        plot_rule=prior_rule,
        plot_enabled=SimpleNamespace(GetValue=lambda: True),
        _on_begin_edit=lambda: None,
        _on_plot=applied.append,
        message=SimpleNamespace(SetLabel=lambda _label: None),
    )
    event = SimpleNamespace(Skip=lambda: None)

    TimeRangeEditor._toggle_plot(editor, event)

    assert applied == [
        PlotTimeRange(
            True,
            TimeRangeEndpoint("fixed", 20.0),
            TimeRangeEndpoint("fixed", 80.0),
        )
    ]
