"""Tests for declarative Play-OEM view registration."""

from __future__ import annotations

import pytest

from ephem_toolkit.play_oem.views.data_view_registry import (
    DataViewPreset,
    DataViewRegistry,
    DataViewSpec,
)


def make_registry() -> DataViewRegistry:
    registry = DataViewRegistry(
        (
            DataViewPreset("overview", "Overview"),
            DataViewPreset("motion", "Motion"),
        )
    )
    registry.register(
        DataViewSpec(
            "trajectory-3d",
            "3D Orbit",
            "overview",
            lambda: None,
        )
    )
    registry.register(
        DataViewSpec(
            "speed-altitude",
            "Speed / Altitude",
            "overview",
            lambda: None,
        )
    )
    registry.register(
        DataViewSpec(
            "rtn",
            "RTN Deltas",
            "motion",
            lambda: None,
        )
    )
    return registry


def test_registry_expands_groups_and_all_from_registered_specs() -> None:
    registry = make_registry()

    assert registry.expand("overview") == (
        "trajectory-3d",
        "speed-altitude",
    )
    assert registry.expand("motion,trajectory-3d") == (
        "rtn",
        "trajectory-3d",
    )
    assert registry.expand("all") == (
        "trajectory-3d",
        "speed-altitude",
        "rtn",
    )


def test_registry_opens_resolved_data_views_once() -> None:
    opened: list[str] = []
    registry = make_registry()
    registry.clear()
    registry.register(
        DataViewSpec(
            "speed-altitude",
            "Speed / Altitude",
            "overview",
            lambda: opened.append("speed-altitude"),
        )
    )
    registry.register(
        DataViewSpec(
            "trajectory-3d",
            "3D Orbit",
            "overview",
            lambda: opened.append("trajectory-3d"),
        )
    )

    registry.open(("overview", "trajectory-3d"))

    assert opened == ["speed-altitude", "trajectory-3d"]


def test_registry_rejects_unknown_names_groups_and_duplicates() -> None:
    registry = make_registry()

    with pytest.raises(ValueError, match="unknown data-view name"):
        registry.expand("not-a-view")

    with pytest.raises(ValueError, match="unknown data-view preset"):
        registry.open_preset("state")

    with pytest.raises(ValueError, match="already registered"):
        registry.register(
            DataViewSpec(
                "speed-altitude",
                "Other Label",
                "overview",
                lambda: None,
            )
        )


def test_view_spec_requires_canonical_fields() -> None:
    with pytest.raises(ValueError, match="name must be non-empty"):
        DataViewSpec("", "DataView", "overview", lambda: None)
    with pytest.raises(ValueError, match="label must be non-empty"):
        DataViewSpec("view", "", "overview", lambda: None)
    with pytest.raises(ValueError, match="view preset must be non-empty"):
        DataViewSpec("view", "DataView", "", lambda: None)
    with pytest.raises(TypeError, match="opener must be callable"):
        DataViewSpec("view", "DataView", "overview", None)  # type: ignore[arg-type]


def test_registry_rejects_specs_for_unknown_groups() -> None:
    registry = DataViewRegistry()

    with pytest.raises(ValueError, match="unknown data-view preset"):
        registry.register(
            DataViewSpec("custom", "Custom", "custom", lambda: None)
        )


def test_group_all_is_reserved() -> None:
    with pytest.raises(ValueError, match="reserved"):
        DataViewPreset("all", "All")
