"""Propagate OMM orbits: SGP4 for TLE-based OMMs, Kepler for others."""

from .propagate_omm import main

__all__ = ["main"]
