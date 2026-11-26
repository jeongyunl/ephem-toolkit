"""Shared platform detection for the Play-OEM GUI."""

from __future__ import annotations

from functools import lru_cache
import os
import sys


@lru_cache(maxsize=1)
def is_gtk() -> bool:
    """Return whether wxPython is using its GTK 3 port."""
    import wx

    return "gtk3" in wx.PlatformInfo


@lru_cache(maxsize=1)
def is_macos() -> bool:
    """Return whether wxPython is running on macOS."""
    import wx

    return wx.Platform == "__WXMAC__"


@lru_cache(maxsize=1)
def is_linux() -> bool:
    """Return whether the Python process is running on Linux."""
    return sys.platform.startswith("linux")


@lru_cache(maxsize=1)
def is_gtk_wayland() -> bool:
    """Return whether Play-OEM is running on GTK with a Wayland backend."""
    if not is_gtk():
        return False

    backend = os.environ.get("GDK_BACKEND", "").lower().split(",")
    if backend:
        selected = {item.strip() for item in backend if item.strip()}
        if "wayland" in selected:
            return True
        if "x11" in selected:
            return False
    return bool(os.environ.get("WAYLAND_DISPLAY")) or (
        os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    )
