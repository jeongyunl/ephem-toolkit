"""Compatibility imports for the Legacy speed/altitude time-series view."""

from .legacy_speed_altitude import LegacySpeedAltitudeView

SpeedAltitudeView = LegacySpeedAltitudeView

__all__ = ["SpeedAltitudeView"]
