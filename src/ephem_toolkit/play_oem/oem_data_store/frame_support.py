"""Earth-centered frame metadata and derived chunk writers."""

from __future__ import annotations

import numpy as np

from ..ground_track import (
    EARTH_CENTERS,
    GroundTrackPreparationError,
    states_to_itrf_m_batch,
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
    start: int,
    stop: int,
    output: np.ndarray,
) -> None:
    """Write one Earth-fixed derived chunk."""
    frame_name = earth_centered_frame_name(snapshot, "Earth-fixed positions")
    if frame_name is None:
        raise RuntimeError("Earth-fixed frame metadata is unavailable")
    output[start:stop, 0] = snapshot.raw[start:stop, 0]
    converted = states_to_itrf_m_batch(
        snapshot.raw[start:stop, 1:7],
        frame_name,
        snapshot.raw[start:stop, 0],
    )
    output[start:stop, 1:4] = converted[:, :3]
