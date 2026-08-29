"""Propagator interface for orbital propagation.

This module provides a unified interface for all propagators in the toolkit:
- KeplerPropagator: Two-body Keplerian propagation
- MeanJ2Propagator: J2 secular mean-element propagation
- Sgp4Propagator: SGP4 TLE propagation (requires tudatpy)
- NumericalPropagator: Perturbed numerical propagation (requires tudatpy)
"""

from ephem_toolkit.core.propagator.base import (
    AnomalyType,
    KeplerianState,
    OutputMode,
    Propagator,
)
from ephem_toolkit.core.propagator.kepler import (
    KeplerPropagator,
    cartesian_to_keplerian,
    keplerian_to_cartesian,
    true_to_eccentric_anomaly,
    eccentric_to_true_anomaly,
    eccentric_to_mean_anomaly,
    mean_to_eccentric_anomaly,
    mean_to_true_anomaly,
    true_to_mean_anomaly,
    mean_motion_to_semi_major_axis,
    semi_major_axis_to_mean_motion,
)

__all__ = [
    "AnomalyType",
    "KeplerianState",
    "KeplerPropagator",
    "OutputMode",
    "Propagator",
    "cartesian_to_keplerian",
    "keplerian_to_cartesian",
    "true_to_eccentric_anomaly",
    "eccentric_to_true_anomaly",
    "eccentric_to_mean_anomaly",
    "mean_to_eccentric_anomaly",
    "mean_to_true_anomaly",
    "true_to_mean_anomaly",
    "mean_motion_to_semi_major_axis",
    "semi_major_axis_to_mean_motion",
]
