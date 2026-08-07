"""Utilities for resolving and loading TudatPy SPICE kernels."""

from __future__ import annotations

import os
from pathlib import Path

_SPICE_CACHE_FILE: Path = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    / "tudatpy-utils"
    / "spice_kernel_path"
)
"""XDG cache file path for the resolved SPICE kernel directory."""


def get_spice_kernel_path() -> str:
    """Return the Tudatpy SPICE kernel path using an XDG-style cache file.

    Returns
    -------
    str
        Path to the SPICE kernel directory.
    """
    try:
        cached_path: str = _SPICE_CACHE_FILE.read_text(encoding="utf-8").strip()
        if cached_path and Path(cached_path).is_dir():
            return cached_path
    except OSError:
        pass

    from tudatpy import data

    resolved_path: str = data.get_spice_kernel_path()

    try:
        _SPICE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SPICE_CACHE_FILE.write_text(resolved_path, encoding="utf-8")
    except OSError:
        # Cache writes are best effort; continue with the resolved path.
        pass

    return resolved_path
