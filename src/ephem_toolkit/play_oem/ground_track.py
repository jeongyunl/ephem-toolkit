"""Earth-fixed coordinate preparation for the Ground Track view."""

from __future__ import annotations

from functools import lru_cache
from dataclasses import dataclass
from typing import Any

import numpy as np

EARTH_CENTERS = frozenset({"EARTH", "399"})
# Configure the Earth-fixed target once for all Play-OEM conversions. This is
# fixed for the lifetime of a store so its derived caches remain consistent.
EARTH_FIXED_FRAME_NAME = "ITRF1993"
J2000_EQUIVALENT_FRAMES = frozenset({"J2000", "EME2000", "ICRF", "GCRF"})
SUPPORTED_SOURCE_FRAMES = frozenset({"J2000", "TEME", "ITRF1993"})
EARTH_RADIUS_AUTHALIC_M = 6_371_007.1809


def normalize_frame_name(frame_name: str) -> str:
    """Return the canonical spelling used by play-oem for an OEM frame.

    The viewer treats ITRF and ITRF1993 labels as the ITRF93 realization.
    """
    normalized_frame = frame_name.strip().upper()
    if normalized_frame in {"ITRF", "ITRF1993", "ITRF93"}:
        return "ITRF93"
    return normalized_frame


def normalize_conversion_frame_name(frame_name: str) -> str:
    """Return the frame name used for Earth-fixed conversion dispatch."""
    normalized_frame = normalize_frame_name(frame_name)
    if normalized_frame in J2000_EQUIVALENT_FRAMES:
        return "J2000"
    if normalized_frame == "ITRF93":
        return "ITRF1993"
    return normalized_frame


class GroundTrackPreparationError(ValueError):
    """Raised when an OEM cannot be prepared as a valid Earth ground track."""


@dataclass(frozen=True)
class GroundTrackCoordinates:
    """Prepared WGS-84 geodetic samples in radians and TT seconds."""

    timestamps_s: np.ndarray
    latitude_rad: np.ndarray
    longitude_rad: np.ndarray
    segment_ids: np.ndarray
    source_frame: str


@dataclass(frozen=True)
class GroundTrackRun:
    """A drawable track run with longitude relative to its map center."""

    timestamps_s: np.ndarray
    latitude_rad: np.ndarray
    longitude_relative_rad: np.ndarray


@lru_cache(maxsize=1)
def _wgs84_geocentric_transformer() -> Any:
    """Return a cached ECEF-to-WGS-84 geographic transformer."""
    from pyproj import Transformer

    return Transformer.from_crs("EPSG:4978", "EPSG:4979", always_xy=True)


def _ecef_to_wgs84_geodetic(ecef_m: np.ndarray) -> np.ndarray:
    """Convert ECEF meters to WGS-84 ``[latitude, longitude, altitude]``."""
    try:
        transformer = _wgs84_geocentric_transformer()
        if len(ecef_m) == 1:
            longitude_deg, latitude_deg, altitude_m = transformer.transform(
                *(float(value) for value in ecef_m[0]), errcheck=True
            )
            longitude_deg = np.asarray([longitude_deg], dtype=float)
            latitude_deg = np.asarray([latitude_deg], dtype=float)
            altitude_m = np.asarray([altitude_m], dtype=float)
        else:
            longitude_deg, latitude_deg, altitude_m = transformer.transform(
                ecef_m[:, 0], ecef_m[:, 1], ecef_m[:, 2], errcheck=True
            )
    except Exception as error:
        raise GroundTrackPreparationError(
            f"Cannot convert Earth-fixed OEM positions to WGS-84 coordinates: {error}"
        ) from error
    return np.column_stack(
        (np.deg2rad(latitude_deg), np.deg2rad(longitude_deg), altitude_m)
    )


def _convert_inertial_state_to_itrf(
    frame_name: str, epoch_tt_s: float, state_m: np.ndarray
) -> np.ndarray:
    """Load the frame-conversion stack only when an inertial OEM needs it."""
    from ephem_toolkit.core import frame_utils

    try:
        source_frame = frame_utils.Frame[frame_name]
        target_frame = frame_utils.Frame[EARTH_FIXED_FRAME_NAME]
        converted = frame_utils.convert_frame(
            source_frame, target_frame, epoch_tt_s, state_m
        )
    except (KeyError, ValueError, RuntimeError) as error:
        raise GroundTrackPreparationError(
            f"Cannot convert OEM frame {frame_name!r} to {EARTH_FIXED_FRAME_NAME}: {error}"
        ) from error
    if converted is None:
        raise GroundTrackPreparationError(
            f"Conversion from OEM frame {frame_name!r} to {EARTH_FIXED_FRAME_NAME} is unavailable"
        )
    return np.asarray(converted, dtype=float)


def state_position_to_itrf_m(
    state_m: np.ndarray, frame_name: str, epoch_tt_s: float
) -> np.ndarray:
    """Return a supported OEM position in the configured Earth-fixed frame."""
    return _state_to_itrf_m_normalized(
        state_m,
        normalize_conversion_frame_name(frame_name),
        epoch_tt_s,
        source_frame_name=frame_name,
    )[:3].copy()


def states_to_itrf_m_batch(
    states_m: np.ndarray,
    frame_name: str,
    epoch_tt_s: np.ndarray,
) -> np.ndarray:
    """Convert many OEM states, using array copies for fixed source frames."""
    states_m = np.asarray(states_m, dtype=float)
    epochs_tt_s = np.asarray(epoch_tt_s, dtype=float)
    if (
        states_m.ndim != 2
        or states_m.shape[1:] != (6,)
        or states_m.shape[0] != epochs_tt_s.size
    ):
        raise GroundTrackPreparationError("Earth-fixed state batch shape is invalid")
    if (
        epochs_tt_s.ndim != 1
        or not np.isfinite(states_m).all()
        or not np.isfinite(epochs_tt_s).all()
    ):
        raise GroundTrackPreparationError("Earth-fixed state batch is invalid")

    normalized_frame = normalize_conversion_frame_name(frame_name)
    if normalized_frame == EARTH_FIXED_FRAME_NAME:
        return states_m.copy()

    converted = np.empty_like(states_m)
    for index, (epoch_tt_s_value, state_m) in enumerate(zip(epochs_tt_s, states_m)):
        converted[index] = _state_to_itrf_m_normalized(
            state_m,
            normalized_frame,
            float(epoch_tt_s_value),
            source_frame_name=frame_name,
        )
    return converted


def _state_to_itrf_m_normalized(
    state_m: np.ndarray,
    normalized_frame: str,
    epoch_tt_s: float,
    *,
    source_frame_name: str,
) -> np.ndarray:
    """Convert a complete state to the configured Earth-fixed frame at its epoch."""
    state_m = np.asarray(state_m, dtype=float)
    if state_m.shape != (6,) or not np.isfinite(state_m).all():
        raise GroundTrackPreparationError("OEM cursor state is invalid")
    if normalized_frame == EARTH_FIXED_FRAME_NAME:
        return state_m.copy()
    if normalized_frame not in SUPPORTED_SOURCE_FRAMES:
        raise GroundTrackPreparationError(
            f"OEM frame {source_frame_name!r} is not supported for Ground Track"
        )
    converted = _convert_inertial_state_to_itrf(normalized_frame, epoch_tt_s, state_m)
    if converted.shape != (6,) or not np.isfinite(converted).all():
        raise GroundTrackPreparationError(
            f"Frame conversion returned an invalid state at TT epoch {epoch_tt_s:.3f}"
        )
    return converted.copy()


def split_ground_track_runs(
    coordinates: GroundTrackCoordinates, center_longitude_deg: float
) -> tuple[GroundTrackRun, ...]:
    """Split a track at OEM gaps and the map seam, adding interpolated seam points.

    Returned longitudes are relative to the map center and lie within ±π. Each
    seam crossing terminates one run at one edge and begins the next at the other.
    """
    if not np.isfinite(center_longitude_deg):
        raise ValueError("center_longitude_deg must be finite")
    arrays = (
        coordinates.timestamps_s,
        coordinates.latitude_rad,
        coordinates.longitude_rad,
        coordinates.segment_ids,
    )
    if any(
        np.asarray(values).shape != coordinates.timestamps_s.shape for values in arrays
    ):
        raise ValueError("ground-track coordinate arrays must have matching shapes")
    if coordinates.timestamps_s.size == 0:
        return ()

    center_rad = np.deg2rad(((center_longitude_deg + 180.0) % 360.0) - 180.0)
    relative_lon = (coordinates.longitude_rad - center_rad + np.pi) % (
        2.0 * np.pi
    ) - np.pi
    if coordinates.timestamps_s.size == 1:
        return (
            GroundTrackRun(
                coordinates.timestamps_s.copy(),
                coordinates.latitude_rad.copy(),
                relative_lon.copy(),
            ),
        )

    segment_changes = np.flatnonzero(
        coordinates.segment_ids[1:] != coordinates.segment_ids[:-1]
    ) + 1
    previous_lon = relative_lon[:-1]
    current_lon = relative_lon[1:]
    delta_lon = current_lon - previous_lon
    crossing_indices = np.flatnonzero(
        (delta_lon < -np.pi) | (delta_lon > np.pi)
    ) + 1
    crossing_indices = crossing_indices[
        ~np.isin(crossing_indices, segment_changes)
    ]

    event_indices = np.unique(
        np.concatenate((segment_changes, crossing_indices))
    )
    runs: list[GroundTrackRun] = []
    run_times: list[np.ndarray] = []
    run_latitudes: list[np.ndarray] = []
    run_longitudes: list[np.ndarray] = []
    run_start = 0

    def append_segment(first: int, stop: int) -> None:
        if first >= stop:
            return
        run_times.append(coordinates.timestamps_s[first:stop])
        run_latitudes.append(coordinates.latitude_rad[first:stop])
        run_longitudes.append(relative_lon[first:stop])

    def finish_run() -> None:
        if not run_times:
            return
        runs.append(
            GroundTrackRun(
                np.concatenate(run_times),
                np.concatenate(run_latitudes),
                np.concatenate(run_longitudes),
            )
        )
        run_times.clear()
        run_latitudes.clear()
        run_longitudes.clear()

    for index in event_indices:
        if index in segment_changes:
            append_segment(run_start, index)
            finish_run()
            run_start = index
            continue

        previous_index = index - 1
        append_segment(run_start, index)
        previous_lon_value = float(relative_lon[previous_index])
        current_lon_value = float(relative_lon[index])
        delta_lon_value = current_lon_value - previous_lon_value
        if delta_lon_value < -np.pi:
            unwrapped_lon = current_lon_value + 2.0 * np.pi
            seam_lon = np.pi
            opposite_seam_lon = -np.pi
        else:
            unwrapped_lon = current_lon_value - 2.0 * np.pi
            seam_lon = -np.pi
            opposite_seam_lon = np.pi
        fraction = (
            (seam_lon - previous_lon_value)
            / (unwrapped_lon - previous_lon_value)
        )
        seam_time = coordinates.timestamps_s[previous_index] + fraction * (
            coordinates.timestamps_s[index]
            - coordinates.timestamps_s[previous_index]
        )
        seam_latitude = coordinates.latitude_rad[previous_index] + fraction * (
            coordinates.latitude_rad[index]
            - coordinates.latitude_rad[previous_index]
        )
        run_times.append(np.asarray([seam_time], dtype=float))
        run_latitudes.append(np.asarray([seam_latitude], dtype=float))
        run_longitudes.append(np.asarray([seam_lon], dtype=float))
        finish_run()
        run_times.append(
            np.asarray([seam_time, coordinates.timestamps_s[index]], dtype=float)
        )
        run_latitudes.append(
            np.asarray(
                [seam_latitude, coordinates.latitude_rad[index]],
                dtype=float,
            )
        )
        run_longitudes.append(
            np.asarray([opposite_seam_lon, current_lon_value], dtype=float)
        )
        run_start = index + 1

    append_segment(run_start, coordinates.timestamps_s.size)
    finish_run()
    return tuple(runs)
