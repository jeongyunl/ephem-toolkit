"""Earth-fixed coordinate preparation for the Ground Track view."""

from __future__ import annotations

from functools import lru_cache
from dataclasses import dataclass
from typing import Any

import numpy as np

EARTH_CENTERS = frozenset({"EARTH", "399"})
DIRECT_EARTH_FIXED_FRAMES = frozenset({"ITRF", "ITRF1993", "ITRF93"})
INERTIAL_FRAMES = frozenset({"J2000", "EME2000", "ICRF", "GCRF", "TEME"})
EARTH_RADIUS_AUTHALIC_M = 6_371_007.1809


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

    source_frame_name = "J2000" if frame_name == "J2000" else frame_name
    if source_frame_name == "ITRF93":
        source_frame_name = "ITRF1993"
    try:
        source_frame = frame_utils.Frame[source_frame_name]
        # Construct from the enum value because the existing Frame member
        # annotations make Pylance infer ``Frame.ITRF`` as ``str``.
        target_frame = frame_utils.Frame("ITRF")
        converted = frame_utils.convert_frame(
            source_frame, target_frame, epoch_tt_s, state_m
        )
    except (KeyError, ValueError, RuntimeError) as error:
        raise GroundTrackPreparationError(
            f"Cannot convert OEM frame {frame_name!r} to ITRF: {error}"
        ) from error
    if converted is None:
        raise GroundTrackPreparationError(
            f"Conversion from OEM frame {frame_name!r} to ITRF is unavailable"
        )
    return np.asarray(converted, dtype=float)


def state_position_to_itrf_m(
    state_m: np.ndarray, frame_name: str, epoch_tt_s: float
) -> np.ndarray:
    """Return a supported OEM position in ITRF meters at one TT epoch."""
    normalized_frame = frame_name.strip().upper()
    if normalized_frame == "ITRF93":
        normalized_frame = "ITRF1993"
    state_m = np.asarray(state_m, dtype=float)
    if state_m.shape != (6,) or not np.isfinite(state_m).all():
        raise GroundTrackPreparationError("OEM cursor state is invalid")
    if normalized_frame in DIRECT_EARTH_FIXED_FRAMES:
        return state_m[:3].copy()
    if normalized_frame not in INERTIAL_FRAMES:
        raise GroundTrackPreparationError(
            f"OEM frame {frame_name!r} is not supported for Ground Track"
        )
    converted = _convert_inertial_state_to_itrf(normalized_frame, epoch_tt_s, state_m)
    if converted.shape != (6,) or not np.isfinite(converted).all():
        raise GroundTrackPreparationError(
            f"Frame conversion returned an invalid state at TT epoch {epoch_tt_s:.3f}"
        )
    return converted[:3].copy()


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
    runs: list[GroundTrackRun] = []
    run_times: list[float] = []
    run_latitudes: list[float] = []
    run_longitudes: list[float] = []

    def finish_run() -> None:
        if not run_times:
            return
        runs.append(
            GroundTrackRun(
                np.asarray(run_times, dtype=float),
                np.asarray(run_latitudes, dtype=float),
                np.asarray(run_longitudes, dtype=float),
            )
        )
        run_times.clear()
        run_latitudes.clear()
        run_longitudes.clear()

    for index in range(coordinates.timestamps_s.size):
        if (
            index == 0
            or coordinates.segment_ids[index] != coordinates.segment_ids[index - 1]
        ):
            finish_run()
            run_times.append(float(coordinates.timestamps_s[index]))
            run_latitudes.append(float(coordinates.latitude_rad[index]))
            run_longitudes.append(float(relative_lon[index]))
            continue

        previous_lon = run_longitudes[-1]
        current_lon = float(relative_lon[index])
        delta_lon = current_lon - previous_lon
        if delta_lon < -np.pi:
            unwrapped_lon = current_lon + 2.0 * np.pi
            seam_lon = np.pi
            opposite_seam_lon = -np.pi
        elif delta_lon > np.pi:
            unwrapped_lon = current_lon - 2.0 * np.pi
            seam_lon = -np.pi
            opposite_seam_lon = np.pi
        else:
            run_times.append(float(coordinates.timestamps_s[index]))
            run_latitudes.append(float(coordinates.latitude_rad[index]))
            run_longitudes.append(current_lon)
            continue

        fraction = (seam_lon - previous_lon) / (unwrapped_lon - previous_lon)
        seam_time = coordinates.timestamps_s[index - 1] + fraction * (
            coordinates.timestamps_s[index] - coordinates.timestamps_s[index - 1]
        )
        seam_latitude = coordinates.latitude_rad[index - 1] + fraction * (
            coordinates.latitude_rad[index] - coordinates.latitude_rad[index - 1]
        )
        run_times.append(float(seam_time))
        run_latitudes.append(float(seam_latitude))
        run_longitudes.append(float(seam_lon))
        finish_run()
        run_times.extend((float(seam_time), float(coordinates.timestamps_s[index])))
        run_latitudes.extend(
            (float(seam_latitude), float(coordinates.latitude_rad[index]))
        )
        run_longitudes.extend((float(opposite_seam_lon), current_lon))

    finish_run()
    return tuple(runs)
