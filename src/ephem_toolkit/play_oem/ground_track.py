"""Earth-fixed coordinate preparation for the Ground Track view."""

from __future__ import annotations

from functools import lru_cache
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike

EARTH_CENTERS = frozenset({"EARTH", "399"})
DIRECT_EARTH_FIXED_FRAMES = frozenset({"ITRF", "ITRF1993", "ITRF93"})
INERTIAL_FRAMES = frozenset({"J2000", "EME2000", "ICRF", "GCRF", "TEME"})
EARTH_RADIUS_AUTHALIC_M = 6_371_007.1809


class GroundTrackPreparationError(ValueError):
    """Raised when an OEM cannot be prepared as a valid Earth ground track."""


@dataclass(frozen=True)
class GroundTrackSource:
    """Source samples and metadata needed to prepare a Ground Track history."""

    timestamps_s: np.ndarray
    states_m: np.ndarray
    segment_ids: np.ndarray
    center_name: str
    frame_name: str

    @classmethod
    def from_samples(
        cls,
        timestamps_s: ArrayLike,
        states_m: ArrayLike,
        segment_ids: ArrayLike,
        center_name: str,
        frame_name: str,
    ) -> GroundTrackSource:
        """Create an immutable-by-convention copy of the OEM ground-track inputs."""
        return cls(
            np.asarray(timestamps_s, dtype=float).copy(),
            np.asarray(states_m, dtype=float).copy(),
            np.asarray(segment_ids, dtype=int).copy(),
            center_name,
            frame_name,
        )


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


class EarthFixedPositionCache:
    """Share converted source-sample positions between Earth-fixed views."""

    def __init__(self) -> None:
        self._source: GroundTrackSource | None = None
        self._positions_m: np.ndarray | None = None
        self._computed: np.ndarray | None = None

    def clear(self) -> None:
        """Discard converted positions after the active OEM is replaced."""
        self._source = None
        self._positions_m = None
        self._computed = None

    def positions(
        self,
        source: GroundTrackSource,
        index_range: tuple[int, int] | None = None,
    ) -> np.ndarray:
        """Return OEM sample positions in ITRF, converting only missing samples.

        ``index_range`` limits both conversion and the returned rows to
        ``[start, stop)``; omitting it covers every sample.
        """
        self._ensure_source(source)
        assert self._positions_m is not None
        assert self._computed is not None
        timestamps_s = np.asarray(source.timestamps_s, dtype=float)
        states_m = np.asarray(source.states_m, dtype=float)
        start, stop = (0, timestamps_s.size) if index_range is None else index_range
        for index in start + np.flatnonzero(~self._computed[start:stop]):
            self._positions_m[index] = state_position_to_itrf_m(
                states_m[index], source.frame_name, float(timestamps_s[index])
            )
            self._computed[index] = True
        positions = self._positions_m[start:stop].view()
        positions.setflags(write=False)
        return positions

    def position_for_state(
        self, source: GroundTrackSource, state_m: np.ndarray, epoch_tt_s: float
    ) -> np.ndarray:
        """Reuse a converted OEM sample at an exact epoch, otherwise convert state."""
        self._ensure_source(source)
        timestamps_s = np.asarray(source.timestamps_s, dtype=float)
        states_m = np.asarray(source.states_m, dtype=float)
        index = int(np.searchsorted(timestamps_s, epoch_tt_s))
        if (
            index < timestamps_s.size
            and timestamps_s[index] == epoch_tt_s
            and np.array_equal(states_m[index], state_m)
        ):
            assert self._positions_m is not None
            assert self._computed is not None
            if not self._computed[index]:
                self._positions_m[index] = state_position_to_itrf_m(
                    states_m[index], source.frame_name, float(epoch_tt_s)
                )
                self._computed[index] = True
            return self._positions_m[index].copy()
        return state_position_to_itrf_m(state_m, source.frame_name, epoch_tt_s)

    def _ensure_source(self, source: GroundTrackSource) -> None:
        if source is self._source:
            return
        timestamps_s = np.asarray(source.timestamps_s, dtype=float)
        self._source = source
        self._positions_m = np.empty((timestamps_s.size, 3), dtype=float)
        self._computed = np.zeros(timestamps_s.size, dtype=bool)


def window_indices(
    timestamps_s: np.ndarray,
    bounds: tuple[float, float],
    margin_s: float = 0.0,
) -> tuple[int, int]:
    """Return ``[start, stop)`` sample indices covering bounds plus one sample each side."""
    start = int(np.searchsorted(timestamps_s, bounds[0] - margin_s, side="left"))
    stop = int(np.searchsorted(timestamps_s, bounds[1] + margin_s, side="right"))
    count = len(timestamps_s)
    return max(0, start - 1), min(count, stop + 1)


def prepare_ground_track(
    source: GroundTrackSource,
    *,
    position_cache: EarthFixedPositionCache | None = None,
    bounds: tuple[float, float] | None = None,
    margin_s: float = 0.0,
) -> GroundTrackCoordinates:
    """Convert supported OEM samples to WGS-84 geodetic coordinates.

    With ``bounds``, only samples within the bounds (plus ``margin_s`` and one
    neighbouring sample on each side) are converted.

    Earth-fixed coordinates use their positions directly. Supported inertial states
    are converted at each TT epoch. No GUI, plotting, or projection library is imported.
    """
    center_name = source.center_name.strip().upper()
    if center_name not in EARTH_CENTERS:
        raise GroundTrackPreparationError(
            f"Ground Track requires an Earth-centered OEM; found {source.center_name!r}"
        )

    frame_name = source.frame_name.strip().upper()
    if frame_name == "ITRF93":
        frame_name = "ITRF1993"
    direct_earth_fixed = frame_name in DIRECT_EARTH_FIXED_FRAMES
    if not direct_earth_fixed and frame_name not in INERTIAL_FRAMES:
        raise GroundTrackPreparationError(
            f"OEM frame {source.frame_name!r} is not supported for Ground Track"
        )

    timestamps_s = np.asarray(source.timestamps_s, dtype=float)
    states_m = np.asarray(source.states_m, dtype=float)
    segment_ids = np.asarray(source.segment_ids, dtype=int)
    if timestamps_s.ndim != 1 or timestamps_s.size == 0:
        raise GroundTrackPreparationError(
            "Ground Track requires at least one OEM sample"
        )
    index_range: tuple[int, int] | None = None
    if bounds is not None and states_m.shape == (timestamps_s.size, 6):
        index_range = window_indices(timestamps_s, bounds, margin_s)
        window = slice(*index_range)
        timestamps_s = timestamps_s[window]
        states_m = states_m[window]
        segment_ids = segment_ids[window]
    if states_m.shape != (timestamps_s.size, 6):
        raise GroundTrackPreparationError(
            "OEM states must have shape (number of timestamps, 6)"
        )
    if segment_ids.shape != timestamps_s.shape:
        raise GroundTrackPreparationError(
            "OEM segment IDs must match the number of timestamps"
        )
    if not np.isfinite(timestamps_s).all() or not np.isfinite(states_m).all():
        raise GroundTrackPreparationError("OEM samples contain non-finite values")
    if np.any(np.diff(timestamps_s) <= 0.0):
        raise GroundTrackPreparationError("OEM timestamps must be strictly increasing")
    if np.any(np.diff(segment_ids) < 0):
        raise GroundTrackPreparationError("OEM segment IDs must be non-decreasing")

    if position_cache is None:
        position_cache = EarthFixedPositionCache()
    try:
        earth_fixed_positions_m = position_cache.positions(source, index_range)
    except GroundTrackPreparationError:
        raise
    except Exception as error:
        raise GroundTrackPreparationError(
            f"Cannot convert OEM frame {frame_name!r} to ITRF: {error}"
        ) from error

    geodetic = _ecef_to_wgs84_geodetic(earth_fixed_positions_m)
    latitude_rad = np.asarray(geodetic[:, 0], dtype=float)
    longitude_rad = np.asarray(geodetic[:, 1], dtype=float)
    if not np.isfinite(latitude_rad).all() or not np.isfinite(longitude_rad).all():
        raise GroundTrackPreparationError(
            "WGS-84 conversion returned non-finite geodetic coordinates"
        )
    if np.any(geodetic[:, 2] < -1.0e-3):
        raise GroundTrackPreparationError(
            "OEM contains an Earth-fixed position inside the WGS-84 ellipsoid"
        )

    return GroundTrackCoordinates(
        timestamps_s=timestamps_s.copy(),
        latitude_rad=latitude_rad,
        longitude_rad=longitude_rad,
        segment_ids=segment_ids.copy(),
        source_frame=frame_name,
    )


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
