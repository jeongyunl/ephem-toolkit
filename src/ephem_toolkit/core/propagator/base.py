"""Base classes and types for the propagator interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

import numpy as np


class OutputMode(Enum):
    """Controls what propagate_to / propagate_by return."""

    NONE = "none"  # advance reference epoch, return None
    FINAL = "final"  # return (epoch_s, state) for the target epoch
    TRAJECTORY = "trajectory"  # return [(epoch_s, state), ...] from reference epoch


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
    """Epoch at which :attr:`elements` is defined (TT, s since J2000 TT)."""

    def __post_init__(self) -> None:
        # Make the backing array immutable so that the frozen-dataclass
        # guarantee covers the array contents, not just the attribute slot.
        object.__setattr__(self, "elements", np.array(self.elements, dtype=float))
        self.elements.flags.writeable = False


InitialStateT = TypeVar("InitialStateT")


class Propagator(ABC, Generic[InitialStateT]):
    """Abstract base class for orbital propagators.

    All propagators share a common interface:
    - Set initial state via ``set_initial_state``
    - Query state at absolute epochs via ``propagate_to``
    - Query state at relative times via ``propagate_by``
    - All outputs are Cartesian states in the same frame as the initial state

    Epochs are Terrestrial Time (TT), seconds since J2000 (2000-01-01 12:00:00 TT).
    """

    def __init__(self) -> None:
        self._initial_state_set: bool = False
        self._reference_epoch_s: float | None = None

    @abstractmethod
    def set_initial_state(self, initial_state: InitialStateT) -> None:
        """Set initial state and reset reference_epoch_s to the initial epoch.

        Subclasses must call ``super().set_initial_state(initial_state)`` to
        set the ``_initial_state_set`` flag.

        Parameters
        ----------
        initial_state : InitialStateT
            Initial state (type depends on concrete propagator).
        """
        self._initial_state_set = True

    @property
    def reference_epoch_s(self) -> float:
        """Current reference epoch (TT, s since J2000 TT).

        Advances after each propagation call.

        Returns
        -------
        float
            Reference epoch in TT seconds since J2000.

        Raises
        ------
        RuntimeError
            If initial state has not been set.
        """
        if self._reference_epoch_s is None:
            raise RuntimeError(
                "Reference epoch not set. Call set_initial_state() first."
            )
        return self._reference_epoch_s

    @abstractmethod
    def get_initial_epoch_s(self) -> float:
        """Return the epoch of the initial state (TT, s since J2000 TT).

        This is fixed and does not advance with propagation.

        Returns
        -------
        float
            Initial epoch in TT seconds since J2000.
        """
        ...

    @abstractmethod
    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        """Subclass hook: Cartesian state at target_epoch_s.

        Parameters
        ----------
        target_epoch_s : float
            Target epoch (TT, s since J2000 TT).

        Returns
        -------
        np.ndarray
            Cartesian state [x, y, z, vx, vy, vz] in meters and m/s.
        """
        ...

    def _propagate_trajectory_impl(
        self, from_epoch_s: float, to_epoch_s: float
    ) -> list[tuple[float, np.ndarray]]:
        """Subclass hook: trajectory samples from from_epoch_s to to_epoch_s.

        Default implementation returns a single sample at to_epoch_s.
        Override for integrators that produce intermediate samples.

        Parameters
        ----------
        from_epoch_s : float
            Start epoch (TT, s since J2000 TT).
        to_epoch_s : float
            End epoch (TT, s since J2000 TT).

        Returns
        -------
        list[tuple[float, np.ndarray]]
            List of (epoch_s, state) tuples.
        """
        return [(to_epoch_s, self._propagate_to_impl(to_epoch_s))]

    def _require_initial_state(self) -> None:
        """Raise if initial state has not been set.

        Raises
        ------
        RuntimeError
            If set_initial_state() has not been called.
        """
        if not self._initial_state_set:
            raise RuntimeError(
                "Initial state not set. Call set_initial_state() first."
            )

    def propagate_to(
        self, target_epoch_s: float, output: OutputMode = OutputMode.FINAL
    ) -> tuple[float, np.ndarray] | list[tuple[float, np.ndarray]] | None:
        """Propagate to target_epoch_s and advance reference_epoch_s.

        Parameters
        ----------
        target_epoch_s : float
            Target epoch (TT, s since J2000 TT).
        output : OutputMode, optional
            Controls return value:
            - NONE: return None
            - FINAL: return (epoch_s, state)
            - TRAJECTORY: return [(epoch_s, state), ...] from previous
              reference_epoch_s to target_epoch_s

        Returns
        -------
        tuple[float, np.ndarray] | list[tuple[float, np.ndarray]] | None
            Depends on output mode.

        Raises
        ------
        RuntimeError
            If initial state has not been set.
        """
        self._require_initial_state()

        if output == OutputMode.NONE:
            self._reference_epoch_s = target_epoch_s
            return None
        elif output == OutputMode.FINAL:
            state = self._propagate_to_impl(target_epoch_s)
            self._reference_epoch_s = target_epoch_s
            return (target_epoch_s, state)
        elif output == OutputMode.TRAJECTORY:
            trajectory = self._propagate_trajectory_impl(
                self._reference_epoch_s, target_epoch_s
            )
            self._reference_epoch_s = target_epoch_s
            return trajectory
        else:
            raise ValueError(f"Unknown output mode: {output}")

    def propagate_by(
        self, time_elapsed_s: float, output: OutputMode = OutputMode.FINAL
    ) -> tuple[float, np.ndarray] | list[tuple[float, np.ndarray]] | None:
        """Propagate time_elapsed_s past reference_epoch_s.

        Parameters
        ----------
        time_elapsed_s : float
            Time to propagate forward (seconds).
        output : OutputMode, optional
            Controls return value (see propagate_to).

        Returns
        -------
        tuple[float, np.ndarray] | list[tuple[float, np.ndarray]] | None
            Depends on output mode.

        Raises
        ------
        RuntimeError
            If initial state has not been set.
        """
        return self.propagate_to(self.reference_epoch_s + time_elapsed_s, output=output)
