"""Brouwer J2 secular mean-element propagator."""

from __future__ import annotations

import numpy as np

from ephem_toolkit.core.consts import (
    EARTH_EQUATORIAL_RADIUS_M,
    EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    EARTH_J2,
)
from ephem_toolkit.core.propagator.base import (
    AnomalyType,
    KeplerianState,
    Propagator,
)


class BrouwerJ2Propagator(Propagator[KeplerianState]):
    """Brouwer J2 secular mean-element propagator.

    Propagates Brouwer mean Keplerian elements using J2 secular rates, then
    converts to Cartesian state via Brouwer short-period corrections.

    Initial state elements must be **Brouwer mean elements** — not osculating,
    not SGP4/TLE mean elements. Element[5] is mean anomaly.

    References
    ----------
    Brouwer, D. "Solution of the Problem of Artificial Satellite Theory
    Without Drag", Astronomical Journal, 64, 1959.
    """

    anomaly_type = AnomalyType.MEAN

    def __init__(
        self,
        initial_state: KeplerianState,
        mu_m3_s2: float = EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
        R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
        J2: float = EARTH_J2,
    ) -> None:
        """Initialize Brouwer J2 propagator.

        Parameters
        ----------
        initial_state : KeplerianState
            Initial Brouwer mean elements + epoch (TT, s since J2000 TT).
            Element[5] must be mean anomaly.
        mu_m3_s2 : float
            Gravitational parameter (m³/s²). Defaults to Earth's GM.
        R_e_m : float
            Earth equatorial radius (m). Defaults to WGS-84 value.
        J2 : float
            J2 zonal harmonic coefficient. Defaults to WGS-84 value.
        """
        super().__init__()
        self._mu_m3_s2 = mu_m3_s2
        self._R_e_m = R_e_m
        self._J2 = J2
        self.set_initial_state(initial_state)

    def set_initial_state(self, initial_state: KeplerianState) -> None:
        """Set initial Brouwer mean state and reset reference epoch.

        Parameters
        ----------
        initial_state : KeplerianState
            Initial Brouwer mean elements + epoch.
        """
        super().set_initial_state(initial_state)
        self._initial_state = initial_state
        self._reference_epoch_s = initial_state.epoch_s

    def get_initial_epoch_s(self) -> float:
        """Return epoch of initial state (TT, s since J2000 TT).

        Returns
        -------
        float
            Initial epoch in TT seconds since J2000.
        """
        return self._initial_state.epoch_s

    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        """Propagate to target epoch and return Cartesian state.

        Applies J2 secular rates to advance the Brouwer mean elements, then
        converts to Cartesian via Brouwer short-period corrections.

        Parameters
        ----------
        target_epoch_s : float
            Target epoch (TT, s since J2000 TT).

        Returns
        -------
        np.ndarray
            Cartesian state [x, y, z, vx, vy, vz] in meters and m/s.
        """
        # Deferred import to avoid circular dependency:
        # mean_kepler -> propagator -> brouwer_j2 -> mean_kepler
        from ephem_toolkit.core.mean_kepler import (
            brouwer_mean_to_cartesian,
            propagate_brouwer_j2,
        )

        elapsed_s = target_epoch_s - self.get_initial_epoch_s()
        propagated = propagate_brouwer_j2(
            self._initial_state.elements,
            elapsed_s,
            self._mu_m3_s2,
            self._R_e_m,
            self._J2,
        )
        return brouwer_mean_to_cartesian(
            propagated,
            self._mu_m3_s2,
            self._R_e_m,
            self._J2,
        )
