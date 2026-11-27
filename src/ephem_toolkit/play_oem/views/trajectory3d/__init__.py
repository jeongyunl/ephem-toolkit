"""3D trajectory data-view backends for play-oem."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .mpl_backend import Trajectory3DView

__all__ = ["Trajectory3DView"]


def __getattr__(name: str) -> object:
    if name == "Trajectory3DView":
        from .mpl_backend import Trajectory3DView

        return Trajectory3DView
    raise AttributeError(name)
