"""Toolkit-neutral interface for playback plot views."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from matplotlib.figure import Figure

from ..series import OrbitSeries
from ..time_unit import TimeUnit

if TYPE_CHECKING:
    import wx


class View(Protocol):
    """Lifecycle shared by all playback views."""

    name: str

    def build(self, series: OrbitSeries, time_unit: TimeUnit, /) -> Figure | wx.Window:
        """Build the view content and its initial cursor state."""
        ...

    def update(self, t_s: float, /) -> None:
        """Move the view's cursor to an absolute OEM time."""
        ...

    def close(self) -> None:
        """Release the view's plot resources."""
        ...
