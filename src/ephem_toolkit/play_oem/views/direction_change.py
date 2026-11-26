"""Compatibility imports for the Legacy direction-change time-series view."""

from .legacy_direction_change import LegacyDirectionChangeView

DirectionChangeView = LegacyDirectionChangeView

__all__ = ["DirectionChangeView"]
