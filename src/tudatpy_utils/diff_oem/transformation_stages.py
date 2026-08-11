"""Transformation stages for OEM comparison pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

import numpy as np

import core.misc as misc
import core.interpolator.lagrange as lagrange

from .comparison import rotate_state
from .data_structures import TransformationStageInput
from .types import State, StatePair

INTERPOLATION_DEGREE: int = 8
"""Polynomial degree used for OEM state interpolation."""


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
            lambda state: rotate_state(state, fit_result),
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
        euler_angles_deg = misc.rotation_matrix_to_euler_angles(fit_result)

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
        euler_angles_deg = misc.rotation_matrix_to_euler_angles(fit_result)
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
        euler_angles_deg = misc.rotation_matrix_to_euler_angles(fit_result)
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
        TIME_SHIFT_FIT_DURATION_S: float = 3600.0
        TIME_SHIFT_MAX_FIT_SAMPLES: int = 120

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
