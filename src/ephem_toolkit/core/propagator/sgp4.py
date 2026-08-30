"""SGP4 propagator wrapping TudatPy's SGP4 ephemeris.

Requires tudatpy. Import is deferred to avoid loading tudatpy at module level.
"""

from __future__ import annotations

import numpy as np
from typing_extensions import override

from ephem_toolkit.core import tle
from ephem_toolkit.core.propagator.base import Propagator


class Sgp4Propagator(Propagator[tle.Tle]):
    """SGP4 propagator built from a NORAD TLE.

    Wraps TudatPy's ``environment_setup.ephemeris.sgp4`` ephemeris.
    Requires tudatpy to be installed.

    Initial state is a :class:`~ephem_toolkit.core.tle.Tle` object.
    The epoch is derived from the TLE's ``epoch_year``/``epoch_day`` fields.
    """

    def __init__(self, initial_state: tle.Tle) -> None:
        """Initialize SGP4 propagator from a TLE.

        Parameters
        ----------
        initial_state : tle.Tle
            Parsed TLE object. Epoch is read from TLE fields.
        """
        super().__init__()
        self.set_initial_state(initial_state)

    @override
    def set_initial_state(self, initial_state: tle.Tle) -> None:
        """Set TLE and build SGP4 ephemeris.

        Parameters
        ----------
        initial_state : tle.Tle
            Parsed TLE object.
        """
        super().set_initial_state(initial_state)

        from tudatpy.dynamics import environment_setup  # deferred heavy import

        line1, line2 = tle.format_tle_strings(initial_state)
        ephemeris_settings = environment_setup.ephemeris.sgp4(line1, line2)
        self._ephemeris = environment_setup.create_body_ephemeris(
            ephemeris_settings,
            body_name=initial_state.object_name or "UNKNOWN",
        )
        self._tle = initial_state
        self._reference_epoch_s = tle.tle_epoch_to_tt_s(
            initial_state.epoch_year, initial_state.epoch_day
        )

    @override
    def get_initial_epoch_s(self) -> float:
        """Return TLE epoch (TT, s since J2000 TT).

        Returns
        -------
        float
            TLE epoch in TT seconds since J2000.
        """
        return tle.tle_epoch_to_tt_s(self._tle.epoch_year, self._tle.epoch_day)

    @override
    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        """Query SGP4 ephemeris at target epoch.

        Parameters
        ----------
        target_epoch_s : float
            Target epoch (TT, s since J2000 TT).

        Returns
        -------
        np.ndarray
            Cartesian state [x, y, z, vx, vy, vz] in meters and m/s.
        """
        return np.asarray(self._ephemeris.cartesian_state(target_epoch_s))
