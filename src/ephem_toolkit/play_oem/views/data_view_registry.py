"""Declarative data-view names, presets, and opening behavior for play-oem."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

@dataclass(frozen=True)
class DataViewSpec:
    """Canonical metadata and opener for one Play-OEM data view."""

    name: str
    label: str
    group: str
    opener: Callable[[], None]

    def __post_init__(self) -> None:
        name = self.name.strip()
        label = self.label.strip()
        group = self.group.strip()
        if not name:
            raise ValueError("data-view name must be non-empty")
        if not label:
            raise ValueError("data-view label must be non-empty")
        if not group:
            raise ValueError("view preset must be non-empty")
        if not callable(self.opener):
            raise TypeError("view opener must be callable")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "group", group)


@dataclass(frozen=True)
class DataViewPreset:
    """Canonical data-view preset metadata."""

    name: str
    label: str

    def __post_init__(self) -> None:
        name = self.name.strip()
        label = self.label.strip()
        if not name:
            raise ValueError("data-view preset name must be non-empty")
        if not label:
            raise ValueError("data-view preset label must be non-empty")
        if name == "all":
            raise ValueError("all is reserved for derived preset expansion")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "label", label)


class DataViewSpecMixin:
    """Expose a data-view class as declarative registry metadata."""

    name: str
    label: str
    group: str

    @classmethod
    def view_spec(
        cls,
        opener: Callable[[], None],
    ) -> DataViewSpec:
        """Build a registry specification for this view class."""
        return DataViewSpec(
            name=cls.name,
            label=cls.label,
            group=cls.group,
            opener=opener,
        )



class DataViewRegistry:
    """Expand data-view selections and open registered data views without duplicates."""

    def __init__(self, presets: Sequence[DataViewPreset] = ()) -> None:
        self._groups: dict[str, DataViewPreset] = {}
        for preset in presets:
            if not isinstance(preset, DataViewPreset):
                raise TypeError("presets must contain DataViewPreset instances")
            if preset.name in self._groups:
                raise ValueError(f"preset is already registered: {preset.name!r}")
            self._groups[preset.name] = preset
        self._specs: dict[str, DataViewSpec] = {}

    @property
    def registered_data_views(self) -> tuple[str, ...]:
        """Return registered view names in display registration order."""
        return tuple(self._specs)

    def label_for(self, name: str) -> str:
        """Return a data view or preset label."""
        if name in self._specs:
            return self._specs[name].label
        if name in self._groups:
            return self._groups[name].label
        if name == "all":
            return "All"
        raise ValueError(f"unknown data-view name: {name!r}")

    def register(self, spec: DataViewSpec) -> None:
        """Register one declarative view specification."""
        if not isinstance(spec, DataViewSpec):
            raise TypeError("spec must be a DataViewSpec")
        if spec.name in self._specs:
            raise ValueError(f"view is already registered: {spec.name!r}")
        if spec.group not in self._groups:
            raise ValueError(f"unknown data-view preset: {spec.group!r}")
        self._specs[spec.name] = spec

    def clear(self) -> None:
        """Remove all registered view specifications and openers."""
        self._specs.clear()

    def expand(self, selection: str | Sequence[str]) -> tuple[str, ...]:
        """Expand comma-separated data views and groups into unique view names."""
        if isinstance(selection, str):
            names = [name.strip() for name in selection.split(",")]
        else:
            names = [name.strip() for item in selection for name in item.split(",")]
        if not names or any(not name for name in names):
            raise ValueError("at least one non-empty data-view name is required")

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
                    f"unknown data-view name {name!r}; choose from: {known_names}"
                )
            for member in members:
                if member not in expanded:
                    expanded.append(member)
        return tuple(expanded)

    def can_open(self, selection: str | Sequence[str]) -> bool:
        """Return whether every view in a selection has an opener."""
        return all(name in self._specs for name in self.expand(selection))

    def open_data_view(self, name: str) -> None:
        """Open or raise one registered view."""
        if name not in self._specs:
            raise ValueError(f"unknown data-view name: {name!r}")
        self.open((name,))

    def open_preset(self, name: str) -> None:
        """Open or raise all data views in a registered preset."""
        if name != "all" and name not in self._groups:
            raise ValueError(f"unknown data-view preset: {name!r}")
        self.open((name,))

    def open(self, selection: str | Sequence[str]) -> None:
        """Open a selection only when all its data views are implemented."""
        data_view_names = self.expand(selection)
        unavailable = [name for name in data_view_names if name not in self._specs]
        if unavailable:
            names = ", ".join(unavailable)
            raise ValueError(f" data_views are not implemented yet: {names}")
        for name in data_view_names:
            self._specs[name].opener()


def parse_data_view_selection(value: str) -> tuple[str, ...]:
    """Parse canonical comma-separated data-view names or presets without aliases."""
    names = tuple(name.strip() for name in value.split(","))
    if not names or any(not name for name in names):
        raise ValueError("at least one non-empty plot name is required")
    return names
