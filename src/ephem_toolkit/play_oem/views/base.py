"""Toolkit-neutral interface for playback plot views."""

from __future__ import annotations

from typing import Protocol

from matplotlib.figure import Figure

from ..series import OrbitSeries
from ..time_unit import TimeUnit


class View(Protocol):
    """Lifecycle shared by all playback views."""

    name: str

    def build(self, series: OrbitSeries, time_unit: TimeUnit) -> Figure:
        """Build the static plot and its initial cursor artists."""
        ...

    def update(self, t_s: float) -> None:
        """Move the view's cursor to an absolute OEM time."""
        ...

    def close(self) -> None:
        """Release the view's plot resources."""
        ...
