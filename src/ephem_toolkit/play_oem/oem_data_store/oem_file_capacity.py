"""OEM state-row capacity scanning."""

from __future__ import annotations

from pathlib import Path
from threading import Event

import ephem_toolkit.play_oem.oem_data_store as public_store
from ephem_toolkit.core.ccsds.odm import ODM_MAX_LINE_LENGTH


_CAPACITY_SCAN_CHUNK_SIZE: int = 1024 * 1024
"""Text chunk size used by OEM capacity scans."""
public_store._CAPACITY_SCAN_CHUNK_SIZE = _CAPACITY_SCAN_CHUNK_SIZE


def capacity_for_file(
    source: Path,
    cancel_event: Event | None = None,
) -> int:
    """Count likely state rows within an OEM file."""
    line_count = 0
    in_covariance = False
    pending = ""
    with source.open("r", encoding="utf-8", newline=None) as stream:
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("capacity scan cancelled")
        while chunk := stream.read(public_store._CAPACITY_SCAN_CHUNK_SIZE):
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("capacity scan cancelled")
            combined = pending + chunk
            lines = combined.split("\n")
            pending = lines.pop()
            if lines and max(map(len, lines)) > ODM_MAX_LINE_LENGTH:
                raise ValueError(
                    f"OEM exceeds {ODM_MAX_LINE_LENGTH}-character line limit"
                )
            complete_end = len(combined) - len(pending)
            position = 0
            search_position = 0
            while search_position < complete_end:
                start_index = combined.find(
                    "COVARIANCE_START",
                    search_position,
                    complete_end,
                )
                stop_index = combined.find(
                    "COVARIANCE_STOP",
                    search_position,
                    complete_end,
                )
                if start_index < 0:
                    marker_index, marker = stop_index, "COVARIANCE_STOP"
                elif stop_index < 0 or start_index < stop_index:
                    marker_index, marker = start_index, "COVARIANCE_START"
                else:
                    marker_index, marker = stop_index, "COVARIANCE_STOP"
                if marker_index < 0:
                    break
                line_start = (
                    combined.rfind(
                        "\n",
                        0,
                        marker_index,
                    )
                    + 1
                )
                line_end = combined.find(
                    "\n",
                    marker_index,
                    complete_end,
                )
                if combined[line_start:line_end].strip() == marker:
                    if not in_covariance:
                        line_count += combined.count(
                            "\n",
                            position,
                            line_start,
                        )
                    in_covariance = marker == "COVARIANCE_START"
                    position = line_end + 1
                    search_position = position
                else:
                    search_position = marker_index + len(marker)
            if not in_covariance:
                line_count += combined.count(
                    "\n",
                    position,
                    complete_end,
                )
            if len(pending) > ODM_MAX_LINE_LENGTH:
                raise ValueError(
                    f"OEM exceeds {ODM_MAX_LINE_LENGTH}-character line limit"
                )
    if pending:
        if len(pending) > ODM_MAX_LINE_LENGTH:
            raise ValueError(f"OEM exceeds {ODM_MAX_LINE_LENGTH}-character line limit")
        if pending.strip() == "COVARIANCE_START":
            in_covariance = True
        elif pending.strip() == "COVARIANCE_STOP":
            in_covariance = False
        elif not in_covariance:
            line_count += 1
    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("capacity scan cancelled")
    return max(line_count, 1)
