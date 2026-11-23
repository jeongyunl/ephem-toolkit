"""Earth-centered frame metadata and derived chunk writers."""

from __future__ import annotations

import numpy as np

from ..ground_track import (
    EARTH_CENTERS,
    GroundTrackPreparationError,
    normalize_conversion_frame_name,
    _state_position_to_itrf_m_normalized,
)
from ..series import SeriesGroupName, compute_series_chunk
from .public_types import LoadStatus, StoreSnapshot


def earth_centered_frame_name(
    snapshot: StoreSnapshot,
    purpose: str,
) -> str | None:
    """Return an Earth-centered OEM reference frame name."""
    metadata = dict(snapshot.meta)
    frame_name = metadata.get("REF_FRAME")
    center_name = metadata.get("CENTER_NAME")
    if not isinstance(frame_name, str) or not isinstance(center_name, str):
        if snapshot.status is LoadStatus.COMPLETE:
            raise GroundTrackPreparationError(
                f"{purpose} requires CENTER_NAME and REF_FRAME metadata"
            )
        return None
    if center_name.strip().upper() not in EARTH_CENTERS:
        raise GroundTrackPreparationError(
            f"{purpose} requires an Earth-centered OEM; " f"found {center_name!r}"
        )
    return frame_name


def write_series_chunk(
    snapshot: StoreSnapshot,
    group: SeriesGroupName,
    start: int,
    stop: int,
    output: np.ndarray,
) -> None:
    """Write one derived series chunk."""
    output[start:stop] = compute_series_chunk(
        snapshot.raw,
        snapshot.segment_ids,
        group,
        start,
        stop,
    )


def write_earth_fixed_chunk(
    snapshot: StoreSnapshot,
    frame_name: str,
    start: int,
    stop: int,
    output: np.ndarray,
) -> None:
    """Write one Earth-fixed derived chunk."""
    normalized_frame = normalize_conversion_frame_name(frame_name)
    for row in range(start, stop):
        output[row, 0] = snapshot.raw[row, 0]
        output[row, 1:4] = _state_position_to_itrf_m_normalized(
            snapshot.raw[row, 1:7],
            normalized_frame,
            float(snapshot.raw[row, 0]),
            source_frame_name=frame_name,
        )
