"""Debug utilities for diff_oem module."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import ephem_toolkit.core.time_utils as time_utils

_debug: bool = False
"""Module-level debug flag, set by the CLI entry point."""


def set_debug(enabled: bool) -> None:
    """Enable or disable module-level debug logging.

    Parameters
    ----------
    enabled : bool
        Whether to enable debug output.
    """
    global _debug
    _debug = enabled


def debug_format_epoch(epoch_s: float) -> str:
    """Format POSIX epoch as ISO8601 string.

    Parameters
    ----------
    epoch_s : float
        POSIX timestamp in seconds.

    Returns
    -------
    str
        ISO8601 formatted datetime string.
    """
    dt = datetime.fromtimestamp(epoch_s, tz=timezone.utc)
    return time_utils.datetime_to_iso8601(dt)


def debug_print(message: str, module: str = "utils") -> None:
    """Print a debug message to stderr when debugging is enabled.

    Parameters
    ----------
    message : str
        Debug message to print.
    module : str, default="utils"
        Module name for the debug prefix.
    """
    if _debug:
        print(f"[diff_oem.{module}] {message}", file=sys.stderr)


def debug_print_time_range(
    label: str,
    start_epoch_s: float | datetime | None,
    stop_epoch_s: float | datetime | None,
) -> None:
    """Print one labeled time range to stderr.

    Parameters
    ----------
    label : str
        Descriptive label for the time range.
    start_epoch_s : float | datetime | None
        Start epoch in POSIX seconds or datetime, or None.
    stop_epoch_s : float | datetime | None
        Stop epoch in POSIX seconds or datetime, or None.
    """
    if not _debug:
        return

    if start_epoch_s is None or stop_epoch_s is None:
        range_str = "[ none, none ]"
    else:
        if isinstance(start_epoch_s, datetime):
            start_str = time_utils.datetime_to_iso8601(start_epoch_s)
        else:
            start_str = debug_format_epoch(start_epoch_s)
        if isinstance(stop_epoch_s, datetime):
            stop_str = time_utils.datetime_to_iso8601(stop_epoch_s)
        else:
            stop_str = debug_format_epoch(stop_epoch_s)
        range_str = f"[ {start_str}, {stop_str} ]"
    print(
        f"[diff_oem] {label}: {range_str}",
        file=sys.stderr,
    )
