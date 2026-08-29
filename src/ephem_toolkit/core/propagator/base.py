"""Base interfaces for orbit propagators.

All epochs in this module are **ephemeris time** — seconds since the J2000
epoch (2000-01-01 12:00:00 TT).  Concrete propagators may treat this as
TDB or TT; the ≈1.7 ms difference is ignored.

References:
    https://en.wikipedia.org/wiki/Orbital_elements
    https://en.wikipedia.org/wiki/Epoch_(astronomy)#Julian_years_and_J2000
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

import numpy as np

InitialStateT = TypeVar("InitialStateT")
"""Per-subclass initial-state type: `KeplerianState`, `Tle`, config object, etc.

Every concrete ``InitialStateT`` must carry its own reference epoch, whether
explicitly (a dedicated field) or implicitly (an object that already has an
epoch, such as a TLE or a propagation config). There is no bare/anonymous
state representation without an epoch attached.
"""


class OutputMode(Enum):
    """Controls what :meth:`Propagator.propagate_to` / :meth:`Propagator.propagate_by` return.

    ``NONE``
        Advance the reference epoch but return ``None``.
    ``FINAL``
        Return a single ``(epoch_s, state)`` tuple for the target epoch.
    ``TRAJECTORY``
        Return a list of ``(epoch_s, state)`` tuples covering every
        internally computed sample from the previous reference epoch to the
        target epoch.  Each ``epoch_s`` is ephemeris time (seconds since
        J2000).
    """

    NONE = "none"
    FINAL = "final"
    TRAJECTORY = "trajectory"


class Propagator(ABC, Generic[InitialStateT]):
    """Top-level interface shared by every propagator in the project.

    A propagator is configured via :meth:`set_initial_state` with whatever
    initial-state representation it needs, then queried for the Cartesian
    state at a target epoch.  All epoch arguments and return values are
    **ephemeris time** — seconds since J2000 (TDB/TT).

    The propagator maintains a **reference epoch** that starts at the
    initial epoch (set by :meth:`set_initial_state`) and advances to the
    target epoch after each call to :meth:`propagate_to` or
    :meth:`propagate_by`.

    Subclasses must call :meth:`set_initial_state` from their ``__init__``
    to ensure the propagator is always in a valid, queryable state.
    Calling :meth:`propagate_to` or :meth:`propagate_by` before
    :meth:`set_initial_state` raises :class:`RuntimeError`.
    """

    def __init__(self) -> None:
        self._initial_state_set: bool = False
        self._reference_epoch_s: float | None = None

    @abstractmethod
    def set_initial_state(self, initial_state: InitialStateT) -> None:
        """Set (or replace) the propagator's initial state.

        Also resets :attr:`reference_epoch_s` to the initial epoch.

        Notes
        -----
        Concrete implementations **must** call
        ``super().set_initial_state(initial_state)`` (or set
        ``self._initial_state_set = True`` directly) so that the
        uninitialised-state guard works correctly.  After calling
        ``super()``, set ``self._reference_epoch_s`` to the initial epoch
        derived from ``initial_state``.
        """
        self._initial_state_set = True

    def _require_initial_state(self) -> None:
        """Raise :class:`RuntimeError` if no initial state has been set."""
        if not self._initial_state_set:
            raise RuntimeError(
                f"{type(self).__name__}.set_initial_state() must be called "
                "before propagation."
            )

    @property
    def reference_epoch_s(self) -> float:
        """Current reference epoch in ephemeris time (seconds since J2000).

        Initialised to the initial epoch by :meth:`set_initial_state` and
        advanced to the target epoch after each propagation call.
        """
        self._require_initial_state()
        assert self._reference_epoch_s is not None
        return self._reference_epoch_s

    @abstractmethod
    def get_initial_epoch_s(self) -> float:
        """Return the epoch of the initial state in ephemeris time (seconds since J2000).

        Fixed; does not advance.
        """

    @abstractmethod
    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        """Subclass hook: compute the Cartesian state at *target_epoch_s*.

        Parameters
        ----------
        target_epoch_s : float
            Target epoch in ephemeris time (seconds since J2000).

        Returns
        -------
        np.ndarray
            Cartesian state ``[x, y, z, vx, vy, vz]`` in SI units.
        """

    def _propagate_trajectory_impl(
        self,
        from_epoch_s: float,
        to_epoch_s: float,
    ) -> list[tuple[float, np.ndarray]]:
        """Subclass hook: return trajectory samples from *from_epoch_s* to *to_epoch_s*.

        Default implementation returns a single sample at *to_epoch_s*.
        Propagators that naturally produce intermediate samples (e.g. a
        numerical integrator) should override this.
        """
        return [(to_epoch_s, self._propagate_to_impl(to_epoch_s))]

    def propagate_to(
        self,
        target_epoch_s: float,
        output: OutputMode = OutputMode.FINAL,
    ) -> tuple[float, np.ndarray] | list[tuple[float, np.ndarray]] | None:
        """Propagate to *target_epoch_s* and advance :attr:`reference_epoch_s`.

        Parameters
        ----------
        target_epoch_s : float
            Target epoch in ephemeris time (seconds since J2000).
        output : OutputMode
            ``NONE``  — return ``None``.
            ``FINAL`` — return ``(epoch_s, state)`` at *target_epoch_s*.
            ``TRAJECTORY`` — return ``[(epoch_s, state), ...]`` from the
            previous :attr:`reference_epoch_s` to *target_epoch_s*.

        Returns
        -------
        tuple[float, np.ndarray] | list[tuple[float, np.ndarray]] | None
        """
        self._require_initial_state()
        prev_ref = self._reference_epoch_s
        assert prev_ref is not None

        if output is OutputMode.NONE:
            result = None
        elif output is OutputMode.FINAL:
            result = (target_epoch_s, self._propagate_to_impl(target_epoch_s))
        else:  # TRAJECTORY
            result = self._propagate_trajectory_impl(prev_ref, target_epoch_s)

        self._reference_epoch_s = target_epoch_s
        return result

    def propagate_by(
        self,
        time_elapsed_s: float,
        output: OutputMode = OutputMode.FINAL,
    ) -> tuple[float, np.ndarray] | list[tuple[float, np.ndarray]] | None:
        """Propagate *time_elapsed_s* past :attr:`reference_epoch_s`.

        Parameters
        ----------
        time_elapsed_s : float
            Seconds to advance from the current :attr:`reference_epoch_s`.
        output : OutputMode
            Same semantics as :meth:`propagate_to`.

        Returns
        -------
        tuple[float, np.ndarray] | list[tuple[float, np.ndarray]] | None
        """
        return self.propagate_to(
            self.reference_epoch_s + time_elapsed_s,
            output=output,
        )


class AnomalyType(Enum):
    """Semantic meaning of the 6th Keplerian element produced by a propagator."""

    TRUE = "true"
    MEAN = "mean"


@dataclass(frozen=True)
class KeplerianState:
    """Keplerian elements paired with the epoch at which they are defined.

    The ``elements`` array is made read-only in :meth:`__post_init__` so
    that the frozen-dataclass invariant extends to the array contents, not
    just the attribute binding.
    """

    elements: np.ndarray
    """Keplerian elements ``[a, e, i, omega, RAAN, anomaly]``."""
    epoch_s: float
    """Epoch at which :attr:`elements` is defined, in ephemeris time
    (seconds since J2000)."""

    def __post_init__(self) -> None:
        # Make the backing array immutable so that the frozen-dataclass
        # guarantee covers the array contents, not just the attribute slot.
        object.__setattr__(
            self, "elements", np.array(self.elements, dtype=float)
        )
        self.elements.flags.writeable = False
