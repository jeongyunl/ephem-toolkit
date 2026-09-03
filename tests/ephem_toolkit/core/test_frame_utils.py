"""Tests for core/frame_utils.py — TEME and J2000 frame conversions."""

from __future__ import annotations

import numpy as np
import pytest

import core.frame_utils as frame_utils

TEST_ROTATION: np.ndarray = np.array(
    [
        [0.0, -1.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
)
"""Known 90-degree rotation about the z-axis."""

TEST_STATE: np.ndarray = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
"""Six-component Cartesian state used by the conversion tests."""


def test_teme_to_j2000_rotates_position_and_velocity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should apply the TudatPy rotation independently to position and velocity."""
    requested_epochs: list[float] = []

    def fake_teme_to_j2000(epoch_tt_s: float) -> np.ndarray:
        requested_epochs.append(epoch_tt_s)
        return TEST_ROTATION

    monkeypatch.setattr(
        frame_utils.element_conversion, "teme_to_j2000", fake_teme_to_j2000
    )

    result = frame_utils.teme_to_j2000(123.5, TEST_STATE)
    expected = np.concatenate(
        (
            TEST_STATE[:3] @ TEST_ROTATION,
            TEST_STATE[3:] @ TEST_ROTATION,
        )
    )

    np.testing.assert_allclose(result, expected)
    assert result.shape == (6,)
    assert requested_epochs == [123.5]


def test_j2000_to_teme_uses_transposed_rotation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should apply the inverse rotation independently to position and velocity."""
    monkeypatch.setattr(
        frame_utils.element_conversion,
        "teme_to_j2000",
        lambda epoch_tt_s: TEST_ROTATION,
    )

    result = frame_utils.j2000_to_teme(123.5, TEST_STATE)
    rotation_to_teme = TEST_ROTATION.T
    expected = np.concatenate(
        (
            TEST_STATE[:3] @ rotation_to_teme,
            TEST_STATE[3:] @ rotation_to_teme,
        )
    )

    np.testing.assert_allclose(result, expected)
    assert result.shape == (6,)


def test_teme_j2000_round_trip_restores_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should restore a TEME state after conversion to J2000 and back."""
    monkeypatch.setattr(
        frame_utils.element_conversion,
        "teme_to_j2000",
        lambda epoch_tt_s: TEST_ROTATION,
    )

    j2000_state = frame_utils.teme_to_j2000(123.5, TEST_STATE)
    restored_state = frame_utils.j2000_to_teme(123.5, j2000_state)

    np.testing.assert_allclose(restored_state, TEST_STATE)


def test_spice_convert_frame_uses_state_rotation_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should use TudatPy's combined state rotation matrix when available."""
    state_rotation_matrix = np.eye(6)
    requested_arguments: list[tuple[str, str, float]] = []

    def fake_state_rotation_matrix(
        base_frame: str, target_frame: str, epoch_tt_s: float
    ) -> np.ndarray:
        requested_arguments.append((base_frame, target_frame, epoch_tt_s))
        return state_rotation_matrix

    monkeypatch.setattr(
        frame_utils.spice,
        "compute_state_rotation_matrix_between_frames",
        fake_state_rotation_matrix,
        raising=False,
    )
    monkeypatch.setattr(
        frame_utils.spice,
        "compute_rotation_matrix_between_frames",
        lambda *args: pytest.fail("Should use the combined state rotation matrix"),
    )

    result = frame_utils.spice_convert_frame("J2000", "ITRF93", 123.5, TEST_STATE)

    np.testing.assert_allclose(result, TEST_STATE)
    assert requested_arguments == [("J2000", "ITRF93", 123.5)]


def test_spice_convert_frame_builds_state_matrix_from_rotation_and_derivative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should build 6x6 state matrix when combined state rotation is unavailable."""
    rotation_matrix = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 0.9, -0.1],
            [0.0, 0.1, 0.9],
        ]
    )
    rotation_derivative = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.0, 0.01, -0.02],
            [0.0, 0.02, 0.01],
        ]
    )

    monkeypatch.setattr(
        frame_utils, "_has_compute_state_rotation_matrix_between_frames", False
    )
    monkeypatch.setattr(
        frame_utils.spice,
        "compute_rotation_matrix_between_frames",
        lambda base, target, epoch: rotation_matrix,
    )
    monkeypatch.setattr(
        frame_utils.spice,
        "compute_rotation_matrix_derivative_between_frames",
        lambda base, target, epoch: rotation_derivative,
    )

    result = frame_utils.spice_convert_frame("J2000", "ITRF93", 100.0, TEST_STATE)

    # Expected state matrix structure:
    # [R    0]
    # [dR   R]
    expected_state_matrix = np.zeros((6, 6))
    expected_state_matrix[0:3, 0:3] = rotation_matrix
    expected_state_matrix[3:6, 0:3] = rotation_derivative
    expected_state_matrix[3:6, 3:6] = rotation_matrix

    expected_result = expected_state_matrix @ TEST_STATE

    np.testing.assert_allclose(result, expected_result)


def test_load_spice_kernels_loads_required_kernels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should load all SPICE kernels required by frame conversions."""
    load_kernel_calls: list[str] = []

    def fake_load_kernel(kernel_name: str) -> None:
        load_kernel_calls.append(kernel_name)

    monkeypatch.setattr(frame_utils.spice_utils, "load_kernel", fake_load_kernel)
    frame_utils._load_spice_kernels()

    assert load_kernel_calls == [
        "naif0012.tls",
        "pck00011.tpc",
        "gm_de431.tpc",
        "earth_200101_990825_predict.bpc",
        "inpop19a_TDB_m100_p100_spice.bsp",
    ]


def test_tudat_convert_inertial_to_body_fixed_applies_rotation_and_transport_term(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should apply rotation matrix and subtract the transport term for velocity."""
    rotation_matrix = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 0.8, -0.6],
            [0.0, 0.6, 0.8],
        ]
    )
    angular_velocity = np.array([0.0, 0.0, 0.1])  # rad/s about z-axis

    class FakeRotationModel:
        def inertial_to_body_fixed_rotation(self, epoch: float) -> np.ndarray:
            return rotation_matrix

        def angular_velocity_in_body_fixed_frame(self, epoch: float) -> np.ndarray:
            return angular_velocity

    rotation_model = FakeRotationModel()
    inertial_state = np.array([1000.0, 2000.0, 3000.0, 100.0, 200.0, 300.0])

    result = frame_utils.tudat_convert_inertial_to_body_fixed(
        rotation_model, 100.0, inertial_state
    )

    # Expected position: R @ r_inertial
    expected_position = rotation_matrix @ inertial_state[0:3]

    # Expected velocity: R @ v_inertial - omega x r_body_fixed
    rotated_velocity = rotation_matrix @ inertial_state[3:6]
    transport_term = np.cross(angular_velocity, expected_position)
    expected_velocity = rotated_velocity - transport_term

    expected_state = np.concatenate([expected_position, expected_velocity])

    np.testing.assert_allclose(result, expected_state)
    assert result.shape == (6,)


def test_tudat_convert_body_fixed_to_inertial_applies_rotation_and_transport_term(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should apply rotation matrix and add the transport term for velocity."""
    rotation_matrix = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 0.8, 0.6],
            [0.0, -0.6, 0.8],
        ]
    )
    angular_velocity = np.array([0.0, 0.0, 0.05])  # rad/s about z-axis

    class FakeRotationModel:
        def body_fixed_to_inertial_rotation(self, epoch: float) -> np.ndarray:
            return rotation_matrix

        def angular_velocity_in_inertial_frame(self, epoch: float) -> np.ndarray:
            return angular_velocity

    rotation_model = FakeRotationModel()
    body_fixed_state = np.array([5000.0, 6000.0, 7000.0, 50.0, 60.0, 70.0])

    result = frame_utils.tudat_convert_body_fixed_to_inertial(
        rotation_model, 200.0, body_fixed_state
    )

    # Expected position: R @ r_body_fixed
    expected_position = rotation_matrix @ body_fixed_state[0:3]

    # Expected velocity: R @ v_body_fixed + omega x r_inertial
    rotated_velocity = rotation_matrix @ body_fixed_state[3:6]
    transport_term = np.cross(angular_velocity, expected_position)
    expected_velocity = rotated_velocity + transport_term

    expected_state = np.concatenate([expected_position, expected_velocity])

    np.testing.assert_allclose(result, expected_state)
    assert result.shape == (6,)


def test_tudat_inertial_body_fixed_round_trip_restores_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should restore inertial state after conversion to body-fixed and back."""
    # Use a realistic rotation matrix (small rotation about z-axis)
    angle = 0.1  # radians
    cos_a = np.cos(angle)
    sin_a = np.sin(angle)
    rotation_inertial_to_body = np.array(
        [
            [cos_a, sin_a, 0.0],
            [-sin_a, cos_a, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    rotation_body_to_inertial = rotation_inertial_to_body.T
    angular_velocity_body = np.array([0.0, 0.0, 0.05])
    angular_velocity_inertial = rotation_body_to_inertial @ angular_velocity_body

    class FakeRotationModel:
        def inertial_to_body_fixed_rotation(self, epoch: float) -> np.ndarray:
            return rotation_inertial_to_body

        def body_fixed_to_inertial_rotation(self, epoch: float) -> np.ndarray:
            return rotation_body_to_inertial

        def angular_velocity_in_body_fixed_frame(self, epoch: float) -> np.ndarray:
            return angular_velocity_body

        def angular_velocity_in_inertial_frame(self, epoch: float) -> np.ndarray:
            return angular_velocity_inertial

    rotation_model = FakeRotationModel()
    inertial_state = np.array([7000000.0, 0.0, 0.0, 0.0, 7500.0, 0.0])

    body_fixed_state = frame_utils.tudat_convert_inertial_to_body_fixed(
        rotation_model, 100.0, inertial_state
    )
    restored_state = frame_utils.tudat_convert_body_fixed_to_inertial(
        rotation_model, 100.0, body_fixed_state
    )

    # Use relative tolerance appropriate for numerical precision with large values
    np.testing.assert_allclose(restored_state, inertial_state, rtol=1e-12, atol=1e-6)


def test_tudat_spice_rotation_model_returns_cached_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should return cached rotation model on subsequent calls."""
    create_calls: list[str] = []

    class FakeRotationModel:
        pass

    def fake_create_rotation_model(
        body_name: str, global_frame: str, settings: object
    ) -> object:
        create_calls.append(body_name)
        return FakeRotationModel()

    monkeypatch.setattr(
        frame_utils, "_tudat_create_rotation_model", fake_create_rotation_model
    )
    monkeypatch.setattr(frame_utils, "_tudat_spice_rotation_model", None)

    # First call should create the model
    model1 = frame_utils.tudat_spice_rotation_model()
    assert len(create_calls) == 1
    assert create_calls[0] == "Earth"

    # Set the cached model
    monkeypatch.setattr(frame_utils, "_tudat_spice_rotation_model", model1)

    # Second call should return cached model
    model2 = frame_utils.tudat_spice_rotation_model()
    assert model1 is model2
    assert len(create_calls) == 1  # No additional calls


def test_tudat_iau2006_rotation_model_returns_cached_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should return cached rotation model on subsequent calls."""
    create_calls: list[str] = []

    class FakeRotationModel:
        pass

    def fake_create_rotation_model(
        body_name: str, global_frame: str, settings: object
    ) -> object:
        create_calls.append(body_name)
        return FakeRotationModel()

    monkeypatch.setattr(
        frame_utils, "_tudat_create_rotation_model", fake_create_rotation_model
    )
    monkeypatch.setattr(frame_utils, "_tudat_iau2006_rotation_model", None)

    # First call should create the model
    model1 = frame_utils.tudat_iau2006_rotation_model()
    assert len(create_calls) == 1
    assert create_calls[0] == "Earth"

    # Set the cached model
    monkeypatch.setattr(frame_utils, "_tudat_iau2006_rotation_model", model1)

    # Second call should return cached model
    model2 = frame_utils.tudat_iau2006_rotation_model()
    assert model1 is model2
    assert len(create_calls) == 1  # No additional calls


def test_spice_convert_frame_j2000_to_itrf93(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should correctly convert from J2000 to ITRF93 frame."""
    # Create a realistic state transformation matrix
    state_matrix = np.eye(6)
    state_matrix[0:3, 0:3] = TEST_ROTATION
    state_matrix[3:6, 3:6] = TEST_ROTATION

    monkeypatch.setattr(
        frame_utils.spice,
        "compute_state_rotation_matrix_between_frames",
        lambda base, target, epoch: state_matrix,
        raising=False,
    )

    result = frame_utils.spice_convert_frame("J2000", "ITRF93", 100.0, TEST_STATE)

    expected = state_matrix @ TEST_STATE
    np.testing.assert_allclose(result, expected)


def test_spice_convert_frame_itrf93_to_j2000(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should correctly convert from ITRF93 to J2000 frame."""
    # Create inverse transformation
    state_matrix = np.eye(6)
    state_matrix[0:3, 0:3] = TEST_ROTATION.T
    state_matrix[3:6, 3:6] = TEST_ROTATION.T

    monkeypatch.setattr(
        frame_utils.spice,
        "compute_state_rotation_matrix_between_frames",
        lambda base, target, epoch: state_matrix,
        raising=False,
    )

    result = frame_utils.spice_convert_frame("ITRF93", "J2000", 100.0, TEST_STATE)

    expected = state_matrix @ TEST_STATE
    np.testing.assert_allclose(result, expected)
