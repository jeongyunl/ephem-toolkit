"""Tests for common/frame_utils.py — TEME and J2000 frame conversions."""

from __future__ import annotations

import numpy as np
import pytest

import common.frame_utils as frame_utils

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

    def fake_teme_to_j2000(epoch_tdb_s: float) -> np.ndarray:
        requested_epochs.append(epoch_tdb_s)
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


def test_j2000_to_teme_uses_transposed_rotation(monkeypatch) -> None:
    """Should apply the inverse rotation independently to position and velocity."""
    monkeypatch.setattr(
        frame_utils.element_conversion,
        "teme_to_j2000",
        lambda epoch_tdb_s: TEST_ROTATION,
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
        lambda epoch_tdb_s: TEST_ROTATION,
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
        base_frame: str, target_frame: str, epoch_tdb_s: float
    ) -> np.ndarray:
        requested_arguments.append((base_frame, target_frame, epoch_tdb_s))
        return state_rotation_matrix

    monkeypatch.setattr(frame_utils, "_did_load_spice_kernels", True)
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
