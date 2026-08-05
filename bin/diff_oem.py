#!/usr/bin/env python3
"""Compare corresponding states from two OEM files.

Usage:
    python3 bin/diff_oem.py <reference_oem.oem> <comparison_oem.oem>
    python3 bin/diff_oem.py - <comparison_oem.oem>
    python3 bin/diff_oem.py <reference_oem.oem> -

The utility reports time, position, and velocity differences. Use ``-`` for one
stdin input. Interpolation options compare states at matching epochs.
"""

from __future__ import annotations

import argparse
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, TextIO

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

import common.common as common
import common.interpolator.lagrange as lagrange
import common.oem as oem
import common.time_utils as time_utils

INTERPOLATION_DEGREE: int = 8
"""Polynomial degree used for OEM state interpolation."""

ROTATION_FIT_DURATION_S: float = 3600.0
"""Duration of the state history used by the optional rotation fit."""

TIME_SHIFT_FIT_DURATION_S: float = 3600.0
"""Duration of comparison data used by the time-shift fit."""

TIME_SHIFT_MAX_FIT_SAMPLES: int = 120
"""Maximum number of comparison samples used by the time-shift objective."""

TRANSFORM_STAGE_OPTIONS: dict[str, str] = {
    "--rot": "rot",
    "--rot-xy": "rot_xy",
    "--rot-z": "rot_z",
    "--time-shift": "time_shift",
}
"""Supported transformation-stage options mapped to internal stage keys."""

State = tuple[float, np.ndarray]
"""Single OEM-like state as ``(timestamp, state_m)``."""

StatePair = tuple[State, State]
"""Reference/comparison state pair used by comparisons and fitting."""


@dataclass
class TransformationStageInput:
    """Data prepared by the pipeline for fitting one transformation stage."""

    state_pairs: list[StatePair]
    """Reference/comparison state pairs prepared for fitting."""

    reference_interpolator: lagrange.LagrangeInterpolator | None
    """Optional interpolator for reference states."""

    comparison_interpolator: lagrange.LagrangeInterpolator | None
    """Optional interpolator for comparison states."""

    def resolve_state_pairs(self) -> list[StatePair]:
        """Resolve fitting pairs using the configured interpolators.

        Returns
        -------
        list[StatePair]
            State pairs successfully resolved at comparable epochs.
        """
        resolved_state_pairs: list[StatePair] = []
        for reference_state, comparison_state in self.state_pairs:
            try:
                resolved_state_pairs.append(
                    _resolve_state_pair(
                        reference_state,
                        comparison_state,
                        self.reference_interpolator,
                        self.comparison_interpolator,
                    )
                )
            except ValueError:
                continue
        return resolved_state_pairs


class TransformationStage(ABC):
    """Base class for fit-transform stages in the comparison pipeline."""

    name: str
    requires_reference_interpolation: bool = False

    @abstractmethod
    def build_fit_pairs(
        self,
        reference_states: list[State],
        comparison_states: list[State],
    ) -> list[StatePair]:
        """Build the reference/comparison data used to fit this stage.

        Parameters
        ----------
        reference_states : list[State]
            Reference state history.
        comparison_states : list[State]
            Comparison state history.

        Returns
        -------
        list[StatePair]
            State pairs selected for fitting.
        """

    @abstractmethod
    def fit(self, stage_input: TransformationStageInput) -> Any:
        """Fit and return this stage's transformation parameters.

        Parameters
        ----------
        stage_input : TransformationStageInput
            State pairs and interpolators prepared for fitting.

        Returns
        -------
        Any
            Fitted transformation parameters.
        """

    @abstractmethod
    def transform(self, states: list[State], fit_result: Any) -> list[State]:
        """Transform comparison states using fitted stage parameters.

        Parameters
        ----------
        states : list[State]
            Comparison state history to transform.
        fit_result : Any
            Parameters produced by :meth:`fit`.

        Returns
        -------
        list[State]
            Transformed comparison state history.
        """

    def describe_fit(self, fit_result: Any) -> str | None:
        """Return a human-readable description of fitted parameters.

        Parameters
        ----------
        fit_result : Any
            Parameters produced by :meth:`fit`.

        Returns
        -------
        str or None
            Human-readable fit description, if available.
        """
        del fit_result
        return None


class RotationStage(TransformationStage):
    """Fit and apply a fixed comparison-to-reference rotation."""

    name = "comparison-to-reference rotation"

    def __init__(
        self,
        reference_oem: State,
        interpolate_ref: bool,
        interpolate_data: bool,
        fit_overlap_start: float,
        fit_overlap_stop: float,
        fit_span_s: float,
    ) -> None:
        """Initialize a fixed-rotation fitting stage.

        Parameters
        ----------
        reference_oem : State
            First reference state, used when reference interpolation is enabled.
        interpolate_ref : bool
            Whether to interpolate reference states at comparison epochs.
        interpolate_data : bool
            Whether to interpolate comparison states at reference epochs.
        fit_overlap_start : float
            Start of the overlapping fitting interval (POSIX seconds).
        fit_overlap_stop : float
            End of the overlapping fitting interval (POSIX seconds).
        fit_span_s : float
            Duration of the initial fitting interval (seconds).
        """
        self.reference_oem = reference_oem
        self.interpolate_ref = interpolate_ref
        self.interpolate_data = interpolate_data
        self.fit_overlap_start = fit_overlap_start
        self.fit_overlap_stop = fit_overlap_stop
        self.fit_span_s = fit_span_s

    def build_fit_pairs(
        self,
        reference_states: list[State],
        comparison_states: list[State],
    ) -> list[StatePair]:
        """Select state pairs from the initial rotation fitting interval.

        Parameters
        ----------
        reference_states : list[State]
            Reference state history.
        comparison_states : list[State]
            Comparison state history.

        Returns
        -------
        list[StatePair]
            State pairs selected for rotation fitting.
        """
        if self.interpolate_data:
            base_pairs = [
                (state, comparison_states[0])
                for state in reference_states
                if self.fit_overlap_start <= state[0] <= self.fit_overlap_stop
            ]
        elif self.interpolate_ref:
            base_pairs = [
                (self.reference_oem, state)
                for state in comparison_states
                if self.fit_overlap_start <= state[0] <= self.fit_overlap_stop
            ]
        else:
            base_pairs = [
                (reference_state, comparison_state)
                for reference_state, comparison_state in zip(
                    reference_states, comparison_states
                )
                if self.fit_overlap_start <= reference_state[0] <= self.fit_overlap_stop
            ]

        rotation_stop_epoch_s = self.fit_overlap_start + self.fit_span_s
        return [
            (reference_state, comparison_state)
            for reference_state, comparison_state in base_pairs
            if self.fit_overlap_start
            <= (
                comparison_state[0]
                if self.interpolate_ref and not self.interpolate_data
                else reference_state[0]
            )
            <= rotation_stop_epoch_s
        ]

    def fit(self, stage_input: TransformationStageInput) -> np.ndarray:
        """Fit the comparison-to-reference rotation matrix.

        Parameters
        ----------
        stage_input : TransformationStageInput
            State pairs and interpolators prepared for fitting.

        Returns
        -------
        numpy.ndarray
            Fitted three-by-three rotation matrix.

        Raises
        ------
        ValueError
            If fewer than two state pairs are available.
        """
        resolved_state_pairs = stage_input.resolve_state_pairs()

        if len(resolved_state_pairs) < 2:
            raise ValueError(
                "--rot requires at least two state pairs in the rotation fitting span"
            )

        return self._fit_rotation_matrix(resolved_state_pairs)

    @staticmethod
    def _fit_rotation_matrix(state_pairs: list[StatePair]) -> np.ndarray:
        """Fit a rotation using comparison and reference positions only."""
        reference_vectors = np.vstack(
            [reference_state[1][0:3] for reference_state, _ in state_pairs]
        )
        comparison_vectors = np.vstack(
            [comparison_state[1][0:3] for _, comparison_state in state_pairs]
        )
        covariance = comparison_vectors.T @ reference_vectors
        left_vectors, _, right_vectors_transposed = np.linalg.svd(covariance)
        determinant_correction = np.eye(3)
        if np.linalg.det(right_vectors_transposed.T @ left_vectors.T) < 0.0:
            determinant_correction[-1, -1] = -1.0
        return right_vectors_transposed.T @ determinant_correction @ left_vectors.T

    @staticmethod
    def _apply_state_transform(
        states: list[State],
        transform: Callable[[np.ndarray], np.ndarray],
    ) -> list[State]:
        """Return transformed states while preserving original state epochs."""
        return [(timestamp, transform(state)) for timestamp, state in states]

    def transform(self, states: list[State], fit_result: np.ndarray) -> list[State]:
        """Apply the fitted rotation to comparison states.

        Parameters
        ----------
        states : list[State]
            Comparison state history to transform.
        fit_result : numpy.ndarray
            Three-by-three rotation matrix.

        Returns
        -------
        list[State]
            Rotated comparison state history.
        """
        return self._apply_state_transform(
            states,
            lambda state: _rotate_state(state, fit_result),
        )

    def describe_fit(self, fit_result: np.ndarray) -> str:
        """Describe the fitted rotation for report output.

        Parameters
        ----------
        fit_result : numpy.ndarray
            Fitted three-by-three rotation matrix.

        Returns
        -------
        str
            Human-readable fit description.
        """
        euler_angles_deg = common.rotation_matrix_to_euler_angles(fit_result)

        # Calculate angular separation (total rotation angle) from rotation matrix
        # Using the formula: angle = arccos((trace(R) - 1) / 2)
        trace = np.trace(fit_result)
        angular_separation_rad = np.arccos(np.clip((trace - 1) / 2, -1, 1))
        angular_separation_deg = np.degrees(angular_separation_rad)

        return (
            "Applied comparison-to-reference rotation matrix to "
            "comparison position and velocity states:\n"
            + np.array2string(fit_result, precision=6)
            + f"\n\nAngular separation: {angular_separation_deg:.6f} deg"
            + "\n\nEuler angles (ZYX convention, intrinsic rotations):\n"
            + f"  Rotation about Z (yaw):   {euler_angles_deg[0]:+.6f} deg\n"
            + f"  Rotation about Y (pitch): {euler_angles_deg[1]:+.6f} deg\n"
            + f"  Rotation about X (roll):  {euler_angles_deg[2]:+.6f} deg"
        )


class RotationXYStage(RotationStage):
    """Fit and apply a comparison-to-reference rotation around X and Y only."""

    name = "comparison-to-reference X/Y rotation"

    def fit(self, stage_input: TransformationStageInput) -> np.ndarray:
        """Fit a comparison-to-reference rotation around X and Y.

        Parameters
        ----------
        stage_input : TransformationStageInput
            State pairs and interpolators prepared for fitting.

        Returns
        -------
        numpy.ndarray
            Fitted three-by-three rotation matrix.
        """
        resolved_state_pairs = stage_input.resolve_state_pairs()

        if len(resolved_state_pairs) < 2:
            raise ValueError(
                "--rot-xy requires at least two state pairs in the rotation fitting span"
            )

        return self._fit_xy_rotation_matrix(resolved_state_pairs)

    @staticmethod
    def _rotation_matrix_x(angle_rad: float) -> np.ndarray:
        """Return a right-handed rotation matrix around the X axis."""
        cosine = np.cos(angle_rad)
        sine = np.sin(angle_rad)
        return np.array([[1.0, 0.0, 0.0], [0.0, cosine, -sine], [0.0, sine, cosine]])

    @staticmethod
    def _rotation_matrix_y(angle_rad: float) -> np.ndarray:
        """Return a right-handed rotation matrix around the Y axis."""
        cosine = np.cos(angle_rad)
        sine = np.sin(angle_rad)
        return np.array([[cosine, 0.0, sine], [0.0, 1.0, 0.0], [-sine, 0.0, cosine]])

    @classmethod
    def _fit_xy_rotation_matrix(cls, state_pairs: list[StatePair]) -> np.ndarray:
        """Fit an X/Y rotation using positions only."""
        reference_vectors = np.concatenate(
            [reference_state[1][0:3] for reference_state, _ in state_pairs]
        )
        comparison_vectors = np.concatenate(
            [comparison_state[1][0:3] for _, comparison_state in state_pairs]
        )
        angles = np.zeros(2)

        def residual(current_angles: np.ndarray) -> np.ndarray:
            rotation = cls._rotation_matrix_y(
                current_angles[1]
            ) @ cls._rotation_matrix_x(current_angles[0])
            rotated_vectors = np.concatenate(
                [
                    rotation @ comparison_vectors[index : index + 3]
                    for index in range(0, len(comparison_vectors), 3)
                ]
            )
            return rotated_vectors - reference_vectors

        for _ in range(25):
            current_residual = residual(angles)
            jacobian = np.empty((len(current_residual), 2))
            for parameter_index in range(2):
                probe_angles = angles.copy()
                probe_angles[parameter_index] += 1.0e-7
                jacobian[:, parameter_index] = (
                    residual(probe_angles) - current_residual
                ) / 1.0e-7
            delta, _, _, _ = np.linalg.lstsq(jacobian, -current_residual, rcond=None)
            angles += delta
            if np.linalg.norm(delta) < 1.0e-12:
                break

        return cls._rotation_matrix_y(angles[1]) @ cls._rotation_matrix_x(angles[0])

    def describe_fit(self, fit_result: np.ndarray) -> str:
        """Describe the fitted X/Y rotation for report output.

        Parameters
        ----------
        fit_result : numpy.ndarray
            Fitted three-by-three rotation matrix.

        Returns
        -------
        str
            Human-readable fit description.
        """
        euler_angles_deg = common.rotation_matrix_to_euler_angles(fit_result)
        return (
            "Applied comparison-to-reference X/Y rotation matrix to "
            "comparison position and velocity states:\n"
            + np.array2string(fit_result, precision=6)
            + "\n\nEuler angles (ZYX convention, intrinsic rotations):\n"
            + f"  Rotation about Z (yaw):   {euler_angles_deg[0]:+.6f} deg\n"
            + f"  Rotation about Y (pitch): {euler_angles_deg[1]:+.6f} deg\n"
            + f"  Rotation about X (roll):  {euler_angles_deg[2]:+.6f} deg"
        )


class RotationZStage(RotationStage):
    """Fit and apply a comparison-to-reference rotation around Z only."""

    name = "comparison-to-reference Z rotation"

    def fit(self, stage_input: TransformationStageInput) -> np.ndarray:
        """Fit a comparison-to-reference rotation around Z.

        Parameters
        ----------
        stage_input : TransformationStageInput
            State pairs and interpolators prepared for fitting.

        Returns
        -------
        numpy.ndarray
            Fitted three-by-three rotation matrix.
        """
        resolved_state_pairs = stage_input.resolve_state_pairs()

        if len(resolved_state_pairs) < 2:
            raise ValueError(
                "--rot-z requires at least two state pairs in the rotation fitting span"
            )

        return self._fit_z_rotation_matrix(resolved_state_pairs)

    @staticmethod
    def _rotation_matrix_z(angle_rad: float) -> np.ndarray:
        """Return a right-handed rotation matrix around the Z axis."""
        cosine = np.cos(angle_rad)
        sine = np.sin(angle_rad)
        return np.array([[cosine, -sine, 0.0], [sine, cosine, 0.0], [0.0, 0.0, 1.0]])

    @classmethod
    def _fit_z_rotation_matrix(cls, state_pairs: list[StatePair]) -> np.ndarray:
        """Fit a Z rotation using positions only."""
        reference_vectors = np.concatenate(
            [reference_state[1][0:3] for reference_state, _ in state_pairs]
        )
        comparison_vectors = np.concatenate(
            [comparison_state[1][0:3] for _, comparison_state in state_pairs]
        )
        angle = 0.0

        def residual(current_angle: float) -> np.ndarray:
            rotation = cls._rotation_matrix_z(current_angle)
            rotated_vectors = np.concatenate(
                [
                    rotation @ comparison_vectors[index : index + 3]
                    for index in range(0, len(comparison_vectors), 3)
                ]
            )
            return rotated_vectors - reference_vectors

        for _ in range(25):
            current_residual = residual(angle)
            probe_residual = residual(angle + 1.0e-7)
            derivative = (probe_residual - current_residual) / 1.0e-7
            delta_array, _, _, _ = np.linalg.lstsq(
                derivative[:, np.newaxis], -current_residual, rcond=None
            )
            delta = float(delta_array[0])
            angle += delta
            if abs(delta) < 1.0e-12:
                break

        return cls._rotation_matrix_z(angle)

    def describe_fit(self, fit_result: np.ndarray) -> str:
        """Describe the fitted Z rotation for report output.

        Parameters
        ----------
        fit_result : numpy.ndarray
            Fitted three-by-three rotation matrix.

        Returns
        -------
        str
            Human-readable fit description.
        """
        euler_angles_deg = common.rotation_matrix_to_euler_angles(fit_result)
        return (
            "Applied comparison-to-reference Z rotation matrix to "
            "comparison position and velocity states:\n"
            + np.array2string(fit_result, precision=6)
            + "\n\nEuler angles (ZYX convention, intrinsic rotations):\n"
            + f"  Rotation about Z (yaw):   {euler_angles_deg[0]:+.6f} deg\n"
            + f"  Rotation about Y (pitch): {euler_angles_deg[1]:+.6f} deg\n"
            + f"  Rotation about X (roll):  {euler_angles_deg[2]:+.6f} deg"
        )


class TimeShiftStage(TransformationStage):
    """Fit and apply a constant comparison timestamp shift."""

    name = "comparison time shift"
    requires_reference_interpolation = True

    def __init__(
        self,
        reference_oem: State,
        fit_overlap_start: float,
        fit_overlap_stop: float,
    ) -> None:
        """Initialize a constant time-shift fitting stage.

        Parameters
        ----------
        reference_oem : State
            First reference state used to build fallback interpolation data.
        fit_overlap_start : float
            Start of the overlapping fitting interval (POSIX seconds).
        fit_overlap_stop : float
            End of the overlapping fitting interval (POSIX seconds).
        """
        self.reference_oem = reference_oem
        self.fit_overlap_start = fit_overlap_start
        self.fit_overlap_stop = fit_overlap_stop

    def build_fit_pairs(
        self,
        reference_states: list[State],
        comparison_states: list[State],
    ) -> list[StatePair]:
        """Select comparison states from the fitting interval.

        Parameters
        ----------
        reference_states : list[State]
            Reference state history.
        comparison_states : list[State]
            Comparison state history.

        Returns
        -------
        list[StatePair]
            Pairs containing the first reference state and selected comparison
            states.
        """
        if not reference_states:
            return []
        return [
            (reference_states[0], comparison_state)
            for comparison_state in comparison_states
            if self.fit_overlap_start <= comparison_state[0] <= self.fit_overlap_stop
        ]

    def fit(self, stage_input: TransformationStageInput) -> float:
        """Fit a constant comparison timestamp shift.

        Parameters
        ----------
        stage_input : TransformationStageInput
            State pairs and reference interpolator used for fitting.

        Returns
        -------
        float
            Timestamp bias to subtract from comparison epochs (seconds).

        Raises
        ------
        ValueError
            If no comparison states are available for fitting.
        """
        state_pairs = stage_input.state_pairs
        reference_interpolator = stage_input.reference_interpolator
        if reference_interpolator is None:
            reference_interpolator = lagrange.LagrangeInterpolator(
                dimension=6, degree=INTERPOLATION_DEGREE
            )
            reference_states = [pair[0] for pair in state_pairs]
            reference_interpolator.set_data(reference_states)

        reference_epochs = np.asarray(reference_interpolator.independent_values)
        reference_positions_m = np.asarray(
            [state[0:3] for state in reference_interpolator.dependent_values]
        )
        first_comparison_epoch_s = min(
            comparison_state[0] for _, comparison_state in state_pairs
        )
        time_shift_limit_s = TIME_SHIFT_FIT_DURATION_S / 2.0
        fit_comparison_states = [
            comparison_state
            for _, comparison_state in state_pairs
            if comparison_state[0]
            <= first_comparison_epoch_s + TIME_SHIFT_FIT_DURATION_S
        ]
        if not fit_comparison_states:
            raise ValueError("--time-shift requires at least one comparison state")
        if len(fit_comparison_states) > TIME_SHIFT_MAX_FIT_SAMPLES:
            sample_indices = np.linspace(
                0,
                len(fit_comparison_states) - 1,
                TIME_SHIFT_MAX_FIT_SAMPLES,
                dtype=int,
            )
            fit_comparison_states = [
                fit_comparison_states[index] for index in sample_indices
            ]
        comparison_epochs = np.asarray([state[0] for state in fit_comparison_states])
        comparison_positions_m = np.asarray(
            [state[1][0:3] for state in fit_comparison_states]
        )

        def position_error(bias_s: float) -> float:
            query_epochs = comparison_epochs - bias_s
            valid = (query_epochs >= reference_epochs[0]) & (
                query_epochs <= reference_epochs[-1]
            )
            if not np.any(valid):
                return float("inf")
            reference_position_m = np.column_stack(
                [
                    np.interp(
                        query_epochs[valid],
                        reference_epochs,
                        reference_positions_m[:, axis],
                    )
                    for axis in range(3)
                ]
            )
            residuals_m = comparison_positions_m[valid] - reference_position_m
            return float(np.mean(np.sum(residuals_m * residuals_m, axis=1)))

        coarse_step_s = max(1.0, TIME_SHIFT_FIT_DURATION_S / 720.0)
        coarse_offsets_s = np.arange(
            -time_shift_limit_s,
            time_shift_limit_s + coarse_step_s,
            coarse_step_s,
        )
        coarse_errors = np.array(
            [position_error(bias_s) for bias_s in coarse_offsets_s]
        )
        best_bias_s = float(coarse_offsets_s[int(np.argmin(coarse_errors))])

        lower_bound_s = max(-time_shift_limit_s, best_bias_s - coarse_step_s)
        upper_bound_s = min(time_shift_limit_s, best_bias_s + coarse_step_s)
        golden_ratio = (1.0 + np.sqrt(5.0)) / 2.0
        left_bound_s = lower_bound_s
        right_bound_s = upper_bound_s
        left_probe_s = right_bound_s - (right_bound_s - left_bound_s) / golden_ratio
        right_probe_s = left_bound_s + (right_bound_s - left_bound_s) / golden_ratio
        left_error = position_error(left_probe_s)
        right_error = position_error(right_probe_s)
        for _ in range(24):
            if left_error <= right_error:
                right_bound_s = right_probe_s
                right_probe_s = left_probe_s
                right_error = left_error
                left_probe_s = (
                    right_bound_s - (right_bound_s - left_bound_s) / golden_ratio
                )
                left_error = position_error(left_probe_s)
            else:
                left_bound_s = left_probe_s
                left_probe_s = right_probe_s
                left_error = right_error
                right_probe_s = (
                    left_bound_s + (right_bound_s - left_bound_s) / golden_ratio
                )
                right_error = position_error(right_probe_s)

        candidate_biases_s = np.array([best_bias_s, left_probe_s, right_probe_s])
        candidate_errors = np.array(
            [position_error(bias_s) for bias_s in candidate_biases_s]
        )
        return float(
            np.clip(
                candidate_biases_s[int(np.argmin(candidate_errors))],
                -time_shift_limit_s,
                time_shift_limit_s,
            )
        )

    def transform(self, states: list[State], fit_result: float) -> list[State]:
        """Subtract the fitted timestamp bias from comparison states.

        Parameters
        ----------
        states : list[State]
            Comparison state history to transform.
        fit_result : float
            Timestamp bias to subtract (seconds).

        Returns
        -------
        list[State]
            Comparison states with shifted epochs.
        """
        return [(timestamp - fit_result, state.copy()) for timestamp, state in states]

    def describe_fit(self, fit_result: float) -> str:
        """Describe the fitted time shift for report output.

        Parameters
        ----------
        fit_result : float
            Timestamp bias to subtract (seconds).

        Returns
        -------
        str
            Human-readable fit description.
        """
        return (
            "Applied comparison time shift (bias subtraction): " f"{fit_result:+.9f} s"
        )


@dataclass
class ComparisonResult:
    """Named results returned by :func:`compare_states`."""

    reference_epoch: datetime
    """Reference state epoch."""

    comparison_epoch: datetime
    """Comparison state epoch."""

    time_diff_s: float | None
    """Comparison epoch minus reference epoch, when no interpolation is used."""

    position_diff_km: np.ndarray
    """Comparison minus reference position (km)."""

    position_diff_magnitude_km: float
    """Magnitude of the position difference (km)."""

    velocity_diff_km_s: np.ndarray
    """Comparison minus reference velocity (km/s)."""

    velocity_diff_magnitude_km_s: float
    """Magnitude of the velocity difference (km/s)."""

    rtn_position_km: np.ndarray
    """Comparison minus reference position in the reference RTN frame (km)."""

    rtn_velocity_km_s: np.ndarray
    """Comparison minus reference velocity in the reference RTN frame (km/s)."""


def read_states(source: TextIO | str | Path) -> list[tuple[float, np.ndarray]]:
    """Read all states from an OEM file or text stream.

    Comments and blank lines are skipped by :class:`oem.CcsdsOem`.

    Parameters
    ----------
    source : TextIO, str, or pathlib.Path
        Readable OEM stream or path to an OEM file containing state data.

    Returns
    -------
    list[tuple[float, np.ndarray]]
        ``(timestamp, state_m)`` pairs where *timestamp* is POSIX seconds and
        *state_m* is a six-element vector in meters and meters per second.

    Raises
    ------
    ValueError
        If file cannot be read or no valid state is found.
    """
    try:
        oem_data = oem.CcsdsOem.read(source)
    except OSError as error:
        raise ValueError(f"Could not read file '{source}': {error}") from error

    if not oem_data.states:
        raise ValueError(f"No valid OEM-like state found in '{source}'")
    return oem_data.states


def _get_overlapping_time_range(
    reference_states: list[tuple[float, np.ndarray]],
    comparison_states: list[tuple[float, np.ndarray]],
) -> tuple[float, float] | None:
    """Return the inclusive time range shared by two ordered state lists."""
    overlap_start: float = max(reference_states[0][0], comparison_states[0][0])
    overlap_stop: float = min(reference_states[-1][0], comparison_states[-1][0])
    if overlap_start > overlap_stop:
        return None
    return overlap_start, overlap_stop


def _resolve_time_bound(value: str, reference_epoch_s: float) -> float:
    """Resolve an absolute or reference-relative time bound to POSIX seconds."""
    parsed_value: datetime | timedelta = time_utils.parse_time_or_duration(value)
    reference_datetime: datetime = datetime.fromtimestamp(
        reference_epoch_s, tz=timezone.utc
    )
    if isinstance(parsed_value, timedelta):
        parsed_value = reference_datetime + parsed_value
    return parsed_value.timestamp()


def _parse_rotation_fit_span(value: str) -> float:
    """Parse a positive duration used for fitting the optional rotation."""
    return time_utils.parse_duration_to_seconds(value)


def _format_epoch(epoch_s: float | None) -> str:
    """Format a POSIX epoch for debug output."""
    if epoch_s is None:
        return "none"
    epoch = datetime.fromtimestamp(epoch_s, tz=timezone.utc)
    return time_utils.datetime_to_iso8601(epoch)


def _print_debug_range(
    label: str,
    start_epoch_s: float | None,
    stop_epoch_s: float | None,
) -> None:
    """Print one labeled time range to stderr."""
    print(
        f"[diff_oem] {label}: start={_format_epoch(start_epoch_s)}, "
        f"stop={_format_epoch(stop_epoch_s)}",
        file=sys.stderr,
    )


def _rotate_state(state: np.ndarray, rotation_matrix: np.ndarray) -> np.ndarray:
    """Rotate position and velocity components of an SI state vector."""
    rotated_state = state.copy()
    rotated_state[0:3] = rotation_matrix @ state[0:3]
    rotated_state[3:6] = rotation_matrix @ state[3:6]
    return rotated_state


def _resolve_state_pair(
    reference_oem: State,
    comparison_oem: State,
    reference_interpolator: lagrange.LagrangeInterpolator | None = None,
    comparison_interpolator: lagrange.LagrangeInterpolator | None = None,
) -> StatePair:
    """Resolve one state pair to concrete vectors at comparable epochs."""
    reference_timestamp: float
    reference_state_m: np.ndarray
    reference_timestamp, reference_state_m = reference_oem
    comparison_timestamp: float
    comparison_state_m: np.ndarray
    comparison_timestamp, comparison_state_m = comparison_oem

    if comparison_interpolator is not None:
        comparison_timestamp = reference_timestamp
        interpolated_state: np.ndarray | None = comparison_interpolator.interpolate(
            reference_timestamp
        )
        if interpolated_state is None:
            reference_epoch = datetime.fromtimestamp(
                reference_timestamp, tz=timezone.utc
            )
            raise ValueError(
                "Reference epoch "
                f"{time_utils.datetime_to_iso8601(reference_epoch)} is outside "
                "the comparison OEM interpolation range"
            )
        comparison_state_m = interpolated_state

    if reference_interpolator is not None:
        interpolation_timestamp = comparison_timestamp
        interpolated_state = reference_interpolator.interpolate(interpolation_timestamp)
        if interpolated_state is None:
            comparison_epoch = datetime.fromtimestamp(
                interpolation_timestamp, tz=timezone.utc
            )
            raise ValueError(
                "Comparison epoch "
                f"{time_utils.datetime_to_iso8601(comparison_epoch)} is outside "
                "the reference OEM interpolation range"
            )
        reference_timestamp = interpolation_timestamp
        reference_state_m = interpolated_state

    return (
        (reference_timestamp, reference_state_m),
        (comparison_timestamp, comparison_state_m),
    )


def compare_states(
    reference_oem: State,
    comparison_oem: State,
    reference_interpolator: lagrange.LagrangeInterpolator | None = None,
    comparison_interpolator: lagrange.LagrangeInterpolator | None = None,
    comparison_rotation_matrix: np.ndarray | None = None,
) -> ComparisonResult:
    """Compare two OEM-like states and return differences.

    Parameters
    ----------
    reference_oem : tuple[float, np.ndarray]
        Reference ``(timestamp, state_m)`` tuple from the OEM state history.
    comparison_oem : tuple[float, np.ndarray]
        Comparison ``(timestamp, state_m)`` tuple from the OEM state history.
    reference_interpolator : LagrangeInterpolator, optional
        Interpolator built from the reference OEM. When provided, the reference
        state is evaluated at the comparison epoch instead of using the supplied
        reference state's epoch and vector.
    comparison_interpolator : LagrangeInterpolator, optional
        Interpolator built from the comparison OEM. When provided, the comparison
        state is evaluated at the reference epoch.
    comparison_rotation_matrix : numpy.ndarray, optional
        Rotation applied to the comparison position and velocity before calculating
        differences.

    Returns
    -------
    ComparisonResult
        Comparison result containing epochs, time difference in seconds,
        position difference in km, and velocity difference in km/s.
    """
    (reference_timestamp, reference_state_m), (
        comparison_timestamp,
        comparison_state_m,
    ) = _resolve_state_pair(
        reference_oem,
        comparison_oem,
        reference_interpolator,
        comparison_interpolator,
    )

    if comparison_rotation_matrix is not None:
        comparison_state_m = _rotate_state(
            comparison_state_m, comparison_rotation_matrix
        )

    reference_epoch = datetime.fromtimestamp(reference_timestamp, tz=timezone.utc)
    comparison_epoch = datetime.fromtimestamp(comparison_timestamp, tz=timezone.utc)
    reference_position_km: np.ndarray = (
        reference_state_m[0:3] / oem.KILOMETERS_TO_METERS
    )
    reference_velocity_km_s: np.ndarray = (
        reference_state_m[3:6] / oem.KILOMETERS_TO_METERS
    )
    comparison_position_km: np.ndarray = (
        comparison_state_m[0:3] / oem.KILOMETERS_TO_METERS
    )
    comparison_velocity_km_s: np.ndarray = (
        comparison_state_m[3:6] / oem.KILOMETERS_TO_METERS
    )

    time_diff_s: float | None = None
    if reference_interpolator is None and comparison_interpolator is None:
        time_diff_s = (comparison_epoch - reference_epoch).total_seconds()

    position_diff_km: np.ndarray = comparison_position_km - reference_position_km
    position_diff_magnitude_km: float = float(np.linalg.norm(position_diff_km))

    velocity_diff_km_s: np.ndarray = comparison_velocity_km_s - reference_velocity_km_s
    velocity_diff_magnitude_km_s: float = float(np.linalg.norm(velocity_diff_km_s))
    rtn_state_m_s: np.ndarray = common.transform_to_rtn(
        comparison_state_m, reference_state_m
    )
    rtn_position_km: np.ndarray = rtn_state_m_s[0:3] / oem.KILOMETERS_TO_METERS
    rtn_velocity_km_s: np.ndarray = rtn_state_m_s[3:6] / oem.KILOMETERS_TO_METERS

    return ComparisonResult(
        reference_epoch=reference_epoch,
        comparison_epoch=comparison_epoch,
        time_diff_s=time_diff_s,
        position_diff_km=position_diff_km,
        position_diff_magnitude_km=position_diff_magnitude_km,
        velocity_diff_km_s=velocity_diff_km_s,
        velocity_diff_magnitude_km_s=velocity_diff_magnitude_km_s,
        rtn_position_km=rtn_position_km,
        rtn_velocity_km_s=rtn_velocity_km_s,
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments with attributes ``reference_oem``,
        ``comparison_oem``, ``verbose``, ``debug``, ``interpolate_ref``, and
        ``interpolate_data``. The ``--interpolate`` convenience option enables
        both interpolation flags, and is represented by the parsed interpolation
        attributes. ``stage_sequence`` records transformation stage order as
        requested in the CLI.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Compare two OEM-like Cartesian states and report differences in time, "
            "position, and velocity."
        )
    )
    parser.add_argument(
        "reference_oem",
        metavar="<reference_oem.oem>",
        help="Reference OEM file path or '-' to read from stdin.",
    )
    parser.add_argument(
        "comparison_oem",
        metavar="<comparison_oem.oem>",
        help="Comparison OEM file path or '-' to read from stdin.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed component-wise differences.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print time-range determination details to stderr.",
    )
    parser.add_argument(
        "--interpolate-ref",
        action="store_true",
        help="Interpolate the reference OEM at each comparison state timestamp.",
    )
    parser.add_argument(
        "--interpolate-data",
        action="store_true",
        default=True,
        help=(
            "Interpolate comparison data at each reference state timestamp "
            "(default)."
        ),
    )
    parser.add_argument(
        "--interpolate",
        action="store_true",
        help="Interpolate both reference and comparison OEM data.",
    )
    parser.add_argument(
        "--rtn",
        action="store_true",
        help="Include comparison state coordinates in the reference RTN frame.",
    )
    parser.add_argument(
        "--rot",
        action="store_true",
        help=(
            "Fit a fixed rotation from the initial comparison state span and "
            "apply it before reporting differences. May be repeated."
        ),
    )
    parser.add_argument(
        "--rot-xy",
        action="store_true",
        help=(
            "Fit a fixed rotation around the X and Y axes from the initial "
            "comparison state span. May be repeated."
        ),
    )
    parser.add_argument(
        "--rot-z",
        action="store_true",
        help=(
            "Fit a fixed rotation around the Z axis from the initial comparison "
            "state span. May be repeated."
        ),
    )
    parser.add_argument(
        "--time-shift",
        action="store_true",
        help=(
            "Fit a constant comparison epoch bias and shift comparison timestamps "
            "before reporting differences. May be repeated."
        ),
    )
    parser.add_argument(
        "--rot-fit-span",
        type=_parse_rotation_fit_span,
        default=ROTATION_FIT_DURATION_S,
        metavar="<duration>",
        help=(
            "Duration of the initial state span used for --rot fitting "
            f"(default: {ROTATION_FIT_DURATION_S:g}s)."
        ),
    )
    parser.add_argument(
        "--start",
        metavar="<iso8601|duration>",
        default=None,
        help=(
            "Start epoch as an ISO 8601 timestamp or duration relative to the "
            "first reference epoch."
        ),
    )
    parser.add_argument(
        "--stop",
        metavar="<iso8601|duration>",
        default=None,
        help=(
            "Stop epoch as an ISO 8601 timestamp or duration relative to the "
            "first reference epoch."
        ),
    )
    args = parser.parse_args()
    args.stage_sequence = _extract_stage_sequence(sys.argv[1:])
    if args.interpolate:
        args.interpolate_ref = True
        args.interpolate_data = True
    if args.reference_oem == "-" and args.comparison_oem == "-":
        parser.error("reference_oem and comparison_oem cannot both be '-'")
    return args


def _extract_stage_sequence(argv: list[str]) -> list[str]:
    """Return transformation stage keys in order of CLI appearance."""
    stage_sequence: list[str] = []
    for token in argv:
        option = token.split("=", maxsplit=1)[0]
        stage_key = TRANSFORM_STAGE_OPTIONS.get(option)
        if stage_key is not None:
            stage_sequence.append(stage_key)
    return stage_sequence


@dataclass
class ComparisonOutput:
    """Comparison rows and options used to render a report with statistics."""

    comparison_results: list[tuple[float, ComparisonResult | None]]
    """Comparison results keyed by their query epochs."""

    reference_interpolator: lagrange.LagrangeInterpolator | None
    """Optional interpolator used for reference states."""

    comparison_interpolator: lagrange.LagrangeInterpolator | None
    """Optional interpolator used for comparison states."""

    verbose: bool
    """Whether to include component-wise differences."""

    rtn: bool
    """Whether to include reference-frame RTN differences."""

    title: str | None = None
    """Optional report title."""

    fit_description: str | None = None
    """Optional description of the applied transformation fit."""

    @staticmethod
    def _get_output_columns(
        include_time_difference: bool,
        verbose: bool,
        rtn: bool,
        include_comparison_epoch: bool,
    ) -> list[str]:
        """Return output column names for the selected comparison details."""
        columns: list[str] = ["index", "reference\nepoch"]
        if include_comparison_epoch:
            columns.append("comparison\nepoch")
        if include_time_difference:
            columns.append("time\ndifference\n(s)")
        columns.extend(["position\ndifference\n(km)", "velocity\ndifference\n(km/s)"])
        if verbose:
            columns.extend(
                [
                    "dX\n(km)",
                    "dY\n(km)",
                    "dZ\n(km)",
                    "dVX\n(km/s)",
                    "dVY\n(km/s)",
                    "dVZ\n(km/s)",
                ]
            )
        if rtn:
            columns.extend(
                [
                    "RTN r\n(km)",
                    "RTN t\n(km)",
                    "RTN n\n(km)",
                    "RTN vr\n(km/s)",
                    "RTN vt\n(km/s)",
                    "RTN vn\n(km/s)",
                ]
            )
        return columns

    @staticmethod
    def _get_output_column_widths(columns: list[str]) -> list[int]:
        """Return shared display widths for header and data columns."""
        widths: list[int] = []
        for column in columns:
            label_width: int = max(map(len, column.split("\n")))
            if column == "index":
                data_width: int = 5
            elif "epoch" in column:
                data_width = 24
            else:
                data_width = 10
            widths.append(max(label_width, data_width))
        return widths

    @classmethod
    def _format_output_row(cls, values: list[str], columns: list[str]) -> str:
        """Format output values in consistently spaced columns."""
        column_widths = cls._get_output_column_widths(columns)
        aligned_values = [
            f"{value:>{width}}" for value, width in zip(values, column_widths)
        ]
        return "  ".join(aligned_values).rstrip()

    @classmethod
    def _format_output_header(cls, columns: list[str]) -> str:
        """Format a multi-line header with aligned column labels."""
        header_lines = [column.split("\n") for column in columns]
        column_widths = cls._get_output_column_widths(columns)
        lines: list[str] = []
        for line_index in range(max(map(len, header_lines))):
            line_values = [
                (
                    lines_for_column[line_index]
                    if line_index < len(lines_for_column)
                    else ""
                )
                for lines_for_column in header_lines
            ]
            lines.append(
                "  ".join(
                    f"{value:<{width}}"
                    for value, width in zip(line_values, column_widths)
                ).rstrip()
            )
        return "\n".join(lines)

    def print_header(
        self,
        include_time_difference: bool,
        include_comparison_epoch: bool,
    ) -> None:
        """Print this report's aligned column header.

        Parameters
        ----------
        include_time_difference : bool
            Whether to include the time-difference column.
        include_comparison_epoch : bool
            Whether to include the comparison epoch column.
        """
        columns = self._get_output_columns(
            include_time_difference,
            self.verbose,
            self.rtn,
            include_comparison_epoch,
        )
        print(self._format_output_header(columns))

    def print_result(
        self,
        index: int,
        comparison_result: ComparisonResult | None,
        include_comparison_epoch: bool,
        query_epoch: datetime | None,
    ) -> None:
        """Print one result row using this report's formatting options.

        Parameters
        ----------
        index : int
            One-based row index.
        comparison_result : ComparisonResult or None
            Result to render, or ``None`` for an invalid boundary sample.
        include_comparison_epoch : bool
            Whether to include the comparison epoch column.
        query_epoch : datetime or None
            Query epoch used when ``comparison_result`` is ``None``.
        """
        if comparison_result is None:
            if query_epoch is None:
                raise ValueError("query_epoch is required for an empty comparison row")
            values = [str(index), time_utils.datetime_to_iso8601(query_epoch)]
            if include_comparison_epoch:
                values.append("")
            columns = self._get_output_columns(
                include_time_difference=False,
                verbose=self.verbose,
                rtn=self.rtn,
                include_comparison_epoch=include_comparison_epoch,
            )
            values.extend([""] * (len(columns) - len(values)))
            print(self._format_output_row(values, columns))
            return

        values: list[str] = [
            str(index),
            time_utils.datetime_to_iso8601(comparison_result.reference_epoch),
        ]
        if include_comparison_epoch:
            values.append(
                time_utils.datetime_to_iso8601(comparison_result.comparison_epoch)
            )
        if comparison_result.time_diff_s is not None:
            values.append(f"{comparison_result.time_diff_s:.6f}")
        values.extend(
            [
                f"{comparison_result.position_diff_magnitude_km:.3f}",
                f"{comparison_result.velocity_diff_magnitude_km_s:.6f}",
            ]
        )
        if self.verbose:
            values.extend(
                [
                    f"{comparison_result.position_diff_km[index]:+.3f}"
                    for index in range(3)
                ]
                + [
                    f"{comparison_result.velocity_diff_km_s[index]:+.6f}"
                    for index in range(3)
                ]
            )
        if self.rtn:
            values.extend(
                [
                    f"{comparison_result.rtn_position_km[index]:+.3f}"
                    for index in range(3)
                ]
                + [
                    f"{comparison_result.rtn_velocity_km_s[index]:+.6f}"
                    for index in range(3)
                ]
            )
        columns = self._get_output_columns(
            comparison_result.time_diff_s is not None,
            self.verbose,
            self.rtn,
            include_comparison_epoch,
        )
        print(self._format_output_row(values, columns))

    def print_statistics(self, include_time_difference: bool) -> None:
        """Print summary statistics for this report's comparison results.

        Parameters
        ----------
        include_time_difference : bool
            Whether to include time-difference statistics.
        """
        comparison_results = [
            result for _, result in self.comparison_results if result is not None
        ]
        if not comparison_results:
            print("\nStatistics: no valid comparison results")
            return

        criteria: list[tuple[str, np.ndarray]] = [
            (
                "position difference (km)",
                np.array(
                    [result.position_diff_magnitude_km for result in comparison_results]
                ),
            ),
            (
                "velocity difference (km/s)",
                np.array(
                    [
                        result.velocity_diff_magnitude_km_s
                        for result in comparison_results
                    ]
                ),
            ),
        ]
        if include_time_difference:
            criteria.insert(
                0,
                (
                    "time difference (s)",
                    np.array(
                        [
                            result.time_diff_s
                            for result in comparison_results
                            if result.time_diff_s is not None
                        ]
                    ),
                ),
            )
        if self.verbose:
            criteria.extend(
                [
                    (
                        f"d{axis} (km)",
                        np.array(
                            [
                                result.position_diff_km[index]
                                for result in comparison_results
                            ]
                        ),
                    )
                    for index, axis in enumerate(("X", "Y", "Z"))
                ]
            )
            criteria.extend(
                [
                    (
                        f"dV{axis} (km/s)",
                        np.array(
                            [
                                result.velocity_diff_km_s[index]
                                for result in comparison_results
                            ]
                        ),
                    )
                    for index, axis in enumerate(("X", "Y", "Z"))
                ]
            )
        if self.rtn:
            criteria.extend(
                [
                    (
                        f"RTN {axis} (km)",
                        np.array(
                            [
                                result.rtn_position_km[index]
                                for result in comparison_results
                            ]
                        ),
                    )
                    for index, axis in enumerate(("r", "t", "n"))
                ]
            )
        print("\nStatistics (mean, std, min, max)")
        rtn_statistics_started = False
        for label, values in criteria:
            if label.startswith("RTN ") and not rtn_statistics_started:
                print("\nStatistics (std, min, max)")
                rtn_statistics_started = True
            if label.endswith("(km)"):
                value_format = "+.3f"
            elif label.endswith("(km/s)"):
                value_format = "+.6f"
            else:
                value_format = "+.9g"
            if label.startswith("RTN "):
                print(
                    f"{label}: {format(np.std(values), value_format)}, "
                    f"{format(np.min(values), value_format)}, "
                    f"{format(np.max(values), value_format)}"
                )
            else:
                print(
                    f"{label}: {format(np.mean(values), value_format)}, "
                    f"{format(np.std(values), value_format)}, "
                    f"{format(np.min(values), value_format)}, "
                    f"{format(np.max(values), value_format)}"
                )

    def print(self) -> None:
        """Print comparison rows followed by their summary statistics."""
        include_time_difference = (
            self.reference_interpolator is None and self.comparison_interpolator is None
        )
        if self.title is not None:
            print(f"\n{self.title}")
        self.print_header(
            include_time_difference=include_time_difference,
            include_comparison_epoch=include_time_difference,
        )
        for index, (query_epoch_s, comparison_result) in enumerate(
            self.comparison_results, start=1
        ):
            self.print_result(
                index,
                comparison_result,
                include_comparison_epoch=include_time_difference,
                query_epoch=datetime.fromtimestamp(query_epoch_s, tz=timezone.utc),
            )
        if self.fit_description is not None:
            print("\n" + self.fit_description)
        self.print_statistics(
            include_time_difference=include_time_difference,
        )


def _create_interpolator(
    states: list[State],
    enabled: bool,
) -> lagrange.LagrangeInterpolator | None:
    """Create a Lagrange interpolator for state history when enabled."""
    if not enabled:
        return None
    interpolator = lagrange.LagrangeInterpolator(
        dimension=6, degree=INTERPOLATION_DEGREE
    )
    interpolator.set_data(states)
    return interpolator


def _build_comparison_pairs(
    reference_states: list[State],
    comparison_states: list[State],
    reference_oem: State,
    interpolate_ref: bool,
    interpolate_data: bool,
    has_time_window: bool,
    overlap_start: float | None,
    overlap_stop: float | None,
) -> list[StatePair]:
    """Build comparison query pairs from interpolation and time-window options."""
    if interpolate_data:
        return [
            (state, comparison_states[0])
            for state in reference_states
            if not has_time_window or overlap_start <= state[0] <= overlap_stop
        ]
    if interpolate_ref:
        return [
            (reference_oem, state)
            for state in comparison_states
            if not has_time_window or overlap_start <= state[0] <= overlap_stop
        ]
    if has_time_window:
        return [
            (reference_state, comparison_state)
            for reference_state, comparison_state in zip(
                reference_states, comparison_states
            )
            if overlap_start <= reference_state[0] <= overlap_stop
        ]
    return list(zip(reference_states, comparison_states))


class TransformationPipeline:
    """Manage and execute an ordered sequence of transformation stages."""

    def __init__(
        self,
        reference_states: list[State],
        comparison_states: list[State],
        stages: list[TransformationStage],
        build_pairs: Callable[[list[State], list[State]], list[StatePair]],
        interpolate_ref: bool,
        interpolate_data: bool,
        debug: bool = False,
    ) -> None:
        """Initialize an ordered transformation pipeline.

        Parameters
        ----------
        reference_states : list[State]
            Reference state history.
        comparison_states : list[State]
            Comparison state history.
        stages : list[TransformationStage]
            Transformation stages to fit and apply in order.
        build_pairs : Callable
            Function that builds comparison pairs for a pair of histories.
        interpolate_ref : bool
            Whether to interpolate reference states during comparison.
        interpolate_data : bool
            Whether to interpolate comparison states during comparison.
        debug : bool, default=False
            Whether to print pipeline progress to stderr.
        """
        self.reference_states = reference_states
        self.comparison_states = comparison_states
        self.stages = stages
        self.build_pairs = build_pairs
        self.interpolate_ref = interpolate_ref
        self.interpolate_data = interpolate_data
        self.debug = debug

    def execute(self) -> list[tuple[TransformationStage, Any, list[State]]]:
        """Fit and apply each stage in order.

        Returns
        -------
        list[tuple[TransformationStage, Any, list[State]]]
            Each stage, its fitted result, and its transformed comparison states.
        """
        stage_outputs: list[tuple[TransformationStage, Any, list[State]]] = []
        current_comparison_states = self.comparison_states
        if self.debug:
            print(
                f"[diff_oem] Pipeline start: stages={len(self.stages)}, "
                f"reference_states={len(self.reference_states)}, "
                f"comparison_states={len(self.comparison_states)}",
                file=sys.stderr,
            )
        reference_interpolator = _create_interpolator(
            self.reference_states,
            self.interpolate_ref
            or any(stage.requires_reference_interpolation for stage in self.stages),
        )

        for stage_index, stage in enumerate(self.stages, start=1):
            if self.debug:
                print(
                    f"[diff_oem] Pipeline stage {stage_index}/{len(self.stages)} "
                    f"start: {stage.name}, "
                    f"input_states={len(current_comparison_states)}",
                    file=sys.stderr,
                )
            comparison_interpolator = _create_interpolator(
                current_comparison_states,
                self.interpolate_data,
            )
            fit_pairs = stage.build_fit_pairs(
                self.reference_states,
                current_comparison_states,
            )
            if self.debug:
                print(
                    f"[diff_oem] Pipeline stage {stage_index}/{len(self.stages)} "
                    f"fitting: fit_pairs={len(fit_pairs)}",
                    file=sys.stderr,
                )
            stage_input = TransformationStageInput(
                state_pairs=fit_pairs,
                reference_interpolator=reference_interpolator,
                comparison_interpolator=comparison_interpolator,
            )
            fit_result = stage.fit(stage_input)
            current_comparison_states = stage.transform(
                current_comparison_states, fit_result
            )
            stage_outputs.append((stage, fit_result, current_comparison_states))

            self.build_pairs(self.reference_states, current_comparison_states)
            if self.debug:
                print(
                    f"[diff_oem] Pipeline stage {stage_index}/{len(self.stages)} "
                    f"complete: {stage.name}, "
                    f"output_states={len(current_comparison_states)}",
                    file=sys.stderr,
                )

        if self.debug:
            print("[diff_oem] Pipeline complete", file=sys.stderr)
        return stage_outputs


def _compare_pairs(
    comparison_pairs: list[StatePair],
    reference_interpolator: lagrange.LagrangeInterpolator | None,
    comparison_interpolator: lagrange.LagrangeInterpolator | None,
    comparison_rotation_matrix: np.ndarray | None,
) -> list[tuple[float, ComparisonResult | None]]:
    """Evaluate selected state pairs with an optional comparison rotation."""
    comparison_results: list[tuple[float, ComparisonResult | None]] = []
    for reference_state, comparison_state in comparison_pairs:
        query_epoch_s = (
            comparison_state[0]
            if reference_interpolator is not None and comparison_interpolator is None
            else reference_state[0]
        )
        try:
            comparison_results.append(
                (
                    query_epoch_s,
                    compare_states(
                        reference_state,
                        comparison_state,
                        reference_interpolator,
                        comparison_interpolator,
                        comparison_rotation_matrix,
                    ),
                )
            )
        except ValueError as error:
            # A boundary sample can still fall outside the interpolator window.
            if (
                (
                    reference_interpolator is not None
                    or comparison_interpolator is not None
                )
                and str(error).endswith("outside the reference OEM interpolation range")
            ) or (
                comparison_interpolator is not None
                and str(error).endswith(
                    "outside the comparison OEM interpolation range"
                )
            ):
                comparison_results.append((query_epoch_s, None))
                continue
            raise
    return comparison_results


def main() -> None:
    """Main entry point for the state comparison CLI.

    Parses command-line arguments, reads OEM state vectors from files or
    stdin, compares corresponding OEM states, and prints a header followed by
    one tab-separated result row per comparison to stdout.
    Exits with status 1 on error.
    """
    args: argparse.Namespace = parse_arguments()

    try:
        reference_source: TextIO | str = (
            sys.stdin if args.reference_oem == "-" else args.reference_oem
        )
        comparison_source: TextIO | str = (
            sys.stdin if args.comparison_oem == "-" else args.comparison_oem
        )
        reference_states = read_states(reference_source)
        comparison_states = read_states(comparison_source)
        reference_oem = reference_states[0]
        has_time_window: bool = args.start is not None or args.stop is not None

        overlapping_time_range = _get_overlapping_time_range(
            reference_states, comparison_states
        )
        if args.debug:
            _print_debug_range(
                "Reference range", reference_states[0][0], reference_states[-1][0]
            )
            _print_debug_range(
                "Comparison range", comparison_states[0][0], comparison_states[-1][0]
            )
            if overlapping_time_range is None:
                _print_debug_range("Initial overlap", None, None)
            else:
                _print_debug_range("Initial overlap", *overlapping_time_range)

        # Explicit windows are only meaningful when the histories overlap.
        if overlapping_time_range is None and has_time_window:
            if args.debug:
                _print_debug_range("Effective range", None, None)
            return

        if overlapping_time_range is not None:
            overlap_start, overlap_stop = overlapping_time_range
        else:
            overlap_start = overlap_stop = None
        fit_overlap_start = overlap_start
        fit_overlap_stop = overlap_stop

        if has_time_window:
            reference_epoch_s: float = reference_states[0][0]
            requested_start: float = (
                overlap_start
                if args.start is None
                else _resolve_time_bound(args.start, reference_epoch_s)
            )
            requested_stop: float = (
                overlap_stop
                if args.stop is None
                else _resolve_time_bound(args.stop, requested_start)
            )
            if requested_start > requested_stop:
                raise ValueError("--start must be earlier than or equal to --stop")
            overlap_start = max(overlap_start, requested_start)
            overlap_stop = min(overlap_stop, requested_stop)
            if overlap_start > overlap_stop:
                if args.debug:
                    _print_debug_range("Effective range", None, None)
                return

            if args.debug:
                _print_debug_range("Requested range", requested_start, requested_stop)

        if args.debug:
            _print_debug_range("Effective range", overlap_start, overlap_stop)
            if args.rot or args.rot_xy or args.rot_z or args.time_shift:
                if fit_overlap_start is None or fit_overlap_stop is None:
                    _print_debug_range("Transformation fitting range", None, None)
                else:
                    _print_debug_range(
                        "Transformation fitting range",
                        fit_overlap_start,
                        fit_overlap_stop,
                    )
            if args.rot or args.rot_xy:
                if fit_overlap_start is None or fit_overlap_stop is None:
                    _print_debug_range("Rotation fitting range", None, None)
                else:
                    _print_debug_range(
                        "Rotation fitting range",
                        fit_overlap_start,
                        min(
                            fit_overlap_stop,
                            fit_overlap_start + args.rot_fit_span,
                        ),
                    )

        build_pairs = lambda ref_states, cmp_states: _build_comparison_pairs(
            ref_states,
            cmp_states,
            reference_oem,
            args.interpolate_ref,
            args.interpolate_data,
            has_time_window,
            overlap_start,
            overlap_stop,
        )

        # Each interpolator evaluates one history at epochs from the other.
        reference_interpolator = _create_interpolator(
            reference_states,
            args.interpolate_ref,
        )
        comparison_interpolator = _create_interpolator(
            comparison_states,
            args.interpolate_data,
        )
        comparison_pairs = build_pairs(reference_states, comparison_states)

        stages: list[TransformationStage] = []
        stage_sequence: list[str] = list(args.stage_sequence)
        if args.rot and "rot" not in stage_sequence:
            stage_sequence.append("rot")
        if args.rot_xy and "rot_xy" not in stage_sequence:
            stage_sequence.append("rot_xy")
        if args.rot_z and "rot_z" not in stage_sequence:
            stage_sequence.append("rot_z")
        if args.time_shift and "time_shift" not in stage_sequence:
            stage_sequence.append("time_shift")

        for stage_key in stage_sequence:
            if fit_overlap_start is None or fit_overlap_stop is None:
                raise ValueError(
                    "Transformation stages require overlapping reference and "
                    "comparison histories"
                )

            if stage_key == "rot":
                stages.append(
                    RotationStage(
                        reference_oem,
                        args.interpolate_ref,
                        args.interpolate_data,
                        fit_overlap_start,
                        fit_overlap_stop,
                        args.rot_fit_span,
                    )
                )
            elif stage_key == "rot_xy":
                stages.append(
                    RotationXYStage(
                        reference_oem,
                        args.interpolate_ref,
                        args.interpolate_data,
                        fit_overlap_start,
                        fit_overlap_stop,
                        args.rot_fit_span,
                    )
                )
            elif stage_key == "rot_z":
                stages.append(
                    RotationZStage(
                        reference_oem,
                        args.interpolate_ref,
                        args.interpolate_data,
                        fit_overlap_start,
                        fit_overlap_stop,
                        args.rot_fit_span,
                    )
                )
            elif stage_key == "time_shift":
                stages.append(
                    TimeShiftStage(
                        reference_oem,
                        fit_overlap_start,
                        fit_overlap_stop,
                    )
                )

        normal_results = _compare_pairs(
            comparison_pairs,
            reference_interpolator,
            comparison_interpolator,
            None,
        )
        if not normal_results:
            return
        ComparisonOutput(
            comparison_results=normal_results,
            reference_interpolator=reference_interpolator,
            comparison_interpolator=comparison_interpolator,
            verbose=args.verbose,
            rtn=args.rtn,
            title="Normal comparison" if stages else None,
        ).print()
        if stages:
            pipeline = TransformationPipeline(
                reference_states=reference_states,
                comparison_states=comparison_states,
                stages=stages,
                build_pairs=build_pairs,
                interpolate_ref=args.interpolate_ref,
                interpolate_data=args.interpolate_data,
                debug=args.debug,
            )
            stage_outputs = pipeline.execute()

            for stage_index, (
                stage,
                fit_result,
                transformed_comparison_states,
            ) in enumerate(
                stage_outputs,
                start=1,
            ):
                transformed_comparison_pairs = build_pairs(
                    reference_states,
                    transformed_comparison_states,
                )
                transformed_comparison_interpolator = _create_interpolator(
                    transformed_comparison_states,
                    args.interpolate_data,
                )
                transformed_results = _compare_pairs(
                    transformed_comparison_pairs,
                    reference_interpolator,
                    transformed_comparison_interpolator,
                    None,
                )
                ComparisonOutput(
                    comparison_results=transformed_results,
                    reference_interpolator=reference_interpolator,
                    comparison_interpolator=transformed_comparison_interpolator,
                    verbose=args.verbose,
                    rtn=args.rtn,
                    title=f"Comparison after stage {stage_index}: {stage.name}",
                    fit_description=stage.describe_fit(fit_result),
                ).print()

    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
