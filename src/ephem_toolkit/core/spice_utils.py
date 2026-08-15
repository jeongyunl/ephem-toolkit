"""Utilities for resolving and loading TudatPy SPICE kernels.

References:
    https://naif.jpl.nasa.gov/naif/toolkit.html
    https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/kernel.html
"""

from __future__ import annotations

import os
from pathlib import Path

from tudatpy.interface import spice

_SPICE_CACHE_FILE: Path = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    / "ephem-toolkit"
    / "spice_kernel_path"
)
"""XDG cache file path for the resolved SPICE kernel directory."""

_loaded_kernels: set[str] = set()
"""Absolute kernel paths that have already been loaded."""


def get_spice_kernel_path() -> str:
    """Return the Tudatpy SPICE kernel path using an XDG-style cache file.

    Returns
    -------
    str
        Path to the SPICE kernel directory.

    References
    ----------
    https://naif.jpl.nasa.gov/naif/toolkit.html
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


def load_kernel(kernel_file: str, kernel_path: str | Path | None = None) -> None:
    """Load a SPICE kernel from the specified or cached kernel directory.

    Parameters
    ----------
    kernel_file : str
        Name of the SPICE kernel file.
    kernel_path : str or Path, optional
        Directory containing the kernel file. Defaults to the cached TudatPy
        SPICE kernel directory.

    References
    ----------
    https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/kernel.html
    """
    if kernel_path is None:
        kernel_path = get_spice_kernel_path()

    kernel_file_path: str = str(Path(kernel_path) / kernel_file)

    if kernel_file_path not in _loaded_kernels:
        print(f"Loading SPICE kernel: {kernel_file_path}", file=os.sys.stderr)
        spice.load_kernel(kernel_file_path)
        _loaded_kernels.add(kernel_file_path)
