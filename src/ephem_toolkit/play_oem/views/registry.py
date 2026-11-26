"""Declarative view names, groups, and opening behavior for play-oem."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

@dataclass(frozen=True)
class ViewSpec:
    """Canonical metadata and opener for one Play-OEM view."""

    name: str
    label: str
    group: str
    opener: Callable[[], None]

    def __post_init__(self) -> None:
        name = self.name.strip()
        label = self.label.strip()
        group = self.group.strip()
        if not name:
            raise ValueError("view name must be non-empty")
        if not label:
            raise ValueError("view label must be non-empty")
        if not group:
            raise ValueError("view group must be non-empty")
        if not callable(self.opener):
            raise TypeError("view opener must be callable")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "group", group)


@dataclass(frozen=True)
class ViewGroup:
    """Canonical view group metadata."""

    name: str
    label: str

    def __post_init__(self) -> None:
        name = self.name.strip()
        label = self.label.strip()
        if not name:
            raise ValueError("view group name must be non-empty")
        if not label:
            raise ValueError("view group label must be non-empty")
        if name == "all":
            raise ValueError("all is reserved for derived view-group expansion")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "label", label)


class LegacyViewSpecMixin:
    """Expose a view class as declarative registry metadata."""

    name: str
    label: str
    group: str

    @classmethod
    def view_spec(
        cls,
        opener: Callable[[], None],
    ) -> ViewSpec:
        """Build a registry specification for this view class."""
        return ViewSpec(
            name=cls.name,
            label=cls.label,
            group=cls.group,
            opener=opener,
        )


ViewSpecMixin = LegacyViewSpecMixin


class ViewRegistry:
    """Expand plot selections and open registered views without duplicates."""

    def __init__(self, groups: Sequence[ViewGroup] = ()) -> None:
        self._groups: dict[str, ViewGroup] = {}
        for group in groups:
            if not isinstance(group, ViewGroup):
                raise TypeError("groups must contain ViewGroup instances")
            if group.name in self._groups:
                raise ValueError(f"group is already registered: {group.name!r}")
            self._groups[group.name] = group
        self._specs: dict[str, ViewSpec] = {}

    @property
    def registered_views(self) -> tuple[str, ...]:
        """Return registered view names in display registration order."""
        return tuple(self._specs)

    def label_for(self, name: str) -> str:
        """Return a view or group label."""
        if name in self._specs:
            return self._specs[name].label
        if name in self._groups:
            return self._groups[name].label
        if name == "all":
            return "All"
        raise ValueError(f"unknown plot name: {name!r}")

    def register(self, spec: ViewSpec) -> None:
        """Register one declarative view specification."""
        if not isinstance(spec, ViewSpec):
            raise TypeError("spec must be a ViewSpec")
        if spec.name in self._specs:
            raise ValueError(f"view is already registered: {spec.name!r}")
        if spec.group not in self._groups:
            raise ValueError(f"unknown view group: {spec.group!r}")
        self._specs[spec.name] = spec

    def clear(self) -> None:
        """Remove all registered view specifications and openers."""
        self._specs.clear()

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
            if name == "all":
                members = tuple(self._specs)
            elif name in self._groups:
                members = tuple(
                    spec.name
                    for spec in self._specs.values()
                    if spec.group == name
                )
            elif name in self._specs:
                members = (name,)
            else:
                known_names = ", ".join(
                    list(self._groups)
                    + ["all"]
                    + list(self._specs)
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
        return all(name in self._specs for name in self.expand(selection))

    def open_view(self, name: str) -> None:
        """Open or raise one registered view."""
        if name not in self._specs:
            raise ValueError(f"unknown view name: {name!r}")
        self.open((name,))

    def open_group(self, name: str) -> None:
        """Open or raise all views in a registered group."""
        if name != "all" and name not in self._groups:
            raise ValueError(f"unknown plot group: {name!r}")
        self.open((name,))

    def open(self, selection: str | Sequence[str]) -> None:
        """Open a selection only when all its views are implemented."""
        view_names = self.expand(selection)
        unavailable = [name for name in view_names if name not in self._specs]
        if unavailable:
            names = ", ".join(unavailable)
            raise ValueError(f"plots are not implemented yet: {names}")
        for name in view_names:
            self._specs[name].opener()


def parse_plot_selection(value: str) -> tuple[str, ...]:
    """Parse canonical comma-separated names or groups without aliases."""
    names = tuple(name.strip() for name in value.split(","))
    if not names or any(not name for name in names):
        raise ValueError("at least one non-empty plot name is required")
    return names
