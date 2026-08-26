"""CLI compatibility layer for the TLE wrapper."""

from . import propagate_tle

parse_arguments = propagate_tle.parse_arguments

__all__ = ["parse_arguments"]
