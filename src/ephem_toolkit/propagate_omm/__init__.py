"""Propagate OMM orbits: SGP4 for TLE-based OMMs, Kepler for others."""

from . import __main__ as propagate_omm

main = propagate_omm.main
cli = propagate_omm.cli

__all__ = ["main", "cli"]
