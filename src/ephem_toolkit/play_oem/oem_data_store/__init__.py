"""OEM data store public compatibility package."""

from __future__ import annotations

from .data_store import OemDataStore
from .public_types import (
    AppendNotice,
    ColumnGroupView,
    EarthFixedPositions,
    GroundTrackGroups,
    InterpolationPolicy,
    LoadStatus,
    LookAngleProfileView,
    OemMetadata,
    QueryRequest,
    RangeHint,
    RawAppendNotice,
    RawReservation,
    RawSnapshot,
    ResetNotice,
    RowSpan,
    StationAccessView,
    StoreNotice,
    StoreQuery,
    StoreSnapshot,
    SeriesGroups,
    TierName,
    TierNotice,
    TimeCoverage,
)
from .public_types import (
    DERIVED_CHUNK_SIZE,
    EARTH_FIXED_COLUMNS,
    GROUND_TRACK_COLUMNS,
    STATION_PROFILE_COLUMNS,
)
from ephem_toolkit.play_oem.series import (
    SERIES_GROUPS,
    SeriesGroupName,
)
import math

__all__ = [
    "AppendNotice",
    "ColumnGroupView",
    "EarthFixedPositions",
    "GroundTrackGroups",
    "InterpolationPolicy",
    "LoadStatus",
    "LookAngleProfileView",
    "OemMetadata",
    "OemDataStore",
    "QueryRequest",
    "RangeHint",
    "RawAppendNotice",
    "RawReservation",
    "RawSnapshot",
    "ResetNotice",
    "RowSpan",
    "StationAccessView",
    "StoreNotice",
    "StoreQuery",
    "StoreSnapshot",
    "SeriesGroups",
    "TierName",
    "TierNotice",
    "TimeCoverage",
]


def __getattr__(name: str):
    if name in {"_PrefetchFuture", "_ScheduledWork"}:
        from . import internal_types

        return getattr(internal_types, name)
    if name.startswith("_") or name in {
        "ODM_MAX_LINE_LENGTH",
        "station_metrics",
        "GroundTrackPreparationError",
        "ACCESS_WINDOW_MIN_MARGIN_S",
        "ACCESS_WINDOW_MARGIN_FRACTION",
        "wgs",
    }:
        if name in {
            "ODM_MAX_LINE_LENGTH",
            "station_metrics",
            "GroundTrackPreparationError",
            "ACCESS_WINDOW_MIN_MARGIN_S",
            "ACCESS_WINDOW_MARGIN_FRACTION",
            "wgs",
        }:
            if name == "ODM_MAX_LINE_LENGTH":
                from ephem_toolkit.core.ccsds.odm import ODM_MAX_LINE_LENGTH

                return ODM_MAX_LINE_LENGTH
            if name == "station_metrics":
                from ephem_toolkit.play_oem.ground_stations import station_metrics

                return station_metrics
            if name == "GroundTrackPreparationError":
                from ephem_toolkit.play_oem.ground_track import (
                    GroundTrackPreparationError,
                )

                return GroundTrackPreparationError
            if name in (
                "ACCESS_WINDOW_MIN_MARGIN_S",
                "ACCESS_WINDOW_MARGIN_FRACTION",
            ):
                from ephem_toolkit.play_oem import station_access

                return getattr(station_access, name)
            if name == "wgs":
                from ephem_toolkit.core import wgs

                return wgs
        from . import store_support

        return getattr(store_support, name)
    if name in {"_PrefetchFuture", "_ScheduledWork"}:
        from . import internal_types

        return getattr(internal_types, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
