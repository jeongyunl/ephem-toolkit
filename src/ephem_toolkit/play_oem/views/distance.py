"""Compatibility imports for the Legacy geocentric-distance time-series view."""

from .legacy_distance import LegacyGeocentricDistanceView

GeocentricDistanceView = LegacyGeocentricDistanceView

__all__ = ["GeocentricDistanceView"]
