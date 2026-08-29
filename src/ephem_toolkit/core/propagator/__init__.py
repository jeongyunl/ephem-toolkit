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
from ephem_toolkit.core.propagator.sgp4 import (
    Sgp4Propagator,
    Tle,
    read_tle,
    write_tle,
    format_tle_strings,
    create_tle_from_mean_keplerian,
    tle_epoch_to_tt_s,
    tle_epoch_to_datetime,
    datetime_to_tle_epoch,
    tle_epoch_to_iso8601,
    iso8601_to_tle_epoch,
)

__all__ = [
    "AnomalyType",
    "BrouwerJ2Propagator",
    "KeplerianState",
    "KeplerPropagator",
    "OutputMode",
    "Propagator",
    "Sgp4Propagator",
    "Tle",
    "cartesian_to_keplerian",
    "create_tle_from_mean_keplerian",
    "datetime_to_tle_epoch",
    "eccentric_to_mean_anomaly",
    "eccentric_to_true_anomaly",
    "format_tle_strings",
    "iso8601_to_tle_epoch",
    "keplerian_to_cartesian",
    "mean_motion_to_semi_major_axis",
    "mean_to_eccentric_anomaly",
    "mean_to_true_anomaly",
    "read_tle",
    "semi_major_axis_to_mean_motion",
    "tle_epoch_to_datetime",
    "tle_epoch_to_iso8601",
    "tle_epoch_to_tt_s",
    "true_to_eccentric_anomaly",
    "true_to_mean_anomaly",
    "write_tle",
]
