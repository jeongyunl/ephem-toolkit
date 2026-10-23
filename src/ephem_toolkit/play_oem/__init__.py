"""Interactive playback for CCSDS OEM ephemeris data.

Keep the initializer light so the toolkit-independent time-range model can be
imported without initializing wxPython or plotting backends.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["cli", "main"]


def __getattr__(name: str) -> Callable[..., Any]:
    if name in __all__:
        from importlib import import_module

        module = import_module(".__main__", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted((*globals(), *(__all__)))
