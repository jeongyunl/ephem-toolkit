"""Tests for plot-name and group resolution."""

from __future__ import annotations

import pytest

from ephem_toolkit.play_oem.views.registry import VIEW_LABELS, ViewRegistry
from ephem_toolkit.play_oem.views import registry as view_registry


def test_registry_expands_groups_and_deduplicates_views() -> None:
    registry = ViewRegistry()

    assert registry.expand(("overview", "trajectory-3d")) == (
        "trajectory-3d",
        "speed-altitude",
    )
    assert registry.expand("state-vectors") == (
        "trajectory-3d",
        "state-components",
    )
    assert registry.expand("motion") == (
        "rtn",
        "angular-velocity",
        "direction-change",
        "distance",
    )
    assert registry.expand("all") == tuple(name for name, _ in VIEW_LABELS)


def test_registry_opens_each_resolved_view_once() -> None:
    registry = ViewRegistry()
    opened: list[str] = []
    registry.register_view("trajectory-3d", lambda: opened.append("trajectory-3d"))
    registry.register_view("speed-altitude", lambda: opened.append("speed-altitude"))

    registry.open(("overview", "trajectory-3d"))

    assert opened == ["trajectory-3d", "speed-altitude"]


def test_registry_reports_unimplemented_group_members_before_opening() -> None:
    registry = ViewRegistry()
    opened: list[str] = []
    registry.register_view("trajectory-3d", lambda: opened.append("trajectory-3d"))

    with pytest.raises(ValueError, match="state-components"):
        registry.open_group("state")

    assert opened == []


def test_ground_station_access_is_in_all_but_not_overview() -> None:
    assert "ground-station-access" in view_registry.GROUP_MEMBERS["all"]
    assert "ground-station-access" not in view_registry.GROUP_MEMBERS["overview"]
