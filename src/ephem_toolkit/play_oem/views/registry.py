"""Shared plot names, groups and opening behavior for play-oem."""

from __future__ import annotations

from collections.abc import Callable, Sequence

VIEW_LABELS = (
    ("trajectory-3d", "3D Orbit"),
    ("state-components", "State Components"),
    ("speed-altitude", "Speed / Altitude"),
    ("rtn", "RTN Deltas"),
    ("angular-velocity", "Angular Velocity"),
    ("direction-change", "Direction Change"),
    ("distance", "Geocentric Distance"),
)

GROUP_LABELS = (
    ("overview", "Overview"),
    ("state", "State"),
    ("motion", "Motion"),
    ("all", "All"),
)

GROUP_MEMBERS = {
    "overview": ("trajectory-3d", "speed-altitude"),
    "state": ("state-components",),
    "motion": ("rtn", "angular-velocity", "direction-change", "distance"),
    "all": tuple(name for name, _ in VIEW_LABELS),
}

_VIEW_NAMES = frozenset(name for name, _ in VIEW_LABELS)
_GROUP_NAMES = frozenset(name for name, _ in GROUP_LABELS)
_VIEW_LABEL_BY_NAME = dict(VIEW_LABELS)


class ViewRegistry:
    """Expand plot selections and open registered views without duplicates."""

    def __init__(self) -> None:
        self._openers: dict[str, Callable[[], None]] = {}

    @property
    def registered_views(self) -> tuple[str, ...]:
        """Return implemented view names in their documented order."""
        return tuple(name for name, _ in VIEW_LABELS if name in self._openers)

    def label_for(self, name: str) -> str:
        """Return a view or group label."""
        if name in _VIEW_LABEL_BY_NAME:
            return _VIEW_LABEL_BY_NAME[name]
        for group_name, label in GROUP_LABELS:
            if name == group_name:
                return label
        raise ValueError(f"unknown plot name: {name!r}")

    def register_view(self, name: str, opener: Callable[[], None]) -> None:
        """Register an implemented view opener."""
        if name not in _VIEW_NAMES:
            raise ValueError(f"unknown view name: {name!r}")
        if name in self._openers:
            raise ValueError(f"view is already registered: {name!r}")
        self._openers[name] = opener

    def expand(self, selection: str | Sequence[str]) -> tuple[str, ...]:
        """Expand comma-separated views and groups into unique view names."""
        if isinstance(selection, str):
            names = [name.strip() for name in selection.split(",")]
        else:
            names = [name.strip() for item in selection for name in item.split(",")]
        if not names or any(not name for name in names):
            raise ValueError("at least one non-empty plot name is required")

        expanded: list[str] = []
        for name in names:
            if name in GROUP_MEMBERS:
                members = GROUP_MEMBERS[name]
            elif name in _VIEW_NAMES:
                members = (name,)
            else:
                known_names = ", ".join(
                    [group for group, _ in GROUP_LABELS]
                    + [view for view, _ in VIEW_LABELS]
                )
                raise ValueError(
                    f"unknown plot name {name!r}; choose from: {known_names}"
                )
            for member in members:
                if member not in expanded:
                    expanded.append(member)
        return tuple(expanded)

    def can_open(self, selection: str | Sequence[str]) -> bool:
        """Return whether every view in a selection has an opener."""
        return all(name in self._openers for name in self.expand(selection))

    def open_view(self, name: str) -> None:
        """Open or raise one registered view."""
        if name not in _VIEW_NAMES:
            raise ValueError(f"unknown view name: {name!r}")
        self.open((name,))

    def open_group(self, name: str) -> None:
        """Open or raise all views in a registered group."""
        if name not in _GROUP_NAMES:
            raise ValueError(f"unknown plot group: {name!r}")
        self.open((name,))

    def open(self, selection: str | Sequence[str]) -> None:
        """Open a selection only when all its views are implemented."""
        view_names = self.expand(selection)
        unavailable = [name for name in view_names if name not in self._openers]
        if unavailable:
            names = ", ".join(unavailable)
            raise ValueError(f"plots are not implemented yet: {names}")
        for name in view_names:
            self._openers[name]()


def parse_plot_selection(value: str) -> tuple[str, ...]:
    """Parse CLI plot names and groups using the shared registry."""
    return ViewRegistry().expand(value)
