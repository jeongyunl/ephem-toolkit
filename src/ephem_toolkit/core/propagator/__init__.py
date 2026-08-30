"""Propagator interface for orbital propagation.

This module provides a unified interface for all propagators in the toolkit:
- KeplerPropagator: Two-body Keplerian propagation
- BrouwerJ2Propagator: J2 secular mean-element propagation
- Sgp4Propagator: SGP4 TLE propagation (requires tudatpy)
- NumericalPropagator: Perturbed numerical propagation (requires tudatpy)
"""

from ephem_toolkit.core.propagator.base import (
    AnomalyType,
    KeplerianState,
    OutputMode,
    Propagator,
)
from ephem_toolkit.core.propagator.brouwer_j2 import BrouwerJ2Propagator
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
from ephem_toolkit.core.propagator.sgp4 import Sgp4Propagator

__all__ = [
    "AnomalyType",
    "BrouwerJ2Propagator",
    "KeplerianState",
    "KeplerPropagator",
    "OutputMode",
    "Propagator",
    "Sgp4Propagator",
    "cartesian_to_keplerian",
    "eccentric_to_mean_anomaly",
    "eccentric_to_true_anomaly",
    "keplerian_to_cartesian",
    "mean_motion_to_semi_major_axis",
    "mean_to_eccentric_anomaly",
    "mean_to_true_anomaly",
    "semi_major_axis_to_mean_motion",
    "true_to_eccentric_anomaly",
    "true_to_mean_anomaly",
]
