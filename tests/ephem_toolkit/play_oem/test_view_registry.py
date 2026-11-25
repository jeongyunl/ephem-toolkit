"""Tests for declarative Play-OEM view registration."""

from __future__ import annotations

import pytest

from ephem_toolkit.play_oem.views.registry import (
    ViewGroup,
    ViewRegistry,
    ViewSpec,
)


def make_registry() -> ViewRegistry:
    registry = ViewRegistry(
        (
            ViewGroup("overview", "Overview"),
            ViewGroup("motion", "Motion"),
        )
    )
    registry.register(
        ViewSpec(
            "trajectory-3d",
            "3D Orbit",
            "overview",
            lambda: None,
        )
    )
    registry.register(
        ViewSpec(
            "speed-altitude",
            "Speed / Altitude",
            "overview",
            lambda: None,
        )
    )
    registry.register(
        ViewSpec(
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


def test_registry_opens_resolved_views_once() -> None:
    opened: list[str] = []
    registry = make_registry()
    registry.clear()
    registry.register(
        ViewSpec(
            "speed-altitude",
            "Speed / Altitude",
            "overview",
            lambda: opened.append("speed-altitude"),
        )
    )
    registry.register(
        ViewSpec(
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

    with pytest.raises(ValueError, match="unknown plot name"):
        registry.expand("not-a-view")

    with pytest.raises(ValueError, match="unknown plot group"):
        registry.open_group("state")

    with pytest.raises(ValueError, match="already registered"):
        registry.register(
            ViewSpec(
                "speed-altitude",
                "Other Label",
                "overview",
                lambda: None,
            )
        )


def test_view_spec_requires_canonical_fields() -> None:
    with pytest.raises(ValueError, match="name must be non-empty"):
        ViewSpec("", "View", "overview", lambda: None)
    with pytest.raises(ValueError, match="label must be non-empty"):
        ViewSpec("view", "", "overview", lambda: None)
    with pytest.raises(ValueError, match="group must be non-empty"):
        ViewSpec("view", "View", "", lambda: None)
    with pytest.raises(TypeError, match="opener must be callable"):
        ViewSpec("view", "View", "overview", None)  # type: ignore[arg-type]


def test_registry_rejects_specs_for_unknown_groups() -> None:
    registry = ViewRegistry()

    with pytest.raises(ValueError, match="unknown view group"):
        registry.register(
            ViewSpec("custom", "Custom", "custom", lambda: None)
        )


def test_group_all_is_reserved() -> None:
    with pytest.raises(ValueError, match="reserved"):
        ViewGroup("all", "All")
